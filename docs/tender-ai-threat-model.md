# Tender AI threat model

The matrix is regression coverage informed by relevant OWASP GenAI risk categories. It is not a blanket “OWASP compliant” claim.

| Threat | Boundary | Deterministic evidence | Result |
| --- | --- | --- | --- |
| Direct/indirect prompt injection | TED prose remains untrusted data; instruction-like fragments are quarantined and cannot become eligibility | `indirect-source-injection` | Pass |
| Retrieved instruction execution / vector manipulation | Retrieved prompt-like text has no authority over tools, profile or grounding | `retrieval-injection-claim` | Pass |
| Trusted-profile manipulation | Supplier facts are runtime-owned and absent from model-controlled schemas | `trusted-profile-boundary` | Pass |
| Tool argument smuggling / excessive agency | Strict nested schemas reject unknown/privileged fields and unknown tools | `tool-argument-smuggling-rejected` | Pass |
| Forged evidence IDs | Claims resolve only IDs returned by executed tools | `forged-citation` | Pass |
| Cross-document contamination | Explicit publication references must match cited evidence metadata | `cross-notice` | Pass |
| Cross-lot contamination | Explicit lot references must match cited evidence metadata | `cross-lot` | Pass |
| Unsupported numeric misinformation | Claim numbers must occur in cited evidence | `wrong-numeric` | Pass |
| Decision inconsistency | BID/NO_BID/REVIEW claims require deterministic assessment-tool evidence | `decision-inconsistent` | Pass |
| SSRF | Only official HTTPS TED hostnames are accepted | `loopback-url` | Pass |
| XML entity/size bombs | Body caps precede parse; DTD/entity declarations are rejected | `unsafe-xml` | Pass |
| Unbounded resource use | HTTP/body, agent step/tool/time/output and exact-vector-scan limits | `bounded-rounds` plus existing limit tests | Pass |

The committed suite has 12/12 passing boundaries. The grounding suite separately covers supported claims, wrong deadline/buyer, unverifiable claims and consistent decisions; nine deliberately unsupported pre-gate claims yield zero unsupported claims after the deterministic gate.

Privacy is also a trust boundary. Trace schema v2 rejects raw `query`, `question`, prompt/message, supplier-profile, environment and authorization fields. It stores full query SHA-256 plus length, generated IDs, tool categories/counts, optional model metrics and outcomes. Tests prove raw questions/profiles are absent by default.

Residual risks remain: lexical/embedding retrieval can rank irrelevant evidence; explicit scope enforcement cannot infer an unstated notice/lot identity; regex fallback may miss prose; local SQLite/file access belongs to the operator; the recorded corpus is small and curated; a local model may consistently fall back; and these tests do not establish legal procurement correctness or a production hallucination rate.
