# Changelog

This changelog records real repository releases. Business roles labelled as simulated are portfolio exercises, not historical client work.

## 2026-08-18

### Migrated

- Reprofiled the former job-search implementation into the EU Tender Intelligence Agent. Git history preserves the old product; the active tree now contains only the procurement architecture and redirects the legacy route.

### Added

- Official TED Search API v3 ingestion, linked eForms XML enrichment, normalized procurement entities, incremental SQLite persistence and source-hash version history.
- Structured requirement/award extraction, deterministic supplier qualification, strategic fit, material change events and automatic reassessment.
- Local Qwen/Nomic hybrid RAG, 14 validated procurement tools, claim-level evidence grounding, adversarial fixtures, traces, live verification and an executable evaluation suite.
- Production procurement dashboard with editable demo profile, live TED filters, evidence inspector, watchlist and honest public/local runtime boundary.
- Regional delay-policy selector for 5, 10, 15 and 30 minutes, with threshold-specific delay shares, scores, statuses and problem rankings.
- Daily Digitraffic partition completeness validation before trusted cache/Bronze publication and on local cache read.
- Simulated business requirements, prioritised issue-ready backlog, CR-001 change request, INC-001 incident, stakeholder delivery memo and traceability matrix.
- Power BI semantic-model/report specifications and executive/data-quality DAX measures.
- Fabric activity, watermark, idempotency, quality-gate, promotion and recovery specification.
- Explicit Power BI/Fabric/user manual completion tasks.

### Changed

- TED published-date defaults are now calculated per request from the current UTC calendar date with a 90-day lookback, avoiding build-time epoch dates in rendered production HTML.
- Navigation, metadata and documentation now position EU Tender Intelligence as completed project 03; the favicon cache key advances to `20260818-tender-intelligence-3`.
- The Sites project identity is now tracked and its production build contract is tested, preventing source builds from silently omitting `dist/.openai/hosting.json`.
- Regional Disruption Score now uses the actively selected policy threshold for its delayed-share component; serious delay remains fixed above 15 minutes.
- Historical regional artifact rebuilt from the same 365 source partitions with no coverage/population change.
- Public assets and monitoring requests cache-busted for the release.
- Build/runtime tooling updated to patched Vinext/Cloudflare/RSC/Wrangler versions after dependency audit; no package overrides were introduced.

### Preserved

- Legacy five-minute API fields, target population, missing-timing treatment, cancellation definitions, Åland `No rail service` state and all prior historical evidence.
