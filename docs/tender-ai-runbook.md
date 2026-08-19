# Tender AI runbook

## Local service

Install `requirements-ai.txt`, ensure Ollama has `nomic-embed-text:latest` and `qwen2.5:3b-instruct`, then run `python -m uvicorn tender_ai.server:app --host 127.0.0.1 --port 8099`. `GET /health` is the readiness check. Data defaults to `data/tender-ai/tenders.sqlite3`; traces default to `artifacts/tender-ai-traces.jsonl`. Override only through documented `TENDER_AI_*` environment variables.

For Docker, start the optional Ollama profile, pull both models, then build/start `tender-ai` using the README commands. Named volumes retain SQLite, traces and model weights. Back up the SQLite database only after stopping writers or using SQLite's online backup API; restoration is a replacement of the stopped service volume followed by `PRAGMA integrity_check`.

## Ingestion and watch

Add a persisted notice after it has been ingested: `python -m tender_ai.watch --add NOTICE_ID`. Recheck with `python -m tender_ai.watch --recheck`. The command obtains the latest official publication, performs bounded XML enrichment, idempotently ingests, records actual diffs and reassesses lots. Schedule that exact command with cron/Task Scheduler at an operator-chosen interval; do not overlap runs against the same SQLite file. Failures are emitted with notice/stage/category/message and are not silently counted.

The browser watchlist is intentionally different: it stores IDs on the device and re-runs the current official query only when the user clicks recheck. It is not background monitoring.

## Verification and incidents

Run `npm test`, `python -m tender_ai.evals.run`, `python -m tender_ai.retrieval_benchmark` and `python -m tender_ai.live_verify`. Inspect `artifacts/tender-live-verification.json`, the JSONL trace and `python -m tender_ai.operational_report`. A high fallback rate means model answer quality regressed even when a deterministic answer was safely returned.

For TED 429/5xx failures, honor the recorded retry category and reduce polling frequency; the client already applies Retry-After/backoff/jitter. For integrity failures, stop writers, preserve the damaged DB, run `PRAGMA integrity_check`, restore backup and re-ingest since TED is the source of truth. If evidence changes, stale embeddings are deleted and must be re-indexed.

## Deployment boundary

The public site is deployed through Sites/Cloudflare and contains no Ollama connection. `infra/azure-tender` is an optional private Container Apps service with scale-to-zero and Log Analytics. Terraform validation needs no cloud credentials; actual apply needs the user's Azure subscription and container registry/image. Do not describe Azure as deployed until outputs and an authenticated health check exist.
