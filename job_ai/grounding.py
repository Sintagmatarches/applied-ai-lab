from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any


STOPWORDS = {
    "about", "after", "also", "and", "are", "because", "been", "being", "but",
    "can", "company", "for", "from", "has", "have", "into", "job", "not", "of",
    "only", "role", "that", "the", "their", "this", "to", "with", "you", "your",
}

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "job_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "job_ids"],
                "additionalProperties": False,
            },
        },
        "unknown": {"type": "boolean"},
    },
    "required": ["answer", "claims", "unknown"],
    "additionalProperties": False,
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#.]{2,}", value.lower())
        if token not in STOPWORDS
    }


def _trusted_tool_text(value: Any) -> str:
    """Flatten deterministic tool output while excluding identifiers/URLs."""
    if isinstance(value, dict):
        return " ".join(
            _trusted_tool_text(item)
            for key, item in value.items()
            if key not in {"id", "job_id", "url", "canonical_url"}
        )
    if isinstance(value, list):
        return " ".join(_trusted_tool_text(item) for item in value)
    return str(value)


@dataclass(frozen=True)
class GroundingResult:
    answer: str
    claims: list[dict[str, Any]]
    citations: list[dict[str, str]]
    unknown: bool
    schema_valid: bool
    supported_claims: int
    unsupported_claims: int
    citation_correctness: float


def validate_grounded_output(raw: str, evidence: list[dict[str, Any]]) -> GroundingResult:
    jobs = {str(job["id"]): job for job in evidence}
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return GroundingResult(
            "The local model returned malformed output, so no factual answer was published.",
            [], [], True, False, 0, 0, 1.0,
        )
    schema_valid = (
        isinstance(payload, dict)
        and isinstance(payload.get("answer"), str)
        and isinstance(payload.get("claims"), list)
        and isinstance(payload.get("unknown"), bool)
    )
    if not schema_valid:
        return GroundingResult(
            "The local model returned invalid structured output, so no factual answer was published.",
            [], [], True, False, 0, 0, 1.0,
        )

    supported: list[dict[str, Any]] = []
    unsupported = 0
    citation_total = 0
    citation_valid = 0
    for claim in payload["claims"]:
        if not isinstance(claim, dict) or not isinstance(claim.get("text"), str) or not isinstance(claim.get("job_ids"), list):
            unsupported += 1
            continue
        ids = [str(job_id) for job_id in claim["job_ids"]]
        citation_total += len(ids)
        known_ids = [job_id for job_id in ids if job_id in jobs]
        claim_tokens = _tokens(claim["text"])
        lower_claim = claim["text"].lower()
        if "<untrusted_job_data>" in lower_claim or "</untrusted_job_data>" in lower_claim:
            unsupported += 1
            continue
        supported_ids: list[str] = []
        for job_id in known_ids:
            job = jobs[job_id]
            id_tokens = _tokens(job_id)
            meaningful_claim_tokens = claim_tokens - id_tokens
            if not meaningful_claim_tokens:
                continue
            evidence_fields = [
                str(job.get("title", "")),
                str(job.get("company", "")),
                str(job.get("location", "")),
                " ".join(str(item) for item in job.get("requirements", [])),
                _trusted_tool_text(job.get("_tool_evidence", "")),
            ]
            evidence_tokens = _tokens(" ".join(evidence_fields))
            overlap = len(meaningful_claim_tokens & evidence_tokens) / max(1, len(meaningful_claim_tokens))
            if overlap >= 0.2:
                supported_ids.append(job_id)
        citation_valid += len(supported_ids)
        if supported_ids:
            supported.append(
                {"text": claim["text"].strip(), "job_ids": supported_ids}
            )
        else:
            unsupported += 1

    citation_correctness = citation_valid / citation_total if citation_total else 1.0
    if not supported:
        return GroundingResult(
            "The retrieved vacancies do not contain enough evidence to answer that question.",
            [], [], True, schema_valid, 0, unsupported, citation_correctness,
        )
    cited_ids = list(dict.fromkeys(job_id for claim in supported for job_id in claim["job_ids"]))
    citations = [
        {
            "job_id": job_id,
            "url": jobs[job_id]["canonical_url"],
            "title": jobs[job_id]["title"],
            "source": jobs[job_id]["source"],
        }
        for job_id in cited_ids
    ]
    answer = " ".join(
        f"{claim['text']} {' '.join(f'[{job_id}]' for job_id in claim['job_ids'])}"
        for claim in supported
    )
    return GroundingResult(
        answer, supported, citations, False, schema_valid, len(supported), unsupported, citation_correctness
    )
