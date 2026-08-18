from __future__ import annotations

from datetime import date, timedelta
import json
from typing import Any, Iterator
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from .extraction import extract_requirements, parse_money


SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"
FIELDS = ["publication-number", "notice-identifier", "notice-version", "notice-title", "buyer-name", "buyer-country", "publication-date", "deadline-date-lot", "estimated-value-proc", "estimated-value-cur-proc", "classification-cpv", "place-of-performance-country-lot", "procedure-type", "notice-type", "form-type", "identifier-lot", "title-lot", "description-lot", "estimated-value-lot", "estimated-value-cur-lot", "selection-criterion-name-lot", "selection-criterion-description-lot", "selection-criterion-lot", "requirement-stage-lot", "award-criterion-name-lot", "award-criterion-type-lot", "award-criterion-number-weight-lot", "award-criterion-description-lot", "change-reason-code", "change-description", "change-reason-description", "change-notice-version-identifier", "BT-13716-notice", "links"]


def _strings(value: Any) -> list[str]:
    if isinstance(value, list): return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip(): return [value.strip()]
    return []


def _localized(value: Any) -> list[str]:
    if not isinstance(value, dict): return _strings(value)
    for language in ("eng", "fin", "fra", "deu", "swe"):
        selected = _strings(value.get(language))
        if selected: return selected
    return [item for nested in value.values() for item in _strings(nested)]


def _url(links: Any, kind: str, publication_id: str) -> str | None:
    values = links.get(kind, {}) if isinstance(links, dict) else {}
    if isinstance(values, dict) and values:
        return str(values.get("ENG") or values.get("FIN") or values.get("MUL") or next(iter(values.values())))
    return f"https://ted.europa.eu/en/notice/-/detail/{publication_id}" if kind == "html" else None


def build_query(filters: dict[str, Any]) -> str:
    clauses = []
    if filters.get("keywords"): clauses.append(f'FT ~ "{str(filters["keywords"]).replace(chr(34), "")[:120]}"')
    if filters.get("cpv"): clauses.append(f'classification-cpv = {"".join(c for c in str(filters["cpv"]) if c.isdigit() or c == "*")[:9]}')
    if filters.get("buyer_country"): clauses.append(f'buyer-country = {str(filters["buyer_country"]).upper()[:3]}')
    if filters.get("place_country"): clauses.append(f'place-of-performance-country-lot = {str(filters["place_country"]).upper()[:3]}')
    start = str(filters.get("published_from") or date.today() - timedelta(days=90)).replace("-", "")
    end = str(filters.get("published_to") or date.today()).replace("-", "")
    clauses.append(f"PD = ({start} <> {end})")
    if filters.get("procedure_type"): clauses.append(f'procedure-type = {filters["procedure_type"]}')
    return " AND ".join(clauses)


def normalize(raw: dict[str, Any], fetched_at: str) -> dict[str, Any]:
    notice_id = str(raw.get("notice-identifier") or raw.get("publication-number"))
    publication_id = str(raw.get("publication-number", ""))
    url = _url(raw.get("links"), "html", publication_id) or ""
    lot_ids, titles, descriptions = _strings(raw.get("identifier-lot")), _localized(raw.get("title-lot")), _localized(raw.get("description-lot"))
    deadlines, values = _strings(raw.get("deadline-date-lot")), _strings(raw.get("estimated-value-lot"))
    currencies, places, cpvs = _strings(raw.get("estimated-value-cur-lot")), _strings(raw.get("place-of-performance-country-lot")), _strings(raw.get("classification-cpv"))
    count = max(1, len(lot_ids), len(titles), len(descriptions))
    lots = []
    for index in range(count):
        lots.append({
            "lot_id": lot_ids[index] if index < len(lot_ids) else f"{notice_id}:LOT-{index+1:04d}", "notice_id": notice_id,
            "title": titles[index] if index < len(titles) else (titles[0] if titles else "Untitled lot"),
            "description": descriptions[index] if index < len(descriptions) else (descriptions[0] if descriptions else ""),
            "cpv_codes": [cpvs[index]] if len(cpvs) == count else list(dict.fromkeys(cpvs)),
            "value": parse_money(values[index] if index < len(values) else values[0] if values else None),
            "currency": currencies[index] if index < len(currencies) else currencies[0] if currencies else None,
            "place_of_performance": [places[index]] if index < len(places) else list(dict.fromkeys(places)),
            "deadline": deadlines[index] if index < len(deadlines) else deadlines[0] if deadlines else None,
            "duration": None, "status": "UNKNOWN",
        })
    requirements, requirement_evidence = extract_requirements(notice_id, lots, url)
    award_names, award_types, award_descriptions = _localized(raw.get("award-criterion-name-lot")), _strings(raw.get("award-criterion-type-lot")), _localized(raw.get("award-criterion-description-lot"))
    award_criteria, award_evidence = [], []
    for index, name in enumerate(award_names):
        evidence_id = f"ted:{notice_id}:notice:award-{index+1}"
        award_evidence.append({"evidence_id": evidence_id, "notice_id": notice_id, "lot_id": None, "field": "award_criterion", "excerpt": f"{name}: {award_descriptions[index] if index < len(award_descriptions) else ''}", "source_url": url, "source": "TED"})
        award_criteria.append({"criterion_id": f"{notice_id}:award:{index+1}", "notice_id": notice_id, "lot_id": lot_ids[index] if index < len(lot_ids) else None, "name": name, "type": award_types[index] if index < len(award_types) else "other", "weight": None, "description": award_descriptions[index] if index < len(award_descriptions) else "", "evidence_id": evidence_id})
    return {
        "notice_id": notice_id, "publication_id": publication_id, "notice_type": str(raw.get("notice-type", "unknown")),
        "form_type": str(raw.get("form-type", "unknown")), "title": (_localized(raw.get("notice-title")) or ["Untitled TED notice"])[0],
        "description": " ".join(lot["description"] for lot in lots)[:32000], "buyer": (_localized(raw.get("buyer-name")) or ["Buyer not stated"])[0],
        "buyer_country": (_strings(raw.get("buyer-country")) or ["-"])[0], "procedure_type": str(raw.get("procedure-type", "unknown")),
        "publication_date": str(raw.get("publication-date", "")), "submission_deadline": deadlines[0] if deadlines else None,
        "estimated_value": parse_money(raw.get("estimated-value-proc")), "currency": str(raw.get("estimated-value-cur-proc") or (currencies[0] if currencies else "")) or None,
        "cpv_codes": list(dict.fromkeys(cpvs)), "place_of_performance": list(dict.fromkeys(places)), "notice_url": url,
        "xml_url": _url(raw.get("links"), "xml", publication_id), "source": "TED Search API v3", "discovered_at": fetched_at,
        "updated_at": fetched_at, "version": int(raw.get("notice-version", 1)), "lots": lots, "requirements": requirements,
        "award_criteria": award_criteria, "evidence": [
            {"evidence_id": f"ted:{notice_id}:notice:summary", "notice_id": notice_id, "lot_id": None,
             "field": "notice_summary", "excerpt": (" ".join(lot["description"] for lot in lots) or (_localized(raw.get("notice-title")) or [""])[0])[:1000],
             "source_url": url, "source": "TED"},
            *requirement_evidence, *award_evidence,
        ],
    }


