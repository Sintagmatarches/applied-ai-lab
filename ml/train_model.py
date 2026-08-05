from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
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
    TIMESTAMP,
    read_orders,
)
from ml.parity import FIXTURE_FILE, build_training_fixtures
from ml.temporal_features import add_temporal_features, export_daily_histories
from ml.validate_data import OUTPUT as AUDIT_FILE
from ml.validate_data import build_audit

ARTIFACTS = Path("artifacts")
MODEL_VERSION = "olist-logistic-availability-2026-08-05.1"
PREVIOUS_MODEL_VERSION = "olist-logistic-temporal-2026-07-27.2"
FINAL_TRAIN_FRACTION = 0.70
CALIBRATION_END_FRACTION = 0.85
DEPLOYABLE_MODELS = {"logistic"}


@dataclass(frozen=True)
class BacktestPeriod:
    name: str
    starts_at: str
    ends_at: str


BACKTEST_PERIODS = [
    BacktestPeriod("2017-09/10", "2017-09-01", "2017-11-01"),
    BacktestPeriod("2017-11/12", "2017-11-01", "2018-01-01"),
    BacktestPeriod("2018-01/02", "2018-01-01", "2018-03-01"),
    BacktestPeriod("2018-03/04", "2018-03-01", "2018-04-15"),
]


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                NUMERIC_FEATURES,
            ),
            (
                "categorical",
                Pipeline(
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
                ),
                CATEGORICAL_FEATURES,
            ),
        ]
    )


def build_linear_model() -> LogisticRegression:
    return LogisticRegression(
        max_iter=1_500, C=0.5, solver="liblinear", random_state=42
    )


def build_xgboost_model() -> XGBClassifier:
    return XGBClassifier(
        n_estimators=350,
        max_depth=4,
        learning_rate=0.05,
        min_child_weight=10,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=3,
        reg_alpha=0.1,
        objective="binary:logistic",
        eval_metric="aucpr",
        n_jobs=4,
        random_state=42,
    )


def build_catboost_model() -> CatBoostClassifier:
    return CatBoostClassifier(
        iterations=350,
        depth=6,
        learning_rate=0.05,
        l2_leaf_reg=5,
        loss_function="Logloss",
        eval_metric="PRAUC:type=Classic",
        random_seed=42,
        verbose=False,
        allow_writing_files=False,
        thread_count=4,
    )


def catboost_frame(frame: pd.DataFrame, training_rows: np.ndarray) -> pd.DataFrame:
    prepared = frame[FEATURES].copy()
    medians = prepared.loc[training_rows, NUMERIC_FEATURES].median()
    prepared.loc[:, NUMERIC_FEATURES] = prepared[NUMERIC_FEATURES].fillna(medians)
    prepared.loc[:, CATEGORICAL_FEATURES] = (
        prepared[CATEGORICAL_FEATURES].fillna("__missing__").astype(str)
    )
    return prepared


def top_group_metrics(
    y_true: np.ndarray, probability: np.ndarray, fraction: float
) -> dict:
    size = max(1, int(math.ceil(len(probability) * fraction)))
    selected = np.argsort(-probability, kind="stable")[:size]
    found = int(y_true[selected].sum())
    false_warnings = int(size - found)
    total_late = int(y_true.sum())
    total_safe = int(len(y_true) - total_late)
    return {
        "fraction": float(fraction),
        "orders": int(size),
        "detected_late_orders": found,
        "false_warnings": false_warnings,
        "missed_late_orders": int(total_late - found),
        "correct_safe_orders": int(total_safe - false_warnings),
        "precision": float(found / size),
        "recall": float(found / total_late) if total_late else 0.0,
        "false_warnings_per_detected_late_order": (
            float(false_warnings / found) if found else None
        ),
        "confusion_matrix": [
            [int(total_safe - false_warnings), false_warnings],
            [int(total_late - found), found],
        ],
    }


def ranking_metrics(y_true: np.ndarray, probability: np.ndarray) -> dict:
    prevalence = float(np.mean(y_true))
    pr_auc = float(average_precision_score(y_true, probability))
    return {
        "prevalence": prevalence,
        "pr_auc": pr_auc,
        "pr_auc_lift": float(pr_auc / prevalence) if prevalence else None,
        "roc_auc": float(roc_auc_score(y_true, probability)),
        "top_risk_groups": {
            f"{int(fraction * 100)}%": top_group_metrics(y_true, probability, fraction)
            for fraction in (0.05, 0.10, 0.20)
        },
    }


