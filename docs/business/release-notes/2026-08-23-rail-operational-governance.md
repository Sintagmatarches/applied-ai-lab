# Finland Rail operational-governance release — 2026-08-23

This release turns the regional monitor into a governed operational analytics data product without changing the protected historical KPI contract.

## Delivered

- one versioned Python/TypeScript sample-support and freshness policy;
- mode-calibrated support thresholds, 80% measurement coverage and delayed-share-only Wilson intervals;
- explicit source, validation, Gold publication, coverage and latest-complete-partition evidence;
- one-row-per-date×region additive Gold semantics, a 19-region dimension and station-region bridge;
- persisted/reconciled rolling seven-day Gold plus a real compact publication for 16–22 August 2026;
- daily/manual Java 17 Spark/Delta orchestration with retained evidence;
- accessible 7 DAYS, Fresh/Warning/Stale, Low sample, No data and No rail service states.

## Acceptance matrix

| Issue | Repository evidence | Status after release |
| --- | --- | --- |
| #6 sample support | shared policy, empirical rationale, boundary/Wilson tests, UI/method copy | complete; may close |
| #7 freshness | deterministic boundary/failure/recovery tests, persisted Gold timestamp, workflow and runbook | keep open: Fabric alert destination, drill and dashboard evidence require tenant |
| #8 regional BI | `dim_region`, `bridge_station_region`, additive daily/7d facts and semantic/report contract | keep open: Direct Lake performance and RLS decision require real workspace validation |
| #9 rolling 7d | exact seven-partition gate, late-correction planning, Delta reconciliation, API/UI and real artifact | complete; may close |

No dbt, Airflow, Kafka, hosted Fabric run, PBIX or cloud screenshot is claimed. Generated raw/Delta data remains ignored; only compact reproducible artifacts and executable code are committed.
