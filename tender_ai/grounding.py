from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import re
from typing import Any


ANSWER_SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}, "claims": {"type": "array", "items": {"type": "object", "properties": {"text": {"type": "string"}, "evidence_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["text", "evidence_ids"], "additionalProperties": False}}, "unknown": {"type": "boolean"}}, "required": ["answer", "claims", "unknown"], "additionalProperties": False}
STOPWORDS={"about","after","also","and","are","because","been","being","but","can","for","from","has","have","into","not","of","only","that","the","their","this","tender","to","with","you","your"}


def _tokens(value: str) -> set[str]: return {token for token in re.findall(r"[a-z0-9+#.]{2,}", value.lower()) if token not in STOPWORDS}


@dataclass(frozen=True)
class GroundingResult:
    answer: str; claims: list[dict[str, Any]]; citations: list[dict[str, str]]; unknown: bool
    schema_valid: bool; raw_supported_claims: int; raw_unsupported_claims: int
    post_gate_unsupported_claims: int; evidence_correctness: float
    def public(self) -> dict[str, Any]: return asdict(self)


def validate_grounded_output(raw: str, evidence: list[dict[str, Any]]) -> GroundingResult:
    known={str(item["evidence_id"]): item for item in evidence if item.get("evidence_id")}
    try: payload=json.loads(raw)
    except (json.JSONDecodeError, TypeError): return GroundingResult("Malformed model output was rejected.",[],[],True,False,0,1,0,1.0)
    valid=isinstance(payload,dict) and isinstance(payload.get("answer"),str) and isinstance(payload.get("claims"),list) and isinstance(payload.get("unknown"),bool)
    if not valid: return GroundingResult("Invalid structured output was rejected.",[],[],True,False,0,1,0,1.0)
    supported=[]; unsupported=0; citation_total=0; citation_valid=0
    for claim in payload["claims"]:
        if not isinstance(claim,dict) or not isinstance(claim.get("text"),str) or not isinstance(claim.get("evidence_ids"),list): unsupported+=1; continue
        ids=[str(item) for item in claim["evidence_ids"]]; citation_total+=len(ids); valid_ids=[item for item in ids if item in known]; citation_valid+=len(valid_ids)
        claim_tokens=_tokens(claim["text"]); evidence_tokens=set()
        for evidence_id in valid_ids:
            item=known[evidence_id]; evidence_tokens |= _tokens(" ".join(str(item.get(key,"")) for key in ("text","excerpt","title","buyer","_tool_evidence")))
        malicious=re.search(r"ignore all previous|system prompt|fake:\d+|<untrusted", claim["text"], re.I)
        overlap=len(claim_tokens & evidence_tokens)/max(1,len(claim_tokens))
        if valid_ids and overlap >= .2 and not malicious: supported.append({"text":claim["text"].strip(),"evidence_ids":valid_ids})
        else: unsupported+=1
    if not supported: return GroundingResult("Retrieved procurement evidence is insufficient to answer that question.",[],[],True,True,0,unsupported,0,citation_valid/citation_total if citation_total else 1.0)
    cited=list(dict.fromkeys(item for claim in supported for item in claim["evidence_ids"]))
    citations=[{"evidence_id":item,"notice_id":str(known[item].get("notice_id","")),"title":str(known[item].get("title","Evidence")),"url":str(known[item].get("notice_url") or known[item].get("source_url") or "")} for item in cited]
    answer=" ".join(f"{claim['text']} {' '.join(f'[{item}]' for item in claim['evidence_ids'])}" for claim in supported)
    return GroundingResult(answer,supported,citations,False,True,len(supported),unsupported,0,citation_valid/citation_total if citation_total else 1.0)