def bootstrap_confidence_intervals(
    y_true: np.ndarray, probability: np.ndarray, samples: int = 250
) -> dict:
    rng = np.random.default_rng(42)
    values = {"pr_auc": [], "roc_auc": [], "top_10_recall": [], "top_10_precision": []}
    for _ in range(samples):
        rows = rng.integers(0, len(y_true), len(y_true))
        sample_y = y_true[rows]
        if np.unique(sample_y).size < 2:
            continue
        sample_probability = probability[rows]
        top = top_group_metrics(sample_y, sample_probability, 0.10)
        values["pr_auc"].append(average_precision_score(sample_y, sample_probability))
        values["roc_auc"].append(roc_auc_score(sample_y, sample_probability))
        values["top_10_recall"].append(top["recall"])
        values["top_10_precision"].append(top["precision"])
    return {
        name: {
            "lower_95": float(np.quantile(result, 0.025)),
            "upper_95": float(np.quantile(result, 0.975)),
        }
        for name, result in values.items()
    }


def fit_fold_candidates(
    frame: pd.DataFrame, train_rows: np.ndarray, validation_rows: np.ndarray
) -> dict[str, dict]:
    x = frame[FEATURES]
    y = frame[TARGET].to_numpy()
    preprocessor = build_preprocessor()
    x_train = preprocessor.fit_transform(x.loc[train_rows])
    x_validation = preprocessor.transform(x.loc[validation_rows])
    results: dict[str, dict] = {}
    for name, model in (
        ("logistic", build_linear_model()),
        ("xgboost", build_xgboost_model()),
    ):
        model.fit(x_train, y[train_rows])
        results[name] = ranking_metrics(
            y[validation_rows], model.predict_proba(x_validation)[:, 1]
        )
    cat_frame = catboost_frame(frame, train_rows)
    catboost = build_catboost_model()
    catboost.fit(
        cat_frame.loc[train_rows, FEATURES],
        y[train_rows],
        cat_features=CATEGORICAL_FEATURES,
    )
    results["catboost"] = ranking_metrics(
        y[validation_rows],
        catboost.predict_proba(cat_frame.loc[validation_rows, FEATURES])[:, 1],
    )
    return results


def backtest_models(frame: pd.DataFrame) -> tuple[dict, dict, str]:
    timestamps = frame[TIMESTAMP]
    fold_results: dict[str, list[dict]] = {
        "logistic": [],
        "xgboost": [],
        "catboost": [],
    }
    for period in BACKTEST_PERIODS:
        start = pd.Timestamp(period.starts_at, tz="UTC")
        end = pd.Timestamp(period.ends_at, tz="UTC")
        train_rows = (timestamps < start).to_numpy()
        validation_rows = ((timestamps >= start) & (timestamps < end)).to_numpy()
        results = fit_fold_candidates(frame, train_rows, validation_rows)
        for name, result in results.items():
            fold_results[name].append(
                {
                    "period": period.name,
                    "train_rows": int(train_rows.sum()),
                    "validation_rows": int(validation_rows.sum()),
                    **result,
                }
            )
    summary: dict[str, dict] = {}
    for name, folds in fold_results.items():
        pr_auc = np.array([fold["pr_auc"] for fold in folds])
        pr_lift = np.array([fold["pr_auc_lift"] for fold in folds])
        roc_auc = np.array([fold["roc_auc"] for fold in folds])
        capture = np.array([fold["top_risk_groups"]["10%"]["recall"] for fold in folds])
        summary[name] = {
            "mean_pr_auc": float(pr_auc.mean()),
            "std_pr_auc": float(pr_auc.std()),
            "mean_pr_auc_lift": float(pr_lift.mean()),
            "std_pr_auc_lift": float(pr_lift.std()),
            "mean_roc_auc": float(roc_auc.mean()),
            "std_roc_auc": float(roc_auc.std()),
            "mean_top_10_percent_capture": float(capture.mean()),
            "std_top_10_percent_capture": float(capture.std()),
            "operational_stability_score": float(capture.mean() - capture.std()),
        }
    selected = max(
        summary,
        key=lambda name: (
            summary[name]["operational_stability_score"],
            summary[name]["mean_pr_auc_lift"],
            summary[name]["mean_roc_auc"],
        ),
    )
    return fold_results, summary, selected


