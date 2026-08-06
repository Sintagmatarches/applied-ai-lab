"""Audit the derived Olist dataset before any model is trained."""

from __future__ import annotations

import json
from pathlib import Path

from ml.common import (
    BUILD_MANIFEST_FILE,
    DATA_FILE,
    TARGET,
    chronological_split,
    file_sha256,
    read_orders,
    split_summary,
    validation_errors,
)

OUTPUT = Path("artifacts/data-audit.json")


def build_audit() -> dict:
    """Create a machine-readable report of data quality and time splits."""

    frame = read_orders(DATA_FILE)
    split = chronological_split(frame)
    errors = validation_errors(frame)
    # Missing physical measurements are allowed because the training pipeline
    # imputes them. Structural and target errors still stop the build.
    blocking = {
        key: value
        for key, value in errors.items()
        if value and key not in {"negative_weight", "negative_volume"}
    }
    source_manifest = (
        json.loads(BUILD_MANIFEST_FILE.read_text(encoding="utf-8"))
        if BUILD_MANIFEST_FILE.is_file()
        else None
    )

    return {
        "source": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
        "license": "CC BY-NC-SA 4.0",
        "derived_dataset": str(DATA_FILE).replace("\\", "/"),
        "derived_dataset_sha256": file_sha256(DATA_FILE),
        "build_manifest": source_manifest,
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "unique_order_ids": int(frame["order_id"].nunique(dropna=False)),
        "duplicate_order_ids": int(frame["order_id"].duplicated().sum()),
        "duplicate_rows": int(frame.duplicated().sum()),
        "target": {
            "name": TARGET,
            "definition": (
                "Actual customer delivery more than 24 hours after the "
                "estimated delivery timestamp."
            ),
            "available_at": "order_delivered_customer_date",
            "negative": int((frame[TARGET] == 0).sum()),
            "positive": int((frame[TARGET] == 1).sum()),
            "positive_rate": float(frame[TARGET].mean()),
        },
        "time_range": {
            "starts_at": frame["order_purchase_timestamp"].iloc[0].isoformat(),
            "ends_at": frame["order_purchase_timestamp"].iloc[-1].isoformat(),
        },
        "missing": {
            column: {"count": int(count), "rate": float(count / len(frame))}
            for column, count in frame.isna().sum().items()
            if count
        },
        "checks": errors,
        "blocking_errors": blocking,
        "splits": split_summary(frame, split),
        "notes": [
            "One row represents one delivered order.",
            "For multi-item orders, seller and category come from a deterministic primary-item rule; values, freight, weight and volume are aggregated.",
            "Distance uses robust ZIP-prefix coordinate medians and the haversine formula.",
            "Numeric missing values are imputed from training medians only.",
            "Categorical missing values are imputed from training modes only.",
            "Unknown future categories are encoded as all-zero one-hot groups.",
            "Order IDs, delivery timestamps and target values are excluded from model inputs.",
            "Outcome histories use only labels delivered on UTC days strictly before each order day.",
            "Order-count histories use only purchases on UTC days strictly before each order day.",
        ],
    }


def main() -> None:
    """Write the audit report and stop if a blocking check failed."""

    audit = build_audit()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if audit["blocking_errors"]:
        raise SystemExit(
            "Blocking data validation errors: "
            + json.dumps(audit["blocking_errors"], ensure_ascii=False)
        )
    print(
        f"Validated {audit['rows']:,} rows; "
        f"late rate {audit['target']['positive_rate']:.2%}; report: {OUTPUT}"
    )


if __name__ == "__main__":
    main()
