"""Chronological development-only feature ablation and bounded model search.

This module never reads or scores the newest 15% final benchmark. It writes a
lock artifact containing the feature list, model parameters, and optional blend
weights that must exist before final-benchmark evaluation is allowed.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from ml.common import (
    BASELINE_FEATURES,
    CATEGORICAL_FEATURES,
    DATA_FILE,
    FEATURE_GROUPS,
    NUMERIC_FEATURES,
    TARGET,
    TIMESTAMP,
    read_orders,
)
from ml.temporal_features import add_temporal_features

ARTIFACTS = Path("artifacts")
DEVELOPMENT_REPORT_FILE = ARTIFACTS / "olist-development-search.json"
DEVELOPMENT_LOCK_FILE = ARTIFACTS / "olist-development-lock.json"
RANDOM_SEED = 42


@dataclass(frozen=True)
class DevelopmentFold:
    name: str
    starts_at: str
    ends_at: str


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    family: str
    parameters: dict[str, Any]


DEVELOPMENT_FOLDS = (
    DevelopmentFold("2017-09/10", "2017-09-01", "2017-11-01"),
    DevelopmentFold("2017-11/12", "2017-11-01", "2018-01-01"),
    DevelopmentFold("2018-01/02", "2018-01-01", "2018-03-01"),
    DevelopmentFold("2018-03/04", "2018-03-01", "2018-04-15"),
)


LOGISTIC_CANDIDATES = tuple(
    Candidate(
        f"logistic-c{str(c).replace('.', '_')}-{weight_name}-{penalty}",
        "logistic",
        {"C": c, "class_weight": class_weight, "penalty": penalty},
    )
    for c, weight_name, class_weight, penalty in (
        (0.03, "none", None, "l2"),
        (0.10, "none", None, "l2"),
        (0.30, "none", None, "l2"),
        (1.00, "none", None, "l2"),
        (3.00, "none", None, "l2"),
        (0.10, "balanced", "balanced", "l2"),
        (0.30, "balanced", "balanced", "l2"),
        (1.00, "balanced", "balanced", "l2"),
        (0.10, "positive2", {0: 1.0, 1: 2.0}, "l2"),
        (0.30, "positive2", {0: 1.0, 1: 2.0}, "l2"),
        (1.00, "positive2", {0: 1.0, 1: 2.0}, "l2"),
        (0.10, "positive4", {0: 1.0, 1: 4.0}, "l2"),
        (0.30, "positive4", {0: 1.0, 1: 4.0}, "l2"),
        (1.00, "positive4", {0: 1.0, 1: 4.0}, "l2"),
        (0.03, "none", None, "l1"),
        (0.10, "none", None, "l1"),
        (0.30, "none", None, "l1"),
        (0.30, "balanced", "balanced", "l1"),
    )
)


def _xgb(candidate_id: str, **changes: Any) -> Candidate:
    parameters: dict[str, Any] = {
        "n_estimators": 350,
        "max_depth": 3,
        "learning_rate": 0.05,
        "min_child_weight": 10,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "reg_alpha": 0.1,
        "reg_lambda": 3.0,
        "scale_pos_weight": 1.0,
    }
    parameters.update(changes)
    return Candidate(candidate_id, "xgboost", parameters)


XGBOOST_CANDIDATES = (
    _xgb("xgb-baseline"),
    _xgb("xgb-more-trees", n_estimators=650, learning_rate=0.03),
    _xgb("xgb-shallow", max_depth=2, n_estimators=500),
    _xgb("xgb-deep", max_depth=5, min_child_weight=15),
    _xgb("xgb-fast", n_estimators=250, learning_rate=0.08),
    _xgb("xgb-small-child", min_child_weight=3),
    _xgb("xgb-row-subsample", subsample=0.70),
    _xgb("xgb-column-subsample", colsample_bytree=0.65),
    _xgb("xgb-alpha", reg_alpha=0.75),
    _xgb("xgb-lambda", reg_lambda=10.0),
    _xgb("xgb-positive2", scale_pos_weight=2.0),
    _xgb("xgb-positive4", scale_pos_weight=4.0),
)


def _cat(candidate_id: str, **changes: Any) -> Candidate:
    parameters: dict[str, Any] = {
        "iterations": 500,
        "depth": 6,
        "learning_rate": 0.05,
        "l2_leaf_reg": 5.0,
        "class_weights": None,
        "auto_class_weights": None,
    }
    parameters.update(changes)
    return Candidate(candidate_id, "catboost", parameters)


CATBOOST_CANDIDATES = (
    _cat("cat-baseline"),
    _cat("cat-shallow", depth=4, iterations=700, learning_rate=0.03),
    _cat("cat-deep", depth=8, iterations=400),
    _cat("cat-fast", iterations=350, learning_rate=0.08),
    _cat("cat-low-l2", l2_leaf_reg=2.0),
    _cat("cat-high-l2", l2_leaf_reg=15.0),
    _cat("cat-positive2", class_weights=[1.0, 2.0]),
    _cat("cat-positive4", class_weights=[1.0, 4.0]),
    _cat("cat-sqrt-balanced", auto_class_weights="SqrtBalanced"),
    _cat(
        "cat-regularized-sqrt",
        depth=5,
        iterations=700,
        learning_rate=0.03,
        l2_leaf_reg=10.0,
        auto_class_weights="SqrtBalanced",
    ),
)


def build_preprocessor(feature_names: list[str]) -> ColumnTransformer:
    """Fit imputers/encoders on older training rows only."""

    numeric = [name for name in feature_names if name in NUMERIC_FEATURES]
    categorical = [name for name in feature_names if name in CATEGORICAL_FEATURES]
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
                numeric,
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
                categorical,
            ),
        ]
    )


def top_group_metrics(
    y_true: np.ndarray, score: np.ndarray, fraction: float
) -> dict[str, Any]:
    """Measure a fixed highest-risk review queue with stable tie handling."""

    size = max(1, int(math.ceil(len(score) * fraction)))
    selected = np.argsort(-score, kind="stable")[:size]
    found = int(y_true[selected].sum())
    false_warnings = int(size - found)
    total_late = int(y_true.sum())
    return {
        "fraction": fraction,
        "orders": size,
        "detected_late_orders": found,
        "precision": float(found / size),
        "recall": float(found / total_late) if total_late else 0.0,
        "false_warnings": false_warnings,
        "false_warnings_per_detected_late_order": (
            float(false_warnings / found) if found else None
        ),
    }


def ranking_metrics(y_true: np.ndarray, score: np.ndarray) -> dict[str, Any]:
    prevalence = float(y_true.mean())
    average_precision = float(average_precision_score(y_true, score))
    return {
        "prevalence": prevalence,
        "pr_auc": average_precision,
        "pr_auc_lift": average_precision / prevalence if prevalence else None,
        "roc_auc": float(roc_auc_score(y_true, score)),
        "top_risk_groups": {
            f"{round(fraction * 100)}%": top_group_metrics(y_true, score, fraction)
            for fraction in (0.05, 0.10, 0.20)
        },
    }


def summarize_folds(folds: list[dict[str, Any]]) -> dict[str, float]:
    """Summarize every reported ranking metric across chronological folds."""

    summary: dict[str, float] = {}
    paths = {
        "pr_auc": lambda fold: fold["pr_auc"],
        "pr_auc_lift": lambda fold: fold["pr_auc_lift"],
        "roc_auc": lambda fold: fold["roc_auc"],
        "top_5_recall": lambda fold: fold["top_risk_groups"]["5%"]["recall"],
        "top_5_precision": lambda fold: fold["top_risk_groups"]["5%"]["precision"],
        "top_10_recall": lambda fold: fold["top_risk_groups"]["10%"]["recall"],
        "top_10_precision": lambda fold: fold["top_risk_groups"]["10%"]["precision"],
        "top_20_recall": lambda fold: fold["top_risk_groups"]["20%"]["recall"],
        "top_20_precision": lambda fold: fold["top_risk_groups"]["20%"]["precision"],
        "false_warnings_per_detected_late_order": lambda fold: fold[
            "top_risk_groups"
        ]["10%"]["false_warnings_per_detected_late_order"],
    }
    for name, getter in paths.items():
        values = np.array([getter(fold) for fold in folds], dtype=float)
        summary[f"mean_{name}"] = float(values.mean())
        summary[f"std_{name}"] = float(values.std())
    summary["operational_stability_score"] = (
        summary["mean_top_10_recall"] - summary["std_top_10_recall"]
    )
    return summary


def _candidate_model(candidate: Candidate):
    if candidate.family == "logistic":
        return LogisticRegression(
            max_iter=1_500,
            solver="liblinear",
            random_state=RANDOM_SEED,
            **candidate.parameters,
        )
    if candidate.family == "xgboost":
        return XGBClassifier(
            objective="binary:logistic",
            eval_metric="aucpr",
            n_jobs=4,
            random_state=RANDOM_SEED,
            **candidate.parameters,
        )
    parameters = dict(candidate.parameters)
    if parameters.get("class_weights") is None:
        parameters.pop("class_weights")
    if parameters.get("auto_class_weights") is None:
        parameters.pop("auto_class_weights")
    return CatBoostClassifier(
        loss_function="Logloss",
        eval_metric="PRAUC:type=Classic",
        random_seed=RANDOM_SEED,
        verbose=False,
        allow_writing_files=False,
        thread_count=4,
        **parameters,
    )


def _fold_masks(
    frame: pd.DataFrame, fold: DevelopmentFold
) -> tuple[np.ndarray, np.ndarray]:
    timestamps = frame[TIMESTAMP]
    start = pd.Timestamp(fold.starts_at, tz="UTC")
    end = pd.Timestamp(fold.ends_at, tz="UTC")
    return (timestamps < start).to_numpy(), (
        (timestamps >= start) & (timestamps < end)
    ).to_numpy()


def _fit_predict(
    candidate: Candidate,
    x_train,
    y_train: np.ndarray,
    x_validation,
    y_validation: np.ndarray,
) -> tuple[np.ndarray, int | None]:
    model = _candidate_model(candidate)
    if candidate.family == "catboost":
        # Inputs are manually imputed/scaled/one-hot encoded. CatBoost never
        # receives a categorical column, so it cannot construct ordinary
        # ordered target statistics that ignore delayed label availability.
        model.fit(
            x_train,
            y_train,
            eval_set=(x_validation, y_validation),
            early_stopping_rounds=60,
            verbose=False,
        )
        best_iteration = int(model.get_best_iteration())
    else:
        model.fit(x_train, y_train)
        best_iteration = None
    return model.predict_proba(x_validation)[:, 1], best_iteration


def _feature_stages() -> list[tuple[str, list[str]]]:
    stages: list[tuple[str, list[str]]] = [("current_baseline", list(BASELINE_FEATURES))]
    features = list(BASELINE_FEATURES)
    for stage, group in (
        ("plus_seller_histories", "seller_history"),
        ("plus_multi_seller", "multi_seller"),
        ("plus_geographic", "geographic"),
        ("plus_calendar_promise", "calendar"),
        ("plus_workload", "workload"),
    ):
        features = [*features, *FEATURE_GROUPS[group]]
        stages.append((stage, list(dict.fromkeys(features))))
    return stages


def run_ablation(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Evaluate cumulative information additions with the old model settings."""

    y = frame[TARGET].to_numpy(dtype=int)
    baseline_candidate = Candidate(
        "logistic-baseline-c0_5", "logistic", {"C": 0.5, "class_weight": None, "penalty": "l2"}
    )
    output: list[dict[str, Any]] = []
    for stage, features in _feature_stages():
        fold_metrics: list[dict[str, Any]] = []
        for fold in DEVELOPMENT_FOLDS:
            train_rows, validation_rows = _fold_masks(frame, fold)
            preprocessor = build_preprocessor(features)
            x_train = preprocessor.fit_transform(frame.loc[train_rows, features])
            x_validation = preprocessor.transform(frame.loc[validation_rows, features])
            score, _ = _fit_predict(
                baseline_candidate,
                x_train,
                y[train_rows],
                x_validation,
                y[validation_rows],
            )
            fold_metrics.append(
                {
                    "period": fold.name,
                    "train_rows": int(train_rows.sum()),
                    "validation_rows": int(validation_rows.sum()),
                    **ranking_metrics(y[validation_rows], score),
                }
            )
        output.append(
            {
                "stage": stage,
                "feature_count": len(features),
                "features": features,
                "folds": fold_metrics,
                "summary": summarize_folds(fold_metrics),
            }
        )
        print(
            f"Ablation {stage}: "
            f"top10={output[-1]['summary']['mean_top_10_recall']:.3f} "
            f"stability={output[-1]['summary']['operational_stability_score']:.3f}",
            flush=True,
        )
    return output