def expected_calibration_error(
    y_true: np.ndarray, probability: np.ndarray
) -> tuple[float, list[dict]]:
    table = pd.DataFrame({"actual": y_true, "probability": probability})
    table["bin"] = pd.qcut(table["probability"], q=10, duplicates="drop")
    grouped = table.groupby("bin", observed=True).agg(
        count=("actual", "size"),
        predicted=("probability", "mean"),
        observed=("actual", "mean"),
    )
    ece = float(
        (
            grouped["count"]
            / len(table)
            * (grouped["predicted"] - grouped["observed"]).abs()
        ).sum()
    )
    return ece, [
        {
            "count": int(row["count"]),
            "predicted": float(row["predicted"]),
            "observed": float(row["observed"]),
        }
        for _, row in grouped.iterrows()
    ]


def choose_calibration(raw_score: np.ndarray, y_true: np.ndarray) -> dict:
    cutoff = int(len(raw_score) * 0.60)
    train_score, check_score = raw_score[:cutoff], raw_score[cutoff:]
    train_y, check_y = y_true[:cutoff], y_true[cutoff:]
    platt = LogisticRegression(C=1_000_000, solver="lbfgs", random_state=42).fit(
        train_score.reshape(-1, 1), train_y
    )
    isotonic = IsotonicRegression(out_of_bounds="clip").fit(train_score, train_y)
    candidates = {
        "identity": 1 / (1 + np.exp(-check_score)),
        "platt": platt.predict_proba(check_score.reshape(-1, 1))[:, 1],
        "isotonic": isotonic.predict(check_score),
    }
    evaluation = {
        name: {
            "brier": float(brier_score_loss(check_y, probability)),
            "log_loss": float(log_loss(check_y, np.clip(probability, 1e-8, 1 - 1e-8))),
            "mean_prediction": float(probability.mean()),
            "observed_rate": float(check_y.mean()),
        }
        for name, probability in candidates.items()
    }
    selected = min(
        evaluation,
        key=lambda name: (evaluation[name]["brier"], evaluation[name]["log_loss"]),
    )
    if selected == "platt":
        fitted = LogisticRegression(C=1_000_000, solver="lbfgs", random_state=42).fit(
            raw_score.reshape(-1, 1), y_true
        )
        parameters = {
            "type": "platt",
            "slope": float(fitted.coef_[0, 0]),
            "intercept": float(fitted.intercept_[0]),
        }
    elif selected == "isotonic":
        fitted = IsotonicRegression(out_of_bounds="clip").fit(raw_score, y_true)
        parameters = {
            "type": "isotonic",
            "x": [float(value) for value in fitted.X_thresholds_],
            "y": [float(value) for value in fitted.y_thresholds_],
        }
    else:
        fitted = None
        parameters = {"type": "identity"}
    return {
        "selected": selected,
        "selection_evaluation": evaluation,
        "fitted": fitted,
        "parameters": parameters,
    }


def calibrated_probability(raw_score: np.ndarray, calibration: dict) -> np.ndarray:
    if calibration["selected"] == "platt":
        return calibration["fitted"].predict_proba(raw_score.reshape(-1, 1))[:, 1]
    if calibration["selected"] == "isotonic":
        return calibration["fitted"].predict(raw_score)
    return 1 / (1 + np.exp(-raw_score))


def category_index_maps(
    preprocessor: ColumnTransformer,
) -> tuple[dict[str, dict[str, int]], dict[str, str]]:
    pipeline = preprocessor.named_transformers_["categorical"]
    imputer: SimpleImputer = pipeline.named_steps["imputer"]
    encoder: OneHotEncoder = pipeline.named_steps["one_hot"]
    numeric_count = len(NUMERIC_FEATURES)
    widths = list(encoder._n_features_outs)
    offsets = np.cumsum([0, *widths[:-1]]).tolist()
    baseline = {
        name: str(imputer.statistics_[index])
        for index, name in enumerate(CATEGORICAL_FEATURES)
    }
    maps: dict[str, dict[str, int]] = {}
    for field_index, name in enumerate(CATEGORICAL_FEATURES):
        start = int(offsets[field_index])
        end = start + int(widths[field_index])
        field_map: dict[str, int] = {}
        for raw_value in encoder.categories_[field_index]:
            sample = pd.DataFrame([{**baseline, name: raw_value}])
            encoded = pipeline.transform(sample[CATEGORICAL_FEATURES])
            row = encoded.toarray()[0] if hasattr(encoded, "toarray") else encoded[0]
            active = np.flatnonzero(row[start:end])
            if len(active):
                field_map[str(raw_value)] = numeric_count + start + int(active[0])
        maps[name] = field_map
    return maps, baseline


