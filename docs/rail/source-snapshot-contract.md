# Immutable source snapshot and recovery

The planner hashes each gzip source file. `rail/lakehouse/snapshot.py` then copies
that partition to a unique temporary file while computing its hash. It rejects
bytes that differ from the plan, validates the copied JSON/date/passenger contract,
and publishes exactly those bytes under `content_sha256=...`. Spark reads only this
immutable snapshot. A corrupt existing snapshot fails closed. Corrected source data
gets a separate snapshot, while prior raw bytes remain available for lineage.

This removes a race in the old read/hash/validate/copy sequence: a source refresh
could previously replace the file between reads, causing the hash and rows to refer
to different versions. Tests cover a changed source, wrong date, corrupt snapshot,
identical rerun and retained history after correction.

The Delta integration test also injects a failure after Gold writes but before the
watermark update, then retries a corrected source without `--force`. It checks that
the prior watermark survives the failure, the correction is retried and the business
key still has exactly one fact row.

Run one writer per lakehouse. Atomic file replacement and per-table Delta commits
do not create a multi-table transaction. Readers can observe intermediate table
versions during a failed run; governed publication and the successful watermark
are the consumption boundary. For concurrent writers or direct cross-table readers,
add a publication manifest of explicit Delta versions and concurrency control first.
This change does not claim transactional visibility across all tables.

Refresh completed recent dates to discover source corrections. Identical source
hashes skip transformations; changed hashes replace the affected departure-date
partitions and recompute complete affected seven-day windows. Transform or station
mapping changes still require an explicit `--force-transform` backfill: a source-only
watermark does not identify code/config changes. Byte-level gzip hashes may cause an
extra harmless rerun when the compression envelope changes without row changes.

The registry validates required columns, grain and business-key declarations, with
separate null/duplicate/referential/KPI checks. It is not a complete typed schema
evolution mechanism. Automatic Delta schema merge is still enabled; future schema
changes need reviewed versioned migrations, not a claim of strict type enforcement.
Keep polling/incremental batch terminology; Digitraffic polling is not event streaming.
