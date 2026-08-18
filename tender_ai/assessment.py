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


def assess(notice: dict[str, Any], profile: SupplierProfile) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for requirement in notice.get("requirements", []):
        category = requirement.get("category")
        value = requirement.get("structured_value")
        outcome = "UNKNOWN"
        reason = "The requirement is not structured enough for deterministic comparison."
        if category == "turnover" and isinstance(value, (int, float)):
            outcome = "UNKNOWN" if profile.annual_turnover is None else "PASS" if profile.annual_turnover >= value else "FAIL"
            reason = "Supplier turnover is unknown." if profile.annual_turnover is None else f"Supplier turnover {profile.annual_turnover:.0f} EUR {'meets' if outcome == 'PASS' else 'is below'} {value:.0f} EUR."
        elif category == "references" and isinstance(value, (int, float)):
            outcome = "PASS" if len(profile.references) >= value else "FAIL"
            reason = f"Supplier has {len(profile.references)} references; minimum is {int(value)}."
        elif category == "certification" and isinstance(value, str):
            outcome = "PASS" if value.lower() in {item.lower() for item in profile.certifications} else "FAIL"
            reason = f"{value} {'is present' if outcome == 'PASS' else 'is missing'}."
        elif category == "language" and isinstance(value, str):
            outcome = "PASS" if value.lower() in {item.lower() for item in profile.languages} else "FAIL"
            reason = f"{value} {'is covered' if outcome == 'PASS' else 'is not covered'}."
        checks.append({"requirement_id": requirement["requirement_id"], "outcome": outcome, "reason": reason, "evidence_id": requirement["evidence_id"]})

    text = f"{notice.get('title', '')} {notice.get('description', '')}".lower()
    matched = sum(any(term in text for term in CAPABILITY_TERMS.get(cap.lower(), [cap.lower()])) for cap in profile.capabilities)
    capability = round(70 * matched / max(1, len(profile.capabilities)))
    geography = 15 if notice.get("buyer_country") in profile.countries_served or {"EU", "EEA"} & set(profile.countries_served) else 0
    value = notice.get("estimated_value")
    contract = 15 if value is None or ((profile.min_contract_value or 0) <= value <= (profile.max_contract_value or float("inf"))) else 0
    blocking = [check for check in checks if check["outcome"] == "FAIL"]
    uncertain = [check for check in checks if check["outcome"] == "UNKNOWN"]
    status = "NO_BID" if blocking else "INSUFFICIENT_EVIDENCE" if not checks else "REVIEW" if uncertain else "BID"
    return {
        "status": status, "strategic_fit": capability + geography + contract, "checks": checks,
        "blocking_requirements": blocking, "satisfied_requirements": [c for c in checks if c["outcome"] == "PASS"],
        "uncertain_requirements": uncertain, "assessed_at": datetime.now(timezone.utc).isoformat(),
        "supplier_profile_id": profile.profile_id, "supplier_profile_version": profile.version,
    }
