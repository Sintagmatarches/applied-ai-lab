# Tender AI data and decision definitions

- **TED source version:** version published by TED/eForms. It is never replaced by an internal counter.
- **Ingestion revision:** local immutable snapshot sequence when the canonical source fingerprint changes.
- **Canonical source fingerprint:** hash of source notice/lot fields, excluding derived extraction output.
- **Mandatory:** an applicable eligibility condition explicitly structured or evidenced as required. Only its `FAIL` can block.
- **PASS / FAIL:** trusted supplier facts deterministically satisfy / contradict a structured condition.
- **UNKNOWN:** applicable evidence exists but cannot be compared safely.
- **NOT_APPLICABLE:** TED marks the condition not required for the relevant stage.
- **BID:** all applicable mandatory checks for that lot pass.
- **NO_BID:** at least one applicable mandatory check for that lot fails.
- **REVIEW:** no mandatory failure, but at least one mandatory check is unknown.
- **INSUFFICIENT_EVIDENCE:** no applicable mandatory eligibility evidence was found.
- **Heuristic fit:** uncalibrated component score for ranking; it never overrides eligibility.
- **Security finding:** quarantined document-risk evidence. It is not a procurement requirement.
- **PUBLIC LIVE:** anonymous current TED query and browser-side deterministic assessment.
- **LOCAL AI:** XML, persistence, embeddings, agent and scheduled watch path run by the operator.
- **RECORDED VERIFIED EVIDENCE:** committed timestamped outputs from an actual prior run, not a live browser execution.