def run_logistic_feature_variants(
    frame: pd.DataFrame,
    variants: list[tuple[str, list[str]]],
) -> list[dict[str, Any]]:
    """Compare targeted feature subsets under identical baseline fitting."""

    y = frame[TARGET].to_numpy(dtype=int)
    candidate = Candidate(
        "logistic-baseline-c0_5",
        "logistic",
        {"C": 0.5, "class_weight": None, "penalty": "l2"},
    )
    results: list[dict[str, Any]] = []
    for name, additions in variants:
        features = list(dict.fromkeys([*BASELINE_FEATURES, *additions]))
        folds: list[dict[str, Any]] = []
        for fold in DEVELOPMENT_FOLDS:
            train_rows, validation_rows = _fold_masks(frame, fold)
            preprocessor = build_preprocessor(features)
            x_train = preprocessor.fit_transform(frame.loc[train_rows, features])
            x_validation = preprocessor.transform(frame.loc[validation_rows, features])
            score, _ = _fit_predict(
                candidate,
                x_train,
                y[train_rows],
                x_validation,
                y[validation_rows],
            )
            folds.append(
                {
                    "period": fold.name,
                    "train_rows": int(train_rows.sum()),
                    "validation_rows": int(validation_rows.sum()),
                    **ranking_metrics(y[validation_rows], score),
                }
            )
        result = {
            "stage": name,
            "feature_count": len(features),
            "features": features,
            "folds": folds,
            "summary": summarize_folds(folds),
        }
        results.append(result)
        print(
            f"Variant {name}: top10={result['summary']['mean_top_10_recall']:.3f} "
            f"stability={result['summary']['operational_stability_score']:.3f} "
            f"pr={result['summary']['mean_pr_auc']:.3f}",
            flush=True,
        )
    return results


