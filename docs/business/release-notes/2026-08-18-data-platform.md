# Release 2026-08-18 — executable rail data platform

## Requirement

[Issue #11](https://github.com/Sintagmatarches/applied-ai-lab/issues/11) tracks the request to make Finland Rail a demonstrable production-like Data Engineering / Analytics Engineering case while preserving the live monitor and historical KPI contract.

## Implementation

- PySpark 4.0.4 + Delta Lake 4.0.1 runtime pins;
- immutable content-addressed Bronze payloads and Delta manifest;
- typed/deduplicated Silver journey and station-arrival facts;
- Gold journey, network, route, station and daily regional marts;
- SHA-256 watermark planner, changed-source selection, no-op reruns, partition replacement and forced recovery;
- executable table contracts, freshness/anomaly/duplicate/null/value/referential/Gold gates;
- control tables for runs, quality results, manifest and committed watermarks;
- dedicated Spark/Delta CI job, lineage, runbook and real execution evidence.

dbt was deliberately excluded because the source transformation is nested-JSON Spark work and no persistent SQL warehouse or separate SQL-owned transformation boundary exists.

## Evidence

[`artifacts/rail-lakehouse-execution.json`](../../../artifacts/rail-lakehouse-execution.json) records a real partition run, exact legacy KPI reconciliation, an unchanged-hash second run and forced recovery. The Delta integration suite covers duplicate rejection without watermark advancement and idempotent replay.

Hosted Databricks/Fabric and native Power BI execution remain user-owned credentialed steps and are not claimed. The public monitor and historical definitions are unchanged.

