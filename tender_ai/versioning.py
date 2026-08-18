from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


MATERIAL_FIELDS = {"submission_deadline", "estimated_value", "lots", "requirements", "award_criteria", "buyer", "description", "place_of_performance"}


def structured_diff(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    changes = []
    for field in sorted(MATERIAL_FIELDS | {"title", "procedure_type", "cpv_codes"}):
        if old.get(field) != new.get(field):
            changes.append({
                "field": field, "old_value": old.get(field), "new_value": new.get(field),
                "materiality": "MATERIAL" if field in MATERIAL_FIELDS else "INFORMATIONAL",
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "evidence": new.get("notice_url"),
            })
    return changes
