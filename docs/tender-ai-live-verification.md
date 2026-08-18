# Live TED verification

Executed 18 August 2026 with `python -m tender_ai.live_verify` against the official anonymous TED Search API v3. This was a live network run, not replayed fixtures.

## Acquisition and persistence

Six independent queries returned 34 unique notices after cross-query deduplication:

| Scenario | Returned / current TED matches |
| --- | ---: |
| Finland + data | 8 / 178 |
| Finland + software | 8 / 644 |
| Finland + artificial intelligence | 5 / 5 |
| Finland + analytics | 8 / 19 |
| EU + machine learning | 8 / 42 |
| Finland + ICT/Data CPV `72*` | 8 / 542 |

All 34 normalized notices persisted without database failures: 67 lots, 64 extracted requirements, 54 award criteria, 163 evidence records, 34 immutable notice versions and 34 initial assessments. Twelve linked official XML documents were attempted; eleven succeeded and one `429 Too Many Requests` response was recorded as a failure rather than hidden.

The representative live notice is [TED 131555-2026](https://ted.europa.eu/en/notice/-/detail/131555-2026), “Detection and response technology and services”, buyer Veikkaus Oy. Its linked eForms XML produced cited mandatory conditions including signing and sending an NDA, joint liability for a bidding group and capacity obligations for groups/subcontractors. These conditions remain unstructured and therefore yield `REVIEW`; the engine does not pretend that prose can be passed automatically.

## Retrieval and agent

`nomic-embed-text:latest` generated 163 768-dimensional evidence embeddings in the isolated live database. Hybrid search returned five Finnish data/AI evidence hits.

The installed `qwen2.5:3b-instruct` model selected and successfully executed `get_notice` for notice UUID `2aedcdcc-1912-4080-8776-3e6f8827771e`. The final claim cited `ted:…:notice:summary`, which the deterministic resolver mapped to the real TED URL. Grounding reported one supported claim, zero unsupported claims after the gate and 1.0 evidence correctness. Qwen returned a valid but empty factual claim set, so the documented deterministic evidence fallback published the title/buyer claim instead of weakening the grounding gate.

## Version evidence boundary

The queried latest-only live sample did not expose a defensible multi-publication amendment pair. No real amendment claim is made. The executable regression creates a synthetic change from five to three references and moves the deadline from 3 to 17 September; the material event automatically changes the assessment from `NO_BID` to `REVIEW` because one remaining prose condition is still uncertain. This separation is intentional.

Full raw evidence is in `artifacts/tender-live-verification.json`; the agent trace is in `artifacts/tender-live-agent-trace.jsonl`.
