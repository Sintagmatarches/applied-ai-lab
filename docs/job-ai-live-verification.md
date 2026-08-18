# Local Job AI live verification

This is a dated operational check against real public feed output, separate from the stable evaluation fixture.

Run: `2026-08-18T16:48:17Z`

Public route: production `/api/jobs/search?q=data&location=europe`

Local runtime: Ollama at loopback through the Next.js local proxy

## Full-cycle evidence

- Arbeitnow status: `ok`
- Jobicy status: `ok`
- Normalized/deduplicated public results returned: `56`
- Records selected for this local check: `25`
- SQLite records saved: `25`
- Nomic embeddings created: `25`
- Embedding dimensions: `768`
- Local UI route returned HTTP `200` and `/api/jobs/ai/status` reported both configured models plus `25` jobs / `25` vectors.

The agent was then asked to analyze exact persisted job ID `arbeitnow:head-of-data-gsa-europe-berlin-58521` and state only its title and stored requirements. Qwen selected and successfully called `analyze_job`. The published grounded answer was:

> The job requires knowledge of Python, SQL, Tableau, and Snowflake. `[arbeitnow:head-of-data-gsa-europe-berlin-58521]`

The cited record was [Head of Data - GSA (m/w/d) at sonymusicentertainment](https://www.arbeitnow.com/jobs/companies/sonymusicentertainment/head-of-data-gsa-europe-berlin-58521), sourced through Arbeitnow. Its persisted structured requirements were `SME Germany`, `Python`, `SQL`, `Tableau`, and `Snowflake`, so the published requirement claim is a supported subset.

Execution metrics:

| Metric | Observed |
| --- | ---: |
| Agent status | `ok` |
| Tool | `analyze_job` (`success: true`) |
| Retrieved document IDs | 1 |
| LLM latency | 19,532.571 ms |
| Total request duration | 19,536.223 ms |
| Prompt + completion tokens | 3,649 |
| Supported / unsupported published claims | 1 / 0 |
| Citation correctness | 100% |

The previous broad semantic query also exercised real vector retrieval and returned five current document IDs in 1,199.425 ms, but Qwen did not produce a sufficiently supported final claim. The grounding layer therefore published an explicit insufficient-evidence fallback instead of a fabricated answer. This is retained as evidence that the failure boundary works, not hidden as a success.

The local SQLite database and live trace file remain ignored under `data/job-ai/`. Reproducible fixture-level evidence is committed in `artifacts/job-ai-evaluation.json` and `artifacts/job-ai-traces.jsonl`.
