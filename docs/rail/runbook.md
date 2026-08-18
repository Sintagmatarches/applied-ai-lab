# Finland Rail Lakehouse runbook

## Normal incremental run

1. Run the existing acquisition command for the required completed departure dates.
2. Run `python -m rail.lakehouse.orchestrate --start YYYY-MM-DD --end YYYY-MM-DD`. It acquires missing source partitions and then executes all gates/layers.
3. Confirm `status=SUCCEEDED`, quality checks have no `FAIL`, and the watermark contains the new SHA-256.
4. Refresh downstream historical artifacts or the approved BI model only after the Gold commit.

The scheduler should normally request yesterday plus the prior three completed dates. Same-hash partitions are skipped; revised Digitraffic payloads are selected automatically.

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

Because watermark advancement is the final step, partial Silver/Gold writes remain safe: the retry atomically replaces the same date partitions.

## Orchestration contract

`acquire -> validate source -> immutable Bronze -> Silver transform -> Silver gates -> Gold facts/marts -> Gold contracts -> watermark -> downstream refresh`.

Recommended retries are three attempts with exponential backoff for acquisition only. Contract or quality failures are not transient and must not be blindly retried. A scheduler failure notification must include run id, date range, failed stage and the location of the control tables.

## Platform promotion

The package has no local-path assumptions beyond CLI defaults. Mount/copy the repository into Databricks or Fabric, install `requirements-rail.txt` if the runtime does not already provide compatible Spark/Delta, and supply platform Lakehouse paths via `--source`, `--lakehouse`, `--stations` and `--contracts`. Validate in a non-production workspace before scheduling.
