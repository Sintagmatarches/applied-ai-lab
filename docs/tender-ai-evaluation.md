# EU Tender Intelligence evaluation

The evaluation has three explicitly different evidence classes:

- 14 synthetic procurement cases for deterministic regression only.
- Two recorded real 2026 TED notices with mechanically verifiable structured fields; they are not called human-labelled.
- A timestamped network/Ollama verification artifact, whose fallback and failure states are reported as observed.

The latest `python -m tender_ai.evals.run` result is in `artifacts/tender-evaluation.json`. On the tiny two-notice recorded set, Recall@5, MRR, nDCG@5 and country-filter correctness are 1.0. Structured extraction precision/recall, mandatory classification, lot assignment and numeric award-value accuracy are also 1.0. These values establish fixture correctness only; two notices cannot estimate general procurement-language quality.

The adversarial grounding case contains one supported numeric claim, one contradictory numeric claim and one forged citation. Citation validity is 0.667, raw claim support/factual consistency is 0.333, raw unsupported-claim rate is 0.667 and unsupported claims after the gate are zero. This deliberately negative result is stronger evidence than renaming citation existence as “evidence correctness.”

Agent metrics are read from the latest live artifact and distinguish model success from fallback. A fallback rate of 1.0 means the safety path was used; it is not counted as a successful model answer. Operational output reports TED p50/p95, embedding, retrieval, LLM and total agent latency when observed.

`python -m tender_ai.retrieval_benchmark` measures 768-dimensional exact cosine at 1k/5k/10k candidates and tests vector/lexical blends from 100/0 through 0/100 on the recorded queries. All tested blends currently tie, so the selected 50/50 default is neutral rather than claimed as optimized. The hard 10k scan limit remains until a larger judged set and ANN benchmark justify a change.

Reproduce:

```bash
python -m unittest discover -s tender_ai/tests
npx tsx --test tests/tenders.test.ts
python -m tender_ai.evals.run
python -m tender_ai.retrieval_benchmark
```

Known limitations: the real structured set is small, no defensible live amendment pair has been observed, and local open-source model quality varies by host/model. Synthetic cases cover multi-lot/reordered/missing fields, multilingual data, mandatory/optional semantics, changes and adversarial inputs but are not general-quality labels.