def export_linear_model(
    base_frame: pd.DataFrame,
    preprocessor: ColumnTransformer,
    model: LogisticRegression,
    calibration: dict,
    calibration_probability: np.ndarray,
    report: dict,
) -> dict:
    numeric_pipeline = preprocessor.named_transformers_["numeric"]
    imputer: SimpleImputer = numeric_pipeline.named_steps["imputer"]
    scaler: StandardScaler = numeric_pipeline.named_steps["scale"]
    category_maps, category_defaults = category_index_maps(preprocessor)
    return {
        "model_version": MODEL_VERSION,
        "model_type": "Logistic regression trained in Python with point-in-time histories",
        "display_mode": report["display_mode"],
        "target": TARGET,
        "feature_count": int(len(preprocessor.get_feature_names_out())),
        "features": FEATURES,
        "feature_contract": {
            "version": 1,
            "timestamp": "ISO-8601 instant with timezone, normalized to UTC",
            "calendar_timezone": "UTC",
            "weekday": "ISO-8601 Monday=1 through Sunday=7",
            "route": "seller_state + ' → ' + customer_state",
            "history_granularity": "UTC calendar day",
            "history_cutoff": "event day strictly before prediction day",
            "order_count_event": "order_purchase_timestamp",
            "outcome_event": "label_available_timestamp (actual customer delivery)",
        },
        "prediction_domain": {
            "purchase_timestamp_min": base_frame[TIMESTAMP].iloc[0].isoformat(),
            "purchase_timestamp_max": base_frame[TIMESTAMP].iloc[-1].isoformat(),
            "policy": "Historical demonstration only; dates outside the observed Olist range are rejected.",
        },
        "numeric": {
            name: {
                "index": index,
                "median": float(imputer.statistics_[index]),
                "mean": float(scaler.mean_[index]),
                "scale": float(scaler.scale_[index]),
            }
            for index, name in enumerate(NUMERIC_FEATURES)
        },
        "categorical": {
            name: {"default": category_defaults[name], "indices": category_maps[name]}
            for name in CATEGORICAL_FEATURES
        },
        "linear": {
            "intercept": float(model.intercept_[0]),
            "coefficients": [float(value) for value in model.coef_[0]],
        },
        "calibration": calibration["parameters"],
        "risk_score_probability_quantiles": [
            float(value)
            for value in np.quantile(calibration_probability, np.linspace(0, 1, 101))
        ],
        "risk_levels": {"medium_score": 80, "high_score": 90},
        "history": export_daily_histories(base_frame),
        "test_metrics": report["final_test"],
        "limitations": [
            "Historical Olist orders only, September 2016 through August 2018.",
            "Seller and category represent the deterministic highest-value item for multi-seller orders.",
            "The form uses seller state rather than seller ID, so history is a state-level proxy.",
            "Naive source wall-clock timestamps are preserved as UTC calendar values for deterministic cross-runtime features.",
            "The final-period probability calibration is not reliable enough for an exact probability, so the product displays a relative risk rank.",
        ],
    }


def final_candidate_evaluation(
    frame: pd.DataFrame, train_end: int, test_start: int
) -> tuple[dict, dict]:
    x = frame[FEATURES]
    y = frame[TARGET].to_numpy()
    train_rows = np.arange(len(frame)) < train_end
    test_rows = np.arange(len(frame)) >= test_start
    preprocessor = build_preprocessor()
    x_train = preprocessor.fit_transform(x.loc[train_rows])
    x_test = preprocessor.transform(x.loc[test_rows])
    fitted: dict[str, object] = {}
    results: dict[str, dict] = {}
    for name, model in (
        ("logistic", build_linear_model()),
        ("xgboost", build_xgboost_model()),
    ):
        model.fit(x_train, y[train_rows])
        results[name] = ranking_metrics(y[test_rows], model.predict_proba(x_test)[:, 1])
        fitted[name] = (preprocessor, model)
    cat_frame = catboost_frame(frame, train_rows)
    catboost = build_catboost_model()
    catboost.fit(
        cat_frame.loc[train_rows, FEATURES],
        y[train_rows],
        cat_features=CATEGORICAL_FEATURES,
    )
    results["catboost"] = ranking_metrics(
        y[test_rows], catboost.predict_proba(cat_frame.loc[test_rows, FEATURES])[:, 1]
    )
    fitted["catboost"] = catboost
    return results, fitted


