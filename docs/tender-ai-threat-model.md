# Tender AI threat model

| Threat | Boundary and mitigation | Regression evidence |
| --- | --- | --- |
| Prompt injection / poisoned source text | TED prose is data; instruction-like fragments become `security_findings`, never eligibility or model instructions | quarantine test |
| Tool/profile manipulation | Strict nested schemas reject extra fields; supplier facts are passed outside model arguments | adversarial profile test |
| Forged or irrelevant evidence IDs | IDs resolve only from executed tools; decision claims require assessment-tool evidence | grounding tests |
| Unsupported numeric/decision claims | Exact numeric containment and deterministic BID/NO_BID consistency checks | grounding tests |
| SSRF | HTTPS plus official TED hostname allowlist for linked documents | network allowlist test |
| XML entity/size bombs | Content-Length and streaming byte caps precede parse; DTD/entity declarations rejected | unsafe XML test |
| Malformed TED filters/query injection | Country, CPV, procedure and real ISO dates are allowlisted/validated before expert-query construction | route tests |
| Resource exhaustion | bounded HTTP bodies, retries, XML concurrency, agent steps/tools/time/output and 10k vector scan | unit/CI checks |
| Corrupted/stale local state | transactional ingestion, failure details, schema metadata, stable fingerprints and embedding invalidation | storage/version tests |
| Duplicate/reordered/multilingual fields | stable IDs, dedupe and lot identifiers; conservative fallback if cardinality is ambiguous | parity and lot fixtures |

Residual risks: FTS/SQLite is a single-node local store; local filesystem backup and access control belong to the operator. Regex fallback can miss or conservatively classify prose. The two-notice real evaluation is too small to quantify extraction risk. The public watchlist is browser-local and requires a user-triggered recheck.
