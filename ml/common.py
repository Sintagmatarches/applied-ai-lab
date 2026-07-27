from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


DATA_FILE = Path("data/bq-results-20260727-111149-1785150786733.csv")
TARGET = "late_1d"
TIMESTAMP = "order_purchase_timestamp"

NUMERIC_FEATURES = [
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

CATEGORICAL_FEATURES = [
    "seller_state",
    "customer_state",
    "route",
    "primary_category",
    "primary_payment_type",
]

FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

REQUIRED_COLUMNS = [
    "order_id",
    TIMESTAMP,
    *FEATURES,
    TARGET,
]


@dataclass(frozen=True)
class TimeSplit:
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


def read_orders(path: Path = DATA_FILE) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")

    frame[TIMESTAMP] = pd.to_datetime(frame[TIMESTAMP], utc=True, errors="raise")
    frame = frame.sort_values([TIMESTAMP, "order_id"]).reset_index(drop=True)
    return frame


def chronological_split(frame: pd.DataFrame) -> TimeSplit:
    total = len(frame)
    return TimeSplit(
        train_end=int(total * 0.70),
        validation_end=int(total * 0.85),
        total=total,
    )


def validation_errors(frame: pd.DataFrame) -> dict[str, int]:
    timestamp = frame[TIMESTAMP]
    return {
        "missing_order_id": int(frame["order_id"].isna().sum()),
        "duplicate_order_id": int(frame["order_id"].duplicated().sum()),
        "duplicate_rows": int(frame.duplicated().sum()),
        "invalid_target": int((~frame[TARGET].isin([0, 1])).sum()),
        "invalid_timestamp": int(timestamp.isna().sum()),
        "non_monotonic_timestamp": int(not timestamp.is_monotonic_increasing),
        "non_positive_promised_days": int(
            (frame["promised_delivery_days"] <= 0).sum()
        ),
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
        "purchase_year_mismatch": int(
            frame["purchase_year"].ne(timestamp.dt.year).sum()
        ),
        "purchase_month_mismatch": int(
            frame["purchase_month"].ne(timestamp.dt.month).sum()
        ),
        "purchase_hour_mismatch": int(
            frame["purchase_hour"].ne(timestamp.dt.hour).sum()
        ),
    }


def split_summary(frame: pd.DataFrame, split: TimeSplit) -> dict[str, dict]:
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
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if pd.isna(value):
        return None
    return value
