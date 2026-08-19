# EU Tender Intelligence improvement report

Date: 19 August 2026

## Baseline

The pre-change repository built and its existing suites passed (14 rendered/Worker checks, 27 TypeScript checks and 16 Python tender tests). That green baseline concealed correctness gaps: all failed requirements could block, assessment was notice-level, missing values earned fit points, public/local implementations drifted, model tools could carry supplier facts, security text entered requirements, XML was assigned too broadly, and the evaluation reported small synthetic fixtures as uniformly perfect. The baseline live run found 35 notices and five retrieval hits, but the Qwen answer used deterministic fallback.

## Root causes and corrections

- **Eligibility:** decision aggregation ignored `mandatory` and lot ownership. Both runtimes now implement `PASS/FAIL/UNKNOWN/NOT_APPLICABLE` per lot; only mandatory failures block, and the notice summary preserves eligible/blocked/review/insufficient lots independently.
- **Fit:** a denominator-based capability score made extra capabilities harmful, and missing/global evidence was treated as positive. Components are now additive and inspectable; missing value/geography contributes zero and lot value/deadline are used.
- **TED structure:** requested selection/award fields were not fully consumed, while prose extraction was overused. Structured selection stages, submission languages, award numeric values and weight semantics are primary; regex is fallback.
- **Multi-lot mapping:** array position and whole-document XML text were treated as reliable ownership. XML now maps by real lot identifiers, ambiguous ownership remains unassigned, and parity fixtures cover missing/reordered/multilingual fields.
- **Runtime drift:** TS and Python had independently evolved semantics, including the bug where TypeScript converted absent lot value to `0 EUR`. A canonical cross-runtime fixture now compares lots, requirements, awards and decisions.
- **Agent trust:** assessment tool arguments could conceptually carry model-written supplier facts. The trusted runtime injects the versioned profile outside strict model schemas; adversarial extra profile fields are rejected.
- **Agent orchestration:** one selection pass was not a real agent loop. The loop is bounded by steps, calls and time, returns tool results for further selection, records each stage, forces a strict structured-final repair and exposes model unavailable/rejected/empty/fallback states.
- **Grounding:** citation existence and low lexical overlap were insufficient. Full recursive schema validation, evidence allowlisting, higher support threshold, numeric consistency and deterministic decision-tool consistency now gate claims.
- **Ingestion/security:** official links lacked complete boundary enforcement. HTTPS/hostname allowlists, byte caps before parse, content-type checks, safe XML, Retry-After/backoff/jitter, bounded XML concurrency and categorized failures are implemented. Prompt injection is stored separately as a security finding.
- **Version/storage:** internal revisions were conflated with TED source version and derived extraction could change the source hash. Source version, ingestion revision, schema/extractor versions and canonical fingerprint are separate; CPV rows are normalized and changed evidence invalidates embeddings.
- **Public API/UX:** totals and load-more semantics mixed TED totals with post-filter matches, personalized results were cacheable, and the page opened empty without an obvious workflow. The API now validates real dates/CPV/countries/procedure, reports filtered counts honestly, deduplicates batches and uses private no-store. The page offers one live CPV example, lot decisions, evidence/award inspectors, editable full profile, explicit watch recheck and public/local/recorded boundaries.

## Verification after change

- TypeScript tender suite: 11/11; date suite: 6/6 including year/leap/timezone boundaries and implausible-year guard.
- Python tender suite: 24/24, including multi-step repair, trusted-profile attacks, grounding, SSRF and unsafe XML.
- Typecheck, ESLint, rendered HTML and targeted cross-project regression passed before final release validation.
- Terraform 1.9.8 `fmt -check`, provider initialization and `validate` pass after adding the required Container Apps traffic weight.
- The OCI image built locally with Podman as image `98f4441bf20d…`; a non-root container started and returned HTTP 200 from `/health`. It correctly reported local Ollama disconnected inside that isolated smoke test.
- The first remote dependency audit exposed six 2026 Starlette advisories under the old FastAPI 0.116.1 constraint. FastAPI/Starlette were upgraded and pinned to 0.141.1/1.6.0; the clean-environment audit now blocks regressions in CI.
- Retrieval microbenchmark at 768 dimensions measured 168 ms / 833 ms / 1,660 ms for 1k / 5k / 10k exact scans on this host. All vector/lexical blends tied on the two-query recorded set, so the previous unexplained 72/28 blend was replaced with a neutral 50/50 and the 10k safety boundary retained.

## Evaluation and live evidence

The new evaluation separates 14 synthetic regressions from two recorded real TED notices. The small real structured fixture has Recall@5/MRR/nDCG/filter correctness 1.0 and structured extraction/mandatory/lot/numeric accuracy 1.0; these are fixture results, not general-quality estimates. The adversarial grounding set intentionally records citation validity 0.667, support/factual consistency 0.333 and raw unsupported rate 0.667; the gate leaves zero unsupported claims.

The final live run queried 20 February–19 August 2026 and returned 35 unique notices. Finland `data` had 178 TED matches, `analytics` 20, and ICT/Data CPV `72*` 543; these are procurement matches, not analyst vacancies. Persistence created 68 lots, 124 requirements, 62 award criteria and 261 evidence records with zero failures; 12/12 linked XML attempts succeeded. Embedding took 35.719 s, retrieval 175 ms over 195 candidates, and Qwen/tool execution took 50.799 s.

The local 3B model selected the correct real `get_notice` tool, but still failed to emit an acceptable supported final claim set after schema repair. The published live status remains `DETERMINISTIC_FALLBACK` with fallback rate 1.0 for that single live case. Citation validity/support/factual consistency are 1.0 after fallback and unsupported claims are zero, but this is explicitly not counted as model-answer success. An earlier cold attempt also exposed the old 45-second request timeout; it is now 90 seconds inside the bounded 180-second agent target.

## Remaining limitations and user actions

- The real evaluation set is only two notices and cannot establish general extraction/retrieval quality.
- No defensible real amendment pair was observed; amendment regression evidence remains labelled synthetic.
- Exact Python cosine is capped at 10k candidates; scaling needs a measured ANN implementation and larger judged set.
- Public watch is device-local/manual. Persistent polling exists only in the local CLI until an operator schedules it.
- Azure Container Apps Terraform is validated but not deployed. Actual apply requires the user's subscription, registry image and private Ollama endpoint; this is the only Tender-specific external action in `docs/manual-tasks/USER_ACTIONS.md`.
- The public site does not and cannot run loopback Ollama. It exposes only committed read-only verification evidence for the local AI path.
