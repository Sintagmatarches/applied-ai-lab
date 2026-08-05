from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ml.common import LABEL_AVAILABLE_TIMESTAMP, TARGET, TIMESTAMP

SECONDS_PER_DAY = 86_400
DEFAULT_LATE_PRIOR = 0.05
PRIOR_STRENGTH = 20.0
WINDOW_PRIOR_STRENGTH = 10.0


@dataclass(frozen=True)
class DailyHistory:
    days: np.ndarray
    counts: np.ndarray
    late: np.ndarray


def _days(frame: pd.DataFrame, column: str) -> np.ndarray:
    return (
        frame[column].astype("int64").to_numpy() // 1_000_000_000 // SECONDS_PER_DAY
    ).astype(np.int32)


def _prefix_lookup(
    history: DailyHistory, query_days: np.ndarray, window: int | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    end = np.searchsorted(history.days, query_days, side="left")
    count_prefix = np.concatenate(([0.0], np.cumsum(history.counts)))
    late_prefix = np.concatenate(([0.0], np.cumsum(history.late)))
    if window is None:
        start = np.zeros_like(end)
    else:
        start = np.searchsorted(history.days, query_days - window, side="left")
    first_day = np.where(end > 0, history.days[0], query_days)
    return (
        count_prefix[end] - count_prefix[start],
        late_prefix[end] - late_prefix[start],
        first_day,
    )


def _daily_histories(
    frame: pd.DataFrame,
    key: str,
    event_days: np.ndarray,
    include_late: bool,
) -> dict[str, DailyHistory]:
    source = pd.DataFrame(
        {
            "key": frame[key].fillna("__missing__").astype(str),
            "day": event_days,
            "late": frame[TARGET].to_numpy() if include_late else 0,
        }
    )
    daily = (
        source.groupby(["key", "day"], sort=True, observed=True)["late"]
        .agg(["size", "sum"])
        .reset_index()
    )
    return {
        str(value): DailyHistory(
            days=group["day"].to_numpy(dtype=np.int32),
            counts=group["size"].to_numpy(dtype=float),
            late=group["sum"].to_numpy(dtype=float),
        )
        for value, group in daily.groupby("key", sort=False, observed=True)
    }


def _global_outcome_history(
    frame: pd.DataFrame, availability_days: np.ndarray
) -> DailyHistory:
    daily = (
        pd.DataFrame({"day": availability_days, "late": frame[TARGET].to_numpy()})
        .groupby("day", sort=True)["late"]
        .agg(["size", "sum"])
        .reset_index()
    )
    return DailyHistory(
        days=daily["day"].to_numpy(dtype=np.int32),
        counts=daily["size"].to_numpy(dtype=float),
        late=daily["sum"].to_numpy(dtype=float),
    )


def _smoothed_rate(
    late: np.ndarray,
    count: np.ndarray,
    prior: np.ndarray,
    strength: float,
) -> np.ndarray:
    return (late + strength * prior) / (count + strength)


def _group_features(
    frame: pd.DataFrame,
    key: str,
    prefix: str,
    order_days: np.ndarray,
    availability_days: np.ndarray,
    global_prior: np.ndarray,
    order_windows: tuple[int, ...],
    outcome_windows: tuple[int, ...],
) -> dict[str, np.ndarray]:
    values = frame[key].fillna("__missing__").astype(str).to_numpy()
    order_histories = _daily_histories(frame, key, order_days, include_late=False)
    outcome_histories = _daily_histories(
        frame, key, availability_days, include_late=True
    )
    prior_order_count = np.zeros(len(frame), dtype=float)
    prior_outcome_count = np.zeros(len(frame), dtype=float)
    prior_late = np.zeros(len(frame), dtype=float)
    first_order_day = order_days.copy()
    order_window_counts = {
        window: np.zeros(len(frame), dtype=float) for window in order_windows
    }
    outcome_window_counts = {
        window: np.zeros(len(frame), dtype=float) for window in outcome_windows
    }
    outcome_window_late = {
        window: np.zeros(len(frame), dtype=float) for window in outcome_windows
    }

    for value in np.unique(values):
        rows = np.flatnonzero(values == value)
        query_days = order_days[rows]
        order_history = order_histories.get(value)
        if order_history is not None:
            prior_order_count[rows], _, first_order_day[rows] = _prefix_lookup(
                order_history, query_days
            )
            for window in order_windows:
                order_window_counts[window][rows], _, _ = _prefix_lookup(
                    order_history, query_days, window
                )
        outcome_history = outcome_histories.get(value)
        if outcome_history is not None:
            prior_outcome_count[rows], prior_late[rows], _ = _prefix_lookup(
                outcome_history, query_days
            )
            for window in outcome_windows:
                (
                    outcome_window_counts[window][rows],
                    outcome_window_late[window][rows],
                    _,
                ) = _prefix_lookup(outcome_history, query_days, window)

    output = {
        f"{prefix}_prior_late_rate": _smoothed_rate(
            prior_late,
            prior_outcome_count,
            global_prior,
            PRIOR_STRENGTH,
        ),
        f"{prefix}_prior_order_count_log": np.log1p(prior_order_count),
        f"{prefix}_experience_days_log": np.log1p(
            np.maximum(order_days - first_order_day, 0)
        ),
    }
    for window in order_windows:
        output[f"{prefix}_order_count_{window}d_log"] = np.log1p(
            order_window_counts[window]
        )
    for window in outcome_windows:
        output[f"{prefix}_late_rate_{window}d"] = _smoothed_rate(
            outcome_window_late[window],
            outcome_window_counts[window],
            global_prior,
            WINDOW_PRIOR_STRENGTH,
        )
    return output


def season_from_month(month: pd.Series | np.ndarray) -> np.ndarray:
    values = np.asarray(month, dtype=int)
    return np.select(
        [
            np.isin(values, [12, 1, 2]),
            np.isin(values, [3, 4, 5]),
            np.isin(values, [6, 7, 8]),
        ],
        ["summer", "autumn", "winter"],
        default="spring",
    )


def add_temporal_features(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    order_days = _days(enriched, TIMESTAMP)
    availability_days = _days(enriched, LABEL_AVAILABLE_TIMESTAMP)
    global_history = _global_outcome_history(enriched, availability_days)
    global_count, global_late, _ = _prefix_lookup(global_history, order_days)
    global_prior = np.divide(
        global_late,
        global_count,
        out=np.full(len(enriched), DEFAULT_LATE_PRIOR, dtype=float),
        where=global_count > 0,
    )
    enriched["prior_global_late_rate"] = global_prior

    seller = _group_features(
        enriched,
        key="seller_state",
        prefix="seller_state",
        order_days=order_days,
        availability_days=availability_days,
        global_prior=global_prior,
        order_windows=(),
        outcome_windows=(30, 90),
    )
    route = _group_features(
        enriched,
        key="route",
        prefix="route",
        order_days=order_days,
        availability_days=availability_days,
        global_prior=global_prior,
        order_windows=(7, 30),
        outcome_windows=(30, 90),
    )
    category = _group_features(
        enriched,
        key="primary_category",
        prefix="category",
        order_days=order_days,
        availability_days=availability_days,
        global_prior=global_prior,
        order_windows=(),
        outcome_windows=(),
    )
    wanted = {
        "seller_state_prior_late_rate",
        "seller_state_prior_order_count_log",
        "seller_state_late_rate_30d",
        "seller_state_late_rate_90d",
        "seller_state_experience_days_log",
        "route_prior_late_rate",
        "route_order_count_7d_log",
        "route_order_count_30d_log",
        "route_late_rate_30d",
        "route_late_rate_90d",
        "category_prior_late_rate",
    }
    for name, values in {**seller, **route, **category}.items():
        if name in wanted:
            enriched[name] = values

    enriched["freight_item_ratio"] = (
        enriched["total_freight_value"] / enriched["total_item_value"].clip(lower=1.0)
    ).clip(upper=10.0)
    distance_units = (enriched["distance_km"].fillna(0) / 500.0).clip(lower=1.0)
    enriched["promised_days_per_500km"] = (
        enriched["promised_delivery_days"] / distance_units
    )
    enriched["season"] = season_from_month(enriched["purchase_month"])
    return enriched


def _records(history: DailyHistory, include_late: bool) -> list[list[int]]:
    if include_late:
        return [
            [int(day), int(count), int(late)]
            for day, count, late in zip(
                history.days, history.counts, history.late, strict=True
            )
        ]
    return [
        [int(day), int(count)]
        for day, count in zip(history.days, history.counts, strict=True)
    ]


def export_daily_histories(frame: pd.DataFrame) -> dict:
    order_days = _days(frame, TIMESTAMP)
    availability_days = _days(frame, LABEL_AVAILABLE_TIMESTAMP)
    output: dict[str, object] = {
        "granularity": "utc_day",
        "cutoff": "strictly_before_query_day",
        "global_outcomes": _records(
            _global_outcome_history(frame, availability_days), include_late=True
        ),
        "groups": {},
        "constants": {
            "seconds_per_day": SECONDS_PER_DAY,
            "default_late_prior": DEFAULT_LATE_PRIOR,
            "prior_strength": PRIOR_STRENGTH,
            "window_prior_strength": WINDOW_PRIOR_STRENGTH,
        },
    }
    groups: dict[str, dict] = {}
    for key in ("seller_state", "route", "primary_category"):
        orders = _daily_histories(frame, key, order_days, include_late=False)
        outcomes = _daily_histories(frame, key, availability_days, include_late=True)
        groups[key] = {
            value: {
                "orders": _records(history, include_late=False),
                "outcomes": (
                    _records(outcomes[value], include_late=True)
                    if value in outcomes
                    else []
                ),
            }
            for value, history in orders.items()
        }
    output["groups"] = groups
    return output
