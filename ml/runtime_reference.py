"""Reference Python scorer for the portable production model artifact.

The web application uses TypeScript for inference. This module independently
rebuilds the same features and score in Python so both runtimes can be compared.
"""

from __future__ import annotations

from bisect import bisect_left
from datetime import datetime
import math
from typing import Any


def _epoch_day(timestamp: str, seconds_per_day: int) -> int:
    """Convert a timezone-aware timestamp to its UTC day number."""

    value = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("purchase timestamp must include a timezone")
    return math.floor(value.timestamp() / seconds_per_day)


def _history_totals(
    records: list[list[int]] | None,
    day: int,
    window_days: int | None = None,
) -> tuple[float, float, int]:
    """Sum history records strictly before the order day."""

    if not records:
        return 0.0, 0.0, day
    days = [record[0] for record in records]
    end = bisect_left(days, day)
    start = 0 if window_days is None else bisect_left(days, day - window_days)
    selected = records[start:end]
    count = sum(record[1] for record in selected)
    late = sum(record[2] for record in selected if len(record) > 2)
    first_day = records[0][0] if end else day
    return float(count), float(late), int(first_day)


def _smoothed_rate(late: float, count: float, prior: float, strength: float) -> float:
    """Blend a group delay rate with the wider market rate."""

    return (late + strength * prior) / (count + strength)


def _season(month: int) -> str:
    """Return the Southern Hemisphere season for a month."""

    if month in (12, 1, 2):
        return "summer"
    if month in (3, 4, 5):
        return "autumn"
    if month in (6, 7, 8):
        return "winter"
    return "spring"


def raw_features(artifact: dict, input_data: dict) -> dict[str, float | str]:
    """Recreate every raw model feature for one submitted order."""

    timestamp = datetime.fromisoformat(
        input_data["purchase_timestamp"].replace("Z", "+00:00")
    )
    if timestamp.tzinfo is None:
        raise ValueError("purchase timestamp must include a timezone")
    history = artifact["history"]
    constants = history["constants"]
    day = _epoch_day(input_data["purchase_timestamp"], constants["seconds_per_day"])
    global_count, global_late, _ = _history_totals(history["global_outcomes"], day)
    global_prior = (
        global_late / global_count if global_count else constants["default_late_prior"]
    )
    route = f"{input_data['seller_state']} → {input_data['customer_state']}"
    groups = history["groups"]
    seller = groups["seller_state"].get(input_data["seller_state"], {})
    route_history = groups["route"].get(route, {})
    category = groups["primary_category"].get(input_data["primary_category"], {})

    # Order histories measure activity. Outcome histories contain only orders
    # whose delivery result was already known on the prediction day.
    seller_orders = seller.get("orders", [])
    seller_outcomes = seller.get("outcomes", [])
    route_orders = route_history.get("orders", [])
    route_outcomes = route_history.get("outcomes", [])
    category_outcomes = category.get("outcomes", [])
    seller_count, _, seller_first = _history_totals(seller_orders, day)
    seller_outcome_count, seller_late, _ = _history_totals(seller_outcomes, day)
    seller30_count, seller30_late, _ = _history_totals(seller_outcomes, day, 30)
    seller90_count, seller90_late, _ = _history_totals(seller_outcomes, day, 90)
    route_outcome_count, route_late, _ = _history_totals(route_outcomes, day)
    route7_count, _, _ = _history_totals(route_orders, day, 7)
    route30_count, _, _ = _history_totals(route_orders, day, 30)
    route30_outcomes, route30_late, _ = _history_totals(route_outcomes, day, 30)
    route90_outcomes, route90_late, _ = _history_totals(route_outcomes, day, 90)
    category_count, category_late, _ = _history_totals(category_outcomes, day)
    distance_units = max(float(input_data["distance_km"]) / 500.0, 1.0)

    return {
        "purchase_year": timestamp.year,
        "purchase_month": timestamp.month,
        "purchase_day_of_week": timestamp.isoweekday(),
        "purchase_hour": timestamp.hour,
        "promised_delivery_days": input_data["promised_delivery_days"],
        "same_state": int(input_data["seller_state"] == input_data["customer_state"]),
        "distance_km": input_data["distance_km"],
        "item_count": input_data["item_count"],
        "total_item_value": input_data["total_item_value"],
        "total_freight_value": input_data["total_freight_value"],
        "total_weight_g": input_data["total_weight_g"],
        "total_volume_cm3": input_data["total_volume_cm3"],
        "payment_installments": input_data["payment_installments"],
        "prior_global_late_rate": global_prior,
        "seller_state_prior_late_rate": _smoothed_rate(
            seller_late,
            seller_outcome_count,
            global_prior,
            constants["prior_strength"],
        ),
        "seller_state_prior_order_count_log": math.log1p(seller_count),
        "seller_state_late_rate_30d": _smoothed_rate(
            seller30_late,
            seller30_count,
            global_prior,
            constants["window_prior_strength"],
        ),
        "seller_state_late_rate_90d": _smoothed_rate(
            seller90_late,
            seller90_count,
            global_prior,
            constants["window_prior_strength"],
        ),
        "seller_state_experience_days_log": math.log1p(max(day - seller_first, 0)),
        "route_prior_late_rate": _smoothed_rate(
            route_late,
            route_outcome_count,
            global_prior,
            constants["prior_strength"],
        ),
        "route_order_count_7d_log": math.log1p(route7_count),
        "route_order_count_30d_log": math.log1p(route30_count),
        "route_late_rate_30d": _smoothed_rate(
            route30_late,
            route30_outcomes,
            global_prior,
            constants["window_prior_strength"],
        ),
        "route_late_rate_90d": _smoothed_rate(
            route90_late,
            route90_outcomes,
            global_prior,
            constants["window_prior_strength"],
        ),
        "category_prior_late_rate": _smoothed_rate(
            category_late,
            category_count,
            global_prior,
            constants["prior_strength"],
        ),
        "freight_item_ratio": min(
            float(input_data["total_freight_value"])
            / max(float(input_data["total_item_value"]), 1.0),
            10.0,
        ),
        "promised_days_per_500km": float(input_data["promised_delivery_days"])
        / distance_units,
        "seller_state": input_data["seller_state"],
        "customer_state": input_data["customer_state"],
        "route": route,
        "primary_category": input_data["primary_category"],
        "primary_payment_type": input_data["primary_payment_type"],
        "season": _season(timestamp.month),
    }


