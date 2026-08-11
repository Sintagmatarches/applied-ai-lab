"""Prove that Python training and production inference calculate the same score."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from ml.common import TIMESTAMP
from ml.runtime_reference import raw_features, score

ARTIFACT_FILE = Path("artifacts/olist-model.json")
FIXTURE_FILE = Path("artifacts/parity-fixtures.json")

INPUT_FIELDS = (
    "seller_state",
    "customer_state",
    "promised_delivery_days",
    "primary_category",
    "item_count",
    "total_item_value",
    "total_freight_value",
    "distance_km",
    "total_weight_g",
    "total_volume_cm3",
    "primary_payment_type",
    "payment_installments",
)


def row_input(row: pd.Series) -> dict:
    """Convert one training row into the public API input format."""

    timestamp = row[TIMESTAMP].isoformat().replace("+00:00", "Z")
    return {
        **{
            field: (
                int(row[field])
                if field in {"item_count", "payment_installments"}
                else (
                    float(row[field])
                    if field
                    in {
                        "promised_delivery_days",
                        "total_item_value",
                        "total_freight_value",
                        "distance_km",
                        "total_weight_g",
                        "total_volume_cm3",
                    }
                    else str(row[field])
                )
            )
            for field in INPUT_FIELDS
        },
        "purchase_timestamp": timestamp,
    }


def fixture_document(artifact: dict, named_inputs: Iterable[tuple[str, dict]]) -> dict:
    """Score named examples and store their exact expected Python outputs."""

    return {
        "model_version": artifact["model_version"],
        "contract": artifact["feature_contract"],
        "tolerance": {"vector": 1e-10, "score": 1e-10},
        "cases": [
            {"name": name, "input": input_data, "expected": score(artifact, input_data)}
            for name, input_data in named_inputs
        ],
    }


def _choose_rows(frame: pd.DataFrame) -> list[tuple[str, int]]:
    """Choose final-period examples that cover useful calendar and route cases."""

    usable = frame.dropna(subset=list(INPUT_FIELDS))
    test_start = int(len(frame) * 0.85)
    usable = usable.loc[usable.index >= test_start]
    choices: list[tuple[str, int]] = []
    conditions = (
        (
            "monday_cross_state",
            (usable[TIMESTAMP].dt.dayofweek == 0) & (usable["same_state"] == 0),
        ),
        ("sunday", usable[TIMESTAMP].dt.dayofweek == 6),
        ("same_state", usable["same_state"] == 1),
    )
    for name, condition in conditions:
        matches = usable.loc[condition]
        if matches.empty:
            raise RuntimeError(f"Could not find parity row for {name}")
        choices.append((name, int(matches.index[0])))
    return choices


def build_training_fixtures(
    artifact: dict,
    frame: pd.DataFrame,
    enriched: pd.DataFrame,
    preprocessor,
) -> dict:
    """Compare exported runtime features with the fitted Python preprocessor."""

    numeric_features = list(artifact["numeric"])
    categorical_features = list(artifact["categorical"])
    features = artifact["features"]
    named_inputs: list[tuple[str, dict]] = []
    for name, index in _choose_rows(frame):
        input_data = row_input(frame.loc[index])
        runtime_raw = raw_features(artifact, input_data)
        for feature in numeric_features:
            np.testing.assert_allclose(
                float(runtime_raw[feature]),
                float(enriched.loc[index, feature]),
                rtol=0,
                atol=1e-10,
                err_msg=f"Raw numeric parity failed for {name}.{feature}",
            )
        for feature in categorical_features:
            if str(runtime_raw[feature]) != str(enriched.loc[index, feature]):
                raise AssertionError(
                    f"Raw categorical parity failed for {name}.{feature}: "
                    f"{runtime_raw[feature]!r} != {enriched.loc[index, feature]!r}"
                )
        expected_vector = preprocessor.transform(enriched.loc[[index], features])
        if hasattr(expected_vector, "toarray"):
            expected_vector = expected_vector.toarray()
        reference = score(artifact, input_data)
        np.testing.assert_allclose(
            reference["feature_vector"], expected_vector[0], rtol=0, atol=1e-10
        )
        named_inputs.append((name, input_data))

    # This extra case proves that a category unseen during training is handled
    # consistently instead of crashing or shifting feature positions.
    unknown = dict(named_inputs[0][1])
    unknown["primary_category"] = "future_category"
    unknown_raw = pd.DataFrame([raw_features(artifact, unknown)])[features]
    expected_unknown = preprocessor.transform(unknown_raw)
    if hasattr(expected_unknown, "toarray"):
        expected_unknown = expected_unknown.toarray()
    unknown_score = score(artifact, unknown)
    np.testing.assert_allclose(
        unknown_score["feature_vector"], expected_unknown[0], rtol=0, atol=1e-10
    )
    named_inputs.append(("unknown_category", unknown))
    return fixture_document(artifact, named_inputs)


def check_fixture(artifact_path: Path, fixture_path: Path) -> None:
    """Fail when committed parity examples no longer match the model artifact."""

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    committed = json.loads(fixture_path.read_text(encoding="utf-8"))
    inputs = [(case["name"], case["input"]) for case in committed["cases"]]
    regenerated = fixture_document(artifact, inputs)
    if regenerated != committed:
        raise SystemExit(
            "Parity fixtures are stale. Retrain the model to regenerate them."
        )


def main() -> None:
    """Run the parity check from the command line."""

    parser = argparse.ArgumentParser(
        description="Verify exported Python/TypeScript parity fixtures."
    )
    parser.add_argument("--artifact", type=Path, default=ARTIFACT_FILE)
    parser.add_argument("--fixture", type=Path, default=FIXTURE_FILE)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    check_fixture(args.artifact, args.fixture)
    print(f"Parity fixture matches {args.artifact}: {args.fixture}")


if __name__ == "__main__":
    main()
