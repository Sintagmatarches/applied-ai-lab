from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import re
from typing import Any


ANSWER_SCHEMA = {"type": "object", "properties": {"answer": {"type": "string", "maxLength": 8000}, "claims": {"type": "array", "maxItems": 30, "items": {"type": "object", "properties": {"text": {"type": "string", "maxLength": 1000}, "evidence_ids": {"type": "array", "maxItems": 10, "items": {"type": "string", "maxLength": 300}}}, "required": ["text", "evidence_ids"], "additionalProperties": False}}, "unknown": {"type": "boolean"}}, "required": ["answer", "claims", "unknown"], "additionalProperties": False}
STOPWORDS = {"about", "after", "also", "and", "are", "because", "been", "being", "but", "can", "for", "from", "has", "have", "into", "not", "of", "only", "that", "the", "their", "this", "tender", "to", "with", "you", "your"}


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9+#.]{2,}", value.lower()) if token not in STOPWORDS}


def _schema_valid(value: Any, schema: dict[str, Any]) -> bool:
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, dict):
            return False
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            return False
        if any(key not in value for key in schema.get("required", [])):
            return False
        return all(_schema_valid(item, properties[key]) for key, item in value.items() if key in properties)
    if expected == "array":
        return isinstance(value, list) and len(value) <= schema.get("maxItems", len(value)) and all(_schema_valid(item, schema.get("items", {})) for item in value)
    if expected == "string":
        return isinstance(value, str) and len(value) <= schema.get("maxLength", len(value))
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def _numbers(value: str) -> set[str]:
    return {item.replace(",", ".") for item in re.findall(r"(?<![a-z])\d+(?:[.,]\d+)?", value.lower())}


@dataclass(frozen=True)
class GroundingResult:
    answer: str
    claims: list[dict[str, Any]]
    citations: list[dict[str, str]]
    unknown: bool
    schema_valid: bool
    raw_supported_claims: int
    raw_unsupported_claims: int
    post_gate_unsupported_claims: int
    citation_validity: float
    claim_support_rate: float
    factual_consistency: float
    unsupported_claim_rate: float

    def public(self) -> dict[str, Any]:
        return asdict(self)


def _empty(message: str, *, schema_valid: bool, unsupported: int, citation_validity: float = 1.0) -> GroundingResult:
    rate = 1.0 if unsupported else 0.0
    return GroundingResult(message, [], [], True, schema_valid, 0, unsupported, 0, citation_validity, 0.0, 0.0, rate)


def validate_grounded_output(raw: str, evidence: list[dict[str, Any]]) -> GroundingResult:
    known = {str(item["evidence_id"]): item for item in evidence if item.get("evidence_id")}
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return _empty("Malformed model output was rejected.", schema_valid=False, unsupported=1)
    if not _schema_valid(payload, ANSWER_SCHEMA):
        return _empty("Invalid structured output was rejected.", schema_valid=False, unsupported=1)

    supported, unsupported, citation_total, citation_valid = [], 0, 0, 0
    for claim in payload["claims"]:
        ids = [str(item) for item in claim["evidence_ids"]]
        citation_total += len(ids)
        valid_ids = [item for item in ids if item in known]
        citation_valid += len(valid_ids)
        claim_text = claim["text"].strip()
        claim_tokens = _tokens(claim_text)
        evidence_text = " ".join(
            str(known[evidence_id].get(key, ""))
            for evidence_id in valid_ids
            for key in ("text", "excerpt", "title", "buyer", "_tool_evidence")
        )
        evidence_tokens = _tokens(evidence_text)
        overlap = len(claim_tokens & evidence_tokens) / max(1, len(claim_tokens))
        numeric_consistent = _numbers(claim_text) <= _numbers(evidence_text)
        decision_words = set(re.findall(r"\b(?:BID|NO_BID|REVIEW|INSUFFICIENT_EVIDENCE)\b", claim_text.upper()))
        assessment_evidence = any(known[item].get("_tool_name") in {"assess_supplier_fit", "explain_bid_decision", "find_supplier_gaps"} for item in valid_ids)
        decisions_consistent = not decision_words or assessment_evidence and all(word in evidence_text.upper() for word in decision_words)
        malicious = re.search(r"ignore all previous|system prompt|fake:\d+|<untrusted", claim_text, re.I)
        if valid_ids and len(valid_ids) == len(ids) and overlap >= .5 and numeric_consistent and decisions_consistent and not malicious:
            supported.append({"text": claim_text, "evidence_ids": valid_ids})
        else:
            unsupported += 1

    total = len(supported) + unsupported
    validity = citation_valid / citation_total if citation_total else 1.0
    if not supported:
        return _empty("Retrieved procurement evidence is insufficient to answer that question.", schema_valid=True, unsupported=unsupported, citation_validity=validity)
    cited = list(dict.fromkeys(item for claim in supported for item in claim["evidence_ids"]))
    citations = [{"evidence_id": item, "notice_id": str(known[item].get("notice_id", "")), "title": str(known[item].get("title", "Evidence")), "url": str(known[item].get("notice_url") or known[item].get("source_url") or "")} for item in cited]
    answer = " ".join(f"{claim['text']} {' '.join(f'[{item}]' for item in claim['evidence_ids'])}" for claim in supported)
    support_rate = len(supported) / total if total else 0.0
    return GroundingResult(answer, supported, citations, False, True, len(supported), unsupported, 0, validity, support_rate, support_rate, unsupported / total if total else 0.0)
