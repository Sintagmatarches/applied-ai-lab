# Live TED and local-model verification

Executed 24 August 2026 with `python -m tender_ai.live_verify` against the official anonymous TED Search API v3 and the installed local Ollama models. This is a timestamped network/model run, not deterministic fixture replay and not a CI requirement.

## Official TED results

The 180-day window was 25 February–24 August 2026. Six queries produced 34 unique notices after deduplication:

| Scenario | Returned batch / current TED total |
| --- | ---: |
| Finland + `data` | 8 / 180 |
| Finland + `software` | 8 / 637 |
| Finland + `artificial intelligence` | 5 / 5 |
| Finland + `analytics` | 8 / 20 |
| EU + `machine learning` | 8 / 45 |
| Finland + ICT/Data CPV `72*` | 8 / 535 |

All 34 normalized notices persisted without failures: 67 lots, 124 requirements, 48 award criteria and 239 evidence rows. Twelve linked official XML documents were bounded and parsed with zero failures. These are procurement matches, not jobs or proof that buyers are hiring for the query wording.

The corpus acquisition utility separately looked up and froze the 15 evaluation publications through the same official API on this date. Live verification does not replace that committed corpus.

## Embedding and retrieval

Local `nomic-embed-text:latest`, digest `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`, indexed 239 evidence rows in 47.694 seconds. Ollama returned 21,551 input tokens, 47.592 seconds total model duration and 0.526 seconds load duration; the embedding response did not return generation counts/duration or a done reason, so none are invented.

The 50/50 exact-cosine/FTS retrieval returned five hits from 181 country-filtered candidates in 170.951 ms, including a 52.836 ms query embedding. That embedding response returned nine input tokens, 36.851 ms total model duration and 1.513 ms load duration. The 10,000-candidate boundary was not approached.

## Agent and grounding result

Local `qwen2.5:3b-instruct`, digest `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`, completed its first tool-selection call in 43.070 seconds, selected `get_notice`, and executed it successfully in 3.944 ms. The response returned 922 prompt tokens, 52 completion tokens, 43.067 seconds model duration, 17.950 seconds load, 21.232 seconds prompt evaluation, 3.863 seconds generation and `done_reason=stop` (13.46 generated tokens/second).

The required structured final call then exceeded the 90-second HTTP timeout. The final recorded status is therefore `MODEL_UNAVAILABLE`, not model answered and not deterministic fallback. No model claim or citation was published; the result is unknown with zero unsupported post-gate claims. Total bounded agent time was 133.084 seconds. A successful tool call does not convert the failed final answer into model success.

## Observability result

`artifacts/tender-ai-traces.jsonl` contains seven schema-v2 events across two trace IDs: embedding, retrieval, request start/end, one successful model call, one successful tool call and grounding. Query text and supplier data are absent; full SHA-256 and length are present. Both model digests, prompt `tender-agent-prompt-v4`, eval `tender-eval-v2.0.0`, optional durations/tokens, failure/fallback and grounding fields are recorded.

The v2 operational report has zero corrupt or unsupported-schema lines. Because this is one live agent request, its p50 and p95 are both 133.084 seconds; embedding is 47.694 seconds, retrieval 170.951 ms, recorded successful LLM call 43.070 seconds and tool call 3.944 ms. Totals are 922 prompt / 52 completion / 974 chat tokens. Fallback rate is 0/1; request failure is 1/1 (`MODEL_UNAVAILABLE`); tool success is 1/1; post-gate unsupported claims are zero. Local API monetary cost is explicitly not applicable/not measured—not reported as “free.”

## Boundary

No real amendment/corrigendum pair is claimed. Latest-only search cannot prove a notice change, so deterministic source-version regression remains the evidence for diff/reassessment behavior. Raw results are in `artifacts/tender-live-verification.json`; live trace/report are separate from the deterministic baseline.