def seller_feature_variants() -> list[tuple[str, list[str]]]:
    primary_core = [
        "primary_seller_prior_late_rate",
        "primary_seller_prior_known_count_log",
        "primary_seller_prior_order_count_log",
        "primary_seller_experience_days_log",
    ]
    primary_windows = [
        "primary_seller_late_rate_30d",
        "primary_seller_late_rate_90d",
    ]
    primary_volume = [
        "primary_seller_order_count_7d_log",
        "primary_seller_order_count_30d_log",
        "primary_seller_order_count_90d_log",
        "primary_seller_workload_ratio_log",
    ]
    structure = ["seller_count", "multi_seller", "category_count"]
    multi_rates = [
        "seller_prior_late_rate_weighted",
        "seller_prior_late_rate_max",
        "seller_late_rate_30d_weighted",
        "seller_late_rate_30d_max",
        "seller_late_rate_90d_weighted",
        "seller_late_rate_90d_max",
    ]
    multi_operations = [
        "seller_experience_days_log_min",
        "seller_experience_days_log_max",
        "seller_order_count_7d_log_sum",
        "seller_order_count_30d_log_sum",
        "seller_workload_ratio_log_weighted",
        "seller_workload_ratio_log_max",
    ]
    return [
        ("seller_primary_core", primary_core),
        ("seller_primary_core_windows", [*primary_core, *primary_windows]),
        ("seller_primary_all", [*primary_core, *primary_windows, *primary_volume]),
        ("multi_structure_only", structure),
        ("seller_core_plus_structure", [*primary_core, *structure]),
        (
            "seller_rates_plus_structure",
            [*primary_core, *primary_windows, *structure, *multi_rates],
        ),
        (
            "seller_all_multi",
            [
                *primary_core,
                *primary_windows,
                *primary_volume,
                *structure,
                *multi_rates,
                *multi_operations,
            ],
        ),
    ]


