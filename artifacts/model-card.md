# Olist Delivery Delay Predictor

Model version: `olist-xgb-2026-07-27.1`

## Purpose

Estimate, from facts available when an order is placed, whether an Olist order
will be delivered at least 24 hours after its promised delivery date.

## Data

- Source: a local BigQuery export of the public Olist order history.
- Rows: 95,195 delivered orders, one unique `order_id` per row.
- Period: 15 September 2016 through 29 August 2018.
- Positive target: 6,521 orders (6.85%).

## Leakage policy

The model excludes `order_id`, the full timestamp, `late_1d`, actual delivery
dates and durations, reviews, realized delay size, and every other fact revealed
after purchase. The full timestamp is used only for chronological sorting and
to derive year, month, BigQuery weekday, and hour.

## Time split

- Training: 66,636 oldest orders, through 15 April 2018.
- Validation: 14,279 following orders, through 20 June 2018.
- Final test: 14,280 newest orders, through 29 August 2018.

Imputation, scaling, category encoding, model fitting, calibration, and working
threshold selection do not use the final test labels.

## Selection

The compared candidates were an always-on-time baseline, logistic regression,
and XGBoost. XGBoost had the best validation PR-AUC (14.89%) and was selected
before final-test evaluation. Platt calibration was fitted on validation
margins. The working threshold (12.34%) maximizes validation F2 while limiting
the validation alert rate to 7.5%.

## Final time-test result

- Detected late orders: 138 of 620.
- False warnings: 2,111.
- Precision: 6.14%.
- Recall: 22.26%.
- F1: 9.62%.
- PR-AUC: 6.02%.
- ROC-AUC: 56.92%.
- Confusion matrix: `[[11549, 2111], [482, 138]]`.

At the standard 0.5 threshold the model detects only 4 late orders. The lower
working threshold is retained because the demonstration prioritizes detecting
more risky orders while still flagging a minority of orders.

## Probability quality and limitations

The final-period Brier score is 0.0463. Mean predicted risk is 6.95%, while the
observed final-period rate is 4.34%, so probabilities remain overestimated.
Both delay prevalence and the relationship between features and delays drift
over time. The final-period PR-AUC and ROC-AUC are weak and must be shown
alongside every prediction experience.

This model is a historical demonstration, not an operational delivery
guarantee. Exact distance is supplied by the user because state codes alone
cannot determine it.
