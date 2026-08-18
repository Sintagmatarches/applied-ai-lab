# INC-001 — Empty daily train partition accepted as complete

> **Portfolio simulation.** This incident did not occur in a known production service. It is a realistic tabletop exercise based on a weakness found during the repository audit. The quality gate and tests described below are real code in this repository.

**Simulated severity:** SEV-2 data quality  
**Simulated status:** Resolved and preventive control implemented  
**Affected product:** Historical rail reliability refresh  
**Not affected:** LIVE API path, because it does not use the daily historical cache

## Simulated signal

The source returned HTTP 200 and syntactically valid JSON `[]` for one requested day. The previous ingestion contract checked only that JSON parsed to an array, wrote the compressed file and allowed downstream transformation to continue. Headline volumes then dropped without an explicit failed-partition state.

## Business impact assessment

Potential impact, had this happened: journey/arrival denominators and route rankings for the affected reporting window would be understated. A quiet day could be misread as improved reliability. No monetary or passenger-impact estimate is made because the project has no passenger or revenue data.

## Root cause

The ingestion success criterion was technical transport success (`HTTP 200` + parseable array), not analytical completeness. The same weak rule existed in both the local Python cache and the prepared Fabric notebook. An existing cached file also bypassed source-time validation when read later.

## Containment and correction

1. Stop publication of the affected historical artifact or gold partition.
2. Preserve the last known-good published artifact; do not overwrite it with the partial refresh.
3. Re-request the affected date from Digitraffic.
4. Validate the response against the requested date and passenger-content contract.
5. Rebuild the affected downstream partitions and reconcile counts before republishing.

## Preventive control implemented

`validate_train_partition` now blocks a daily payload when it is:

- not an array;
- an empty array;
- contains non-object records;
- contains a `departureDate` other than the requested partition date;
- contains no `Long-distance` or `Commuter` train.

Validation runs before the temporary file is atomically promoted to the trusted local cache and again on cache read. Therefore a rejected refresh cannot replace a valid cached partition, and a corrupt old file cannot bypass the rule. The Fabric ingestion notebook mirrors the source checks, publishes Bronze only after validation, and the transformation notebook verifies exactly one latest complete, non-empty audit record for every requested date before reading Bronze.

## Automated detection evidence

- `rail/tests/test_pipeline.py::test_daily_partition_quality_gate_accepts_matching_passenger_data`
- `rail/tests/test_pipeline.py::test_daily_partition_quality_gate_rejects_incomplete_payloads`
- `rail/tests/test_pipeline.py::test_rejected_refresh_does_not_replace_a_valid_cached_partition`

Run with:

```bash
npm run test:rail
```

## Residual risk and follow-up

Non-empty data can still be abnormally sparse while satisfying the hard schema/content checks. BL-004 proposes freshness alerting; a later control should compare partition volume with weekday/seasonal history and flag anomalies for review without hard-coding an unsafe universal minimum. This release intentionally avoids an arbitrary row-count threshold that might reject a legitimate low-service day.
