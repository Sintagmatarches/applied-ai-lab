from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any

from .ollama import OllamaClient
from .storage import TenderKnowledgeBase


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left: return 0.0
    dot = sum(a*b for a,b in zip(left,right)); ln=math.sqrt(sum(v*v for v in left)); rn=math.sqrt(sum(v*v for v in right))
    return dot/(ln*rn) if ln and rn else 0.0


@dataclass(frozen=True)
class SearchHit:
    evidence: dict[str, Any]
    vector_score: float
    lexical_score: float
    hybrid_score: float

    def public(self) -> dict[str, Any]:
        return {key: self.evidence.get(key) for key in ("evidence_id", "notice_id", "kind", "text", "title", "buyer", "notice_url", "buyer_country", "cpv_codes", "estimated_value", "submission_deadline")} | {"vector_score": round(self.vector_score, 6), "lexical_score": round(self.lexical_score, 6), "hybrid_score": round(self.hybrid_score, 6)}


class HybridRetriever:
    def __init__(self, storage: TenderKnowledgeBase, ollama: OllamaClient, top_k: int = 5): self.storage, self.ollama, self.top_k = storage, ollama, top_k

    def index_pending(self, limit: int = 100) -> dict[str, Any]:
        rows = self.storage.pending_embeddings(self.ollama.config.embedding_model, limit)
        if not rows: return {"indexed": 0, "latency_ms": 0}
        vectors, metrics = self.ollama.embed([row["text"] for row in rows])
        for row, vector in zip(rows, vectors): self.storage.set_embedding(row["evidence_id"], self.ollama.config.embedding_model, vector)
        return {"indexed": len(rows), "latency_ms": metrics.latency_ms, "model": self.ollama.config.embedding_model}

    def search(self, query: str, *, top_k: int | None = None, country: str | None = None, cpv: str | None = None, buyer: str | None = None, min_value: float | None = None, deadline_before: str | None = None) -> tuple[list[SearchHit], dict[str, Any]]:
        started=time.perf_counter(); vectors, embed_metrics=self.ollama.embed([query]); query_vector=vectors[0]
        lexical_ids=self.storage.lexical_search(query, 50); lexical_rank={item: 1/(rank+1) for rank,item in enumerate(lexical_ids)}
        hits=[]
        candidates = self.storage.embedded_evidence()
        if len(candidates) > self.ollama.config.vector_scan_limit:
            raise RuntimeError(f"Exact vector scan boundary exceeded ({len(candidates)} > {self.ollama.config.vector_scan_limit}); build a local ANN index before scaling further")
        vector_weight = self.ollama.config.retrieval_vector_weight
        lexical_weight = self.ollama.config.retrieval_lexical_weight
        total_weight = vector_weight + lexical_weight
        if total_weight <= 0:
            raise ValueError("retrieval weights must have a positive sum")
        vector_weight, lexical_weight = vector_weight / total_weight, lexical_weight / total_weight
        for item in candidates:
            if country and item.get("buyer_country") != country.upper(): continue
            if cpv and not any(str(code).startswith(cpv.rstrip("*")) for code in item.get("cpv_codes", [])): continue
            if buyer and buyer.lower() not in str(item.get("buyer", "")).lower(): continue
            if min_value is not None and (item.get("estimated_value") is None or item["estimated_value"] < min_value): continue
            if deadline_before and item.get("submission_deadline") and item["submission_deadline"] > deadline_before: continue
            vector=max(0.0, cosine(query_vector,item["vector"])); lexical=lexical_rank.get(item["evidence_id"],0.0)
            hits.append(SearchHit(item,vector,lexical,vector_weight*vector+lexical_weight*lexical))
        hits.sort(key=lambda hit: hit.hybrid_score, reverse=True)
        return hits[:top_k or self.top_k], {"retrieval_latency_ms": round((time.perf_counter()-started)*1000,3), "embedding_latency_ms": embed_metrics.latency_ms, "candidate_count": len(hits), "scan_strategy": "exact_cosine", "vector_weight":round(vector_weight,3), "lexical_weight":round(lexical_weight,3), "scan_limit":self.ollama.config.vector_scan_limit}
