from __future__ import annotations

import json
import math
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from ml.common import (
    CATEGORICAL_FEATURES,
    DATA_FILE,
    FEATURES,
    NUMERIC_FEATURES,
    TARGET,
    chronological_split,
    json_value,
    read_orders,
    split_summary,
)
from ml.validate_data import build_audit


ARTIFACTS = Path("artifacts")
MODEL_VERSION = "olist-xgb-2026-07-27.1"
WORKING_ALERT_CAP = 0.075


def build_preprocessor() -> ColumnTransformer:
    numeric = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "one_hot",
                OneHotEncoder(
                    handle_unknown="ignore",
                    min_frequency=5,
                    sparse_output=True,
                ),
            ),
        ]
    )
    return ColumnTransformer(
        [
            ("numeric", numeric, NUMERIC_FEATURES),
            ("categorical", categorical, CATEGORICAL_FEATURES),
        ]
    )


def metrics(y_true: np.ndarray, probability: np.ndarray, threshold: float) -> dict:
    predicted = (probability >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(
        y_true, predicted, labels=[0, 1]
    ).ravel()
    return {
        "threshold": float(threshold),
        "detected_late_orders": int(tp),
        "false_warnings": int(fp),
        "missed_late_orders": int(fn),
        "correct_safe_orders": int(tn),
        "precision": float(precision_score(y_true, predicted, zero_division=0)),
        "recall": float(recall_score(y_true, predicted, zero_division=0)),
        "f1": float(f1_score(y_true, predicted, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, probability)),
        "roc_auc": float(roc_auc_score(y_true, probability)),
        "brier": float(brier_score_loss(y_true, probability)),
        "log_loss": float(log_loss(y_true, probability)),
        "alert_rate": float(predicted.mean()),
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
    }


def select_threshold(y_true: np.ndarray, probability: np.ndarray) -> dict:
    candidates = np.unique(
        np.quantile(probability, np.linspace(0.01, 0.99, 800))
    )
    scored: list[tuple[float, dict]] = []
    for threshold in candidates:
        result = metrics(y_true, probability, float(threshold))
        if result["alert_rate"] > WORKING_ALERT_CAP:
            continue
        precision = result["precision"]
        recall = result["recall"]
        f2 = (
            5 * precision * recall / (4 * precision + recall)
            if precision + recall
            else 0.0
        )
        scored.append((f2, result))
    if not scored:
        raise RuntimeError("No threshold candidate satisfied the alert-rate cap")
    return max(scored, key=lambda item: item[0])[1]


def calibration_table(y_true: np.ndarray, probability: np.ndarray) -> list[dict]:
    table = pd.DataFrame({"actual": y_true, "probability": probability})
    table["bin"] = pd.qcut(
        table["probability"], q=10, duplicates="drop"
    )
    grouped = table.groupby("bin", observed=True).agg(
        count=("actual", "size"),
        predicted_probability=("probability", "mean"),
        observed_rate=("actual", "mean"),
    )
    return [
        {
            "count": int(row["count"]),
            "predicted_probability": float(row["predicted_probability"]),
            "observed_rate": float(row["observed_rate"]),
        }
        for _, row in grouped.iterrows()
    ]


def category_index_maps(
    preprocessor: ColumnTransformer, frame: pd.DataFrame
) -> tuple[dict[str, dict[str, int]], dict[str, str]]:
    categorical_pipeline = preprocessor.named_transformers_["categorical"]
    imputer: SimpleImputer = categorical_pipeline.named_steps["imputer"]
    encoder: OneHotEncoder = categorical_pipeline.named_steps["one_hot"]
    numeric_count = len(NUMERIC_FEATURES)
    total_width = len(preprocessor.get_feature_names_out())
    field_widths = list(encoder._n_features_outs)
    field_offsets = np.cumsum([0, *field_widths[:-1]]).tolist()
    maps: dict[str, dict[str, int]] = {}
    defaults: dict[str, str] = {}

    baseline = {}
    for index, name in enumerate(CATEGORICAL_FEATURES):
        default = str(imputer.statistics_[index])
        defaults[name] = default
        baseline[name] = default

    for field_index, name in enumerate(CATEGORICAL_FEATURES):
        field_map: dict[str, int] = {}
        field_start = int(field_offsets[field_index])
        field_end = field_start + int(field_widths[field_index])
        for raw_value in encoder.categories_[field_index]:
            sample = pd.DataFrame([{**baseline, name: raw_value}])
            encoded = categorical_pipeline.transform(
                sample[CATEGORICAL_FEATURES]
            )
            row = encoded.toarray()[0] if hasattr(encoded, "toarray") else encoded[0]
            # Infrequent categories intentionally share one active bucket.
            active = np.flatnonzero(row[field_start:field_end])
            if len(active):
                field_map[str(raw_value)] = (
                    numeric_count + field_start + int(active[0])
                )
        maps[name] = field_map

    if any(
        index < numeric_count or index >= total_width
        for field_map in maps.values()
        for index in field_map.values()
    ):
        raise RuntimeError("Exported category feature index is out of range")

    return maps, defaults


def tree_leaf_sum(tree: dict, vector: np.ndarray) -> float:
    node = tree
    while "leaf" not in node:
        feature_index = int(str(node["split"]).removeprefix("f"))
        value = vector[feature_index]
        next_id = node["missing"] if math.isnan(value) else (
            node["yes"]
            if np.float32(value) < np.float32(node["split_condition"])
            else node["no"]
        )
        node = next(
            child for child in node["children"] if child["nodeid"] == next_id
        )
    return float(node["leaf"])


def export_model(
    preprocessor: ColumnTransformer,
    model: XGBClassifier,
    calibrator: LogisticRegression,
    frame: pd.DataFrame,
    split_summaries: dict,
    working_threshold: float,
    results: dict,
) -> dict:
    numeric_pipeline = preprocessor.named_transformers_["numeric"]
    numeric_imputer: SimpleImputer = numeric_pipeline.named_steps["imputer"]
    scaler: StandardScaler = numeric_pipeline.named_steps["scale"]
    category_maps, category_defaults = category_index_maps(
        preprocessor, frame
    )
    trees = [
        json.loads(tree)
        for tree in model.get_booster().get_dump(dump_format="json")
    ]

    reference = frame.iloc[[0]][FEATURES]
    reference_vector = preprocessor.transform(reference)
    if hasattr(reference_vector, "tocsr"):
        reference_sparse = reference_vector.tocsr()
        reference_dense = np.full(
            reference_sparse.shape[1], np.nan, dtype=float
        )
        reference_dense[reference_sparse.indices] = reference_sparse.data
    else:
        reference_dense = np.asarray(reference_vector)[0]
    raw_margin = float(
        model.predict(reference_vector, output_margin=True)[0]
    )
    intercept = raw_margin - sum(
        tree_leaf_sum(tree, reference_dense) for tree in trees
    )

    numeric = {
        name: {
            "index": index,
            "median": float(numeric_imputer.statistics_[index]),
            "mean": float(scaler.mean_[index]),
            "scale": float(scaler.scale_[index]),
        }
        for index, name in enumerate(NUMERIC_FEATURES)
    }

    return {
        "model_version": MODEL_VERSION,
        "model_type": "XGBoost binary classifier with Platt calibration",
        "target": TARGET,
        "positive_definition": (
            "Delivered at least 24 hours after the promised delivery date"
        ),
        "feature_count": int(len(preprocessor.get_feature_names_out())),
        "features": FEATURES,
        "numeric": numeric,
        "categorical": {
            name: {
                "default": category_defaults[name],
                "indices": category_maps[name],
            }
            for name in CATEGORICAL_FEATURES
        },
        "trees": trees,
        "raw_margin_intercept": float(intercept),
        "calibration": {
            "type": "platt",
            "slope": float(calibrator.coef_[0, 0]),
            "intercept": float(calibrator.intercept_[0]),
        },
        "thresholds": {
            "standard": 0.5,
            "working": float(working_threshold),
            "working_alert_cap_on_validation": WORKING_ALERT_CAP,
            "low_medium_boundary": 0.05,
        },
        "training": split_summaries,
        "test_metrics": results["xgboost"]["test"],
        "limitations": [
            "Historical Olist orders only, September 2016 through August 2018.",
            "The final time period has measurable drift and weaker ranking performance.",
            "State-to-state distance is supplied by the user; states alone do not determine exact distance.",
            "A probability is an estimate, not a delivery guarantee.",
        ],
    }


def main() -> None:
    audit = build_audit()
    if audit["blocking_errors"]:
        raise SystemExit(
            "Data validation failed: "
            + json.dumps(audit["blocking_errors"], ensure_ascii=False)
        )

    frame = read_orders(DATA_FILE)
    split = chronological_split(frame)
    x = frame[FEATURES]
    y = frame[TARGET].astype(int).to_numpy()

    preprocessor = build_preprocessor()
    x_train = preprocessor.fit_transform(x.iloc[split.train])
    x_validation = preprocessor.transform(x.iloc[split.validation])
    x_test = preprocessor.transform(x.iloc[split.test])

    models = {
        "dummy": DummyClassifier(strategy="prior").fit(
            x_train, y[split.train]
        ),
        "logistic": LogisticRegression(
            max_iter=1000,
            C=1.0,
            solver="liblinear",
            random_state=42,
        ).fit(x_train, y[split.train]),
        "xgboost": XGBClassifier(
            n_estimators=450,
            max_depth=5,
            learning_rate=0.05,
            min_child_weight=8,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_lambda=2,
            reg_alpha=0.05,
            objective="binary:logistic",
            eval_metric="aucpr",
            n_jobs=4,
            random_state=42,
        ).fit(
            x_train,
            y[split.train],
            eval_set=[(x_validation, y[split.validation])],
            verbose=False,
        ),
    }

    validation_probability = {
        name: model.predict_proba(x_validation)[:, 1]
        for name, model in models.items()
    }
    validation_raw_margin = models["xgboost"].predict(
        x_validation, output_margin=True
    )
    calibrator = LogisticRegression(
        C=1_000_000,
        solver="lbfgs",
        random_state=42,
    ).fit(
        validation_raw_margin.reshape(-1, 1),
        y[split.validation],
    )
    validation_probability["xgboost"] = calibrator.predict_proba(
        validation_raw_margin.reshape(-1, 1)
    )[:, 1]

    selected_model = max(
        ("logistic", "xgboost"),
        key=lambda name: average_precision_score(
            y[split.validation], validation_probability[name]
        ),
    )
    if selected_model != "xgboost":
        raise RuntimeError(
            f"Expected validation selection to choose xgboost, got {selected_model}"
        )

    working = {
        name: select_threshold(
            y[split.validation], validation_probability[name]
        )
        for name in ("logistic", "xgboost")
    }

    results: dict[str, dict] = {}
    for name, model in models.items():
        test_probability = model.predict_proba(x_test)[:, 1]
        if name == "xgboost":
            raw = model.predict(x_test, output_margin=True)
            test_probability = calibrator.predict_proba(
                raw.reshape(-1, 1)
            )[:, 1]

        if name == "dummy":
            threshold = 0.5
        else:
            threshold = working[name]["threshold"]
        results[name] = {
            "validation": {
                "standard_threshold": metrics(
                    y[split.validation],
                    validation_probability[name],
                    0.5,
                ),
                "working_threshold": (
                    metrics(
                        y[split.validation],
                        validation_probability[name],
                        threshold,
                    )
                    if name != "dummy"
                    else metrics(
                        y[split.validation],
                        validation_probability[name],
                        0.5,
                    )
                ),
            },
            "test": {
                "standard_threshold": metrics(
                    y[split.test], test_probability, 0.5
                ),
                "working_threshold": metrics(
                    y[split.test], test_probability, threshold
                ),
                "calibration": calibration_table(
                    y[split.test], test_probability
                ),
            },
        }

    summaries = split_summary(frame, split)
    report = {
        "model_version": MODEL_VERSION,
        "selection_rule": (
            "Highest validation PR-AUC; final test was evaluated only after "
            "the model and working-threshold rule were fixed."
        ),
        "selected_model": selected_model,
        "working_threshold_rule": (
            "Maximize validation F2 while alerting on at most 7.5% of "
            "validation orders."
        ),
        "splits": summaries,
        "feature_policy": {
            "included": FEATURES,
            "excluded": [
                "order_id",
                "order_purchase_timestamp (full value)",
                "late_1d",
                "all post-purchase and post-delivery facts",
            ],
        },
        "models": results,
        "probability_quality": {
            "method": "Platt calibration fitted on the validation period",
            "test_brier": results["xgboost"]["test"]["working_threshold"][
                "brier"
            ],
            "test_mean_prediction": float(
                np.mean(
                    calibrator.predict_proba(
                        models["xgboost"]
                        .predict(x_test, output_margin=True)
                        .reshape(-1, 1)
                    )[:, 1]
                )
            ),
            "test_observed_rate": float(y[split.test].mean()),
            "limitation": (
                "The final period remains overestimated because order mix and "
                "delay prevalence drifted after the validation window."
            ),
        },
    }

    export = export_model(
        preprocessor=preprocessor,
        model=models["xgboost"],
        calibrator=calibrator,
        frame=frame.iloc[split.train],
        split_summaries=summaries,
        working_threshold=working["xgboost"]["threshold"],
        results=results,
    )

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "metrics.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (ARTIFACTS / "olist-model.json").write_text(
        json.dumps(export, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    joblib.dump(
        {
            "preprocessor": preprocessor,
            "model": models["xgboost"],
            "calibrator": calibrator,
            "threshold": working["xgboost"]["threshold"],
            "version": MODEL_VERSION,
        },
        ARTIFACTS / "olist-model.joblib",
        compress=3,
    )

    print(
        json.dumps(
            {
                "selected_model": selected_model,
                "working_threshold": working["xgboost"]["threshold"],
                "test": results["xgboost"]["test"]["working_threshold"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
