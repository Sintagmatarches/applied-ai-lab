# Applied AI Lab

[![CI](https://github.com/Sintagmatarches/applied-ai-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/Sintagmatarches/applied-ai-lab/actions/workflows/ci.yml)

Applied machine-learning projects presented as working, evidence-backed web tools.

[Open the live site](https://applied-ai-lab.smjlw.chatgpt.site/) · [Try the Olist predictor](https://applied-ai-lab.smjlw.chatgpt.site/olist-delivery-delay-predictor)

## Olist Delivery Delay Predictor

The first completed project ranks an order's risk of arriving at least 24 hours after the promised date. It returns a relative score from 0 to 100, not an exact probability.

The implementation includes:

- a reproducible Python training and validation pipeline;
- sequential backtests, a separate calibration period, and an untouched final time-test period;
- leakage-aware historical features calculated from strictly earlier purchase dates;
- an exported logistic-regression model evaluated in the server runtime;
- input validation, counterfactual risk factors, and end-to-end API tests.

## Evaluation

The source dataset contains 95,195 unique orders from September 2016 through August 2018. The final time-test contains 14,280 orders, including 620 late deliveries.

| Metric | Final time-test |
| --- | ---: |
| PR-AUC | 9.90% |
| ROC-AUC | 72.49% |
| Late deliveries found in top-risk 10% | 170 of 620 |
| Top-risk 10% precision | 11.90% |

The model is suitable for ranking and operational prioritization. Its output is not presented as a calibrated delivery probability or guarantee.

## Leakage controls

For each row, aggregate route, seller-state, and category features use purchase dates strictly earlier than that row. The model excludes order identifiers, actual delivery facts, reviews, the target, and realized delay information.

The source export does not record when every historical delay label became available. This limitation is stated in the model card and prevents a stronger point-in-time claim.

## Repository structure

- `app/` — interface and prediction API;
- `lib/olist-model.ts` — validation, feature preparation, inference, and factor calculation;
- `ml/` — data validation, temporal features, model selection, calibration, and tests;
- `artifacts/` — model card, audit, metrics, and deployable model artifacts;
- `tests/` — rendered-page and prediction API tests;
- `docs/screenshots/` — filenames reserved for future screenshots.

The raw BigQuery export is excluded from version control.

## Run locally

Requires Node.js 22.13 or later and Python 3.11 or later.

```bash
npm ci
python -m pip install -r requirements-ml.txt
npm run test:ml
npm test
npm run lint
npm run dev
```

Retraining is explicit:

```bash
python -m ml.validate_data
python -m ml.train_model
```

The application is deployed as a Cloudflare-compatible Worker. Stable public assets use explicit cache-busting versions.
