from __future__ import annotations

import json
from pathlib import Path

from ml.common import (
    DATA_FILE,
    TARGET,
    chronological_split,
    read_orders,
    split_summary,
    validation_errors,
)


OUTPUT = Path("artifacts/data-audit.json")


def build_audit() -> dict:
    frame = read_orders(DATA_FILE)
    split = chronological_split(frame)
    errors = validation_errors(frame)
    blocking = {
        key: value
        for key, value in errors.items()
        if value
        and key
        not in {
            "negative_weight",
            "negative_volume",
        }
    }

    return {
        "source": str(DATA_FILE).replace("\\", "/"),
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "unique_order_ids": int(frame["order_id"].nunique(dropna=False)),
        "duplicate_order_ids": int(frame["order_id"].duplicated().sum()),
        "duplicate_rows": int(frame.duplicated().sum()),
        "target": {
            "name": TARGET,
            "negative": int((frame[TARGET] == 0).sum()),
            "positive": int((frame[TARGET] == 1).sum()),
            "positive_rate": float(frame[TARGET].mean()),
        },
        "time_range": {
            "starts_at": frame["order_purchase_timestamp"].iloc[0].isoformat(),
            "ends_at": frame["order_purchase_timestamp"].iloc[-1].isoformat(),
        },
        "missing": {
            column: {
                "count": int(count),
                "rate": float(count / len(frame)),
            }
            for column, count in frame.isna().sum().items()
            if count
        },
        "checks": errors,
        "blocking_errors": blocking,
        "splits": split_summary(frame, split),
        "notes": [
            "Zero weight and zero volume are retained as plausible unknown/absent physical measurements.",
            "Numeric missing values are imputed from training medians only.",
            "Categorical missing values are imputed from training modes only.",
            "Unknown future categories are encoded as all-zero one-hot groups.",
            "order_id and the full timestamp are excluded from model features.",
            "Historical aggregates exclude the current order date and every later date.",
            "seller_id is absent, so seller_state history is the available proxy.",
        ],
    }


def main() -> None:
    audit = build_audit()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if audit["blocking_errors"]:
        raise SystemExit(
            "Blocking data validation errors: "
            + json.dumps(audit["blocking_errors"], ensure_ascii=False)
        )
    print(
        f"Validated {audit['rows']:,} rows; "
        f"late rate {audit['target']['positive_rate']:.2%}; "
        f"report: {OUTPUT}"
    )


if __name__ == "__main__":
    main()
