# Olist delivery-delay model card

## Model and data

- Version: `olist-logistic-availability-2026-08-05.1`
- Training language: Python (`pandas`, `scikit-learn`; XGBoost and CatBoost benchmarks)
- Production inference: TypeScript reconstruction of the exported logistic pipeline, checked against Python parity fixtures
- Source: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), CC BY-NC-SA 4.0
- Rows: 96,470 delivered orders, 6.77% positive
- Target: delivery more than 24 hours after the estimated delivery timestamp

## Point-in-time policy

Every prediction uses facts available when the order is placed. Order-count histories include purchase days strictly before the prediction day. Late-rate histories include only outcomes whose actual customer-delivery day is strictly before the prediction day. This prevents an earlier purchase with a still-unknown delivery result from leaking its future label.

Source timestamps are naive wall-clock strings. The build preserves their calendar values and marks them UTC; Python and TypeScript both use ISO weekday numbering (Monday=1, Sunday=7). The contract and route separator are embedded in the deployable artifact and verified in CI.

## Selection and final benchmark evidence

The primary selection rule is mean top-10% delay capture minus its standard deviation across four expanding-window backtests. This represents a fixed investigation capacity and remains interpretable when late-order prevalence changes between periods. PR-AUC lift over prevalence and ROC-AUC are tie-breakers. The newest 15% is the final benchmark and is not used for model selection.

| Candidate | PR-AUC | PR-AUC lift | ROC-AUC | Top-10% capture |
| --- | ---: | ---: | ---: | ---: |
| Logistic | 0.063 | 1.48× | 0.634 | 17.3% |
| Xgboost | 0.057 | 1.33× | 0.547 | 15.3% |
| Catboost | 0.066 | 1.55× | 0.616 | 17.1% |

Selected deployment model: **logistic**.

### August 2026 improvement audit

A later development-only search retained seller composition, evaluated point-in-time seller histories and other order-time feature groups, and tuned 18 logistic, 12 XGBoost and 10 CatBoost configurations plus simple blends. The configuration was locked before the existing final benchmark was scored. The frozen blend also captured 107/620 delays, while PR-AUC declined from 0.06320 to 0.06261 and ROC-AUC declined from 0.63439 to 0.59074. Paired bootstrap uncertainty for top-10 capture spanned -16 to +16 delays. It was not a material or stable improvement, so the portable logistic production model was retained unchanged. Full evidence is in `artifacts/olist-improvement-report.md`.

On 14,471 final-benchmark orders (620 late), the selected calibrated ranking achieved PR-AUC 0.063 (95% bootstrap CI 0.057–0.072), ROC-AUC 0.634, and captured 107/620 late orders in the highest-risk 10%. That queue had precision 7.4% and 12.5 false warnings per detected delay.

## Serving behavior

The displayed 0–100 value is a percentile-style relative risk score derived from calibration-period predictions. It is not a causal explanation, a delivery guarantee, or an exact probability. “Sensitivity scenarios” compare the submitted order with a fixed reference order one feature group at a time.

## Limitations

- Historical Brazilian marketplace data from 2016–2018 may not transfer to current operations.
- Multi-seller orders use the highest-value item’s seller and category as a deterministic proxy.
- The public form has seller state, not seller ID; seller history is therefore state-level.
- ZIP-prefix medians approximate distance and some physical attributes are missing and imputed.
- Probability calibration did not transfer reliably to the final period; the UI therefore exposes ranking, not probability.
