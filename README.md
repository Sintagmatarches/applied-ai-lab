# Applied AI Lab

Applied AI Lab is a standalone website for practical, evidence-backed
machine-learning tools. Its first working project is the Olist Delivery Delay
Predictor.

## Olist model

The model ranks whether a delivered order is at risk of arriving at least 24
hours after the promised date (`late_1d = 1`). The public result is a relative
risk score from 0 to 100, not an exact probability.

The model uses:

- purchase calendar fields and season;
- promised delivery window;
- seller state, customer state, route, and same-state flag;
- user-supplied distance;
- item count, category, values, parcel size, and payment facts;
- strictly earlier seller-state, route, and category history;
- recent route counts and state/route late rates over 7, 30, and 90 days;
- freight-to-item-value and promised-days-to-distance ratios.

The source export does not contain `seller_id`, and the existing form does not
request it. Seller history is therefore calculated at seller-state level and
is never described as a specific seller's record.

## Leakage protection

Historical features are calculated by date. For any row, only aggregate orders
from dates strictly before that row's purchase date are available. Orders from
the same day and every later date are excluded.

The model never uses `order_id`, the full timestamp as a unique identifier, the
target, actual delivery facts, reviews, or realized delay information.

The export lacks timestamps showing when each historical delay label became
available. Consequently, the pipeline can guarantee earlier purchase dates,
but cannot prove that every earlier order had already completed delivery.

## Data and validation

The local BigQuery export contains 95,195 unique orders from September 2016
through August 2018 and 6,521 positive targets (6.85%).

```text
python -m pip install -r requirements-ml.txt
python -m ml.validate_data
```

The audit is saved to `artifacts/data-audit.json`.

## Multi-period model selection

Logistic regression, XGBoost, and CatBoost are compared on four sequential
backtests: September–October 2017, November–December 2017,
January–February 2018, and March through 14 April 2018.

Selection uses mean PR-AUC minus its standard deviation. Logistic regression
was selected because it had both the strongest mean result and the best
stability:

- mean PR-AUC: 23.77%;
- mean ROC-AUC: 71.47%;
- mean top-10% delay capture: 29.44%.

The later 14,279-order period is reserved for calibration. The newest 14,280
orders remain untouched until final evaluation.

Retrain with:

```text
python -m ml.train_model
```

Training writes `metrics.json`, a compact server model, a reproducible joblib
bundle, and the model card under `artifacts/`.

## Final time-test result

The final period contains 620 late orders.

- PR-AUC: 9.90%;
- ROC-AUC: 72.49%;
- top-risk 5%: 94 late orders found, 15.16% capture;
- top-risk 10%: 170 found, 27.42% capture, 11.90% precision;
- top-risk 20%: 290 found, 46.77% capture, 10.15% precision;
- false warnings per found late order in the top 10%: 7.40.

Version 1's selected XGBoost model had 6.02% PR-AUC and 56.92% ROC-AUC on the
same final period.

## Probability quality

Identity, Platt, and isotonic calibration are compared inside the separate
calibration period. Nevertheless, the final-period mean probability remains
9.53% against an observed 4.34% late rate. The site therefore does not label
the output as a precise probability.

The server maps the internal score to a relative 0–100 risk score based on the
calibration-period score distribution. It is useful for prioritizing orders,
not for guaranteeing that one order will be late.

## Server prediction

`POST /api/olist/predict` accepts the unchanged raw order form. The server:

1. derives route, same-state, season, and calendar fields;
2. retrieves only historical daily aggregates before the supplied date;
3. builds the exact training feature vector;
4. evaluates the exported logistic model;
5. returns risk score, risk level, model version, and counterfactual factors.

The model and historical lookup tables stay in the server bundle.

## Local development and validation

```text
npm install
npm run dev
npm run test:ml
npm test
npm run lint
```

## Routes

- `/` — lab overview
- `/olist-delivery-delay-predictor` — working model and evidence
- `/api/olist/predict` — server inference
- `/housing-value-forecast` — planned
- `/credit-risk-assessment` — planned
- `/document-processing` — planned
- `/image-recognition` — planned

The site is deployed as a Cloudflare-compatible Worker through Sites. Stable
assets use explicit cache-busting versions.
