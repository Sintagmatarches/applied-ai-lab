# Applied AI Lab

Applied AI Lab is a standalone website for practical, evidence-backed
machine-learning tools. The first working project is the Olist Delivery Delay
Predictor.

## Olist predictor

The model estimates whether a delivered order will arrive at least 24 hours
after the promised date (`late_1d = 1`). It uses only facts available when the
order is placed:

- purchase year, month, BigQuery weekday, and hour;
- promised delivery window;
- seller state, customer state, derived route, and same-state flag;
- user-supplied distance;
- item count and primary category;
- item and freight value;
- parcel weight and volume;
- payment type and installment count.

It never uses `order_id`, the full timestamp as an identifier, the target, actual
delivery facts, reviews, or realized delay information.

## Data and validation

The local source is
`data/bq-results-20260727-111149-1785150786733.csv`, exported from BigQuery. It
contains 95,195 rows and 95,195 unique orders from September 2016 through August
2018. There are 6,521 positive targets (6.85%).

Run:

```text
python -m pip install -r requirements-ml.txt
python -m ml.validate_data
```

The audit checks schema, unique orders, target values, missingness, ranges,
dates, duplicates, and derived-field consistency. Its output is
`artifacts/data-audit.json`.

## Chronological experiment

Orders are sorted by `order_purchase_timestamp` and split without shuffling:

- training: 66,636 oldest orders;
- validation and model selection: 14,279 following orders;
- final untouched time test: 14,280 newest orders.

All imputation, scaling, and category encoding are fitted on training data only.
Unknown future categories are accepted by the server and encoded without
failure.

The experiment compares an always-on-time baseline, logistic regression, and
XGBoost. XGBoost was selected on validation PR-AUC and calibrated with Platt
scaling on the validation period. Training writes:

- `artifacts/metrics.json`;
- `artifacts/olist-model.joblib`;
- `artifacts/olist-model.json`;
- `artifacts/model-card.md`.

Retrain reproducibly with:

```text
python -m ml.train_model
```

## Final time-test result

At the 12.34% working threshold, the selected model:

- detects 138 of 620 late orders;
- creates 2,111 false warnings;
- reaches 6.14% precision, 22.26% recall, and 9.62% F1;
- reaches 6.02% PR-AUC and 56.92% ROC-AUC;
- has confusion matrix `[[11549, 2111], [482, 138]]`.

The newest period is materially harder than validation. Mean predicted risk is
6.95% while the observed test rate is 4.34%. The site displays this drift and
does not present the model as a guarantee.

## Server prediction

`POST /api/olist/predict` accepts one raw order. The server derives route,
same-state, and calendar fields; applies the exported training transforms;
evaluates the exact exported XGBoost trees; calibrates the probability; and
returns risk, decision, counterfactual factor explanations, and model version.
The model artifact is not shipped into the client-side form.

## Local development

```text
npm install
npm run dev
```

Validation:

```text
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

## Production

The site is built as a Cloudflare-compatible Worker through Sites. Production
assets receive content hashes; stable favicon and social assets use explicit
version updates for cache busting.
