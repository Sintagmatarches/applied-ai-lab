"""Evaluate the frozen development winner once on the newest 15% benchmark."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression

from ml.common import BASELINE_FEATURES, DATA_FILE, TARGET, read_orders
from ml.model_selection import (
    CATBOOST_CANDIDATES,
    DEVELOPMENT_LOCK_FILE,
    XGBOOST_CANDIDATES,
    _candidate_model,
    _rank_fraction,
    build_preprocessor,
    ranking_metrics,
)
from ml.temporal_features import add_temporal_features

OUTPUT_FILE = Path("artifacts/olist-final-benchmark.json")
TRAIN_FRACTION = 0.70
FINAL_BENCHMARK_FRACTION = 0.15
BOOTSTRAP_SAMPLES = 1_000
EXPECTED_BASELINE_CAPTURE = 107
EXPECTED_FINAL_LATE_ORDERS = 620


def _candidate(candidate_id: str):
    for candidate in (*XGBOOST_CANDIDATES, *CATBOOST_CANDIDATES):
        if candidate.candidate_id == candidate_id:
            return candidate
    raise ValueError(f"Unknown frozen component: {candidate_id}")


def _paired_bootstrap(
    y_true: np.ndarray,
    baseline_score: np.ndarray,
    selected_score: np.ndarray,
) -> dict[str, Any]:
    """Bootstrap paired order rows so both models see identical resamples."""

    rng = np.random.default_rng(42)
    differences: dict[str, list[float]] = {
        "top_10_recall": [],
        "top_10_detected_late_orders": [],
        "pr_auc": [],
        "roc_auc": [],
    }
    for _ in range(BOOTSTRAP_SAMPLES):
        rows = rng.integers(0, len(y_true), len(y_true))
        sample_y = y_true[rows]
        if np.unique(sample_y).size < 2:
            continue
        baseline = ranking_metrics(sample_y, baseline_score[rows])
        selected = ranking_metrics(sample_y, selected_score[rows])
        baseline_top = baseline["top_risk_groups"]["10%"]
        selected_top = selected["top_risk_groups"]["10%"]
        differences["top_10_recall"].append(
            selected_top["recall"] - baseline_top["recall"]
        )
        differences["top_10_detected_late_orders"].append(
            selected_top["detected_late_orders"]
            - baseline_top["detected_late_orders"]
        )
        differences["pr_auc"].append(selected["pr_auc"] - baseline["pr_auc"])
        differences["roc_auc"].append(selected["roc_auc"] - baseline["roc_auc"])
    return {
        name: {
            "mean_difference": float(np.mean(values)),
            "lower_95": float(np.quantile(values, 0.025)),
            "upper_95": float(np.quantile(values, 0.975)),
            "probability_difference_above_zero": float(np.mean(np.array(values) > 0)),
        }
        for name, values in differences.items()
    }


def main() -> None:
    if not DEVELOPMENT_LOCK_FILE.is_file():
        raise SystemExit(
            "Development lock is required before final-benchmark evaluation."
        )
    lock = json.loads(DEVELOPMENT_LOCK_FILE.read_text(encoding="utf-8"))
    if not lock.get("locked_before_final_benchmark"):
        raise SystemExit("Development artifact does not certify a pre-final lock.")
    if lock["selected_family"] != "rank_blend":
        raise SystemExit("This evaluator expects the frozen rank-blend winner.")

    base_frame = read_orders(DATA_FILE)
    frame = add_temporal_features(base_frame)
    y = frame[TARGET].to_numpy(dtype=int)
    total = len(frame)
    train_end = int(total * TRAIN_FRACTION)
    final_start = int(total * (1.0 - FINAL_BENCHMARK_FRACTION))
    train_rows = np.arange(total) < train_end
    calibration_rows = (np.arange(total) >= train_end) & (
        np.arange(total) < final_start
    )
    final_rows = np.arange(total) >= final_start

    # Refit the historical baseline exactly to produce paired order-level
    # scores; assert that its published 107/620 result is reproduced.
    baseline_preprocessor = build_preprocessor(list(BASELINE_FEATURES))
    baseline_train = baseline_preprocessor.fit_transform(
        frame.loc[train_rows, BASELINE_FEATURES]
    )
    baseline_final = baseline_preprocessor.transform(
        frame.loc[final_rows, BASELINE_FEATURES]
    )
    baseline_model = LogisticRegression(
        max_iter=1_500,
        C=0.5,
        solver="liblinear",
        random_state=42,
    ).fit(baseline_train, y[train_rows])
    baseline_score = baseline_model.predict_proba(baseline_final)[:, 1]
    baseline_metrics = ranking_metrics(y[final_rows], baseline_score)
    baseline_top = baseline_metrics["top_risk_groups"]["10%"]
    if (
        baseline_top["detected_late_orders"] != EXPECTED_BASELINE_CAPTURE
        or int(y[final_rows].sum()) != EXPECTED_FINAL_LATE_ORDERS
    ):
        raise RuntimeError(
            "Published baseline did not reproduce; final comparison is unsafe."
        )

    features = lock["features"]
    preprocessor = build_preprocessor(features)
    x_train = preprocessor.fit_transform(frame.loc[train_rows, features])
    x_calibration = preprocessor.transform(frame.loc[calibration_rows, features])
    x_final = preprocessor.transform(frame.loc[final_rows, features])
    component_scores: dict[str, np.ndarray] = {}
    fitted_details: dict[str, Any] = {}
    for family in ("xgboost", "catboost"):
        candidate_id = lock["parameters"]["components"][family]
        candidate = _candidate(candidate_id)
        model = _candidate_model(candidate)
        if family == "catboost":
            model.fit(
                x_train,
                y[train_rows],
                eval_set=(x_calibration, y[calibration_rows]),
                early_stopping_rounds=60,
                verbose=False,
            )
            fitted_details["catboost_best_iteration"] = int(
                model.get_best_iteration()
            )
        else:
            model.fit(x_train, y[train_rows])
        component_scores[family] = model.predict_proba(x_final)[:, 1]

    weights = lock["parameters"]["weights"]
    selected_score = sum(
        weights[family] * _rank_fraction(component_scores[family])
        for family in ("xgboost", "catboost")
    )
    selected_metrics = ranking_metrics(y[final_rows], selected_score)
    selected_top = selected_metrics["top_risk_groups"]["10%"]
    report = {
        "protocol": {
            "development_lock": str(DEVELOPMENT_LOCK_FILE).replace("\\", "/"),
            "configuration_changed_after_lock": False,
            "train_fraction": TRAIN_FRACTION,
            "calibration_fraction": 0.15,
            "final_benchmark_fraction": FINAL_BENCHMARK_FRACTION,
            "final_benchmark_rows": int(final_rows.sum()),
            "final_benchmark_late_orders": int(y[final_rows].sum()),
        },
        "frozen_configuration": lock,
        "fitted_details": fitted_details,
        "baseline": baseline_metrics,
        "selected": selected_metrics,
        "absolute_change": {
            "top_10_detected_late_orders": (
                selected_top["detected_late_orders"]
                - baseline_top["detected_late_orders"]
            ),
            "top_10_recall": selected_top["recall"] - baseline_top["recall"],
            "top_10_precision": (
                selected_top["precision"] - baseline_top["precision"]
            ),
            "pr_auc": selected_metrics["pr_auc"] - baseline_metrics["pr_auc"],
            "roc_auc": selected_metrics["roc_auc"] - baseline_metrics["roc_auc"],
        },
        "paired_bootstrap_95": _paired_bootstrap(
            y[final_rows], baseline_score, selected_score
        ),
        "component_final_metrics_for_diagnostics_only": {
            family: ranking_metrics(y[final_rows], score)
            for family, score in component_scores.items()
        },
    }
    OUTPUT_FILE.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
