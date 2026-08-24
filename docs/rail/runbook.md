# Finland Rail Lakehouse runbook

## Normal incremental run

1. Run the existing acquisition command for the required completed departure dates.
2. Run `python -m rail.lakehouse.orchestrate --start YYYY-MM-DD --end YYYY-MM-DD`. It acquires missing source partitions and then executes all gates/layers.
3. Confirm `status=SUCCEEDED`, quality checks have no `FAIL`, and the watermark contains the new SHA-256.
4. Refresh downstream historical artifacts or the approved BI model only after the Gold commit.

The governed publisher resolves yesterday in `Europe/Helsinki` plus the prior six completed dates. This calendar rule is independent of runner UTC and remains correct across DST, month and year boundaries. Same-hash partitions are skipped inside a run; because GitHub runners are ephemeral, a scheduled run may reacquire the bounded source window and rebuild local Delta state before publication.

The executable schedule is `.github/workflows/rail-data-platform.yml` (daily 04:17 UTC plus manual `window_end`). A successful build job must show seven available dates, 19 rolling rows, `fresh` at publication and a verified digest. The separate write-scoped job then commits only the immutable snapshot and latest manifest to `rail-publications`. Its Actions artifact contains the Spark log/evidence and compact JSON for 30 days; production persistence is the publication branch, not that expiring artifact.

## Backfill

Pass an inclusive date range. Missing source files fail before Spark writes. Large backfills should be split into bounded ranges so a bad source date is isolated and retries remain cheap.

```bash
python -m rail.lakehouse.orchestrate --start 2026-07-01 --end 2026-07-07
```

## Failure and recovery

- Inspect `control/pipeline_runs` and `control/quality_results` for the run id.
- Correct or reacquire only the rejected source date; never edit Bronze in place.
- Rerun the same range. An uncommitted date is selected automatically.
- Use `--force` only for a deliberate replay after code/contract correction.
- Verify the successful watermark SHA and compare Gold counts/KPIs with the pre-recovery run.
- If freshness is `warning`, inspect the latest Gold publication time and the current workflow before the 60-hour stale boundary.
- If freshness is `stale`, stop downstream refresh, inspect missing/failed dates and timestamp ordering, reacquire only failed dates, rerun, then verify a new `PUBLISHED` control row. Source/API success alone is not recovery.
- If the publication job fails, do not edit `manifest.json` manually. The previous branch commit remains authoritative and production will either keep using it or show the explicit stale bundled fallback. Fix the failed gate/push and rerun the same `window_end`.

Because watermark advancement is the final step, partial Silver/Gold writes remain safe: the retry atomically replaces the same date partitions.

## Orchestration contract

`acquire -> validate source -> immutable Bronze -> Silver transform -> Silver gates -> daily Gold -> complete-window reconciliation -> rolling Gold publication -> watermark -> downstream refresh`.

Recommended retries are three attempts with exponential backoff for acquisition only. Contract or quality failures are not transient and must not be blindly retried. A scheduler failure notification must include run id, date range, failed stage and the location of the control tables.

## Platform promotion

The package has no local-path assumptions beyond CLI defaults. Mount/copy the repository into Databricks or Fabric, install `requirements-rail.txt` if the runtime does not already provide compatible Spark/Delta, and supply platform Lakehouse paths via `--source`, `--lakehouse`, `--stations` and `--contracts`. Validate in a non-production workspace before scheduling.