def split_report(frame: pd.DataFrame, train_end: int, test_start: int) -> dict:
    y = frame[TARGET].to_numpy()
    sections = {
        "train": (0, train_end),
        "calibration": (train_end, test_start),
        "test": (test_start, len(frame)),
    }
    return {
        name: {
            "rows": end - start,
            "late_orders": int(y[start:end].sum()),
            "late_rate": float(y[start:end].mean()),
            "starts_at": frame[TIMESTAMP].iloc[start].isoformat(),
            "ends_at": frame[TIMESTAMP].iloc[end - 1].isoformat(),
        }
        for name, (start, end) in sections.items()
    }


def write_model_card(report: dict, audit: dict) -> None:
    final = report["final_test"]
    top = final["top_risk_groups"]["10%"]
    ci = final["confidence_intervals_95"]
    candidates = report["final_candidate_test"]
    rows = "\n".join(
        f"| {name.title()} | {result['pr_auc']:.3f} | {result['pr_auc_lift']:.2f}× | {result['roc_auc']:.3f} | {result['top_risk_groups']['10%']['recall']:.1%} |"
        for name, result in candidates.items()
    )
    card = f"""# Olist delivery-delay model card

## Model and data

- Version: `{MODEL_VERSION}`
- Training language: Python (`pandas`, `scikit-learn`; XGBoost and CatBoost benchmarks)
- Production inference: TypeScript reconstruction of the exported logistic pipeline, checked against Python parity fixtures
- Source: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), CC BY-NC-SA 4.0
- Rows: {audit['rows']:,} delivered orders, {audit['target']['positive_rate']:.2%} positive
- Target: delivery more than 24 hours after the estimated delivery timestamp

## Point-in-time policy

Every prediction uses facts available when the order is placed. Order-count histories include purchase days strictly before the prediction day. Late-rate histories include only outcomes whose actual customer-delivery day is strictly before the prediction day. This prevents an earlier purchase with a still-unknown delivery result from leaking its future label.

Source timestamps are naive wall-clock strings. The build preserves their calendar values and marks them UTC; Python and TypeScript both use ISO weekday numbering (Monday=1, Sunday=7). The contract and route separator are embedded in the deployable artifact and verified in CI.

## Selection and held-out evidence

The primary selection rule is mean top-10% delay capture minus its standard deviation across four expanding-window backtests. This represents a fixed investigation capacity and remains interpretable when late-order prevalence changes between periods. PR-AUC lift over prevalence and ROC-AUC are tie-breakers. The newest 15% is untouched until the final evaluation.

| Candidate | PR-AUC | PR-AUC lift | ROC-AUC | Top-10% capture |
| --- | ---: | ---: | ---: | ---: |
{rows}

Selected deployment model: **{report['selected_model']}**.

On {final['rows']:,} final-period orders ({final['late_orders']:,} late), the selected calibrated ranking achieved PR-AUC {final['pr_auc']:.3f} (95% bootstrap CI {ci['pr_auc']['lower_95']:.3f}–{ci['pr_auc']['upper_95']:.3f}), ROC-AUC {final['roc_auc']:.3f}, and captured {top['detected_late_orders']:,}/{final['late_orders']:,} late orders in the highest-risk 10%. That queue had precision {top['precision']:.1%} and {top['false_warnings_per_detected_late_order']:.1f} false warnings per detected delay.

## Serving behavior

The displayed 0–100 value is a percentile-style relative risk score derived from calibration-period predictions. It is not a causal explanation, a delivery guarantee, or an exact probability. “Sensitivity scenarios” compare the submitted order with a fixed reference order one feature group at a time.

## Limitations

- Historical Brazilian marketplace data from 2016–2018 may not transfer to current operations.
- Multi-seller orders use the highest-value item’s seller and category as a deterministic proxy.
- The public form has seller state, not seller ID; seller history is therefore state-level.
- ZIP-prefix medians approximate distance and some physical attributes are missing and imputed.
- Probability calibration did not transfer reliably to the final period; the UI therefore exposes ranking, not probability.
"""
    (ARTIFACTS / "model-card.md").write_text(card, encoding="utf-8")


