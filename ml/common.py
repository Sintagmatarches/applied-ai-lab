"""Shared feature names, data loading, and chronological split helpers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

DATA_FILE = Path("data/olist_orders_model.csv")
BUILD_MANIFEST_FILE = Path("data/olist-build-manifest.json")
TARGET = "late_1d"
TIMESTAMP = "order_purchase_timestamp"
LABEL_AVAILABLE_TIMESTAMP = "label_available_timestamp"

# Base features come directly from facts known when an order is placed.
BASE_NUMERIC_FEATURES = [
    "purchase_year",
    "purchase_month",
    "purchase_day_of_week",
    "purchase_hour",
    "promised_delivery_days",
    "same_state",
    "distance_km",
    "item_count",
    "total_item_value",
    "total_freight_value",
    "total_weight_g",
    "total_volume_cm3",
    "payment_installments",
]

# Engineered features summarize only information available before the order.
ENGINEERED_NUMERIC_FEATURES = [
    "prior_global_late_rate",
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
    "freight_item_ratio",
    "promised_days_per_500km",
]

NUMERIC_FEATURES = BASE_NUMERIC_FEATURES + ENGINEERED_NUMERIC_FEATURES

BASE_CATEGORICAL_FEATURES = [
    "seller_state",
    "customer_state",
    "route",
    "primary_category",
    "primary_payment_type",
]

CATEGORICAL_FEATURES = BASE_CATEGORICAL_FEATURES + ["season"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

REQUIRED_COLUMNS = [
    "order_id",
    TIMESTAMP,
    LABEL_AVAILABLE_TIMESTAMP,
    *BASE_NUMERIC_FEATURES,
    *BASE_CATEGORICAL_FEATURES,
    TARGET,
]


@dataclass(frozen=True)
class TimeSplit:
    """Store row boundaries for train, validation, and final test periods."""

    train_end: int
    validation_end: int
    total: int

    @property
    def train(self) -> slice:
        return slice(0, self.train_end)

    @property
    def validation(self) -> slice:
        return slice(self.train_end, self.validation_end)

    @property
    def test(self) -> slice:
        return slice(self.validation_end, self.total)


def file_sha256(path: Path) -> str:
    """Return a stable SHA-256 fingerprint for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_orders(path: Path = DATA_FILE) -> pd.DataFrame:
    """Load the derived dataset, validate its columns, and sort it by time."""

    frame = pd.read_csv(path)
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")

    frame[TIMESTAMP] = pd.to_datetime(frame[TIMESTAMP], utc=True, errors="raise")
    frame[LABEL_AVAILABLE_TIMESTAMP] = pd.to_datetime(
        frame[LABEL_AVAILABLE_TIMESTAMP], utc=True, errors="raise"
    )
    return frame.sort_values([TIMESTAMP, "order_id"], kind="stable").reset_index(
        drop=True
    )


def chronological_split(frame: pd.DataFrame) -> TimeSplit:
    """Keep older orders for training and newer orders for evaluation."""

    total = len(frame)
    return TimeSplit(
        train_end=int(total * 0.70),
        validation_end=int(total * 0.85),
        total=total,
    )


def validation_errors(frame: pd.DataFrame) -> dict[str, int]:
    """Count data problems that could make training unsafe or misleading."""

    timestamp = frame[TIMESTAMP]
    label_timestamp = frame[LABEL_AVAILABLE_TIMESTAMP]
    expected_route = frame["seller_state"] + " → " + frame["customer_state"]
    return {
        "missing_order_id": int(frame["order_id"].isna().sum()),
        "duplicate_order_id": int(frame["order_id"].duplicated().sum()),
        "duplicate_rows": int(frame.duplicated().sum()),
        "invalid_target": int((~frame[TARGET].isin([0, 1])).sum()),
        "invalid_timestamp": int(timestamp.isna().sum()),
        "invalid_label_available_timestamp": int(label_timestamp.isna().sum()),
        "label_available_before_purchase": int((label_timestamp < timestamp).sum()),
        "non_monotonic_timestamp": int(not timestamp.is_monotonic_increasing),
        "non_positive_promised_days": int((frame["promised_delivery_days"] <= 0).sum()),
        "negative_distance": int((frame["distance_km"] < 0).sum()),
        "non_positive_item_count": int((frame["item_count"] <= 0).sum()),
        "negative_item_value": int((frame["total_item_value"] < 0).sum()),
        "negative_freight_value": int((frame["total_freight_value"] < 0).sum()),
        "negative_weight": int((frame["total_weight_g"] < 0).sum()),
        "negative_volume": int((frame["total_volume_cm3"] < 0).sum()),
        "negative_installments": int((frame["payment_installments"] < 0).sum()),
        "invalid_same_state": int((~frame["same_state"].isin([0, 1])).sum()),
        "same_state_mismatch": int(
            frame["same_state"]
            .ne((frame["seller_state"] == frame["customer_state"]).astype(int))
            .sum()
        ),
        "route_mismatch": int(frame["route"].ne(expected_route).sum()),
        "purchase_year_mismatch": int(
            frame["purchase_year"].ne(timestamp.dt.year).sum()
        ),
        "purchase_month_mismatch": int(
            frame["purchase_month"].ne(timestamp.dt.month).sum()
        ),
        "purchase_day_of_week_mismatch": int(
            frame["purchase_day_of_week"].ne(timestamp.dt.dayofweek + 1).sum()
        ),
        "purchase_hour_mismatch": int(
            frame["purchase_hour"].ne(timestamp.dt.hour).sum()
        ),
    }


def split_summary(frame: pd.DataFrame, split: TimeSplit) -> dict[str, dict]:
    """Describe the size, date range, and target rate of each time split."""

    summaries: dict[str, dict] = {}
    for name, rows in (
        ("train", split.train),
        ("validation", split.validation),
        ("test", split.test),
    ):
        section = frame.iloc[rows]
        summaries[name] = {
            "rows": int(len(section)),
            "late_orders": int(section[TARGET].sum()),
            "late_rate": float(section[TARGET].mean()),
            "starts_at": section[TIMESTAMP].iloc[0].isoformat(),
            "ends_at": section[TIMESTAMP].iloc[-1].isoformat(),
        }
    return summaries


def json_value(value):
    """Convert NumPy and pandas scalar values into JSON-safe Python values."""

    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if pd.isna(value):
        return None
    return value
