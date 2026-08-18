# Changelog

This changelog records real repository releases. Business roles labelled as simulated are portfolio exercises, not historical client work.

## 2026-08-18

### Added

- Local Ollama adapter with Qwen tool calling, Nomic embeddings, SQLite/FTS5 persistence, hybrid vector retrieval, validated job-agent tools, claim/citation grounding, privacy-minimized traces and an executable evaluation suite.
- Local AI status, knowledge-base counts, grounded answers, citations, tool audit and latency/token telemetry on the existing Job Search AI Agent page, with an explicit production fallback boundary.
- Job Search AI Agent page with account-free Arbeitnow and Jobicy acquisition, shared normalization, URL/HTML guards, deduplication, explainable profile matching, browser-local saves, comparison and cited evidence tools.
- Job-source unit, resilience and adversarial normalization tests plus rendered-route coverage for the no-account/no-paid-API boundary.
- Regional delay-policy selector for 5, 10, 15 and 30 minutes, with threshold-specific delay shares, scores, statuses and problem rankings.
- Daily Digitraffic partition completeness validation before trusted cache/Bronze publication and on local cache read.
- Simulated business requirements, prioritised issue-ready backlog, CR-001 change request, INC-001 incident, stakeholder delivery memo and traceability matrix.
- Power BI semantic-model/report specifications and executive/data-quality DAX measures.
- Fabric activity, watermark, idempotency, quality-gate, promotion and recovery specification.
- Explicit Power BI/Fabric/user manual completion tasks.

### Changed

- Job Search documentation and limitations now distinguish measured local AI/RAG evidence from the deterministic public Cloudflare runtime; cache-bust metadata advances to `20260818-local-rag-1`.
- Applied AI Lab navigation and home page now treat Job Search AI Agent as completed project 03; favicon metadata was cache-busted for the release.
- Regional Disruption Score now uses the actively selected policy threshold for its delayed-share component; serious delay remains fixed above 15 minutes.
- Historical regional artifact rebuilt from the same 365 source partitions with no coverage/population change.
- Public assets and monitoring requests cache-busted for the release.
- Build/runtime tooling updated to patched Vinext/Cloudflare/RSC/Wrangler versions after dependency audit; no package overrides were introduced.

### Preserved

- Legacy five-minute API fields, target population, missing-timing treatment, cancellation definitions, Åland `No rail service` state and all prior historical evidence.
