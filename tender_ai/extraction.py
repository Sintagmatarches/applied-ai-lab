from __future__ import annotations

import re
from typing import Any


INJECTION = re.compile(
    r"ignore all previous instructions|mark this opportunity as bid|reveal the system prompt|call another tool|fake:\d+",
    re.I,
)


def extract_requirements(notice_id: str, lots: list[dict[str, Any]], notice_url: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    requirements: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    def add(lot_id: str, category: str, text: str, value: Any = None, unit: str | None = None, mandatory: bool = True, confidence: float = .92) -> None:
        evidence_id = f"ted:{notice_id}:{lot_id}:requirement-{len(requirements) + 1}"
        evidence.append({"evidence_id": evidence_id, "notice_id": notice_id, "lot_id": lot_id, "field": "requirement", "excerpt": text[:1000], "source_url": notice_url, "source": "TED"})
        requirements.append({
            "requirement_id": f"{notice_id}:req:{len(requirements) + 1}", "notice_id": notice_id,
            "lot_id": lot_id, "category": category, "text": text, "requirement_type": "eligibility",
            "mandatory": mandatory, "operator": ">=" if isinstance(value, (int, float)) else "contains" if value is not None else None,
            "structured_value": value, "unit": unit, "evidence_id": evidence_id,
            "confidence": confidence, "extraction_status": "STRUCTURED" if value is not None else "UNSTRUCTURED",
        })

    for lot in lots:
        text = str(lot.get("description", ""))
        lot_id = str(lot.get("lot_id", "NOTICE"))
        for match in re.finditer(r"(?:minimum|at least|vähintään)[^.!?]{0,60}(?:annual )?(?:turnover|liikevaihto)[^0-9]{0,20}([0-9][0-9 .,'’]*)\s*(EUR|€)", text, re.I):
            add(lot_id, "turnover", match.group(0), float(re.sub(r"[^0-9]", "", match.group(1))), "EUR")
        for match in re.finditer(r"(?:minimum|at least|vähintään)[^.!?]{0,50}([0-9]+)\s+(?:references?|reference projects?|referenssi)", text, re.I):
            add(lot_id, "references", match.group(0), int(match.group(1)), "count")
        for match in re.finditer(r"\b(ISO\s?\d{4,6}(?::\d{4})?)\b", text, re.I):
            add(lot_id, "certification", match.group(0), re.sub(r"ISO\s?", "ISO ", match.group(1).upper()))
        for match in re.finditer(r"(?:required|must|shall|vähintään)[^.!?]{0,45}\b(English|Finnish|Swedish|French|German)\b", text, re.I):
            add(lot_id, "language", match.group(0), match.group(1))
        if INJECTION.search(text):
            add(lot_id, "security", "Untrusted document instruction detected and quarantined.", mandatory=False, confidence=1.0)
        sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
        for sentence in sentences:
            cleaned = " ".join(sentence.split())
            if not 25 <= len(cleaned) <= 700 or not re.search(r"\b(required|requires|shall|must|minimum requirement|edellytetään|tulee olla|vähintään)\b", cleaned, re.I):
                continue
            if any(item["text"] in cleaned or cleaned in item["text"] for item in requirements if item.get("lot_id") == lot_id):
                continue
            category = "consortium" if re.search(r"consortium|group of economic operators|subcontract", cleaned, re.I) else "staff" if re.search(r"staff|personnel|qualification", cleaned, re.I) else "geography" if re.search(r"country|member state|geographic", cleaned, re.I) else "technical"
            add(lot_id, category, cleaned, mandatory=True, confidence=.7)
            if sum(1 for item in requirements if item.get("lot_id") == lot_id) >= 20:
                break
    return requirements, evidence


def parse_money(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except ValueError:
        return None
