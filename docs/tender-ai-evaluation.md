# EU Tender Intelligence evaluation

## What the evidence means

The project keeps three evidence classes separate:

1. **Deterministic synthetic regression** covers edge cases, adversarial inputs and exact software behavior in CI. It is not real-world quality estimation.
2. **Recorded-real TED evaluation** uses committed published notices and independently represented source-derived expectations. It is not described as human-labelled.
3. **Model-dependent live/recorded verification** records actual local Ollama behavior, fingerprints, tokens, durations, tools and fallback state. It is informational and not a normal-CI gate.

## Corpus v2 and provenance

`tender_ai/evals/real_ted_notices.json` contains 15 notices retrieved anonymously from official `POST https://api.ted.europa.eu/v3/notices/search`. The selection spans Finland, Germany, France, Poland, Spain, the Netherlands, Sweden and Ireland; one to eighteen lots; selection criteria present/absent; price-only and quality/price awards; missing optional fields; multiple CPV areas; and Finnish, Swedish, English, German, French, Polish, Spanish, Basque, Catalan and Occitan submission fields.

Every case records publication number, notice UUID/version, official HTML/XML links when returned, retrieval timestamp, exact source query, selection rationale, explicit field list and compact structured response. Expected lot IDs, country, languages, deadlines, CPV and award values are exact field copies or numeric conversions. Requirement-category names are curated interpretations of the recorded official criterion codes and are explicitly described as such—not independent annotation.

The committed manifest records corpus/query versions, notice IDs, counts and SHA-256 digests. Corpus v2 is `recorded-real-ted-v2.0.0`, with 15 notices and digest `61a7395e6f8fe6663c1348cfb286c088f525a1cbd07e554f471775dd0948c5fa`. Corpus acquisition is an explicit developer action:

```bash
python -m tender_ai.evals.collect_real_ted
# inspect the candidate; deliberate replacement is explicit
python -m tender_ai.evals.collect_real_ted --replace-committed
python -m tender_ai.evals.update_manifest --write
```

CI never calls this path and never silently refreshes fixtures.

## Retrieval methodology and decision

The query set contains 30 curated scenarios: 16 tuning and 14 holdout. Publications, not individual query strings, are assigned wholly to one split, so no notice contributes queries to both. The set covers exact concepts, paraphrases, buyers, countries, CPV, numeric/lot constraints, languages, multi-constraint requests, multilingual terms and a lexically confusing IT hard negative.

`nomic-embed-text:latest` was actually executed locally. `recorded_similarity.json` stores the exact model digest `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`, corpus/query/document digests and the compact cosine matrix—not large vectors. Deterministic CI replays that matrix through the same evidence-level exact-cosine, lexical-rank and weighted-hybrid scoring architecture. A digest mismatch fails before metrics are compared. Synthetic scan vectors remain only in the separate performance microbenchmark.

| Method | Split | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Lexical | tuning (16) | 14/16 | 15/16 | 15/16 | 0.9104 | 0.9144 |
| Vector | tuning (16) | 15/16 | 16/16 | 16/16 | 0.9688 | 0.9769 |
| 50/50 hybrid | tuning (16) | 15/16 | 16/16 | 16/16 | 0.9688 | 0.9769 |
| Lexical | holdout (14) | 14/14 | 14/14 | 14/14 | 1.0000 | 1.0000 |
| Vector | holdout (14) | 13/14 | 14/14 | 14/14 | 0.9643 | 0.9736 |
| 50/50 hybrid | holdout (14) | 14/14 | 14/14 | 14/14 | 1.0000 | 1.0000 |

Filter correctness is reported separately from ranking: all 15/15 scenarios with explicit country, buyer or CPV constraints retained judged-relevant evidence and returned only filter-compliant candidates.

