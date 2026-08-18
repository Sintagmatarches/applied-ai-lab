from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "ref",
    "source",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("job URL must use http or https")
    query = urlencode(
        [(key, val) for key, val in parse_qsl(parts.query) if key.lower() not in TRACKING_PARAMETERS]
    )
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/", query, ""))


def normalized_job_text(job: dict[str, Any]) -> str:
    requirements = job.get("requirements") or job.get("tags") or []
    if not isinstance(requirements, list):
        requirements = []
    fields = [
        f"Title: {job.get('title', '')}",
        f"Company: {job.get('company', '')}",
        f"Location: {job.get('location', '')}",
        f"Source: {job.get('source', '')}",
        f"Requirements: {', '.join(str(item) for item in requirements)}",
        f"Description: {job.get('description', '')}",
    ]
    return "\n".join(fields).strip()[:16_000]


class JobKnowledgeBase:
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
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    canonical_url TEXT NOT NULL UNIQUE,
                    source TEXT NOT NULL,
                    company TEXT NOT NULL,
                    title TEXT NOT NULL,
                    location TEXT NOT NULL,
                    remote INTEGER NOT NULL DEFAULT 0,
                    description TEXT NOT NULL,
                    requirements_json TEXT NOT NULL,
                    discovered_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    normalized_text TEXT NOT NULL,
                    embedding_model TEXT,
                    embedding_dimensions INTEGER,
                    embedding_json TEXT,
                    embedding_updated_at TEXT
                );
                CREATE INDEX IF NOT EXISTS jobs_source_idx ON jobs(source);
                CREATE INDEX IF NOT EXISTS jobs_location_idx ON jobs(location);
                CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(
                    job_id UNINDEXED, title, company, location, requirements, description
                );
                """
            )

    def upsert_jobs(self, jobs: list[dict[str, Any]]) -> int:
        saved = 0
        now = utc_now()
        with self.connection() as connection:
            for raw in jobs:
                job_id = str(raw.get("id", "")).strip()
                company = str(raw.get("company", "")).strip()
                title = str(raw.get("title", "")).strip()
                source = str(raw.get("source", "")).strip()
                description = str(raw.get("description", "")).strip()[:12_000]
                if not all((job_id, company, title, source, description)):
                    continue
                try:
                    url = canonical_url(str(raw.get("url", "")))
                except ValueError:
                    continue
                requirements = raw.get("requirements") or raw.get("tags") or []
                if not isinstance(requirements, list):
                    requirements = []
                requirements = [str(item).strip() for item in requirements if str(item).strip()][:40]
                job = {
                    **raw,
                    "id": job_id,
                    "company": company,
                    "title": title,
                    "source": source,
                    "description": description,
                    "requirements": requirements,
                }
                text = normalized_job_text(job)
                existing = connection.execute(
                    "SELECT normalized_text, discovered_at FROM jobs WHERE id = ?", (job_id,)
                ).fetchone()
                changed = existing is None or existing["normalized_text"] != text
                discovered_at = (
                    str(raw.get("discoveredAt") or raw.get("publishedAt") or now)
                    if existing is None
                    else existing["discovered_at"]
                )
                connection.execute(
                    """
                    INSERT INTO jobs (
                        id, canonical_url, source, company, title, location, remote,
                        description, requirements_json, discovered_at, updated_at,
                        normalized_text, embedding_model, embedding_dimensions,
                        embedding_json, embedding_updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
                    ON CONFLICT(id) DO UPDATE SET
                        canonical_url = excluded.canonical_url,
                        source = excluded.source,
                        company = excluded.company,
                        title = excluded.title,
                        location = excluded.location,
                        remote = excluded.remote,
                        description = excluded.description,
                        requirements_json = excluded.requirements_json,
                        updated_at = excluded.updated_at,
                        normalized_text = excluded.normalized_text,
                        embedding_model = CASE WHEN jobs.normalized_text = excluded.normalized_text THEN jobs.embedding_model ELSE NULL END,
                        embedding_dimensions = CASE WHEN jobs.normalized_text = excluded.normalized_text THEN jobs.embedding_dimensions ELSE NULL END,
                        embedding_json = CASE WHEN jobs.normalized_text = excluded.normalized_text THEN jobs.embedding_json ELSE NULL END,
                        embedding_updated_at = CASE WHEN jobs.normalized_text = excluded.normalized_text THEN jobs.embedding_updated_at ELSE NULL END
                    """,
                    (
                        job_id,
                        url,
                        source,
                        company,
                        title,
                        str(raw.get("location", "Not stated"))[:300],
                        1 if raw.get("remote") else 0,
                        description,
                        json.dumps(requirements, ensure_ascii=False),
                        discovered_at,
                        now,
                        text,
                    ),
                )
                connection.execute("DELETE FROM jobs_fts WHERE job_id = ?", (job_id,))
                connection.execute(
                    "INSERT INTO jobs_fts(job_id, title, company, location, requirements, description) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        job_id,
                        title,
                        company,
                        str(raw.get("location", "Not stated")),
                        " ".join(requirements),
                        description,
                    ),
                )
                saved += 1
                if changed:
                    connection.execute(
                        "UPDATE jobs SET embedding_model = NULL, embedding_dimensions = NULL, embedding_json = NULL, embedding_updated_at = NULL WHERE id = ?",
                        (job_id,),
                    )
        return saved

    def pending_embeddings(self, model: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT id, normalized_text FROM jobs WHERE embedding_json IS NULL OR embedding_model != ? ORDER BY updated_at DESC LIMIT ?",
                (model, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_embedding(self, job_id: str, model: str, vector: list[float]) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE jobs SET embedding_model = ?, embedding_dimensions = ?, embedding_json = ?, embedding_updated_at = ? WHERE id = ?",
                (model, len(vector), json.dumps(vector), utc_now(), job_id),
            )

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["remote"] = bool(result.get("remote"))
        result["requirements"] = json.loads(result.pop("requirements_json", "[]"))
        embedding = result.pop("embedding_json", None)
        result["embedding"] = json.loads(embedding) if embedding else None
        return result

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row(row) if row else None

    def list_jobs(
        self,
        *,
        source: str | None = None,
        location: str | None = None,
        remote_only: bool = False,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if source:
            if source.strip().lower() not in {"all", "any", "*"}:
                clauses.append("lower(source) = lower(?)")
                values.append(source)
        if location:
            lowered = location.strip().lower()
            if lowered in {"europe", "eu", "emea"}:
                clauses.append("(lower(location) LIKE ? OR lower(location) LIKE ? OR lower(location) LIKE ? OR (remote = 1 AND lower(location) = 'remote'))")
                values.extend(["%europe%", "%emea%", "% eu%"])
            elif lowered not in {"all", "any", "*"}:
                clauses.append("lower(location) LIKE ?")
                values.append(f"%{lowered}%")
        if remote_only:
            clauses.append("remote = 1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM jobs {where} ORDER BY updated_at DESC", values
            ).fetchall()
        return [self._row(row) for row in rows]

    def lexical_search(self, query: str, limit: int = 20) -> list[str]:
        tokens = re.findall(r"[a-zA-Z0-9+#.]{2,}", query.lower())[:12]
        if not tokens:
            return []
        expression = " OR ".join(f'"{token}"' for token in tokens)
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT job_id FROM jobs_fts WHERE jobs_fts MATCH ? ORDER BY bm25(jobs_fts) LIMIT ?",
                (expression, limit),
            ).fetchall()
        return [str(row["job_id"]) for row in rows]

    def stats(self) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS jobs, COUNT(embedding_json) AS embeddings, MAX(embedding_dimensions) AS dimensions FROM jobs"
            ).fetchone()
        return dict(row)
