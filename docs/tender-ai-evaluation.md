# EU Tender Intelligence evaluation

Measured 18 August 2026 with `python -m tender_ai.evals.run`. The 14-case procurement fixture is synthetic regression evidence and is not represented as live TED data.

| Area | Result |
| --- | ---: |
| Retrieval Recall@5 / MRR | 1.000 / 1.000 |
| Requirement extraction precision / recall | 1.000 / 1.000 |
| Mandatory classification / numeric / currency / deadline accuracy | 1.000 each |
| Agent tool selection / valid arguments / execution | 1.000 each |
| Grounding raw supported / unsupported claims | 1 / 1 |
| Evidence correctness before gate | 0.500 |
| Unsupported claims after gate | 0 |
| Mandatory-rule / status accuracy | 1.000 / 1.000 |
| Change-field recall / materiality / reassessment | 1.000 each |
| Prompt injection / forged evidence / malicious document / tool manipulation blocked | 1.000 each |
| Structured-output schema validity | 1.000 |

The cases cover obvious BID and NO_BID, missing certification, turnover and reference failures, ambiguous conditions, multiple lots, conflicting/unknown evidence, deadline and eligibility changes, a decision-changing corrigendum, source prompt injection and forged evidence IDs.

These perfect fixture metrics show regression behavior on a small declared set, not general procurement-language performance. Real XML extraction is reported separately and intentionally returns `REVIEW` when conditions cannot be converted safely to deterministic operands. The complete machine-readable output is in `artifacts/tender-evaluation.json`.

Reproduce:

```bash
python -m unittest discover -s tender_ai/tests
python -m tender_ai.evals.run
```
