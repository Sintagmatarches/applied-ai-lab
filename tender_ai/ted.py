from __future__ import annotations

from datetime import date, timedelta
import json
import random
import time
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from .extraction import extract_requirements, parse_money


SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"
OFFICIAL_HOSTS = {"api.ted.europa.eu", "ted.europa.eu"}
MAX_JSON_BYTES = 8_000_000
MAX_XML_BYTES = 2_000_000
FIELDS = [
    "publication-number", "notice-identifier", "notice-version", "notice-title", "buyer-name", "buyer-country",
    "publication-date", "deadline-date-lot", "estimated-value-proc", "estimated-value-cur-proc", "classification-cpv",
    "place-of-performance-country-lot", "procedure-type", "notice-type", "form-type", "identifier-lot", "title-lot",
    "description-lot", "estimated-value-lot", "estimated-value-cur-lot", "selection-criterion-name-lot",
    "selection-criterion-description-lot", "selection-criterion-lot", "requirement-stage-lot", "award-criterion-name-lot",
    "award-criterion-type-lot", "award-criterion-number-weight-lot", "award-criterion-description-lot", "BT-541-Lot",
    "submission-language", "contract-conditions-description-lot", "term-performance-lot", "change-reason-code",
    "change-description", "change-reason-description", "change-notice-version-identifier", "BT-13716-notice", "links",
]