def _candidate_key(result: dict[str, Any]) -> tuple[float, float, float]:
    summary = result["summary"]
    return (
        summary["operational_stability_score"],
        summary["mean_pr_auc_lift"],
        summary["mean_roc_auc"],
    )


def run_model_search(
    frame: pd.DataFrame, features: list[str]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, np.ndarray]]]:
    """Run the declared bounded search on development folds only."""

    y = frame[TARGET].to_numpy(dtype=int)
    candidates = (*LOGISTIC_CANDIDATES, *XGBOOST_CANDIDATES, *CATBOOST_CANDIDATES)
    folds_by_candidate: dict[str, list[dict[str, Any]]] = {
        candidate.candidate_id: [] for candidate in candidates
    }
    scores_by_candidate: dict[str, dict[str, np.ndarray]] = {
        candidate.candidate_id: {} for candidate in candidates
    }
    for fold in DEVELOPMENT_FOLDS:
        train_rows, validation_rows = _fold_masks(frame, fold)
        preprocessor = build_preprocessor(features)
        x_train = preprocessor.fit_transform(frame.loc[train_rows, features])
        x_validation = preprocessor.transform(frame.loc[validation_rows, features])
        for index, candidate in enumerate(candidates, start=1):
            score, best_iteration = _fit_predict(
                candidate,
                x_train,
                y[train_rows],
                x_validation,
                y[validation_rows],
            )
            metric = {
                "period": fold.name,
                "train_rows": int(train_rows.sum()),
                "validation_rows": int(validation_rows.sum()),
                **ranking_metrics(y[validation_rows], score),
            }
            if best_iteration is not None:
                metric["best_iteration"] = best_iteration
            folds_by_candidate[candidate.candidate_id].append(metric)
            scores_by_candidate[candidate.candidate_id][fold.name] = score
            print(
                f"Search {fold.name} {index}/{len(candidates)} "
                f"{candidate.candidate_id}: top10={metric['top_risk_groups']['10%']['recall']:.3f}",
                flush=True,
            )
    results = [
        {
            **asdict(candidate),
            "folds": folds_by_candidate[candidate.candidate_id],
            "summary": summarize_folds(folds_by_candidate[candidate.candidate_id]),
        }
        for candidate in candidates
    ]
    return results, scores_by_candidate


