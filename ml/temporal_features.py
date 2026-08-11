"""Create history features without using information from the future.

Purchase counts become available when an order is placed. Delay outcomes become
available only after delivery, so the two histories use different event dates.
"""

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
    """Store daily order counts and known late outcomes for one history."""

    days: np.ndarray
    counts: np.ndarray
    late: np.ndarray


def _days(frame: pd.DataFrame, column: str) -> np.ndarray:
    """Convert UTC timestamps to integer UTC days for fast comparisons."""

    return (
        frame[column].astype("int64").to_numpy() // 1_000_000_000 // SECONDS_PER_DAY
    ).astype(np.int32)


def _prefix_lookup(
    history: DailyHistory, query_days: np.ndarray, window: int | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read totals strictly before each query day, optionally in a time window."""

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
    """Build a daily history for every state, route, or category value."""

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
    """Build the market-wide history of outcomes that are already known."""

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


def _global_order_history(order_days: np.ndarray) -> DailyHistory:
    """Build the market-wide purchase history available immediately."""

    daily = (
        pd.Series(order_days, name="day")
        .value_counts(sort=False)
        .sort_index()
        .rename_axis("day")
        .reset_index(name="count")
    )
    return DailyHistory(
        days=daily["day"].to_numpy(dtype=np.int32),
        counts=daily["count"].to_numpy(dtype=float),
        late=np.zeros(len(daily), dtype=float),
    )


def _smoothed_rate(
    late: np.ndarray,
    count: np.ndarray,
    prior: np.ndarray,
    strength: float,
) -> np.ndarray:
    """Pull small groups toward a stable prior instead of trusting noisy rates."""

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
    """Create prior counts, delay rates, and experience for one group field."""

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

    # Process one group value at a time, then place its history features back
    # into the matching rows of the full dataset.
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

    experience_days = np.maximum(order_days - first_order_day, 0)
    output = {
        f"{prefix}_prior_late_rate": _smoothed_rate(
            prior_late,
            prior_outcome_count,
            global_prior,
            PRIOR_STRENGTH,
        ),
        f"{prefix}_prior_order_count_log": np.log1p(prior_order_count),
        f"{prefix}_experience_days_log": np.log1p(
            experience_days
        ),
        f"{prefix}_prior_known_count_log": np.log1p(prior_outcome_count),
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
    if 30 in order_windows:
        historical_daily_volume = np.divide(
            prior_order_count,
            np.maximum(experience_days, 30),
            out=np.zeros(len(frame), dtype=float),
            where=prior_order_count > 0,
        )
        recent_daily_volume = order_window_counts[30] / 30.0
        workload_ratio = (recent_daily_volume + 0.01) / (
            historical_daily_volume + 0.01
        )
        output[f"{prefix}_workload_ratio_log"] = np.log1p(
            np.clip(workload_ratio, 0, 20)
        )
    return output


def seller_memberships(frame: pd.DataFrame) -> pd.DataFrame:
    """Expand serialized order sellers into deterministic weighted members."""

    ids = frame["seller_ids"].fillna("").astype(str).str.split("|")
    values = frame["seller_item_values"].fillna("").astype(str).str.split("|")
    membership = pd.DataFrame(
        {
            "row": np.arange(len(frame), dtype=int),
            "seller_id": ids,
            "seller_item_value": values,
        }
    ).explode(["seller_id", "seller_item_value"], ignore_index=True)
    membership["seller_item_value"] = pd.to_numeric(
        membership["seller_item_value"], errors="raise"
    )
    membership["seller_id"] = membership["seller_id"].astype(str)
    totals = membership.groupby("row", observed=True)["seller_item_value"].transform(
        "sum"
    )
    counts = membership.groupby("row", observed=True)["seller_id"].transform("size")
    membership["weight"] = np.divide(
        membership["seller_item_value"].to_numpy(dtype=float),
        totals.to_numpy(dtype=float),
        out=np.divide(np.ones(len(membership)), counts.to_numpy(dtype=float)),
        where=totals.to_numpy(dtype=float) > 0,
    )
    primary_ids = frame["primary_seller_id"].astype(str).to_numpy()
    membership["is_primary"] = membership["seller_id"].to_numpy() == primary_ids[
        membership["row"].to_numpy()
    ]
    if not membership.groupby("row", observed=True)["is_primary"].any().all():
        raise ValueError("Every order must contain its primary seller")
    return membership


def _seller_daily_histories(
    frame: pd.DataFrame,
    membership: pd.DataFrame,
    event_days: np.ndarray,
    include_late: bool,
) -> dict[str, DailyHistory]:
    """Build purchase or known-outcome histories for each unique seller."""

    rows = membership["row"].to_numpy(dtype=int)
    source = pd.DataFrame(
        {
            "seller_id": membership["seller_id"].to_numpy(),
            "day": event_days[rows],
            "late": frame[TARGET].to_numpy()[rows] if include_late else 0,
        }
    )
    daily = (
        source.groupby(["seller_id", "day"], sort=True, observed=True)["late"]
        .agg(["size", "sum"])
        .reset_index()
    )
    return {
        str(seller_id): DailyHistory(
            days=group["day"].to_numpy(dtype=np.int32),
            counts=group["size"].to_numpy(dtype=float),
            late=group["sum"].to_numpy(dtype=float),
        )
        for seller_id, group in daily.groupby(
            "seller_id", sort=False, observed=True
        )
    }


def _seller_features(
    frame: pd.DataFrame,
    order_days: np.ndarray,
    availability_days: np.ndarray,
    global_prior: np.ndarray,
) -> dict[str, np.ndarray]:
    """Create primary- and multi-seller leakage-safe history aggregates."""

    membership = seller_memberships(frame)
    member_rows = membership["row"].to_numpy(dtype=int)
    query_days = order_days[member_rows]
    seller_ids = membership["seller_id"].to_numpy()
    orders = _seller_daily_histories(
        frame, membership, order_days, include_late=False
    )
    outcomes = _seller_daily_histories(
        frame, membership, availability_days, include_late=True
    )
    size = len(membership)
    prior_orders = np.zeros(size, dtype=float)
    prior_known = np.zeros(size, dtype=float)
    prior_late = np.zeros(size, dtype=float)
    first_order_day = query_days.copy()
    order_counts = {window: np.zeros(size, dtype=float) for window in (7, 30, 90)}
    outcome_counts = {window: np.zeros(size, dtype=float) for window in (30, 90)}
    outcome_late = {window: np.zeros(size, dtype=float) for window in (30, 90)}
    for seller_id in np.unique(seller_ids):
        positions = np.flatnonzero(seller_ids == seller_id)
        seller_query_days = query_days[positions]
        order_history = orders[str(seller_id)]
        prior_orders[positions], _, first_order_day[positions] = _prefix_lookup(
            order_history, seller_query_days
        )
        for window in order_counts:
            order_counts[window][positions], _, _ = _prefix_lookup(
                order_history, seller_query_days, window
            )
        outcome_history = outcomes.get(str(seller_id))
        if outcome_history is not None:
            prior_known[positions], prior_late[positions], _ = _prefix_lookup(
                outcome_history, seller_query_days
            )
            for window in outcome_counts:
                (
                    outcome_counts[window][positions],
                    outcome_late[window][positions],
                    _,
                ) = _prefix_lookup(outcome_history, seller_query_days, window)

    member_prior = global_prior[member_rows]
    prior_rate = _smoothed_rate(
        prior_late, prior_known, member_prior, PRIOR_STRENGTH
    )
    late_rate_30d = _smoothed_rate(
        outcome_late[30], outcome_counts[30], member_prior, WINDOW_PRIOR_STRENGTH
    )
    late_rate_90d = _smoothed_rate(
        outcome_late[90], outcome_counts[90], member_prior, WINDOW_PRIOR_STRENGTH
    )
    experience_days = np.maximum(query_days - first_order_day, 0)
    historical_daily = np.divide(
        prior_orders,
        np.maximum(experience_days, 30),
        out=np.zeros(size, dtype=float),
        where=prior_orders > 0,
    )
    workload_ratio_log = np.log1p(
        np.clip((order_counts[30] / 30.0 + 0.01) / (historical_daily + 0.01), 0, 20)
    )
    member_values = pd.DataFrame(
        {
            "row": member_rows,
            "weight": membership["weight"].to_numpy(dtype=float),
            "is_primary": membership["is_primary"].to_numpy(dtype=bool),
            "prior_late_rate": prior_rate,
            "prior_known_count_log": np.log1p(prior_known),
            "prior_order_count_log": np.log1p(prior_orders),
            "late_rate_30d": late_rate_30d,
            "late_rate_90d": late_rate_90d,
            "order_count_7d_log": np.log1p(order_counts[7]),
            "order_count_30d_log": np.log1p(order_counts[30]),
            "order_count_90d_log": np.log1p(order_counts[90]),
            "experience_days_log": np.log1p(experience_days),
            "workload_ratio_log": workload_ratio_log,
        }
    )
    primary = member_values.loc[member_values["is_primary"]].set_index("row")
    primary = primary.reindex(np.arange(len(frame)))
    output = {
        f"primary_seller_{name}": primary[name].to_numpy(dtype=float)
        for name in (
            "prior_late_rate",
            "prior_known_count_log",
            "prior_order_count_log",
            "late_rate_30d",
            "late_rate_90d",
            "order_count_7d_log",
            "order_count_30d_log",
            "order_count_90d_log",
            "experience_days_log",
            "workload_ratio_log",
        )
    }
    grouped = member_values.groupby("row", observed=True)
    weights = member_values["weight"]
    for name in ("prior_late_rate", "late_rate_30d", "late_rate_90d"):
        weighted = (member_values[name] * weights).groupby(
            member_values["row"], observed=True
        ).sum()
        output[f"seller_{name}_weighted"] = weighted.reindex(
            np.arange(len(frame))
        ).to_numpy(dtype=float)
        output[f"seller_{name}_max"] = grouped[name].max().reindex(
            np.arange(len(frame))
        ).to_numpy(dtype=float)
    output["seller_experience_days_log_min"] = grouped[
        "experience_days_log"
    ].min().reindex(np.arange(len(frame))).to_numpy(dtype=float)
    output["seller_experience_days_log_max"] = grouped[
        "experience_days_log"
    ].max().reindex(np.arange(len(frame))).to_numpy(dtype=float)
    for window in (7, 30):
        raw_counts = np.expm1(member_values[f"order_count_{window}d_log"])
        summed = raw_counts.groupby(member_values["row"], observed=True).sum()
        output[f"seller_order_count_{window}d_log_sum"] = np.log1p(
            summed.reindex(np.arange(len(frame))).to_numpy(dtype=float)
        )
    workload_weighted = (member_values["workload_ratio_log"] * weights).groupby(
        member_values["row"], observed=True
    ).sum()
    output["seller_workload_ratio_log_weighted"] = workload_weighted.reindex(
        np.arange(len(frame))
    ).to_numpy(dtype=float)
    output["seller_workload_ratio_log_max"] = grouped[
        "workload_ratio_log"
    ].max().reindex(np.arange(len(frame))).to_numpy(dtype=float)
    return output


def _brazilian_national_holidays(start_year: int, end_year: int) -> np.ndarray:
    """Return the fixed-date Brazilian national holiday calendar.

    The deterministic list follows Lei 662/1949, Lei 1,266/1950,
    Lei 6,802/1980, Lei 10,607/2002 and Lei 14,759/2023. The dataset predates
    the last law, so 20 November is deliberately not counted for 2016-2018.
    """

    month_days = ((1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (12, 25))
    return np.array(
        [
            np.datetime64(f"{year:04d}-{month:02d}-{day:02d}", "D")
            for year in range(start_year, end_year + 1)
            for month, day in month_days
        ],
        dtype="datetime64[D]",
    )


def _add_static_features(enriched: pd.DataFrame) -> None:
    """Add order-time geometry, promise-calendar, and ratio features in place."""

    promised = enriched["order_estimated_delivery_date"]
    purchase_dates = enriched[TIMESTAMP].dt.normalize().to_numpy(dtype="datetime64[D]")
    promised_dates = promised.dt.normalize().to_numpy(dtype="datetime64[D]")
    inclusive_end = promised_dates + np.timedelta64(1, "D")
    weekday_days = np.busday_count(purchase_dates, inclusive_end)
    holidays = _brazilian_national_holidays(
        int(enriched[TIMESTAMP].dt.year.min()), int(promised.dt.year.max())
    )
    business_days = np.busday_count(
        purchase_dates, inclusive_end, holidays=holidays
    )
    interval_days = (inclusive_end - purchase_dates).astype(int)
    enriched["promised_delivery_weekday"] = promised.dt.dayofweek + 1
    enriched["promised_delivery_month"] = promised.dt.month
    enriched["promised_delivery_near_weekend"] = promised.dt.dayofweek.isin(
        [4, 5, 6]
    ).astype(int)
    enriched["weekends_in_promise_window"] = interval_days - weekday_days
    enriched["business_days_in_promise_window"] = business_days
    enriched["national_holidays_in_promise_window"] = weekday_days - business_days

    distance = enriched["distance_km"].clip(lower=0)
    freight = enriched["total_freight_value"].clip(lower=0)
    weight_kg = enriched["total_weight_g"].clip(lower=0) / 1_000.0
    volume = enriched["total_volume_cm3"].clip(lower=0)
    enriched["distance_km_log"] = np.log1p(distance)
    enriched["distance_per_promised_day"] = distance / enriched[
        "promised_delivery_days"
    ].clip(lower=1.0)
    enriched["freight_per_km"] = (freight / distance.clip(lower=10.0)).clip(
        upper=10.0
    )
    enriched["freight_per_kg"] = (freight / weight_kg.clip(lower=0.1)).clip(
        upper=500.0
    )
    enriched["freight_per_item_value"] = (
        freight / enriched["total_item_value"].clip(lower=1.0)
    ).clip(upper=10.0)
    enriched["weight_per_volume"] = (
        enriched["total_weight_g"].clip(lower=0) / volume.clip(lower=1.0)
    ).clip(upper=100.0)
    enriched["multi_seller"] = enriched["seller_count"].gt(1).astype(int)

    def zip_region(values: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(values, errors="coerce")
        return numeric.floordiv(1_000).astype("Int64").astype(str).replace("<NA>", "__missing__")

    enriched["seller_zip_region"] = zip_region(enriched["seller_zip"])
    enriched["customer_zip_region"] = zip_region(enriched["customer_zip"])
    enriched["zip_region_route"] = (
        enriched["seller_zip_region"] + " -> " + enriched["customer_zip_region"]
    )
    enriched["distance_bucket"] = pd.cut(
        distance,
        bins=[-np.inf, 50, 150, 300, 600, 1_000, np.inf],
        labels=["0-50", "50-150", "150-300", "300-600", "600-1000", "1000+"],
    ).astype(str)


def season_from_month(month: pd.Series | np.ndarray) -> np.ndarray:
    """Map Brazilian calendar months to Southern Hemisphere seasons."""

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
    """Add all point-in-time features used by model training."""

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
    global_orders = _global_order_history(order_days)
    global_prior_orders, _, global_first_day = _prefix_lookup(
        global_orders, order_days
    )
    global_window_counts: dict[int, np.ndarray] = {}
    for window in (7, 30, 90):
        global_window_counts[window], _, _ = _prefix_lookup(
            global_orders, order_days, window
        )
        enriched[f"global_order_count_{window}d_log"] = np.log1p(
            global_window_counts[window]
        )
    global_experience = np.maximum(order_days - global_first_day, 0)
    global_historical_daily = np.divide(
        global_prior_orders,
        np.maximum(global_experience, 30),
        out=np.zeros(len(enriched), dtype=float),
        where=global_prior_orders > 0,
    )
    enriched["global_workload_ratio_log"] = np.log1p(
        np.clip(
            (global_window_counts[30] / 30.0 + 0.01)
            / (global_historical_daily + 0.01),
            0,
            20,
        )
    )

    # Seller state, route, and category histories capture different kinds of
    # operational context while applying the same no-future-information rule.
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
        order_windows=(7, 30, 90),
        outcome_windows=(30, 90),
    )
    category = _group_features(
        enriched,
        key="primary_category",
        prefix="category",
        order_days=order_days,
        availability_days=availability_days,
        global_prior=global_prior,
        order_windows=(7, 30, 90),
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
        "route_order_count_90d_log",
        "route_workload_ratio_log",
        "route_late_rate_30d",
        "route_late_rate_90d",
        "category_prior_late_rate",
        "category_order_count_7d_log",
        "category_order_count_30d_log",
        "category_order_count_90d_log",
        "category_workload_ratio_log",
    }
    for name, values in {**seller, **route, **category}.items():
        if name in wanted:
            enriched[name] = values

    for name, values in _seller_features(
        enriched, order_days, availability_days, global_prior
    ).items():
        enriched[name] = values

    # Ratios make shipping cost and promised time comparable across orders of
    # different values and distances.
    enriched["freight_item_ratio"] = (
        enriched["total_freight_value"] / enriched["total_item_value"].clip(lower=1.0)
    ).clip(upper=10.0)
    distance_units = (enriched["distance_km"].fillna(0) / 500.0).clip(lower=1.0)
    enriched["promised_days_per_500km"] = (
        enriched["promised_delivery_days"] / distance_units
    )
    enriched["season"] = season_from_month(enriched["purchase_month"])
    _add_static_features(enriched)
    return enriched


def _records(history: DailyHistory, include_late: bool) -> list[list[int]]:
    """Convert NumPy history arrays into compact JSON records."""

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
    """Export the same histories that the production scorer needs."""

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