def main() -> None:
    audit = build_audit()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDIT_FILE.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if audit["blocking_errors"]:
        raise SystemExit(
            "Data validation failed: "
            + json.dumps(audit["blocking_errors"], ensure_ascii=False)
        )
    base_frame = read_orders(DATA_FILE)
    frame = add_temporal_features(base_frame)
    fold_results, summary, selected = backtest_models(frame)
    if selected not in DEPLOYABLE_MODELS:
        raise RuntimeError(
            f"Backtests selected {selected}, but no audited portable exporter exists for it. "
            "Implement and parity-test that exporter before deployment."
        )

    total = len(frame)
    train_end = int(total * FINAL_TRAIN_FRACTION)
    test_start = int(total * CALIBRATION_END_FRACTION)
    final_candidates, fitted_candidates = final_candidate_evaluation(
        frame, train_end, test_start
    )
    preprocessor, model = fitted_candidates[selected]
    x = frame[FEATURES]
    y = frame[TARGET].to_numpy()
    calibration_raw = model.decision_function(
        preprocessor.transform(x.iloc[train_end:test_start])
    )
    test_raw = model.decision_function(preprocessor.transform(x.iloc[test_start:]))
    calibration = choose_calibration(calibration_raw, y[train_end:test_start])
    calibration_probability = calibrated_probability(calibration_raw, calibration)
    test_probability = calibrated_probability(test_raw, calibration)
    ece, calibration_table = expected_calibration_error(
        y[test_start:], test_probability
    )
    probability_quality = {
        "method": calibration["selected"],
        "selection_evaluation": calibration["selection_evaluation"],
        "test_brier": float(brier_score_loss(y[test_start:], test_probability)),
        "test_log_loss": float(
            log_loss(y[test_start:], np.clip(test_probability, 1e-8, 1 - 1e-8))
        ),
        "test_ece": ece,
        "test_mean_prediction": float(test_probability.mean()),
        "test_observed_rate": float(y[test_start:].mean()),
        "calibration_table": calibration_table,
    }
    observed_rate = probability_quality["test_observed_rate"]
    relative_mean_error = (
        abs(probability_quality["test_mean_prediction"] - observed_rate) / observed_rate
    )
    display_mode = (
        "probability" if ece <= 0.02 and relative_mean_error <= 0.20 else "risk_score"
    )
    final_test = {
        **ranking_metrics(y[test_start:], test_probability),
        "rows": int(total - test_start),
        "late_orders": int(y[test_start:].sum()),
        "confidence_intervals_95": bootstrap_confidence_intervals(
            y[test_start:], test_probability
        ),
    }
    report = {
        "model_version": MODEL_VERSION,
        "previous_model_version": PREVIOUS_MODEL_VERSION,
        "selection_rule": (
            "Highest mean top-10% late-order capture minus its standard deviation "
            "across four sequential time backtests; PR-AUC lift and ROC-AUC break ties."
        ),
        "selected_model": selected,
        "backtest_folds": fold_results,
        "backtest_summary": summary,
        "splits": split_report(frame, train_end, test_start),
        "feature_policy": {
            "included": FEATURES,
            "history_cutoff": (
                "Purchase counts use prior purchase days; late rates use only labels "
                "available on prior delivery days."
            ),
            "calendar_contract": "UTC; ISO weekday Monday=1 through Sunday=7.",
            "seller_limitation": "seller_state is a form-compatible state-level proxy.",
            "excluded": [
                "order_id",
                "full timestamp as a unique model value",
                "late_1d",
                "all delivery outcomes and other post-purchase facts",
            ],
        },
        "final_candidate_test": final_candidates,
        "probability_quality": probability_quality,
        "display_mode": display_mode,
        "final_test": final_test,
    }
    export = export_linear_model(
        base_frame,
        preprocessor,
        model,
        calibration,
        calibration_probability,
        report,
    )
    (ARTIFACTS / "metrics.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (ARTIFACTS / "olist-model.json").write_text(
        json.dumps(export, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
    )
    joblib.dump(
        {
            "preprocessor": preprocessor,
            "model": model,
            "calibration": calibration["parameters"],
            "version": MODEL_VERSION,
            "features": FEATURES,
            "feature_contract": export["feature_contract"],
        },
        ARTIFACTS / "olist-model.joblib",
        compress=3,
    )
    fixtures = build_training_fixtures(export, base_frame, frame, preprocessor)
    FIXTURE_FILE.write_text(
        json.dumps(fixtures, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_model_card(report, audit)
    print(
        json.dumps(
            {
                "selected_model": selected,
                "backtest_summary": summary[selected],
                "display_mode": display_mode,
                "probability_quality": probability_quality,
                "final_test": final_test,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