def _rank_fraction(score: np.ndarray) -> np.ndarray:
    order = np.argsort(score, kind="stable")
    ranks = np.empty(len(score), dtype=float)
    ranks[order] = np.arange(len(score), dtype=float)
    return ranks / max(len(score) - 1, 1)


def evaluate_blends(
    frame: pd.DataFrame,
    search_results: list[dict[str, Any]],
    scores_by_candidate: dict[str, dict[str, np.ndarray]],
) -> list[dict[str, Any]]:
    """Tune simple rank blends among each family's development winner."""

    y = frame[TARGET].to_numpy(dtype=int)
    winners = {
        family: max(
            (result for result in search_results if result["family"] == family),
            key=_candidate_key,
        )
        for family in ("logistic", "xgboost", "catboost")
    }
    weight_sets: list[tuple[float, float, float]] = []
    for logistic_weight in (0.0, 0.25, 0.5, 0.75, 1.0):
        for xgb_weight in (0.0, 0.25, 0.5, 0.75, 1.0):
            cat_weight = 1.0 - logistic_weight - xgb_weight
            if cat_weight < 0 or cat_weight > 1:
                continue
            if sum(weight > 0 for weight in (logistic_weight, xgb_weight, cat_weight)) < 2:
                continue
            weight_sets.append((logistic_weight, xgb_weight, cat_weight))
    output: list[dict[str, Any]] = []
    for weights in weight_sets:
        fold_metrics: list[dict[str, Any]] = []
        for fold in DEVELOPMENT_FOLDS:
            _, validation_rows = _fold_masks(frame, fold)
            blended = np.zeros(int(validation_rows.sum()), dtype=float)
            for weight, family in zip(
                weights, ("logistic", "xgboost", "catboost"), strict=True
            ):
                if weight:
                    candidate_id = winners[family]["candidate_id"]
                    blended += weight * _rank_fraction(
                        scores_by_candidate[candidate_id][fold.name]
                    )
            fold_metrics.append(
                {
                    "period": fold.name,
                    "validation_rows": int(validation_rows.sum()),
                    **ranking_metrics(y[validation_rows], blended),
                }
            )
        candidate_id = "rank-blend-" + "-".join(
            f"{family}{weight:.2f}"
            for family, weight in zip(
                ("log", "xgb", "cat"), weights, strict=True
            )
            if weight
        )
        output.append(
            {
                "candidate_id": candidate_id,
                "family": "rank_blend",
                "parameters": {
                    "weights": dict(
                        zip(("logistic", "xgboost", "catboost"), weights, strict=True)
                    ),
                    "components": {
                        family: winner["candidate_id"]
                        for family, winner in winners.items()
                    },
                },
                "folds": fold_metrics,
                "summary": summarize_folds(fold_metrics),
            }
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lock Olist features and model using development backtests only."
    )
    parser.parse_args()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    base_frame = read_orders(DATA_FILE)
    # The final benchmark begins at 85%. It is present only so histories for
    # earlier rows can be generated; future outcomes cannot affect earlier
    # features because all history lookups are strictly backward-looking.
    frame = add_temporal_features(base_frame)
    ablation = run_ablation(frame)
    seller_variants = run_logistic_feature_variants(frame, seller_feature_variants())
    feature_candidates = [*ablation, *seller_variants]
    selected_feature_result = max(
        feature_candidates,
        key=lambda result: (
            result["summary"]["operational_stability_score"],
            result["summary"]["mean_pr_auc_lift"],
            result["summary"]["mean_roc_auc"],
        ),
    )
    selected_features = selected_feature_result["features"]
    search_results, scores = run_model_search(frame, selected_features)
    blends = evaluate_blends(frame, search_results, scores)
    all_candidates = [*search_results, *blends]
    selected = max(all_candidates, key=_candidate_key)
    report = {
        "protocol": {
            "selection_metric": "mean(top_10_recall) - std(top_10_recall)",
            "folds": [asdict(fold) for fold in DEVELOPMENT_FOLDS],
            "final_benchmark_fraction": 0.15,
            "final_benchmark_evaluated": False,
            "catboost_delayed_label_policy": (
                "Only manually constructed point-in-time numeric histories and "
                "one-hot order-time categories are supplied; CatBoost target "
                "statistics are disabled by construction."
            ),
        },
        "ablation": ablation,
        "seller_feature_variants": seller_variants,
        "feature_search_choice": {
            "stage": selected_feature_result["stage"],
            "feature_count": len(selected_features),
            "features": selected_features,
            "summary": selected_feature_result["summary"],
        },
        "candidate_results": all_candidates,
        "selected": selected,
    }
    DEVELOPMENT_REPORT_FILE.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lock = {
        "locked_before_final_benchmark": True,
        "selection_metric": report["protocol"]["selection_metric"],
        "feature_stage": selected_feature_result["stage"],
        "features": selected_features,
        "selected_candidate_id": selected["candidate_id"],
        "selected_family": selected["family"],
        "parameters": selected["parameters"],
        "development_summary": selected["summary"],
    }
    DEVELOPMENT_LOCK_FILE.write_text(
        json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(lock, indent=2), flush=True)


if __name__ == "__main__":
    main()
