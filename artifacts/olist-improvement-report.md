# Olist honest out-of-time ranking improvement report

## Decision

The August 2026 iteration did **not** produce a material, stable improvement over
the deployed logistic baseline. The frozen development winner tied the baseline
at 107/620 delayed orders captured in the highest-risk 10% on the existing final
benchmark, while PR-AUC fell from 0.06320 to 0.06261. It was therefore rejected
for production. The public TypeScript scorer remains the exact portable version
of the evaluated baseline logistic model.

## Protocol

- Target: `late_1d`, actual customer delivery later than the estimated delivery timestamp plus one day.
- Prediction moment: `order_purchase_timestamp`.
- Model-selection metric: mean top-10% delayed-order recall minus its standard deviation.
- Development: four expanding chronological folds ending before 15 April 2018.
- Final benchmark: newest 15% (14,471 orders, 620 delayed); evaluated only after `artifacts/olist-development-lock.json` fixed features, hyperparameters, and blend weights.
- Search: 18 logistic, 12 XGBoost, and 10 CatBoost configurations plus 12 simple rank blends.
- CatBoost safety: all categoricals were fitted by a training-only one-hot encoder. CatBoost received no raw categorical column and therefore constructed no target statistics that could violate delayed-label availability.

## Baseline and feature ablation

All rows below are development folds only. Feature rows use the original
logistic settings so added information is separated from model complexity.

| Cumulative configuration | Mean top-10 recall | Std | Stability score | Mean PR-AUC |
| --- | ---: | ---: | ---: | ---: |
| Current baseline | 26.68% | 2.99% | 23.68% | 0.2106 |
| + seller-level histories | 26.75% | 3.24% | 23.50% | 0.2120 |
| + multi-seller aggregates | 26.70% | 3.42% | 23.28% | 0.2126 |
| + geographic/logistics | 25.21% | 3.56% | 21.65% | 0.2069 |
| + calendar/promise | 24.47% | 3.92% | 20.56% | 0.2025 |
| + workload | 23.92% | 4.44% | 19.48% | 0.1994 |

Targeted seller sub-ablations also failed to improve the primary stability
criterion. The most useful compact structural variant added only
`seller_count`, `multi_seller`, and `category_count`; its stability score was
23.70%, effectively tied with baseline, and it was the feature set taken into
model search. Seller histories did raise mean PR-AUC and ROC-AUC slightly, but
their top-10 recall varied more over time.

## Model search on the locked feature set

| Development candidate | Mean top-10 recall | Std | Stability score | Mean PR-AUC | Mean ROC-AUC |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original logistic settings | 26.70% | 3.00% | 23.70% | 0.2113 | 0.6983 |
| Tuned logistic, L1, C=0.3, no class weight | 27.34% | 3.29% | 24.05% | 0.2172 | 0.7042 |
| Tuned XGBoost | 25.41% | 3.48% | 21.93% | 0.2068 | 0.6808 |
| Tuned CatBoost, SqrtBalanced | 26.27% | 2.24% | 24.03% | 0.2174 | 0.6846 |
| Frozen 25% XGBoost / 75% CatBoost rank blend | 26.83% | 2.58% | **24.25%** | 0.2177 | 0.6871 |

The blend was selected before final-benchmark access. Its fold-by-fold top-10
recall versus baseline was 27.64% vs 25.75%, 22.43% vs 22.21%, 28.89% vs
29.80%, and 28.35% vs 28.95%. It improved only two of four periods, so even the
development gain was small rather than uniformly directional.

## Final benchmark

| Metric | Deployed baseline | Frozen development winner | Change |
| --- | ---: | ---: | ---: |
| Delays captured in top 10% | **107 / 620** | **107 / 620** | 0 |
| Top-10 recall | 17.26% | 17.26% | 0.00 pp |
| Top-10 precision | 7.39% | 7.39% | 0.00 pp |
| PR-AUC / Average Precision | **0.06320** | 0.06261 | -0.00059 |
| PR-AUC lift over prevalence | **1.475x** | 1.461x | -0.014x |
| ROC-AUC | **0.63439** | 0.59074 | -0.04365 |
| Top-5 recall | 8.87% | **11.45%** | +2.58 pp |
| Top-20 recall | **29.68%** | 25.00% | -4.68 pp |

Paired 1,000-sample bootstrap uncertainty for the selected-minus-baseline
top-10 difference was -16 to +16 detected delayed orders (95% interval), or
-2.59 to +2.57 percentage points of recall. The probability of a positive
top-10 difference was 48.5%. PR-AUC difference was also compatible with no
change (-0.00780 to +0.00837). ROC-AUC was reliably worse (-0.0604 to -0.0270).

## Exact feature additions evaluated

- Seller histories: primary seller prior known count, prior order count, prior known late rate, 30/90-day known late rates, 7/30/90-day purchase volume, experience, and recent-to-historical workload ratio.
- Multi-seller: seller/category counts, multi-seller flag, value-weighted and maximum seller late rates, min/max experience, summed recent load, and aggregated workload ratios.
- Geography/logistics: ZIP-region route, distance bucket/log distance, distance per promised day, freight per kilometre/kg/item value, and weight-to-volume ratio.
- Promise/calendar: promised weekday/month/weekend proximity, weekends, deterministic Brazilian national holidays, and business days inside the purchase-to-promise interval.
- Operations: global, route, category, and seller 7/30/90-day purchase volumes and recent-to-historical load ratios.

## Leakage safety

Seller composition and item-value weights are facts present when the order is
placed. Purchase-volume histories use prior purchase events. Outcome histories
use an order's `late_1d` label only on days strictly after its
`label_available_timestamp`; an earlier purchase whose delivery is unresolved
cannot affect a later order. The implementation is deliberately day-granular,
which is conservative for same-day outcomes. Future labels, realised weather,
carrier handoff, reviews, status changes, and actual delivery timestamps are
not model inputs.

## Limitations

- Seller histories were not stable enough to justify production despite small average PR gains.
- Only 1.32% of model rows are multi-seller, limiting the impact of order-composition features.
- The four folds have materially different prevalence, and the final period shifted again.
- The frozen blend is more complex, less portable, and did not improve the business metric; implementing custom TypeScript tree scorers would add brittleness without value.
- The final benchmark is already observed and must remain a benchmark, not be reused for further tuning.

Machine-readable fold metrics, all candidates, the pre-final lock, and final
uncertainty are in `olist-development-search.json`,
`olist-development-lock.json`, and `olist-final-benchmark.json`.