On tuning, 25/75, 50/50 and 75/25 tied. The frozen tie-break prefers the current neutral 50/50 configuration, so no production weight changed. The holdout was evaluated only after that rule was fixed. One tuning hard negative ranked the relevant Limburg budget application second because lexical support/maintenance terms favoured the security-services notice; the failure artifact includes both vector and lexical contributions.

These 30 queries are curated and correlated within 15 notices. The perfect selected-method holdout score is reported with its 14-query denominator and is not generalized beyond this corpus.

## Structured extraction

The v2 evaluator compares full arrays/multisets and penalizes missing and extra values; it never uses `zip()` in a way that ignores unequal tails.

| Field | Result |
| --- | ---: |
| Lot ID sequence / count | 15/15 / 15/15 notices |
| Lot ID items | 60/60 precision and recall |
| Buyer country | 15/15 notices |
| Submission-language array | 15/15 notices |
| Deadline array / missing behavior | 15/15 notices / 5/5 notices with no recorded deadline |
| CPV values | 51/51 precision and recall |
| Structured requirement categories | 103/111 precision and recall |
| Requirement-to-lot assignment | 70/74 precision and recall |
| Mandatory boolean coverage | 111/111 structured requirements; not classification accuracy because this corpus has no independently represented optional criterion |
| Award weights | 29/29 precision; 29/52 recall |

The award-weight result is deliberately not hidden: several valid TED responses expose `BT-541-Lot` without criterion-name cardinality that the current normalizer can safely associate, so 23 expected numeric values remain absent from normalized award criteria. This is a known extraction limitation and a protected non-worsening baseline, not a fabricated 100% score.

## Grounding, agent and security

The deterministic grounding suite has 12 cases: supported qualitative/numeric claims; wrong numeric/deadline/buyer; forged citation; cross-notice and cross-lot contamination; unverifiable claim; consistent/inconsistent decisions; and indirect source injection. All 12 expected outcomes pass and nine deliberately unsupported pre-gate claims produce zero unsupported post-gate claims.

The agent contract separately checks the 14-tool allowlist, unknown tool/argument rejection, argument smuggling, trusted-profile isolation, step/tool/time bounds and evidence provenance: 7/7 pass. No claim about model planning intelligence is inferred from those software checks.

The security matrix has 12 deterministic boundaries informed by relevant OWASP GenAI risks: direct/indirect injection, retrieved instruction execution, profile manipulation, argument smuggling, forged evidence, cross-document/lot contamination, unsupported numbers, decision inconsistency, SSRF, DTD/entity XML and bounded agency. This is regression coverage, not a blanket “OWASP compliant” claim.

## Evaluation contract and baseline

`evaluation_contract.json` versions the dataset, query split, grounding/security suites, prompt and real model fingerprints. `evaluation_baseline.json` binds those input digests to protected metrics. Exact invariants use equality; aggregate extraction metrics use documented 0.01 non-worsening tolerances; holdout retrieval floors use zero tolerance.

```bash
python -m tender_ai.evals.run --check-baseline
```

If code quality regresses, `artifacts/tender-evaluation-failures.json` names the metric, baseline, current value, tolerance, delta and relevant query IDs. A dataset or model-artifact digest change is reported as an input change, not mislabeled as a model regression. Normal CI never overwrites the baseline.

An intentional update requires review of the new corpus/artifact/result plus an explicit release note:

```bash
python -m tender_ai.evals.run --update-baseline --release-note "Why this new version is legitimate"
python -m tender_ai.evals.run --check-baseline
```

## Reproduce

```bash
python -m unittest discover -s tender_ai/tests -v
npx tsx --test tests/tenders.test.ts
python -m tender_ai.evals.run --check-baseline
python -m tender_ai.retrieval_benchmark
python -m tender_ai.operational_report
```

Remaining limits are material: 15 selected notices do not represent all TED procurement, languages, eForms versions or legal correctness; source-derived expectations are not independent human labels; curated retrieval scenarios do not estimate production traffic or hallucination rates; and local model behavior varies by runtime/model digest.
