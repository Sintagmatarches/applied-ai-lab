# Business requirements

> **Simulated business scenario.** A fictional Network Operations Analytics team needs one public-data monitoring product that supports a rapid national operating view and a reproducible reliability analysis. The scenario is a portfolio simulation, not a real brief from a Finnish rail operator or authority.

## Stakeholders and decisions

| Simulated stakeholder | Decision supported | Cadence |
| --- | --- | --- |
| Head of Network Operations | Where should an analyst investigate disruption now? | Live / intraday |
| Service Performance Manager | Which regions, routes, stations and train types are persistently less reliable? | Weekly / monthly |
| Data Product Owner | Is the refresh complete, explainable and safe to publish? | Every refresh |
| Executive sponsor | Is reliability changing materially, and where is attention required? | Monthly |

## Business problem

Public train events are detailed but operationally difficult to scan. A decision-maker needs a region-first map, consistent delay definitions, transparent data quality and enough drill-down to move from a national exception to a station or route. An analyst also needs a dated historical layer for repeatable comparisons without confusing live estimates with completed outcomes.

## Scope

In scope:

- all 19 Finnish maakunta boundaries from Statistics Finland;
- passenger trains in Digitraffic categories `Long-distance` and `Commuter`;
- LIVE, rolling 24-hour and committed historical views;
- policy-selectable delay thresholds of 5, 10, 15 and 30 whole minutes;
- regional train observations, measured trains, delayed share, average delay, serious delays over 15 minutes, cancellations and a documented disruption score;
- drill-down to problem stations/routes, with sample and missing-data context;
- reproducible historical pipeline, Power BI semantic-model specification and Microsoft Fabric deployment design;
- automated rejection of invalid daily source partitions.

Out of scope:

- causal claims about weather, infrastructure or operator behaviour;
- predictions, passenger counts, ticketing, revenue or monetary benefit estimates;
- an operational SLA or endorsement from the public-data providers;
- native Power BI/Fabric deployment without access to a licensed tenant and Power BI Desktop.

## KPI contract

| ID | KPI | Definition | Denominator / missing-data rule |
| --- | --- | --- | --- |
| KPI-01 | Observed trains | One passenger train per region when at least one commercial passenger stop is inside the selected window | A cross-region train is counted once in each visited region |
| KPI-02 | Measured trains | Observed, non-cancelled trains with actual timing, or a live estimate in LIVE mode | Never infer a missing observation as on time |
| KPI-03 | Delayed trains | Measured trains whose maximum regional stop delay is strictly greater than the selected 5/10/15/30-minute threshold | Measured trains only |
| KPI-04 | Delay share | KPI-03 ÷ KPI-02 | Blank when KPI-02 is zero |
| KPI-05 | Average delay | Mean maximum regional stop delay across measured trains | Early trains remain negative; the score uses only the positive component |
| KPI-06 | Serious delays | Measured trains more than 15 whole minutes late | Fixed incident-severity definition, independent of selected policy threshold |
| KPI-07 | Cancellations | Observed trains cancelled at train level or in the region | KPI-01 for cancellation share |
| KPI-08 | Disruption score | 0–100 composite: 45% selected-threshold delay share, 25% serious-delay share, 20% cancellation share, 10% positive average delay capped at 30 minutes | `100 - disruption score` is the display reliability score; descriptive index, not an official rail KPI |
| KPI-09 | On-time rate (historical BI) | Completed journeys at or below selected threshold ÷ completed journeys | Cancelled or missing-final-actual journeys excluded from completed denominator and exposed separately |

## Functional requirements

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| BR-01 | Present one current national operating picture by maakunta | Map contains 19 regions, exposes Normal/Elevated/Serious/No data/No rail service states and keeps Åland out of scoring |
| BR-02 | Apply a consistent delay-policy selection | User can select 5, 10, 15 or 30 minutes; national and regional delayed counts/shares and score respond without another source request |
| BR-03 | Preserve incident severity while policy changes | Serious delay count remains `>15` for every selected delay threshold |
| BR-04 | Enable exception drill-down | Selected region exposes observation coverage, cancellations and ranked problem stations/routes under the selected threshold |
| BR-05 | Separate current and completed evidence | LIVE may use current estimates; 24 HOURS and HISTORICAL use actual timing only; the UI labels the time window and source freshness |
| BR-06 | Fail honestly | Current-source failures show an unavailable state; no historical or synthetic data is relabelled as live |
| BR-07 | Prevent invalid partition publication | Empty, non-array, passenger-empty or wrong-date daily train partitions fail before the cache/bronze write is committed |
| BR-08 | Make the historical analysis reproducible | Source dates, transformation rules, metric definitions, quality findings and commands are documented and tested |
| BR-09 | Prepare governed BI delivery | Semantic model, DAX, report interactions, quality page and Fabric medallion/orchestration design are versioned; native tenant work remains a named manual task |

## Non-functional requirements

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| NFR-01 | Traceability | Every released simulated request links to requirements, implementation, automated tests and release notes |
| NFR-02 | Accessibility | Map regions are keyboard selectable and carry readable status labels; controls expose pressed state |
| NFR-03 | Performance | Threshold switching is client-side over one snapshot and does not refetch Digitraffic |
| NFR-04 | Reproducibility | Node, TypeScript, Python rail tests and CI commands are documented and pass from committed source |
| NFR-05 | Cache safety | User-visible release changes increment the site asset/API cache version before production deployment |

## Definition of Done

A change is done only when acceptance criteria are met, automated tests cover the failure-prone logic, definitions and limitations are updated, the full relevant test suite passes, source is committed and pushed, and the public deployment is built from that exact commit. Native Power BI/Fabric tasks that require user credentials are not silently marked complete.
