from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any

from .ollama import OllamaClient
from .storage import JobKnowledgeBase


@dataclass(frozen=True)
class SearchHit:
    job: dict[str, Any]
    vector_score: float
    lexical_score: float
    hybrid_score: float

    def public(self) -> dict[str, Any]:
        return {
            "job_id": self.job["id"],
            "url": self.job["canonical_url"],
            "source": self.job["source"],
            "company": self.job["company"],
            "title": self.job["title"],
            "location": self.job["location"],
            "remote": self.job["remote"],
            "requirements": self.job["requirements"],
            "description": self.job["description"],
            "vector_score": round(self.vector_score, 6),
            "lexical_score": round(self.lexical_score, 6),
            "hybrid_score": round(self.hybrid_score, 6),
        }


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class HybridRetriever:
    def __init__(self, storage: JobKnowledgeBase, ollama: OllamaClient):
        self.storage = storage
        self.ollama = ollama

    def index_pending(self, batch_size: int = 16) -> dict[str, Any]:
        pending = self.storage.pending_embeddings(
            self.ollama.config.embedding_model, limit=500
        )
        started = time.perf_counter()
        prompt_tokens = 0
        for offset in range(0, len(pending), batch_size):
            batch = pending[offset : offset + batch_size]
            result = self.ollama.embed([row["normalized_text"] for row in batch])
            prompt_tokens += result.metrics.prompt_tokens or 0
            for row, vector in zip(batch, result.embeddings):
                self.storage.set_embedding(row["id"], result.model, vector)
        return {
            "indexed": len(pending),
            "model": self.ollama.config.embedding_model,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "prompt_tokens": prompt_tokens,
        }

    def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        source: str | None = None,
        location: str | None = None,
        remote_only: bool = False,
    ) -> tuple[list[SearchHit], dict[str, Any]]:
        started = time.perf_counter()
        limit = max(1, min(20, top_k or self.ollama.config.top_k))
        embedded = self.ollama.embed([query])
        query_vector = embedded.embeddings[0]
        candidates = self.storage.list_jobs(
            source=source, location=location, remote_only=remote_only
        )
        lexical_ids = self.storage.lexical_search(query, limit=max(20, limit * 4))
        lexical_rank = {
            job_id: 1.0 - (rank / max(1, len(lexical_ids)))
            for rank, job_id in enumerate(lexical_ids)
        }
        hits: list[SearchHit] = []
        for job in candidates:
            vector = job.get("embedding")
            if not vector:
                continue
            vector_score = (cosine(query_vector, vector) + 1.0) / 2.0
            lexical_score = lexical_rank.get(job["id"], 0.0)
            hybrid_score = 0.75 * vector_score + 0.25 * lexical_score
            hits.append(SearchHit(job, vector_score, lexical_score, hybrid_score))
        hits.sort(key=lambda hit: hit.hybrid_score, reverse=True)
        return hits[:limit], {
            "retrieval_latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "embedding_latency_ms": embedded.metrics.latency_ms,
            "embedding_model": embedded.model,
            "candidate_count": len(candidates),
            "retrieved_ids": [hit.job["id"] for hit in hits[:limit]],
        }
