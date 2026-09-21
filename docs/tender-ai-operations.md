# Tender runtime operations — code release 2.1.0

This applies to the private Python runtime, not the public Cloudflare TED dashboard.
No Azure runtime deployment or production SLO attainment is claimed.

## Health and telemetry

`/live` is an asynchronous, dependency-free process probe. `/ready` returns 503
when the required SQLite schema cannot be read or either configured Ollama model
is unavailable; it checks availability, not model inference or embedding freshness.
SQLite and model-list calls each have a five-second connection timeout. `/health`
remains the legacy diagnostic endpoint. Health responses and operational responses
are `no-store`; server-generated `x-request-id` identifies each request.

Run `python -m uvicorn tender_ai.server:app --port 8099 --no-access-log`.
The container also disables Uvicorn access logs so arbitrary query strings cannot
enter default access telemetry. The application emits JSON to stderr containing
only fixed operations, fixed route names (unknown paths become `other`), bounded
outcomes/status classes, duration and generated correlation IDs. Request IDs are
log fields, never metric dimensions. No automatic HTTP, LLM or logging instrumentation
is enabled. Questions, supplier profiles, request headers/bodies, tool arguments,
exception messages and the separate local evaluation JSONL are never exported.

Set `TENDER_OTLP_ENDPOINT` to a trusted OTLP HTTP collector base URL to enable
OpenTelemetry spans and `tender.operations` / `tender.operation.duration` metrics.
Nested HTTP → agent → tool → retrieval spans and TED calls are instrumented manually.
TED metrics count completed logical requests, including exhausted retries, not each
HTTP attempt. Grounding/fallback categories come from the actual agent result.
Exporter queues are bounded (512 spans, 64 per batch); HTTP export timeout is three
seconds. Telemetry failure must not change the result of application work.
In-memory SDK tests verify parentage, failure recording and privacy boundaries.

The existing Azure Log Analytics workspace can collect these container console
events. Direct Application Insights export and collector infrastructure are not
configured. Do not point OTLP at an Application Insights ingestion URL: the protocols
are not interchangeable. Add an approved Azure export path only after credentials,
data handling and durable storage are resolved.

## SLO proposal, not measured performance

For a continuously running private pilot, propose 99% of valid `/ask` requests
completing without HTTP 5xx or `MODEL_UNAVAILABLE` over 28 days. Track grounded
answers, deterministic fallbacks and insufficient evidence separately: HTTP 200
does not imply a useful or grounded answer. Proposed latency objective: 95% under
120 seconds, to be revised after a measured pilot. Empty traffic yields no SLI,
not 100% availability. Exclude probes and invalid requests from the denominator.

Alert proposals: readiness fails for five consecutive minutes; at least 20 valid
requests in 15 minutes and over 5% failures; three exhausted TED requests in 15
minutes; fallback/unavailable share over 20% with at least 20 agent results. Low
traffic calls for scheduled smoke probes rather than meaningless percentiles.
Use `tender-operations.kql` with a Log Analytics scheduled-query alert. Route the
action group to a real owner before calling it operational monitoring. No alerts
have been provisioned by this change.

## Failure, release and rollback

TED already retries 429/500/502/503/504 and network failures, at most three attempts,
with 20-second per-attempt timeout and capped backoff. Ollama has separate request
and embedding timeouts and no automatic generative retry. The agent's 180-second
budget is checked between calls; it is not hard cancellation of an in-flight call.
Document this distinction when sizing an ingress timeout. A model outage must not
change deterministic supplier qualification.

Run the unit/evaluation gates, build an immutable image tagged by source SHA, and
run `python -m tender_ai.smoke PRIVATE_URL` from inside the deployment network.
The Terraform configuration now uses `/live` and `/ready` independently. It remains
a private-ingress scaffold: SQLite and JSONL currently live on ephemeral container
storage. Do not promote it as a durable service or put real supplier records there.
First choose a supported persistent database/storage design and test backup/restore;
blindly mounting SQLite WAL on a shared network filesystem is not a solution.

Rollback the runtime to the previous immutable image digest, run the same smoke
probe, and verify a known stored notice/assessment. Back up the database consistently
with SQLite's backup API before schema migrations; container rollback does not undo
data migrations. For the public dashboard, redeploy the prior saved Sites version
and verify live TED search separately. Bound replicas and pilot uptime deliberately;
scale-to-zero saves money but cold model startup competes with readiness and latency.
