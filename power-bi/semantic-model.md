# Power BI semantic-model contract

> **Portfolio simulation.** This is an implementation-ready model specification, not evidence that a PBIX/PBIP or tenant dataset has been deployed.

## Tables and grain

| Model table | Source | Grain | Required key |
| --- | --- | --- | --- |
| `Fact Train Journey` | `rail_gold_fact_train_journey` | one Digitraffic `departureDate:trainNumber` passenger journey | `Journey Key` |
| `Fact Station Arrival` | `rail_gold_fact_station_arrival` | one commercial stopping arrival at a Finnish passenger station | `Journey Key` + `Station Code` + scheduled time |
| `Fact Lahti Helsinki Weather` | weather gold table | one direct segment service matched to nearest allowed departure-side observation | segment `Journey Key` |
| `Dim Date` | generated gold dimension | one Finland-local calendar date | `Date` |
| `Dim Route` | distinct journey route keys | one canonical undirected endpoint pair | `Route Key` |
| `Dim Station` | official station metadata | one station code | `Station Code` |
| `Dim Train Service` | distinct category/type/commuter-line combinations | one `Service Key` | `Service Key` |
| `Delay Threshold` | disconnected DATATABLE | one row for 5, 10, 15 or 30 minutes | `Minutes` |
| `Ingestion Audit` | `rail_control_ingestion` | one source-partition attempt | source + partition + retrieval timestamp |

Future BL-005 adds `Dim Region`, `Bridge Station Region` and `Fact Region Snapshot`; do not force region into the current journey model through an ambiguous many-to-many relationship.

## Relationships

All active analytical relationships are `1:*`, single direction, dimension to fact:

```text
Dim Date ───────┬─> Fact Train Journey <─ Dim Route
                └─> Fact Station Arrival <─ Dim Station
Dim Train Service ─> Fact Train Journey
Delay Threshold      (disconnected; read by DAX)
Ingestion Audit      (quality/freshness table; no fact relationship required)
```

`Dim Date[Date]` is the marked date table. Create inactive date relationships only for a named alternative date role and activate them in an explicit measure. Do not enable bi-directional filtering to repair a visual.

## Types and formatting

| Field / measure class | Type | Format |
| --- | --- | --- |
| Date keys | Date (not DateTime) | `yyyy-mm-dd` |
| UTC retrieval/schedule timestamps | DateTime | `yyyy-mm-dd HH:mm` plus “UTC” in title/tooltips |
| Local departure hour | Whole number | `00` |
| Counts | Whole number | `#,0` |
| Rates | Decimal number | `0.0%` |
| Delay measures | Decimal number | `0.0 "min"` |
| Policy sensitivity | Decimal number | `+0.0%;-0.0%;0.0%` |
| Refresh age | Whole number | `0 "h"` |

Sort month labels by month-start/date key and weekday names by ISO weekday number. Hide source flags, surrogate keys and additive `on_time_*` columns from the report field list, while keeping them available for reconciliation.

## Measure ownership and reconciliation

Create a dedicated `_Measures` table and copy [`measures.dax`](measures.dax) without changing denominator logic. Reconcile these fixed evidence points after first load:

- 403,054 modelled journeys;
- 400,518 completed final arrivals;
- 95.81% within 5 minutes;
- 98.91% within 15 minutes;
- 0.49% whole-train cancellation rate;
- 24,351 direct Lahti–Helsinki services.

If a number differs, investigate table grain, cancellation filter, missing actual handling, date coverage and relationship direction before editing a measure.

## Security and lifecycle

The model contains public data and defines no row-level security requirement. Workspace/app permissions still govern distribution. Use a Power BI Project only after opening and saving it in a supported Power BI Desktop version; do not hand-author a fake PBIP structure. Microsoft documents PBIP developer mode and source control at [Power BI Desktop developer mode](https://learn.microsoft.com/en-us/power-bi/developer/projects/).
