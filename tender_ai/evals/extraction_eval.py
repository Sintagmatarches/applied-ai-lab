from __future__ import annotations

from collections import Counter
from typing import Any

from tender_ai.ted import normalize


def _matches(actual: list[Any], expected: list[Any]) -> int:
    left, right = Counter(map(_key, actual)), Counter(map(_key, expected))
    return sum((left & right).values())


def _key(value: Any) -> str:
    if isinstance(value, list):
        return "|".join(map(str, value))
    return str(value)


def _pr(correct: int, actual: int, expected: int) -> dict[str, Any]:
    return {
        "correct": correct,
        "actual": actual,
        "expected": expected,
        "precision": round(correct / actual, 4) if actual else float(expected == 0),
        "recall": round(correct / expected, 4) if expected else float(actual == 0),
    }


def evaluate(corpus: dict[str, Any]) -> dict[str, Any]:
    totals = {
        "categories": [0, 0, 0], "assignments": [0, 0, 0], "weights": [0, 0, 0],
        "mandatory": [0, 0], "lot_ids": [0, 0, 0], "cpv": [0, 0, 0],
    }
    exact = {name: [0, 0] for name in ("lotIdSequence", "lotCount", "buyerCountry", "submissionLanguages", "awardCriterionCount", "deadlineSequence", "missingFieldBehavior")}
    per_notice = []
    for case in corpus["notices"]:
        notice, expected = normalize(case["raw"], case["retrievedAt"]), case["expected"]
        actual_lots = [item["lot_id"] for item in notice["lots"]]
        expected_lots = expected["lotIds"]
        lot_matches = _matches(actual_lots, expected_lots)
        totals["lot_ids"][0] += lot_matches; totals["lot_ids"][1] += len(actual_lots); totals["lot_ids"][2] += len(expected_lots)
        structured = [item for item in notice["requirements"] if item.get("extraction_status") == "STRUCTURED"]
        categories = [item["category"] for item in structured]
        category_matches = _matches(categories, expected["structuredRequirementCategories"])
        totals["categories"][0] += category_matches; totals["categories"][1] += len(categories); totals["categories"][2] += len(expected["structuredRequirementCategories"])
        assignments = [[item["category"], item.get("lot_id")] for item in structured if item.get("lot_id") is not None]
        assignment_matches = _matches(assignments, expected["requirementLotAssignments"])
        totals["assignments"][0] += assignment_matches; totals["assignments"][1] += len(assignments); totals["assignments"][2] += len(expected["requirementLotAssignments"])
        mandatory_correct = sum(bool(item.get("mandatory") is True) for item in structured)
        totals["mandatory"][0] += mandatory_correct; totals["mandatory"][1] += len(structured)
        actual_weights = [item.get("weight") for item in notice["award_criteria"]]
        weight_matches = _matches(actual_weights, expected["awardWeights"])
        totals["weights"][0] += weight_matches; totals["weights"][1] += len(actual_weights); totals["weights"][2] += len(expected["awardWeights"])
        actual_cpv, expected_cpv = list(dict.fromkeys(notice["cpv_codes"])), list(dict.fromkeys(expected["cpvCodes"]))
        cpv_matches = _matches(actual_cpv, expected_cpv)
        totals["cpv"][0] += cpv_matches; totals["cpv"][1] += len(actual_cpv); totals["cpv"][2] += len(expected_cpv)
        actual_deadlines = [item["deadline"] for item in notice["lots"] if item.get("deadline")]
        # TED returns one flattened notice-level submission-language array.
        # normalize() attaches that same source array to every lot, so evaluate
        # it once rather than multiplying duplicate values by the lot count.
        languages = notice["lots"][0]["submission_languages"] if notice["lots"] else []
        checks = {
            "lotIdSequence": actual_lots == expected_lots,
            "lotCount": len(actual_lots) == len(expected_lots),
            "buyerCountry": notice["buyer_country"] == expected["buyerCountry"],
            "submissionLanguages": languages == expected["submissionLanguages"],
            "awardCriterionCount": len(notice["award_criteria"]) == expected["awardCriterionCount"],
            "deadlineSequence": actual_deadlines == expected["deadlines"],
        }
        if not expected["deadlines"]:
            checks["missingFieldBehavior"] = all(item.get("deadline") is None for item in notice["lots"])
        for name, passed in checks.items():
            exact[name][0] += int(passed); exact[name][1] += 1
        failures = [name for name, passed in checks.items() if not passed]
        if weight_matches != max(len(actual_weights), len(expected["awardWeights"])):
            failures.append("awardWeights")
        if category_matches != max(len(categories), len(expected["structuredRequirementCategories"])):
            failures.append("requirementCategories")
        if assignment_matches != max(len(assignments), len(expected["requirementLotAssignments"])):
            failures.append("requirementLotAssignments")
        evaluated_fields = len(checks) + 3
        per_notice.append({"publication": case["publicationNumber"], "passedFields": evaluated_fields - len(failures), "evaluatedFields": evaluated_fields, "failures": failures})
    return {
        "evidenceClass": "recorded-real source-derived field evaluation",
        "noticeCount": len(corpus["notices"]),
        "fieldExactMatch": {name: {"passed": values[0], "cases": values[1], "value": round(values[0] / values[1], 4)} for name, values in exact.items()},
        "lotIdItems": _pr(*totals["lot_ids"]),
        "requirementExtraction": _pr(*totals["categories"]),
        "requirementLotAssignment": _pr(*totals["assignments"]),
        "mandatoryBooleanCoverage": {"present": totals["mandatory"][0], "cases": totals["mandatory"][1], "value": round(totals["mandatory"][0] / totals["mandatory"][1], 4) if totals["mandatory"][1] else None},
        "awardWeightExtraction": _pr(*totals["weights"]),
        "cpvExtraction": _pr(*totals["cpv"]),
        "perNotice": per_notice,
        "limitations": ["Expected values are independently represented source-derived fields, not outputs generated by normalize().", "The mandatory boolean is reported as field coverage, not classification accuracy: this corpus contains no independently represented optional selection criterion."],
    }
