# Olist Delivery Delay Risk Model

Model version: `olist-logistic-temporal-2026-07-27.2`

## Purpose

Rank, from facts available when an order is placed, which Olist orders are at
greatest risk of arriving at least 24 hours after the promised delivery date.

The public result is a relative risk score, not an exact probability.

## Data

- Source: local BigQuery export of the public Olist order history.
- Rows: 95,195 delivered orders and 95,195 unique `order_id` values.
- Period: 15 September 2016 through 29 August 2018.
- Positive target: 6,521 orders (6.85%).
- Limitation: the export has `seller_state` but no `seller_id`.

## Leakage policy

Every historical feature uses aggregates from dates strictly before the order
date. Orders from the same date and all later dates are excluded. This is more
conservative than row-level shifting and prevents same-timestamp leakage.

The model excludes `order_id`, the full timestamp as a unique value,
`late_1d`, actual delivery dates and durations, reviews, realized delay size,
and every other fact revealed after purchase.

Because the export does not include outcome-availability timestamps, it cannot
prove when an earlier order's delay label became known. This limitation is
explicitly documented.

## Historical and derived features

- previous late rate and order count for the seller state;
- seller-state late rate over the previous 30 and 90 days;
- previous route late rate;
- route order count over the previous 7 and 30 days;
- route late rate over the previous 30 and 90 days;
- previous category late rate;
- seller-state experience in days;
- freight-to-item-value ratio;
- promised days relative to each 500 km;
- season, weekday, and original order-time fields.

State-level seller history is an honest proxy, not a claim about a specific
seller.

## Model selection

Logistic regression, XGBoost, and CatBoost were evaluated on four sequential
time backtests:

1. September–October 2017;
2. November–December 2017;
3. January–February 2018;
4. March through 14 April 2018.

Selection uses mean PR-AUC minus its standard deviation. Logistic regression
won with:

- mean PR-AUC: 23.77%;
- PR-AUC standard deviation: 8.11 percentage points;
- mean ROC-AUC: 71.47%;
- mean capture in the top-risk 10%: 29.44%.

## Final untouched time test

The newest 14,280 orders contain 620 late deliveries.

- PR-AUC: 9.90%.
- ROC-AUC: 72.49%.
- Top-risk 5%: 94 late orders found, 15.16% of all late orders, 6.60 false
  warnings per found late order.
- Top-risk 10%: 170 found, 27.42% capture, 11.90% precision, 1,258 false
  warnings, 7.40 false warnings per found late order.
- Top-risk 20%: 290 found, 46.77% capture, 10.15% precision, 2,566 false
  warnings, 8.85 false warnings per found late order.

## Calibration and display policy

Identity, Platt, and isotonic calibration were compared on a later portion of a
separate chronological calibration period. The identity transform had the best
Brier score there.

On the final test, however, the mean model probability was 9.53% while the
observed late rate was 4.34%; expected calibration error was 5.19 percentage
points. The probabilities are therefore not reliable enough to display as
exact percentages.

The server converts the internal model score into a percentile-like risk score
using the calibration-period score distribution. High risk means score 90 or
higher; medium risk means 80–89; otherwise risk is low.

## Practical interpretation

The new model ranks orders materially better than version 1, but 7.4 false
warnings still accompany every late order found in the highest-risk 10%.
It is useful for prioritizing a review queue, not for automatically deciding
that an individual order will be late.
