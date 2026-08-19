from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .domain import SupplierProfile


CAPABILITY_TERMS = {
    "python": ["python"], "sql": ["sql", "database"], "power bi": ["power bi", "business intelligence"],
    "machine learning": ["machine learning", "artificial intelligence"], "ai / llm": ["llm", "artificial intelligence", "generative ai"],
    "data engineering": ["data engineering", "data platform", "etl"], "azure": ["azure", "cloud"],
    "analytics": ["analytics", "data analysis"], "automation": ["automation"],
}


def _check(requirement: dict[str, Any], profile: SupplierProfile, lot_id: str) -> dict[str, Any]:
    category, value = requirement.get("category"), requirement.get("structured_value")
    outcome, reason = "UNKNOWN", "The requirement is not structured enough for deterministic comparison."
    if requirement.get("stage") == "NOT_REQUIRED":
        outcome, reason = "NOT_APPLICABLE", "TED marks this information as not required at this stage."
    elif category == "turnover" and isinstance(value, (int, float)):
        outcome = "UNKNOWN" if profile.annual_turnover is None else "PASS" if profile.annual_turnover >= value else "FAIL"
        reason = "Supplier turnover is unknown." if profile.annual_turnover is None else f"Supplier turnover {profile.annual_turnover:.0f} EUR {'meets' if outcome == 'PASS' else 'is below'} {value:.0f} EUR."
    elif category == "references" and isinstance(value, (int, float)):
        outcome = "PASS" if len(profile.references) >= value else "FAIL"
        reason = f"Supplier has {len(profile.references)} references; minimum is {int(value)}."
    elif category == "certification" and isinstance(value, str):
        outcome = "PASS" if value.lower() in {item.lower() for item in profile.certifications} else "FAIL"
        reason = f"{value} {'is present' if outcome == 'PASS' else 'is missing'}."
    elif category == "language" and isinstance(value, (str, list)):
        accepted = [str(item).lower() for item in (value if isinstance(value, list) else [value])]
        codes = {"english": "eng", "finnish": "fin", "swedish": "swe", "french": "fra", "german": "deu"}
        supplied = [candidate for item in profile.languages for candidate in (item.lower(), codes.get(item.lower(), item.lower()))]
        outcome = "PASS" if any(item in accepted for item in supplied) else "FAIL"
        reason = f"Supplier {'covers' if outcome == 'PASS' else 'does not cover'} an accepted language ({', '.join(accepted)})."
    return {"requirement_id": requirement["requirement_id"], "lot_id": lot_id, "mandatory": bool(requirement.get("mandatory")), "outcome": outcome, "reason": reason, "evidence_id": requirement["evidence_id"]}


def _fit(lot: dict[str, Any], profile: SupplierProfile) -> dict[str, Any]:
    text = f"{lot.get('title', '')} {lot.get('description', '')}".lower()
    matched = [cap for cap in profile.capabilities if any(term in text for term in CAPABILITY_TERMS.get(cap.lower(), [cap.lower()]))]
    capability = min(50, len(matched) * 10)
    geography = 20 if set(lot.get("place_of_performance", [])) & set(profile.countries_served) else 0
    value = lot.get("value")
    contract = 20 if value is not None and (profile.min_contract_value or 0) <= value <= (profile.max_contract_value or float("inf")) else 0
    deadline = lot.get("deadline")
    deadline_score = 10 if deadline and deadline[:10] >= datetime.now(timezone.utc).date().isoformat() else 0
    components = [
        {"name": "capability", "score": capability, "maximum": 50, "evidence": f"Matched: {', '.join(matched)}." if matched else "No declared capability matched the lot text."},
        {"name": "geography", "score": geography, "maximum": 20, "evidence": "Exact place-of-performance country is covered." if geography else "No exact country match; EU/EEA alone is not treated as evidence."},
        {"name": "contract_value", "score": contract, "maximum": 20, "evidence": "Lot value is missing; no positive score awarded." if value is None else "Lot value is inside the supplier range." if contract else "Lot value is outside the supplier range."},
        {"name": "deadline", "score": deadline_score, "maximum": 10, "evidence": "Lot deadline is missing; no positive score awarded." if not deadline else "Lot deadline is still open." if deadline_score else "Lot deadline has passed."},
    ]
    score = sum(item["score"] for item in components)
    return {"score": score, "label": "HIGH" if score >= 70 else "MEDIUM" if score >= 40 else "LOW", "components": components}


def assess(notice: dict[str, Any], profile: SupplierProfile) -> dict[str, Any]:
    lot_assessments: list[dict[str, Any]] = []
    for lot in notice.get("lots", []):
        lot_id = str(lot.get("lot_id"))
        requirements = [item for item in notice.get("requirements", []) if item.get("lot_id") in (None, lot_id)]
        checks = [_check(item, profile, lot_id) for item in requirements]
        blocking = [item for item in checks if item["mandatory"] and item["outcome"] == "FAIL"]
        uncertain = [item for item in checks if item["mandatory"] and item["outcome"] == "UNKNOWN"]
        mandatory = [item for item in checks if item["mandatory"] and item["outcome"] != "NOT_APPLICABLE"]
        status = "NO_BID" if blocking else "INSUFFICIENT_EVIDENCE" if not mandatory else "REVIEW" if uncertain else "BID"
        lot_assessments.append({"lot_id": lot_id, "status": status, "heuristic_fit": _fit(lot, profile), "checks": checks, "blocking_requirements": blocking, "satisfied_requirements": [item for item in checks if item["outcome"] == "PASS"], "uncertain_requirements": uncertain})

    summary = {
        "eligible_lots": [item["lot_id"] for item in lot_assessments if item["status"] == "BID"],
        "blocked_lots": [item["lot_id"] for item in lot_assessments if item["status"] == "NO_BID"],
        "review_lots": [item["lot_id"] for item in lot_assessments if item["status"] == "REVIEW"],
        "insufficient_evidence_lots": [item["lot_id"] for item in lot_assessments if item["status"] == "INSUFFICIENT_EVIDENCE"],
    }
    status = "BID" if summary["eligible_lots"] else "REVIEW" if summary["review_lots"] else "INSUFFICIENT_EVIDENCE" if summary["insufficient_evidence_lots"] else "NO_BID"
    fit = max([item["heuristic_fit"]["score"] for item in lot_assessments] or [0])
    checks = [check for item in lot_assessments for check in item["checks"]]
    return {
        "status": status, "strategic_fit": fit, "heuristic_fit_label": "HIGH" if fit >= 70 else "MEDIUM" if fit >= 40 else "LOW",
        "lot_assessments": lot_assessments, "summary": summary, "checks": checks,
        "blocking_requirements": [check for item in lot_assessments for check in item["blocking_requirements"]],
        "satisfied_requirements": [check for check in checks if check["outcome"] == "PASS"],
        "uncertain_requirements": [check for item in lot_assessments for check in item["uncertain_requirements"]],
        "assessed_at": datetime.now(timezone.utc).isoformat(), "supplier_profile_id": profile.profile_id, "supplier_profile_version": profile.version,
    }
