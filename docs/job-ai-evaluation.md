# Local Job AI evaluation

Run: `2026-08-18T16:43:53.635065+00:00`

Dataset: `2026-08-18.1`

Chat model: `qwen2.5:3b-instruct`

Embedding model: `nomic-embed-text:latest`

These are measured local results from this run, not target values. The fixture contains 8 manually checked jobs, including three adversarial vacancy documents.

## Results

| Area | Metric | Result |
| --- | --- | ---: |
| Retrieval | Recall@3 | 100.0% |
| Retrieval | MRR | 1.000 |
| Agent | Tool-selection accuracy | 83.3% |
| Agent | Expected tool included | 83.3% |
| Agent | Single-tool plan rate | 83.3% |
| Agent | Argument validity | 83.3% |
| Agent | Tool execution success | 83.3% |
| Agent | Request obtained valid tool evidence | 100.0% |
| Grounding | Generated-citation correctness before publication | 45.2% |
| Grounding | Published-citation correctness | 100.0% |
| Grounding | Supported-claim rate after validation | 57.1% |
| Grounding | Unsupported-claim rate before publication | 42.9% |
| Grounding | Unsupported-claim rate after publication gate | 0.0% |
| Grounding | Unknown-question accuracy | 100.0% |
| Structured output | Schema validity | 100.0% |
| Structured storage | Field round-trip accuracy | 100.0% |
| Security | Prompt-injection test pass rate | 100.0% |
| Baseline | Deterministic score reproducibility | 100.0% |
| Match explanation | Numeric explanation coverage | 0.0% |
| Match explanation | Accuracy when numeric scores were stated | 100.0% |

Mean hybrid retrieval latency was 72.0 ms. Mean combined LLM latency across 12 evaluated requests was 13245.6 ms.

## Interpretation

The LLM adds natural-language routing, comparisons and explanations over retrieved evidence. Hybrid vector retrieval improves discovery when a query and vacancy use different wording. Deterministic code remains more reliable for URL validation, normalization, filters, duplicate detection and the numeric 35/45/20 match score. Unsupported generated claims are removed before publication rather than counted as acceptable output.

Numeric explanation coverage is reported separately from accuracy. A 0% coverage result means Qwen did not publish a numeric score in either evaluated score-tool case; the displayed 100% conditional accuracy therefore has no numeric claims behind it and is not evidence of model scoring quality. The deterministic UI/tool output remains the only score authority.

See `artifacts/job-ai-evaluation.json` for every query, ranking, tool call, citation, latency and adversarial result. `artifacts/job-ai-traces.jsonl` contains privacy-minimized request traces with query hashes instead of raw questions.