class TedNetworkError(RuntimeError):
    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _localized(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return _strings(value)
    for language in ("eng", "fin", "fra", "deu", "swe"):
        selected = _strings(value.get(language))
        if selected:
            return selected
    return [item for nested in value.values() for item in _strings(nested)]


def _url(links: Any, kind: str, publication_id: str) -> str | None:
    values = links.get(kind, {}) if isinstance(links, dict) else {}
    if isinstance(values, dict) and values:
        return str(values.get("ENG") or values.get("FIN") or values.get("MUL") or next(iter(values.values())))
    return f"https://ted.europa.eu/en/notice/-/detail/{publication_id}" if kind == "html" else None


def _validate_official_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS or parsed.username or parsed.password:
        raise TedNetworkError("SSRF_BLOCKED", "Only official HTTPS TED resources are allowed")
    return value


def _read_bounded(response: Any, maximum: int, content_types: tuple[str, ...]) -> bytes:
    content_type = str(response.headers.get("content-type", "")).lower()
    if not any(item in content_type for item in content_types):
        raise TedNetworkError("CONTENT_TYPE", f"Unexpected TED Content-Type: {content_type or 'missing'}")
    declared = response.headers.get("content-length")
    if declared and int(declared) > maximum:
        raise TedNetworkError("RESPONSE_TOO_LARGE", "TED response exceeds the configured size limit")
    chunks, size = [], 0
    while True:
        chunk = response.read(min(65_536, maximum + 1 - size))
        if not chunk:
            break
        size += len(chunk)
        if size > maximum:
            raise TedNetworkError("RESPONSE_TOO_LARGE", "TED response exceeds the configured size limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _request(url: str, *, data: bytes | None, accept: str, maximum: int, content_types: tuple[str, ...], timeout: float = 20, attempts: int = 3) -> bytes:
    _validate_official_url(url)
    for attempt in range(attempts):
        request = Request(url, data=data, headers={"content-type": "application/json" if data else accept, "accept": accept, "user-agent": "AppliedAILab-EUTenderIntelligence/3.0"}, method="POST" if data else "GET")
        try:
            with urlopen(request, timeout=timeout) as response:
                return _read_bounded(response, maximum, content_types)
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt + 1 == attempts:
                raise TedNetworkError(f"HTTP_{error.code}", f"TED request failed with HTTP {error.code}") from error
            retry_after = error.headers.get("retry-after")
            delay = min(10.0, float(retry_after)) if retry_after and retry_after.isdigit() else min(5.0, 0.5 * 2**attempt + random.random() * 0.25)
            time.sleep(delay)
        except (URLError, TimeoutError, OSError) as error:
            if attempt + 1 == attempts:
                raise TedNetworkError("NETWORK", f"TED request failed: {type(error).__name__}") from error
            time.sleep(min(5.0, 0.5 * 2**attempt + random.random() * 0.25))
    raise TedNetworkError("RETRY_EXHAUSTED", "TED retry policy exhausted")


def _clean_country(value: Any) -> str:
    cleaned = "".join(item for item in str(value or "").upper() if item.isalpha())
    if cleaned and len(cleaned) != 3:
        raise ValueError("country must be a three-letter TED code")
    return cleaned


def _clean_date(value: Any) -> str:
    text = str(value)
    parsed = date.fromisoformat(text)
    return parsed.isoformat().replace("-", "")


def build_query(filters: dict[str, Any]) -> str:
    clauses = []
    if filters.get("keywords"):
        clauses.append(f'FT ~ "{str(filters["keywords"]).replace(chr(34), "")[:120]}"')
    if filters.get("cpv"):
        cpv = "".join(c for c in str(filters["cpv"]) if c.isdigit() or c == "*")[:9]
        if not cpv or (not cpv.rstrip("*").isdigit()) or "*" in cpv.rstrip("*"):
            raise ValueError("invalid CPV filter")
        clauses.append(f"classification-cpv = {cpv}")
    if filters.get("buyer_country"):
        clauses.append(f'buyer-country = {_clean_country(filters["buyer_country"])}')
    if filters.get("place_country"):
        clauses.append(f'place-of-performance-country-lot = {_clean_country(filters["place_country"])}')
    start = _clean_date(filters.get("published_from") or date.today() - timedelta(days=90))
    end = _clean_date(filters.get("published_to") or date.today())
    if start > end:
        raise ValueError("published_from must not be after published_to")
    clauses.append(f"PD = ({start} <> {end})")
    if filters.get("procedure_type"):
        procedure = str(filters["procedure_type"])
        if procedure not in {"open", "restricted", "neg-w-call", "comp-dial", "innovation", "neg-wo-call", "other"}:
            raise ValueError("invalid procedure type")
        clauses.append(f"procedure-type = {procedure}")
    return " AND ".join(clauses)


def _lot_id_for(lot_ids: list[str], value_count: int, index: int) -> str | None:
    if len(lot_ids) == 1:
        return lot_ids[0]
    return lot_ids[index] if value_count == len(lot_ids) and index < len(lot_ids) else None


def _stage(value: str | None) -> str:
    return {"t-requ": "TENDER", "par-requ": "REQUEST_TO_PARTICIPATE", "not-requ": "NOT_REQUIRED"}.get(value or "", "UNKNOWN")


def _category(code: str, text: str) -> str:
    value = f"{code} {text}".lower()
    if any(item in value for item in ("turnover", "financial", "fin-sta")):
        return "turnover"
    if any(item in value for item in ("register", "professional", "suit-reg")):
        return "professional"
    if any(item in value for item in ("reference", "experience", "past contract")):
        return "references"
    if any(item in value for item in ("staff", "personnel")):
        return "staff"
    return "technical"


def normalize(raw: dict[str, Any], fetched_at: str) -> dict[str, Any]:
    notice_id = str(raw.get("notice-identifier") or raw.get("publication-number"))
    publication_id = str(raw.get("publication-number", ""))
    url = _url(raw.get("links"), "html", publication_id) or ""
    lot_ids, titles, descriptions = _strings(raw.get("identifier-lot")), _localized(raw.get("title-lot")), _localized(raw.get("description-lot"))
    deadlines, values = _strings(raw.get("deadline-date-lot")), _strings(raw.get("estimated-value-lot"))
    currencies, places, cpvs = _strings(raw.get("estimated-value-cur-lot")), _strings(raw.get("place-of-performance-country-lot")), _strings(raw.get("classification-cpv"))
    languages = _strings(raw.get("submission-language"))
    count = max(1, len(lot_ids), len(titles), len(descriptions))
    lots = [{
        "lot_id": lot_ids[index] if index < len(lot_ids) else f"{notice_id}:LOT-{index+1:04d}", "notice_id": notice_id,
        "title": titles[index] if index < len(titles) else (titles[0] if titles else "Untitled lot"),
        "description": descriptions[index] if index < len(descriptions) else (descriptions[0] if descriptions else ""),
        "cpv_codes": [cpvs[index]] if len(cpvs) == count else list(dict.fromkeys(cpvs)),
        "value": parse_money(values[index] if index < len(values) else values[0] if values else None),
        "currency": currencies[index] if index < len(currencies) else currencies[0] if currencies else None,
        "place_of_performance": [places[index]] if index < len(places) else list(dict.fromkeys(places)),
        "deadline": deadlines[index] if index < len(deadlines) else deadlines[0] if deadlines else None,
        "duration": None, "status": "UNKNOWN", "submission_languages": languages,
    } for index in range(count)]
    prose_requirements, security_findings, prose_evidence = extract_requirements(notice_id, lots, url)
    structured_requirements, structured_evidence = [], []
    selection_codes = _strings(raw.get("selection-criterion-lot"))
    selection_names = _localized(raw.get("selection-criterion-name-lot"))
    selection_descriptions = _localized(raw.get("selection-criterion-description-lot"))
    stages = _strings(raw.get("requirement-stage-lot"))
    selection_count = max(len(selection_codes), len(selection_names), len(selection_descriptions))
    for index in range(selection_count):
        code = selection_codes[index] if index < len(selection_codes) else "selection-criterion"
        text = selection_descriptions[index] if index < len(selection_descriptions) else selection_names[index] if index < len(selection_names) else code
        selected_stage = _stage(stages[index] if index < len(stages) else None)
        lot_id = _lot_id_for(lot_ids, selection_count, index)
        evidence_id = f"ted:{notice_id}:{lot_id or 'notice'}:selection-{index+1}"
        structured_evidence.append({"evidence_id": evidence_id, "notice_id": notice_id, "lot_id": lot_id, "field": "selection_criterion", "excerpt": text[:1000], "source_url": url, "source": "TED Search API v3"})
        structured_requirements.append({"requirement_id": f"{notice_id}:selection:{index+1}", "notice_id": notice_id, "lot_id": lot_id, "category": _category(code, text), "text": text, "requirement_type": "eligibility", "mandatory": selected_stage != "NOT_REQUIRED", "operator": None, "structured_value": None, "unit": None, "stage": selected_stage, "source_field": "selection-criterion-lot", "evidence_id": evidence_id, "confidence": 1.0 if lot_id else .75, "extraction_status": "STRUCTURED"})
    for lot in lots:
        if not languages:
            continue
        text = f"Tender submission language must be one of: {', '.join(languages)}."
        evidence_id = f"ted:{notice_id}:{lot['lot_id']}:submission-language"
        structured_evidence.append({"evidence_id": evidence_id, "notice_id": notice_id, "lot_id": lot["lot_id"], "field": "submission_language", "excerpt": text, "source_url": url, "source": "TED Search API v3"})
        structured_requirements.append({"requirement_id": f"{notice_id}:{lot['lot_id']}:submission-language", "notice_id": notice_id, "lot_id": lot["lot_id"], "category": "language", "text": text, "requirement_type": "eligibility", "mandatory": True, "operator": "one_of", "structured_value": languages, "unit": None, "stage": "TENDER", "source_field": "submission-language", "evidence_id": evidence_id, "confidence": 1.0, "extraction_status": "STRUCTURED"})
    award_names, award_types = _localized(raw.get("award-criterion-name-lot")), _strings(raw.get("award-criterion-type-lot"))
    award_descriptions = _localized(raw.get("award-criterion-description-lot"))
    award_numbers, award_weight_types = _strings(raw.get("BT-541-Lot")), _strings(raw.get("award-criterion-number-weight-lot"))
    award_criteria, award_evidence = [], []
    for index, name in enumerate(award_names):
        lot_id = _lot_id_for(lot_ids, len(award_names), index)
        evidence_id = f"ted:{notice_id}:{lot_id or 'notice'}:award-{index+1}"
        award_evidence.append({"evidence_id": evidence_id, "notice_id": notice_id, "lot_id": lot_id, "field": "award_criterion", "excerpt": f"{name}: {award_descriptions[index] if index < len(award_descriptions) else ''}", "source_url": url, "source": "TED Search API v3"})
        award_criteria.append({"criterion_id": f"{notice_id}:award:{index+1}", "notice_id": notice_id, "lot_id": lot_id, "name": name, "type": award_types[index] if index < len(award_types) else "other", "weight": parse_money(award_numbers[index]) if index < len(award_numbers) else None, "weight_type": award_weight_types[index] if index < len(award_weight_types) else None, "description": award_descriptions[index] if index < len(award_descriptions) else "", "evidence_id": evidence_id})
    return {
        "notice_id": notice_id, "publication_id": publication_id, "notice_type": str(raw.get("notice-type", "unknown")),
        "form_type": str(raw.get("form-type", "unknown")), "title": (_localized(raw.get("notice-title")) or ["Untitled TED notice"])[0],
        "description": " ".join(lot["description"] for lot in lots)[:32_000], "buyer": (_localized(raw.get("buyer-name")) or ["Buyer not stated"])[0],
        "buyer_country": (_strings(raw.get("buyer-country")) or ["-"])[0], "procedure_type": str(raw.get("procedure-type", "unknown")),
        "publication_date": str(raw.get("publication-date", "")), "submission_deadline": deadlines[0] if deadlines else None,
        "estimated_value": parse_money(raw.get("estimated-value-proc")), "currency": str(raw.get("estimated-value-cur-proc") or (currencies[0] if currencies else "")) or None,
        "cpv_codes": list(dict.fromkeys(cpvs)), "place_of_performance": list(dict.fromkeys(places)), "notice_url": url,
        "xml_url": _url(raw.get("links"), "xml", publication_id), "source": "TED Search API v3", "discovered_at": fetched_at,
        "updated_at": fetched_at, "source_version": int(raw.get("notice-version", 1)), "lots": lots,
        "requirements": [*structured_requirements, *prose_requirements], "award_criteria": award_criteria,
        "security_findings": security_findings, "evidence": [
            {"evidence_id": f"ted:{notice_id}:notice:summary", "notice_id": notice_id, "lot_id": None, "field": "notice_summary", "excerpt": (" ".join(lot["description"] for lot in lots) or (_localized(raw.get("notice-title")) or [""])[0])[:1000], "source_url": url, "source": "TED Search API v3"},
            *structured_evidence, *prose_evidence, *award_evidence,
        ],
    }


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _descendant_text(element: ET.Element, names: set[str]) -> list[str]:
    return [" ".join(" ".join(item.itertext()).split()) for item in element.iter() if _local(item.tag) in names and " ".join(" ".join(item.itertext()).split())]


class TedClient:
    def search(self, filters: dict[str, Any], *, limit: int = 20, token: str | None = None, page: int = 1) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": build_query(filters), "fields": FIELDS, "scope": "ACTIVE", "limit": max(1, min(250, limit)), "paginationMode": "ITERATION" if token else "PAGE_NUMBER", "onlyLatestVersions": True}
        if token:
            payload["iterationNextToken"] = token
        else:
            payload["page"] = max(1, min(15_000, page))
        raw = _request(SEARCH_URL, data=json.dumps(payload).encode(), accept="application/json", maximum=MAX_JSON_BYTES, content_types=("application/json",))
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TedNetworkError("INVALID_JSON", "TED returned invalid JSON") from error
        return {**body, "query": payload["query"]}

    def get_latest_publication(self, publication_id: str) -> dict[str, Any] | None:
        if not re_fullmatch_publication(publication_id):
            raise ValueError("invalid TED publication identifier")
        payload = {"query": f"publication-number = {publication_id}", "fields": FIELDS, "scope": "ALL", "limit": 1, "page": 1, "paginationMode": "PAGE_NUMBER", "onlyLatestVersions": True}
        raw = _request(SEARCH_URL, data=json.dumps(payload).encode(), accept="application/json", maximum=MAX_JSON_BYTES, content_types=("application/json",))
        try:
            notices = json.loads(raw.decode("utf-8")).get("notices", [])
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as error:
            raise TedNetworkError("INVALID_JSON", "TED returned invalid JSON") from error
        return notices[0] if notices else None

    def iterate(self, filters: dict[str, Any], *, batch_size: int = 100, max_batches: int = 10) -> Iterator[dict[str, Any]]:
        token = None
        for _ in range(max_batches):
            batch = self.search(filters, limit=batch_size, token=token)
            yield batch
            token = batch.get("iterationNextToken")
            if not token:
                break

    def enrich_from_xml(self, notice: dict[str, Any], *, max_chars_per_lot: int = 12_000) -> dict[str, Any]:
        if not notice.get("xml_url"):
            return notice
        raw = _request(str(notice["xml_url"]), data=None, accept="application/xml", maximum=MAX_XML_BYTES, content_types=("application/xml", "text/xml"))
        lowered = raw[:4096].lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise TedNetworkError("UNSAFE_XML", "DTD and entity declarations are not allowed")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as error:
            raise TedNetworkError("INVALID_XML", "TED returned malformed XML") from error
        enriched = {**notice, "lots": [dict(lot) for lot in notice.get("lots", [])]}
        by_id = {str(lot["lot_id"]): lot for lot in enriched["lots"]}
        xml_evidence: list[dict[str, Any]] = []
        xml_requirements: list[dict[str, Any]] = []
        xml_awards: list[dict[str, Any]] = []
        for lot_node in (node for node in root.iter() if _local(node.tag) == "ProcurementProjectLot"):
            ids = [str(item.text).strip() for item in lot_node.iter() if _local(item.tag) == "ID" and item.text and str(item.text).strip().startswith("LOT-")]
            if not ids or ids[0] not in by_id:
                continue
            lot_id, target = ids[0], by_id[ids[0]]
            texts = _descendant_text(lot_node, {"Description", "Note"})
            document_text = "\n".join(dict.fromkeys(texts))[:max_chars_per_lot]
            if document_text:
                target["description"] = f"{target.get('description', '')}\n{document_text}"[:max_chars_per_lot]
                xml_evidence.append({"evidence_id": f"ted:{notice['notice_id']}:{lot_id}:document:xml", "notice_id": notice["notice_id"], "lot_id": lot_id, "field": "procurement_document", "excerpt": document_text[:1000], "source_url": notice["xml_url"], "source": "TED eForms XML"})
            for selection in (node for node in lot_node.iter() if _local(node.tag) == "SelectionCriteria"):
                codes = [str(item.text).strip() for item in selection.iter() if _local(item.tag) == "TendererRequirementTypeCode" and item.text and item.attrib.get("listName") == "selection-criterion"]
                descriptions = _descendant_text(selection, {"Description"})
                if not codes and not descriptions:
                    continue
                code, text = (codes or ["selection-criterion"])[0], (descriptions or codes)[0]
                evidence_id = f"ted:{notice['notice_id']}:{lot_id}:xml-selection-{len(xml_requirements)+1}"
                xml_evidence.append({"evidence_id": evidence_id, "notice_id": notice["notice_id"], "lot_id": lot_id, "field": "selection_criterion", "excerpt": text[:1000], "source_url": notice["xml_url"], "source": "TED eForms XML"})
                xml_requirements.append({"requirement_id": f"{notice['notice_id']}:xml-selection:{len(xml_requirements)+1}", "notice_id": notice["notice_id"], "lot_id": lot_id, "category": _category(code, text), "text": text, "requirement_type": "eligibility", "mandatory": True, "operator": None, "structured_value": None, "unit": None, "stage": "UNKNOWN", "source_field": "eforms:SelectionCriteria", "evidence_id": evidence_id, "confidence": 1.0, "extraction_status": "STRUCTURED"})
            for criterion in (node for node in lot_node.iter() if _local(node.tag) == "SubordinateAwardingCriterion"):
                types = [str(item.text).strip() for item in criterion.iter() if _local(item.tag) == "AwardingCriterionTypeCode" and item.text]
                names = _descendant_text(criterion, {"Name"})
                descriptions = _descendant_text(criterion, {"Description"})
                numbers = [parse_money(item.text) for item in criterion.iter() if _local(item.tag) == "ParameterNumeric" and item.text]
                weight_types = [str(item.text).strip() for item in criterion.iter() if _local(item.tag) == "ParameterCode" and item.text]
                if not types and not names and not descriptions:
                    continue
                name = (names or types or ["Award criterion"])[0]
                evidence_id = f"ted:{notice['notice_id']}:{lot_id}:xml-award-{len(xml_awards)+1}"
                xml_evidence.append({"evidence_id": evidence_id, "notice_id": notice["notice_id"], "lot_id": lot_id, "field": "award_criterion", "excerpt": f"{name}: {(descriptions or [''])[0]}"[:1000], "source_url": notice["xml_url"], "source": "TED eForms XML"})
                xml_awards.append({"criterion_id": f"{notice['notice_id']}:xml-award:{len(xml_awards)+1}", "notice_id": notice["notice_id"], "lot_id": lot_id, "name": name, "type": (types or ["other"])[0], "weight": numbers[0] if numbers else None, "weight_type": weight_types[0] if weight_types else None, "description": (descriptions or [""])[0], "evidence_id": evidence_id})
        prose, security, prose_evidence = extract_requirements(notice["notice_id"], enriched["lots"], notice["notice_url"])
        xml_requirement_text = {(item["lot_id"], item["text"]) for item in xml_requirements}
        existing_structured = [item for item in notice.get("requirements", []) if item.get("source_field") != "description-lot" and (item.get("lot_id"), item.get("text")) not in xml_requirement_text and not (item.get("lot_id") is None and any(item.get("text") == text for _, text in xml_requirement_text))]
        existing_evidence = [item for item in notice.get("evidence", []) if item.get("field") not in {"requirement", "security_finding", "procurement_document"}]
        enriched["description"] = " ".join(str(lot.get("description", "")) for lot in enriched["lots"])[:32_000]
        enriched["requirements"] = [*xml_requirements, *existing_structured, *prose]
        if xml_awards:
            enriched["award_criteria"] = xml_awards
        enriched["security_findings"] = security
        enriched["evidence"] = [*existing_evidence, *xml_evidence, *prose_evidence]
        return enriched


def re_fullmatch_publication(value: str) -> bool:
    left, separator, year = value.partition("-")
    return separator == "-" and 1 <= len(left) <= 8 and left.isdigit() and len(year) == 4 and year.isdigit()
