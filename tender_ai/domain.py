from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal


Decision = Literal["BID", "REVIEW", "NO_BID", "INSUFFICIENT_EVIDENCE"]


@dataclass
class SupplierProfile:
    profile_id: str
    version: int
    company_name: str
    countries_served: list[str]
    capabilities: list[str]
    certifications: list[str]
    annual_turnover: float | None
    employee_capacity: int | None
    references: list[dict[str, Any]]
    languages: list[str]
    min_contract_value: float | None
    max_contract_value: float | None
    geographic_constraints: list[str] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return asdict(self)


DEMO_PROFILE = SupplierProfile(
    profile_id="demo-eu-data-ai", version=1,
    company_name="European Data / AI Consultancy (demo profile)",
    countries_served=["FIN", "EU", "EEA"],
    capabilities=["Python", "SQL", "Power BI", "Machine Learning", "AI / LLM", "Data Engineering", "Azure", "Analytics", "Automation"],
    certifications=[], annual_turnover=750_000, employee_capacity=12,
    references=[{"name": f"Demo analytics project {index}", "value": 150_000} for index in range(1, 5)],
    languages=["English", "Finnish"], min_contract_value=25_000, max_contract_value=2_000_000,
)


def normalize_text(notice: dict[str, Any]) -> str:
    sections = [
        f"Title: {notice.get('title', '')}", f"Buyer: {notice.get('buyer', '')}",
        f"Country: {notice.get('buyer_country', '')}", f"CPV: {' '.join(notice.get('cpv_codes', []))}",
        f"Description: {notice.get('description', '')}",
    ]
    for lot in notice.get("lots", []):
        sections.append(f"Lot {lot.get('lot_id')}: {lot.get('title')} {lot.get('description')}")
    for requirement in notice.get("requirements", []):
        sections.append(f"Requirement {requirement.get('requirement_id')}: {requirement.get('text')}")
    for criterion in notice.get("award_criteria", []):
        sections.append(f"Award criterion: {criterion.get('name')} {criterion.get('description')}")
    return "\n".join(sections)[:32_000]