def prepare_feature_vector(artifact: dict, input_data: dict) -> list[float]:
    """Apply training-time imputation, scaling, and one-hot encoding."""

    vector = [0.0] * artifact["feature_count"]
    features = raw_features(artifact, input_data)
    for name, transform in artifact["numeric"].items():
        raw_value = features[name]
        value = float(raw_value) if raw_value is not None else transform["median"]
        if not math.isfinite(value):
            value = transform["median"]
        vector[transform["index"]] = (value - transform["mean"]) / transform["scale"]
    for name, transform in artifact["categorical"].items():
        value = str(features.get(name, transform["default"]))
        index = transform["indices"].get(value)
        if index is not None:
            vector[index] = 1.0
    return vector


def _sigmoid(value: float) -> float:
    """Convert a linear score to a probability without numeric overflow."""

    if value >= 0:
        inverse = math.exp(-value)
        return 1 / (1 + inverse)
    exponential = math.exp(value)
    return exponential / (1 + exponential)


def _calibrated_probability(artifact: dict, raw_score: float) -> float:
    """Apply the calibration method selected on the calibration period."""

    calibration = artifact["calibration"]
    if calibration["type"] == "platt":
        return _sigmoid(calibration["slope"] * raw_score + calibration["intercept"])
    if calibration["type"] == "isotonic":
        x = calibration["x"]
        y = calibration["y"]
        if raw_score <= x[0]:
            return y[0]
        if raw_score >= x[-1]:
            return y[-1]
        upper = bisect_left(x, raw_score)
        lower = upper - 1
        width = x[upper] - x[lower]
        return (
            y[upper]
            if width == 0
            else y[lower] + (raw_score - x[lower]) / width * (y[upper] - y[lower])
        )
    return _sigmoid(raw_score)


def probability_to_risk_score(artifact: dict, probability: float) -> float:
    """Convert probability to a percentile-style score from 0 to 100."""

    quantiles = artifact["risk_score_probability_quantiles"]
    if probability <= quantiles[0]:
        return 0.0
    if probability >= quantiles[-1]:
        return 100.0
    upper = bisect_left(quantiles, probability)
    lower = upper - 1
    width = quantiles[upper] - quantiles[lower]
    fraction = 0.0 if width == 0 else (probability - quantiles[lower]) / width
    return min(100.0, max(0.0, lower + fraction))


def score(artifact: dict, input_data: dict) -> dict[str, Any]:
    """Calculate the feature vector, linear score, probability, and risk rank."""

    vector = prepare_feature_vector(artifact, input_data)
    raw_score = artifact["linear"]["intercept"] + sum(
        coefficient * value
        for coefficient, value in zip(
            artifact["linear"]["coefficients"], vector, strict=True
        )
    )
    probability = _calibrated_probability(artifact, raw_score)
    return {
        "feature_vector": vector,
        "raw_score": raw_score,
        "probability": probability,
        "risk_score": probability_to_risk_score(artifact, probability),
    }
