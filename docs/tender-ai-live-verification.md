# Live TED and local-model verification

Executed 19 August 2026 with `python -m tender_ai.live_verify` against the official anonymous TED Search API v3 and the locally installed Ollama models. This is a timestamped network run, not replayed fixture output.

## Official search results

The 180-day window was 20 February–19 August 2026. Six queries yielded 35 unique notices after deduplication:

| Scenario | Returned batch / TED total |
| --- | ---: |
| Finland + `data` | 8 / 178 |
| Finland + `software` | 8 / 647 |
| Finland + `artificial intelligence` | 5 / 5 |
| Finland + `analytics` | 8 / 20 |
| EU + `machine learning` | 8 / 44 |
| Finland + ICT/Data CPV `72*` | 8 / 543 |

These are procurement full-text/CPV matches, not job vacancies or evidence that an organisation is hiring a “data analyst.” A match may be software, security, data-platform, consultancy or another contract whose notice text contains the term. The UI example therefore uses Finland + CPV `72*` rather than pretending TED is a job-search source.

All 35 notices persisted without failures: 68 lots, 124 requirements, 62 award criteria and 261 evidence rows. The run created 35 initial source snapshots and 35 lot-level assessments. Twelve official linked XML documents were bounded and parsed with zero failures in this run.

`nomic-embed-text:latest` indexed all 261 evidence rows in 35.719 seconds. The 50/50 hybrid retrieval returned five hits from 195 filtered candidates in 175 ms (query embedding 81 ms). Exact scan remained below the 10,000-candidate safety boundary.

## Agent and grounding result

`qwen2.5:3b-instruct` selected `get_notice` for real notice [131555-2026](https://ted.europa.eu/en/notice/-/detail/131555-2026) and the tool succeeded in 3 ms. The bounded loop used two model steps, 3,122 prompt tokens, 843 completion tokens and 50.799 seconds total model/agent time.

The model still did not produce an acceptable supported claim set after the strict structured-final repair. The safety path therefore published a deterministic title/buyer claim with the real summary evidence ID. The recorded status is explicitly `DETERMINISTIC_FALLBACK`, fallback rate 1.0 for this single live agent case, citation validity 1.0, claim support 1.0 and zero unsupported claims after the gate. This is a safe grounded result, but it is not reported as successful model answering.

An earlier cold run exceeded the former 45-second model HTTP timeout. The per-call timeout was increased to 90 seconds while the agent remains bounded by steps, tool calls and a 180-second overall target. The successful rerun above is the committed evidence; the open-source 3B model's final-answer reliability remains a known limitation.

## Change boundary

Latest-only search did not expose a defensible amendment/corrigendum pair, so no real amendment is claimed. Synthetic version regression remains labelled synthetic and verifies stable source fingerprints, immutable ingestion revisions, field diffs and automatic reassessment.

Raw evidence is in `artifacts/tender-live-verification.json`; the agent event is in `artifacts/tender-live-agent-trace.jsonl`. The public page reads only the compact committed `artifacts/tender-public-evidence.json` and does not contact local Ollama.