class TedClient:
    def search(self, filters: dict[str, Any], *, limit: int = 20, token: str | None = None, page: int = 1) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": build_query(filters), "fields": FIELDS, "scope": "ACTIVE", "limit": max(1, min(250, limit)), "paginationMode": "ITERATION" if token else "PAGE_NUMBER", "onlyLatestVersions": True}
        if token: payload["iterationNextToken"] = token
        else: payload["page"] = max(1, min(15000, page))
        request = Request(SEARCH_URL, data=json.dumps(payload).encode(), headers={"content-type": "application/json", "accept": "application/json", "user-agent": "AppliedAILab-EUTenderIntelligence/2.0"}, method="POST")
        with urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode())
        return {**body, "query": payload["query"]}

    def iterate(self, filters: dict[str, Any], *, batch_size: int = 100, max_batches: int = 10) -> Iterator[dict[str, Any]]:
        token = None
        for _ in range(max_batches):
            batch = self.search(filters, limit=batch_size, token=token)
            yield batch
            token = batch.get("iterationNextToken")
            if not token: break

    def enrich_from_xml(self, notice: dict[str, Any], *, max_chars: int = 50_000) -> dict[str, Any]:
        """Fetch the official linked eForms XML and add bounded inert document text."""
        if not notice.get("xml_url"):
            return notice
        with urlopen(Request(str(notice["xml_url"]), headers={"accept": "application/xml", "user-agent": "AppliedAILab-EUTenderIntelligence/2.0"}), timeout=20) as response:
            root = ET.fromstring(response.read())
        selected: list[str] = []
        seen: set[str] = set()
        for element in root.iter():
            if not element.tag.endswith(("Description", "Note", "SelectionCriterion", "SpecificTendererRequirement", "ContractingSystem")):
                continue
            text = " ".join(" ".join(element.itertext()).split())
            if len(text) >= 20 and text not in seen:
                seen.add(text); selected.append(text)
            if sum(map(len, selected)) >= max_chars:
                break
        document_text = "\n".join(selected)[:max_chars]
        if not document_text:
            return notice
        enriched = {**notice, "lots": [dict(lot) for lot in notice.get("lots", [])]}
        if not enriched["lots"]:
            enriched["lots"] = [{"lot_id": f"{notice['notice_id']}:NOTICE", "description": document_text, "title": notice.get("title", ""), "cpv_codes": notice.get("cpv_codes", []), "value": notice.get("estimated_value"), "currency": notice.get("currency"), "place_of_performance": notice.get("place_of_performance", []), "deadline": notice.get("submission_deadline"), "duration": None, "status": "UNKNOWN"}]
        else:
            enriched["lots"][0]["description"] = f"{enriched['lots'][0].get('description', '')}\n{document_text}"[:max_chars]
        requirements, requirement_evidence = extract_requirements(notice["notice_id"], enriched["lots"], notice["notice_url"])
        existing_non_requirements = [item for item in notice.get("evidence", []) if item.get("field") != "requirement"]
        document_evidence = {"evidence_id": f"ted:{notice['notice_id']}:document:xml", "notice_id": notice["notice_id"], "lot_id": None, "field": "procurement_document", "excerpt": document_text[:1000], "source_url": notice["xml_url"], "source": "TED XML"}
        enriched["description"] = f"{notice.get('description', '')}\n{document_text}"[:32_000]
        enriched["requirements"] = requirements
        enriched["evidence"] = [*existing_non_requirements, document_evidence, *requirement_evidence]
        return enriched
