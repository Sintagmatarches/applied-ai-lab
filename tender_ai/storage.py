from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator

from .assessment import assess
from .domain import SupplierProfile, normalize_text
from .versioning import structured_diff


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_hash(notice: dict[str, Any]) -> str:
    material = {key: notice.get(key) for key in ("title", "description", "buyer", "submission_deadline", "estimated_value", "currency", "cpv_codes", "place_of_performance", "lots", "requirements", "award_criteria")}
    return hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class TenderKnowledgeBase:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS notices (
                    notice_id TEXT PRIMARY KEY, publication_id TEXT NOT NULL, notice_type TEXT, form_type TEXT,
                    title TEXT NOT NULL, description TEXT, buyer TEXT, buyer_country TEXT, procedure_type TEXT,
                    publication_date TEXT, submission_deadline TEXT, estimated_value REAL, currency TEXT,
                    cpv_codes_json TEXT NOT NULL, place_json TEXT NOT NULL, notice_url TEXT NOT NULL, xml_url TEXT,
                    source TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, source_version INTEGER NOT NULL,
                    source_hash TEXT NOT NULL, normalized_text TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS lots (
                    lot_id TEXT NOT NULL, notice_id TEXT NOT NULL REFERENCES notices(notice_id) ON DELETE CASCADE,
                    title TEXT, description TEXT, cpv_codes_json TEXT, value REAL, currency TEXT, place_json TEXT,
                    deadline TEXT, duration TEXT, status TEXT, PRIMARY KEY(notice_id, lot_id)
                );
                CREATE TABLE IF NOT EXISTS requirements (
                    requirement_id TEXT PRIMARY KEY, notice_id TEXT NOT NULL REFERENCES notices(notice_id) ON DELETE CASCADE,
                    lot_id TEXT, category TEXT, text TEXT NOT NULL, requirement_type TEXT, mandatory INTEGER NOT NULL,
                    operator TEXT, structured_value_json TEXT, unit TEXT, evidence_id TEXT NOT NULL,
                    confidence REAL, extraction_status TEXT
                );
                CREATE TABLE IF NOT EXISTS award_criteria (
                    criterion_id TEXT PRIMARY KEY, notice_id TEXT NOT NULL REFERENCES notices(notice_id) ON DELETE CASCADE,
                    lot_id TEXT, name TEXT, type TEXT, weight REAL, description TEXT, evidence_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY, notice_id TEXT NOT NULL REFERENCES notices(notice_id) ON DELETE CASCADE,
                    lot_id TEXT, field TEXT, excerpt TEXT, source_url TEXT NOT NULL, source TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notice_versions (
                    notice_id TEXT NOT NULL, version INTEGER NOT NULL, fetched_at TEXT NOT NULL, source_hash TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL, PRIMARY KEY(notice_id, version)
                );
                CREATE TABLE IF NOT EXISTS change_events (
                    change_id INTEGER PRIMARY KEY AUTOINCREMENT, notice_id TEXT NOT NULL, from_version INTEGER,
                    to_version INTEGER, field TEXT NOT NULL, old_value_json TEXT, new_value_json TEXT,
                    materiality TEXT NOT NULL, detected_at TEXT NOT NULL, evidence TEXT
                );
                CREATE TABLE IF NOT EXISTS supplier_profiles (
                    profile_id TEXT NOT NULL, version INTEGER NOT NULL, company_name TEXT NOT NULL, profile_json TEXT NOT NULL,
                    created_at TEXT NOT NULL, PRIMARY KEY(profile_id, version)
                );
                CREATE TABLE IF NOT EXISTS assessments (
                    assessment_id INTEGER PRIMARY KEY AUTOINCREMENT, notice_id TEXT NOT NULL, notice_version INTEGER NOT NULL,
                    profile_id TEXT NOT NULL, profile_version INTEGER NOT NULL, status TEXT NOT NULL,
                    strategic_fit INTEGER NOT NULL, assessment_json TEXT NOT NULL, assessed_at TEXT NOT NULL,
                    trigger TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS embeddings (
                    evidence_id TEXT PRIMARY KEY, notice_id TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL,
                    model TEXT, dimensions INTEGER, vector_json TEXT, updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS ingestion_state (
                    source TEXT NOT NULL, query_hash TEXT NOT NULL, iteration_token TEXT, last_publication_date TEXT,
                    updated_at TEXT NOT NULL, stats_json TEXT NOT NULL, PRIMARY KEY(source, query_hash)
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(evidence_id UNINDEXED, notice_id UNINDEXED, title, buyer, text);
                CREATE INDEX IF NOT EXISTS notices_country_idx ON notices(buyer_country);
                CREATE INDEX IF NOT EXISTS notices_deadline_idx ON notices(submission_deadline);
                CREATE INDEX IF NOT EXISTS changes_notice_idx ON change_events(notice_id, detected_at);
            """)

    def save_profile(self, profile: SupplierProfile) -> None:
        with self.connection() as connection:
            connection.execute("INSERT OR REPLACE INTO supplier_profiles VALUES (?, ?, ?, ?, ?)", (profile.profile_id, profile.version, profile.company_name, json.dumps(profile.public(), ensure_ascii=False), utc_now()))

    def ingest(self, notices: list[dict[str, Any]], profile: SupplierProfile | None = None) -> dict[str, Any]:
        stats = {"fetched": len(notices), "new": 0, "updated": 0, "unchanged": 0, "changes": 0, "reassessments": 0, "failures": 0}
        if profile: self.save_profile(profile)
        for notice in notices:
            try:
                result = self._ingest_one(notice, profile)
                stats[result["state"]] += 1
                stats["changes"] += result["changes"]
                stats["reassessments"] += result["reassessed"]
            except (KeyError, TypeError, ValueError, sqlite3.Error):
                stats["failures"] += 1
        return stats

    def _ingest_one(self, notice: dict[str, Any], profile: SupplierProfile | None) -> dict[str, Any]:
        notice_id, now, digest = str(notice["notice_id"]), utc_now(), source_hash(notice)
        with self.connection() as connection:
            previous_row = connection.execute("SELECT source_hash, source_version FROM notices WHERE notice_id=?", (notice_id,)).fetchone()
            previous_version = connection.execute("SELECT version, snapshot_json FROM notice_versions WHERE notice_id=? ORDER BY version DESC LIMIT 1", (notice_id,)).fetchone()
            if previous_row and previous_row["source_hash"] == digest:
                connection.execute("UPDATE notices SET last_seen=? WHERE notice_id=?", (now, notice_id))
                return {"state": "unchanged", "changes": 0, "reassessed": 0}
            version = int(previous_version["version"] + 1) if previous_version else 1
            snapshot = {**notice, "version": version}
            changes = structured_diff(json.loads(previous_version["snapshot_json"]), snapshot) if previous_version else []
            connection.execute("""
                INSERT INTO notices VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(notice_id) DO UPDATE SET publication_id=excluded.publication_id, notice_type=excluded.notice_type,
                form_type=excluded.form_type,title=excluded.title,description=excluded.description,buyer=excluded.buyer,
                buyer_country=excluded.buyer_country,procedure_type=excluded.procedure_type,publication_date=excluded.publication_date,
                submission_deadline=excluded.submission_deadline,estimated_value=excluded.estimated_value,currency=excluded.currency,
                cpv_codes_json=excluded.cpv_codes_json,place_json=excluded.place_json,notice_url=excluded.notice_url,
                xml_url=excluded.xml_url,last_seen=excluded.last_seen,source_version=excluded.source_version,
                source_hash=excluded.source_hash,normalized_text=excluded.normalized_text
            """, (
                notice_id, notice.get("publication_id", notice_id), notice.get("notice_type"), notice.get("form_type"), notice.get("title", "Untitled"),
                notice.get("description", ""), notice.get("buyer", ""), notice.get("buyer_country", ""), notice.get("procedure_type", ""),
                notice.get("publication_date"), notice.get("submission_deadline"), notice.get("estimated_value"), notice.get("currency"),
                json.dumps(notice.get("cpv_codes", [])), json.dumps(notice.get("place_of_performance", [])), notice.get("notice_url", ""), notice.get("xml_url"),
                notice.get("source", "TED Search API v3"), notice.get("discovered_at", now) if not previous_row else self._first_seen(connection, notice_id), now, version, digest, normalize_text(notice),
            ))
            for table in ("lots", "requirements", "award_criteria", "evidence"):
                connection.execute(f"DELETE FROM {table} WHERE notice_id=?", (notice_id,))
            for lot in notice.get("lots", []):
                connection.execute("INSERT INTO lots VALUES (?,?,?,?,?,?,?,?,?,?,?)", (lot["lot_id"], notice_id, lot.get("title"), lot.get("description"), json.dumps(lot.get("cpv_codes", [])), lot.get("value"), lot.get("currency"), json.dumps(lot.get("place_of_performance", [])), lot.get("deadline"), lot.get("duration"), lot.get("status")))
            for requirement in notice.get("requirements", []):
                connection.execute("INSERT INTO requirements VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (requirement["requirement_id"], notice_id, requirement.get("lot_id"), requirement.get("category"), requirement.get("text"), requirement.get("requirement_type"), int(bool(requirement.get("mandatory"))), requirement.get("operator"), json.dumps(requirement.get("structured_value")), requirement.get("unit"), requirement["evidence_id"], requirement.get("confidence"), requirement.get("extraction_status")))
            for criterion in notice.get("award_criteria", []):
                connection.execute("INSERT INTO award_criteria VALUES (?,?,?,?,?,?,?,?)", (criterion["criterion_id"], notice_id, criterion.get("lot_id"), criterion.get("name"), criterion.get("type"), criterion.get("weight"), criterion.get("description"), criterion["evidence_id"]))
            for item in notice.get("evidence", []):
                connection.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?,?)", (item["evidence_id"], notice_id, item.get("lot_id"), item.get("field"), item.get("excerpt"), item.get("source_url"), item.get("source", "TED")))
            connection.execute("INSERT INTO notice_versions VALUES (?,?,?,?,?)", (notice_id, version, now, digest, json.dumps(snapshot, ensure_ascii=False)))
            for change in changes:
                connection.execute("INSERT INTO change_events(notice_id,from_version,to_version,field,old_value_json,new_value_json,materiality,detected_at,evidence) VALUES (?,?,?,?,?,?,?,?,?)", (notice_id, version - 1, version, change["field"], json.dumps(change["old_value"], ensure_ascii=False), json.dumps(change["new_value"], ensure_ascii=False), change["materiality"], change["detected_at"], change["evidence"]))
            connection.execute("DELETE FROM evidence_fts WHERE notice_id=?", (notice_id,))
            for item in notice.get("evidence", []) or [{"evidence_id": f"ted:{notice_id}:notice", "excerpt": normalize_text(notice)}]:
                connection.execute("INSERT INTO evidence_fts VALUES (?,?,?,?,?)", (item["evidence_id"], notice_id, notice.get("title", ""), notice.get("buyer", ""), item.get("excerpt", "")))
                connection.execute("INSERT OR REPLACE INTO embeddings(evidence_id,notice_id,kind,text,model,dimensions,vector_json,updated_at) VALUES (?,?,?,?,NULL,NULL,NULL,NULL)", (item["evidence_id"], notice_id, item.get("field", "notice"), item.get("excerpt", "")))
            if profile and (not previous_row or any(change["materiality"] == "MATERIAL" for change in changes)):
                assessment = assess(snapshot, profile)
                connection.execute("INSERT INTO assessments(notice_id,notice_version,profile_id,profile_version,status,strategic_fit,assessment_json,assessed_at,trigger) VALUES (?,?,?,?,?,?,?,?,?)", (notice_id, version, profile.profile_id, profile.version, assessment["status"], assessment["strategic_fit"], json.dumps(assessment, ensure_ascii=False), assessment["assessed_at"], "INITIAL" if not previous_row else "MATERIAL_CHANGE"))
                reassessed = 1
            else: reassessed = 0
        return {"state": "updated" if previous_row else "new", "changes": len(changes), "reassessed": reassessed}

    @staticmethod
    def _first_seen(connection: sqlite3.Connection, notice_id: str) -> str:
        row = connection.execute("SELECT first_seen FROM notices WHERE notice_id=?", (notice_id,)).fetchone()
        return str(row["first_seen"])

    def get_notice(self, notice_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM notices WHERE notice_id=?", (notice_id,)).fetchone()
            if not row: return None
            result = dict(row)
            result["cpv_codes"] = json.loads(result.pop("cpv_codes_json")); result["place_of_performance"] = json.loads(result.pop("place_json"))
            result["lots"] = [dict(item) for item in connection.execute("SELECT * FROM lots WHERE notice_id=?", (notice_id,))]
            requirements = [dict(item) for item in connection.execute("SELECT * FROM requirements WHERE notice_id=?", (notice_id,))]
            for item in requirements: item["structured_value"] = json.loads(item.pop("structured_value_json")); item["mandatory"] = bool(item["mandatory"])
            result["requirements"] = requirements
            result["award_criteria"] = [dict(item) for item in connection.execute("SELECT * FROM award_criteria WHERE notice_id=?", (notice_id,))]
            result["evidence"] = [dict(item) for item in connection.execute("SELECT * FROM evidence WHERE notice_id=?", (notice_id,))]
            return result

    def list_notices(self, *, country: str | None = None, buyer: str | None = None, cpv: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        clauses, values = [], []
        if country:
            normalized_country = {"FINLAND": "FIN", "SUOMI": "FIN"}.get(country.upper(), country.upper())
            clauses.append("buyer_country=?"); values.append(normalized_country)
        if buyer: clauses.append("lower(buyer) LIKE ?"); values.append(f"%{buyer.lower()}%")
        if cpv: clauses.append("cpv_codes_json LIKE ?"); values.append(f"%{cpv}%")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connection() as connection:
            ids = [row["notice_id"] for row in connection.execute(f"SELECT notice_id FROM notices{where} ORDER BY last_seen DESC LIMIT ?", (*values, limit))]
        return [item for notice_id in ids if (item := self.get_notice(notice_id))]

    def lexical_search(self, query: str, limit: int = 20) -> list[str]:
        tokens = re.findall(r"[a-zA-Z0-9+#.]{2,}", query.lower())[:12]
        if not tokens: return []
        with self.connection() as connection:
            return [str(row["evidence_id"]) for row in connection.execute("SELECT evidence_id FROM evidence_fts WHERE evidence_fts MATCH ? ORDER BY bm25(evidence_fts) LIMIT ?", (" OR ".join(f'\"{token}\"' for token in tokens), limit))]

    def pending_embeddings(self, model: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return [dict(row) for row in connection.execute("SELECT evidence_id, text FROM embeddings WHERE vector_json IS NULL OR model!=? LIMIT ?", (model, limit))]

    def set_embedding(self, evidence_id: str, model: str, vector: list[float]) -> None:
        with self.connection() as connection:
            connection.execute("UPDATE embeddings SET model=?, dimensions=?, vector_json=?, updated_at=? WHERE evidence_id=?", (model, len(vector), json.dumps(vector), utc_now(), evidence_id))

    def embedded_evidence(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute("SELECT e.*, n.title, n.buyer, n.notice_url, n.buyer_country, n.cpv_codes_json, n.estimated_value, n.submission_deadline FROM embeddings e JOIN notices n USING(notice_id) WHERE e.vector_json IS NOT NULL").fetchall()
        result=[]
        for row in rows:
            item=dict(row); item["vector"] = json.loads(item.pop("vector_json")); item["cpv_codes"] = json.loads(item.pop("cpv_codes_json")); result.append(item)
        return result

    def changes(self, notice_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM change_events WHERE notice_id=? ORDER BY change_id", (notice_id,)).fetchall()
        return [dict(row) for row in rows]

    def versions(self, notice_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute("SELECT version,fetched_at,source_hash,snapshot_json FROM notice_versions WHERE notice_id=? ORDER BY version", (notice_id,)).fetchall()
        return [{**dict(row), "snapshot": json.loads(row["snapshot_json"])} for row in rows]

    def latest_assessment(self, notice_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM assessments WHERE notice_id=? ORDER BY assessment_id DESC LIMIT 1", (notice_id,)).fetchone()
        return {**dict(row), "assessment": json.loads(row["assessment_json"])} if row else None

    def stats(self) -> dict[str, Any]:
        with self.connection() as connection:
            return {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("notices", "lots", "requirements", "award_criteria", "evidence", "notice_versions", "change_events", "supplier_profiles", "assessments", "embeddings")}
