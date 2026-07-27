from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ml.common import TARGET, TIMESTAMP


SECONDS_PER_DAY = 86_400
DEFAULT_LATE_PRIOR = 0.05
PRIOR_STRENGTH = 20.0
WINDOW_PRIOR_STRENGTH = 10.0


@dataclass(frozen=True)
class DailyHistory:
    days: np.ndarray
    counts: np.ndarray
    late: np.ndarray


def _order_days(frame: pd.DataFrame) -> np.ndarray:
    return (
        frame[TIMESTAMP].astype("int64").to_numpy()
        // 1_000_000_000
        // SECONDS_PER_DAY
    ).astype(np.int32)


def _prefix_lookup(
    history: DailyHistory, query_days: np.ndarray, window: int | None = None
) -> tuple[np.ndarray, np.ndarray]:
    end = np.searchsorted(history.days, query_days, side="left")
    count_prefix = np.concatenate(([0.0], np.cumsum(history.counts)))
    late_prefix = np.concatenate(([0.0], np.cumsum(history.late)))
    if window is None:
        start = np.zeros_like(end)
    else:
        start = np.searchsorted(
            history.days, query_days - window, side="left"
        )
    return (
        count_prefix[end] - count_prefix[start],
        late_prefix[end] - late_prefix[start],
    )


def _daily_histories(
    frame: pd.DataFrame, key: str, order_days: np.ndarray
) -> dict[str, DailyHistory]:
    daily = (
        pd.DataFrame(
            {
                "key": frame[key].fillna("__missing__").astype(str),
                "day": order_days,
                "late": frame[TARGET].to_numpy(),
            }
        )
        .groupby(["key", "day"], sort=True, observed=True)["late"]
        .agg(["size", "sum"])
        .reset_index()
    )
    histories: dict[str, DailyHistory] = {}
    for value, group in daily.groupby("key", sort=False, observed=True):
        histories[str(value)] = DailyHistory(
            days=group["day"].to_numpy(dtype=np.int32),
            counts=group["size"].to_numpy(dtype=float),
            late=group["sum"].to_numpy(dtype=float),
        )
    return histories


def _global_history(
    frame: pd.DataFrame, order_days: np.ndarray
) -> DailyHistory:
    daily = (
        pd.DataFrame({"day": order_days, "late": frame[TARGET].to_numpy()})
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
    global_prior: np.ndarray,
    windows: tuple[int, ...],
) -> dict[str, np.ndarray]:
    values = frame[key].fillna("__missing__").astype(str).to_numpy()
    histories = _daily_histories(frame, key, order_days)
    count_before = np.zeros(len(frame), dtype=float)
    late_before = np.zeros(len(frame), dtype=float)
    first_day = np.full(len(frame), order_days, dtype=np.int32)
    window_counts = {
        window: np.zeros(len(frame), dtype=float) for window in windows
    }
    window_late = {
        window: np.zeros(len(frame), dtype=float) for window in windows
    }

    for value, history in histories.items():
        rows = np.flatnonzero(values == value)
        days = order_days[rows]
        count_before[rows], late_before[rows] = _prefix_lookup(history, days)
        first_day[rows] = history.days[0]
        for window in windows:
            (
                window_counts[window][rows],
                window_late[window][rows],
            ) = _prefix_lookup(history, days, window)

    output = {
        f"{prefix}_prior_late_rate": _smoothed_rate(
            late_before,
            count_before,
            global_prior,
            PRIOR_STRENGTH,
        ),
        f"{prefix}_prior_order_count_log": np.log1p(count_before),
        f"{prefix}_experience_days_log": np.log1p(
            np.maximum(order_days - first_day, 0)
        ),
    }
    for window in windows:
        output[f"{prefix}_order_count_{window}d_log"] = np.log1p(
            window_counts[window]
        )
        output[f"{prefix}_late_rate_{window}d"] = _smoothed_rate(
            window_late[window],
            window_counts[window],
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
    order_days = _order_days(enriched)
    global_history = _global_history(enriched, order_days)
    global_count, global_late = _prefix_lookup(global_history, order_days)
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
        global_prior=global_prior,
        windows=(30, 90),
    )
    route = _group_features(
        enriched,
        key="route",
        prefix="route",
        order_days=order_days,
        global_prior=global_prior,
        windows=(7, 30, 90),
    )
    category = _group_features(
        enriched,
        key="primary_category",
        prefix="category",
        order_days=order_days,
        global_prior=global_prior,
        windows=(),
    )

    for name, values in {**seller, **route, **category}.items():
        enriched[name] = values

    enriched["freight_item_ratio"] = (
        enriched["total_freight_value"]
        / enriched["total_item_value"].clip(lower=1.0)
    ).clip(upper=10.0)
    distance_units = (enriched["distance_km"].fillna(0) / 500.0).clip(
        lower=1.0
    )
    enriched["promised_days_per_500km"] = (
        enriched["promised_delivery_days"] / distance_units
    )
    enriched["season"] = season_from_month(enriched["purchase_month"])
    return enriched


def export_daily_histories(frame: pd.DataFrame) -> dict:
    order_days = _order_days(frame)
    output: dict[str, object] = {}
    global_history = _global_history(frame, order_days)
    output["global"] = [
        [
            int(day),
            int(count),
            int(late),
        ]
        for day, count, late in zip(
            global_history.days,
            global_history.counts,
            global_history.late,
            strict=True,
        )
    ]
    for key in ("seller_state", "route", "primary_category"):
        output[key] = {
            value: [
                [int(day), int(count), int(late)]
                for day, count, late in zip(
                    history.days,
                    history.counts,
                    history.late,
                    strict=True,
                )
            ]
            for value, history in _daily_histories(
                frame, key, order_days
            ).items()
        }
    output["constants"] = {
        "seconds_per_day": SECONDS_PER_DAY,
        "default_late_prior": DEFAULT_LATE_PRIOR,
        "prior_strength": PRIOR_STRENGTH,
        "window_prior_strength": WINDOW_PRIOR_STRENGTH,
    }
    return output
