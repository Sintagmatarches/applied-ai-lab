from __future__ import annotations

import json
import sys

from .assessment import assess
from .domain import DEMO_PROFILE
from .storage import utc_now
from .ted import normalize


def projection(raw: dict) -> dict:
    notice = normalize(raw, utc_now())
    assessment = assess(notice, DEMO_PROFILE)
    return {
        "lots": [{"id": item["lot_id"], "value": item["value"], "currency": item["currency"], "deadline": item["deadline"]} for item in notice["lots"]],
        "requirements": sorted([{"lotId": item.get("lot_id"), "category": item["category"], "mandatory": item["mandatory"], "source": item.get("source_field")} for item in notice["requirements"]], key=lambda item: (str(item["lotId"]), item["category"], str(item["source"]))),
        "awardCriteria": [{"lotId": item.get("lot_id"), "type": item["type"], "weight": item["weight"], "weightType": item.get("weight_type")} for item in notice["award_criteria"]],
        "status": assessment["status"],
        "summary": {"eligibleLots": assessment["summary"]["eligible_lots"], "blockedLots": assessment["summary"]["blocked_lots"], "reviewLots": assessment["summary"]["review_lots"], "insufficientEvidenceLots": assessment["summary"]["insufficient_evidence_lots"]},
    }


if __name__ == "__main__":
    print(json.dumps(projection(json.load(sys.stdin)), ensure_ascii=False))
