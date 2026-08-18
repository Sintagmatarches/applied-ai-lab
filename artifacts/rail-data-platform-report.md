# Finland Rail data-platform delivery report

## Preserved baseline

The live regional monitor, 24-hour and historical modes, 19-region geospatial join, Åland `No rail service` handling, 365-day analytical snapshot, delay thresholds 5/10/15/30, existing source-quality validation, public API, Power BI model and historical KPI artifacts remain intact.

## Added

PySpark 4.0.4 and Delta Lake 4.0.1 now provide an executable local/CI Lakehouse: immutable content-addressed Bronze, normalized journey and station-arrival Silver facts, Gold journey/network/route/station/regional marts, Delta audit and watermark tables, executable contracts, blocking gates, idempotent date replacement, changed-source detection, backfill/forced recovery, lineage, runbook and a dedicated CI integration job.

dbt was not added: nested Digitraffic JSON requires Spark transformations and a second SQL execution layer would duplicate contracts/orchestration without a persistent SQL warehouse or separate SQL-owning team.

## Real execution

The 2026-07-31 real Digitraffic partition produced 887 journey facts, 9,525 station-arrival facts and 72 regional threshold rows from 1,415 source train records. A second run processed zero partitions because the committed SHA-256 matched. Forced recovery replaced the same partition without duplicate facts. Nine gates passed and the intentionally old evidence partition produced an explicit non-blocking freshness warning. Gold exactly reconciled with the existing Python implementation: scheduled 887, completed 880, cancelled 7 and on-time-at-five-minutes 813.

All six Lakehouse tests passed in 114.518 seconds in the Linux/JDK 17 runtime, including duplicate-partition rejection without watermark advancement and initial/no-op/forced Delta transactions. Raw run evidence is in [`rail-lakehouse-execution.json`](rail-lakehouse-execution.json).

## Honest platform boundary

The pipeline was run locally through WSL2 and is exercised in Linux CI. It was not run in Databricks Free Edition or Microsoft Fabric because those environments require the repository owner's login/workspace. The code, paths, contracts and runbook are prepared; no hosted execution or Power BI publication is claimed.
