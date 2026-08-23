from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "rail/contracts/operational_policy.json"
POLICY = json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def parse_utc(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Freshness timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def wilson_interval(successes: int, observations: int) -> dict[str, float] | None:
    if observations <= 0:
        return None
    if successes < 0 or successes > observations:
        raise ValueError("Wilson successes must be between zero and observations")
    z = float(POLICY["sampleSupport"]["wilsonZ"])
    proportion = successes / observations
    denominator = 1 + z * z / observations
    centre = (proportion + z * z / (2 * observations)) / denominator
    half_width = z * math.sqrt(
        proportion * (1 - proportion) / observations + z * z / (4 * observations * observations)
    ) / denominator
    return {"lower": max(0.0, centre - half_width), "upper": min(1.0, centre + half_width)}


def sample_support(mode: str, observed: int, measured: int, *, has_service: bool = True) -> dict[str, Any]:
    config = POLICY["sampleSupport"]
    mode_policy = config["modes"][mode]
    coverage = measured / observed if observed else None
    required = int(mode_policy["minimumMeasured"])
    if not has_service or observed == 0:
        status = "not-applicable"
    elif measured >= required and coverage is not None and coverage >= config["minimumMeasurementCoverage"]:
        status = "sufficient"
    else:
        status = "low-sample"
    return {
        "status": status,
        "observedCount": observed,
        "measuredCount": measured,
        "measurementCoverage": coverage,
        "requiredMinimumMeasured": required,
        "minimumMeasurementCoverage": config["minimumMeasurementCoverage"],
        "policyVersion": config["version"],
        "rationale": mode_policy["rationale"],
    }


def coverage_contract(expected: Iterable[str], available: Iterable[str], failed: Iterable[str] = ()) -> dict[str, Any]:
    expected_values = list(expected)
    available_values = list(available)
    failed_values = list(failed)
    expected_dates = sorted(set(expected_values))
    available_dates = sorted(set(available_values))
    failed_dates = sorted(set(failed_values))
    duplicate_count = len(available_values) - len(available_dates)
    missing_dates = sorted(set(expected_dates) - set(available_dates))
    if not available_dates:
        status = "unavailable"
    elif missing_dates or failed_dates or duplicate_count:
        status = "partial"
    else:
        status = "complete"
    return {
        "status": status,
        "expectedDates": expected_dates,
        "availableDates": available_dates,
        "missingDates": missing_dates,
        "failedDates": failed_dates,
        "duplicatePartitions": duplicate_count,
        "coverageRatio": len(set(expected_dates) & set(available_dates)) / len(expected_dates) if expected_dates else 1.0,
    }


def freshness_contract(
    mode: str,
    *,
    now: str | datetime,
    source_retrieved_at: str | datetime | None,
    validated_at: str | datetime | None,
    gold_published_at: str | datetime | None,
    coverage_status: str = "complete",
) -> dict[str, Any]:
    config = POLICY["freshness"]
    mode_policy = config["modes"][mode]
    now_value = parse_utc(now)
    source = parse_utc(source_retrieved_at)
    validated = parse_utc(validated_at)
    gold = parse_utc(gold_published_at)
    assert now_value is not None
    if mode == "historical":
        return {
            "state": "not-applicable",
            "evaluatedAt": iso_utc(now_value),
            "ageMinutes": None,
            "basis": mode_policy["basis"],
            "policyVersion": config["version"],
            "reason": mode_policy["rationale"],
            "sourceRetrievedAt": iso_utc(source) if source else None,
            "validatedAt": iso_utc(validated) if validated else None,
            "goldPublishedAt": iso_utc(gold) if gold else None,
        }
    timestamps = [value for value in (source, validated, gold) if value is not None]
    if source and validated and source > validated or validated and gold and validated > gold:
        state, reason, age = "stale", "Freshness timestamps violate source ≤ validation ≤ Gold ordering.", None
    elif coverage_status != "complete":
        state, reason, age = "stale", "The requested governed window is incomplete.", None
    else:
        basis_value = {"sourceRetrievedAt": source, "validatedAt": validated, "goldPublishedAt": gold}[mode_policy["basis"]]
        if basis_value is None:
            state, reason, age = "stale", f"Required {mode_policy['basis']} evidence is unavailable.", None
        else:
            age = max(0.0, (now_value - basis_value).total_seconds() / 60)
            if age <= mode_policy["warningAfterMinutes"]:
                state, reason = "fresh", "The governed publication is within its operating target."
            elif age <= mode_policy["staleAfterMinutes"]:
                state, reason = "warning", "The publication missed its normal target but remains inside the stale boundary."
            else:
                state, reason = "stale", "The publication is older than the allowed stale boundary."
    return {
        "state": state,
        "evaluatedAt": iso_utc(now_value),
        "ageMinutes": round(age, 1) if age is not None else None,
        "basis": mode_policy["basis"],
        "policyVersion": config["version"],
        "reason": reason,
        "sourceRetrievedAt": iso_utc(source) if source else None,
        "validatedAt": iso_utc(validated) if validated else None,
        "goldPublishedAt": iso_utc(gold) if gold else None,
    }
