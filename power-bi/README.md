# Power BI analytical component

The Power BI component is designed for a Direct Lake connection to the Fabric Gold tables. The repository contains the star-schema contract, production DAX measures and a page-by-page report specification. A `.pbix`/`.pbip` file and public embed are not fabricated because Power BI Desktop, a Fabric workspace and tenant publishing permissions are not available in this environment.

> **Portfolio simulation.** The simulated stakeholder scenario is documented in `docs/business/`; the source metrics and DAX contract are real repository evidence, while native report deployment remains an explicit manual task.

Implementation pack:

- [`semantic-model.md`](semantic-model.md) — table grain, relationships, types, formatting, reconciliation and lifecycle;
- [`measures.dax`](measures.dax) — threshold-aware executive, route, station, quality and freshness measures;
- [`report-spec.md`](report-spec.md) — page layouts, filters, interactions, tooltips and accessibility;
- [`docs/manual-tasks/power-bi.md`](../docs/manual-tasks/power-bi.md) — only the native Desktop/tenant work that cannot be completed from this repository.

## Semantic model

Relationships are single-direction, one-to-many from dimensions into facts:

- `dim_date[date]` → `fact_train_journey[local_date]` and `fact_station_arrival[local_date]`;
- `dim_route[route_key]` → `fact_train_journey[route_key]`;
- `dim_station[station_code]` → `fact_station_arrival[station_code]`;
- `dim_train_service[service_key]` → `fact_train_journey[service_key]`;
- `delay_threshold` remains disconnected and drives the threshold-aware measures.

Hide technical keys and raw additive flags from report view. Mark `dim_date` as the date table. Format rates as percentages and delays as `0.0 min`. Do not create bidirectional relationships to make a visual work; resolve filter paths in the model.

## Report pages

1. **Executive Overview** — completed journeys, selected-threshold on-time rate, cancellations, median/P90 delay, monthly trend and clear coverage/freshness card.
2. **Routes** — volume/reliability scatter, route ranking with minimum-observation filter, distribution and month consistency. Tooltip includes both directions and sample size.
3. **Stations** — commercial-arrival reliability, missing-actual rate and cancellation rate. Do not label a busy station “worst” without the denominator.
4. **Time Patterns** — weekday, local departure hour, month and train category. Use a single selected threshold across visuals.
5. **Lahti–Helsinki** — direction comparison, time-of-day profile, delay accumulation and direct-service sample sizes.
6. **Weather Study** — overlapping condition groups, matched/unmatched counts and the non-causal warning permanently visible.
7. **Data Quality & Method** — coverage, last refresh, duplicate check, missing actuals, partial/whole cancellation definitions and source attribution.

## Deployment

After the Fabric Lakehouse and semantic model are created:

1. Add the measures from `measures.dax` to a dedicated `_Measures` table.
2. Build and review every page against the sample-size and attribution requirements above.
3. Configure scheduled refresh/Direct Lake fallback according to the tenant capacity.
4. Run the report with at least one mobile layout.
5. Share through an approved workspace/app. Only add a public embed to Applied AI Lab if the tenant owner explicitly accepts that access level and no sensitive data is present.

Microsoft warns that Power BI `Publish to web` allows anyone on the internet to view the report and its underlying detail-level data without authentication. It also requires the relevant Power BI licence and an enabled tenant setting. The project therefore ships the interactive website instead of pretending a safe public Power BI embed already exists.

## Official implementation references

- [Direct Lake overview](https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-overview)
- [TMDL view and Power BI projects](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-tmdl-view)
- [Publish to web security and licence considerations](https://learn.microsoft.com/en-gb/power-bi/collaborate-share/service-publish-to-web)
