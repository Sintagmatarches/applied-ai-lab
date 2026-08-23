# Fabric pipeline and lifecycle specification

> **Portfolio simulation.** This is an implementation-ready deployment design. It has not been executed in a Microsoft Fabric tenant from this repository environment.

## Pipeline contract

**Name:** `pl_finland_rail_daily`  
**Time zone:** `Europe/Helsinki`  
**Schedule:** daily after the previous operating day is expected to be stable  
**Parameters:**

| Parameter | Type | Default | Use |
| --- | --- | --- | --- |
| `p_end_date` | ISO date | Helsinki yesterday | newest departure-date partition |
| `p_refresh_recent_days` | integer | 7 | retain enough completed dates to publish and re-read recent corrections |
| `p_start_date` | ISO date | `p_end_date - p_refresh_recent_days` | calculated pipeline input |
| `p_run_id` | string | pipeline run ID | lineage/audit correlation |

## Activity flow

```text
Set Helsinki dates
  -> Ingest and validate Bronze (01_ingest_digitraffic)
  -> Assert expected complete partition audit rows
  -> Transform Silver + quality gates (02_transform_quality)
  -> Publish Gold atomically by affected partitions
  -> Build affected complete rolling 7-day region windows
  -> Reconcile 19 regions, 7 components, counts and threshold flags
  -> Record Gold publication timestamp
  -> Record successful watermark
  -> Refresh/notify downstream semantic model
```

Failure from any activity skips watermark advancement and downstream refresh. Retry network acquisition with bounded exponential backoff; do not retry deterministic validation errors until the source or requested parameters change.

## Watermark and idempotency

- Watermark grain: source + partition date, with latest successful source hash and Gold publication timestamp.
- Reprocessing the same source hash must be idempotent.
- A changed source hash inside the rolling correction window replaces only affected Silver/Gold partitions.
- Bronze remains source-partitioned and auditable; Gold uses `replaceWhere` or an equivalent targeted transaction, never an unbounded append.
- The “successful” watermark is written only after Bronze validation, Silver checks, Gold reconciliation and downstream-read readiness.

## Blocking quality gates

| Gate | Stage | Failure action |
| --- | --- | --- |
| Non-empty array, matching `departureDate`, at least one passenger train | before Bronze publish | fail partition; retain previous good Bronze |
| One latest complete non-empty audit row per requested date | before Bronze read | fail run; no partial date window |
| Unique `(departureDate, trainNumber)` passenger key | Silver | fail run |
| Valid first passenger departure and final passenger arrival | Silver | invalid records counted/excluded according to method; unexpected spike investigated |
| Gold unique journey key | before publish | fail run |
| `on_time_5 >= on_time_10 >= on_time_15 >= on_time_30` is **not** valid for flags; correct invariant is the reverse per row/count | Gold reconciliation | assert `on_time_5 <= on_time_10 <= on_time_15 <= on_time_30` |
| Completed + cancelled + missing-final-actual reconciliation | Gold reconciliation | fail run on unexplained difference |
| Seven distinct dates, 19 region rows, measured ≤ observed, delayed_5 ≥ delayed_10 ≥ delayed_15 ≥ delayed_30 | rolling Gold | retain prior publication; no watermark |

The repository Spark path implements the rolling Gold reconciliation and publication control row. Fabric alert destinations, drill evidence and semantic refresh history remain tenant tasks because they require a live workspace.

## Audit columns

Retain `source`, `partition_date`, `retrieved_at`, `source_url`, `record_count`, `content_sha256`, `bronze_path`, `status`, `run_id`, optional `error_class` and `error_message`. Error text must not contain secrets. Keep failed attempt rows; a later success is a new row, not an update that erases evidence.

## Dev/Test/Prod promotion

1. Connect only the Development workspace to the reviewed Git branch or adopt the organisation's approved Git pattern.
2. Validate notebook/lakehouse bindings in Development.
3. Deploy to Test and run a small closed historical range plus a correction-window rerun.
4. Compare Gold KPIs with the committed evidence snapshot.
5. Apply target-stage notebook/lakehouse deployment rules, then approve Production.

Microsoft notes that Fabric notebook deployment rules belong on the target stage and take priority over auto-binding; Lakehouse Git/deployment tracks metadata, not table/file data. See [notebook source control and deployment](https://learn.microsoft.com/en-us/fabric/data-engineering/notebook-source-control-deployment) and [Lakehouse Git/deployment behaviour](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-git-deployment-pipelines).

## Operational runbook

- **Source/network failure:** retry within policy; retain watermark; notify owner with date/run ID.
- **Partition content failure:** quarantine attempt, follow [INC-001](../docs/incidents/INC-001-empty-daily-partition.md), do not publish a shortened window.
- **Schema failure:** capture schema diff, stop Silver/Gold, update contract/tests through reviewed code.
- **Reconciliation failure:** retain previous Gold, compare keys/filters and only republish after root cause is understood.
- **Semantic refresh failure:** Gold remains valid; retry downstream refresh separately and expose stale refresh age.
