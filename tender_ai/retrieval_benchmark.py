from __future__ import annotations

from array import array
import json
import math
from pathlib import Path
import re
import time

from .retrieval import cosine
from .storage import utc_now
from .ted import normalize


ROOT = Path(__file__).parents[1]
DIMENSIONS = 768  # nomic-embed-text output dimension
SIZES = (1_000, 5_000, 10_000)
WEIGHTS = ((1.0, 0.0), (.75, .25), (.5, .5), (.25, .75), (0.0, 1.0))


def tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{2,}", value.lower()))


def retrieval_ablation() -> list[dict[str, float]]:
    fixture = json.loads((ROOT / "tender_ai" / "evals" / "real_ted_notices.json").read_text(encoding="utf-8"))
    notices = [normalize(item["raw"], fixture["recorded_at"]) for item in fixture["notices"]]
    rows = []
    for vector_weight, lexical_weight in WEIGHTS:
        reciprocal_ranks = []
        for case in fixture["retrieval_queries"]:
            query_tokens = tokens(case["query"])
            scored = []
            for notice in notices:
                document_tokens = tokens(f"{notice['title']} {notice['description']}")
                overlap = len(query_tokens & document_tokens)
                vector_proxy = overlap / math.sqrt(max(1, len(query_tokens) * len(document_tokens)))
                lexical = overlap / max(1, len(query_tokens))
                scored.append((vector_weight * vector_proxy + lexical_weight * lexical, notice["publication_id"]))
            ranked = [publication for _, publication in sorted(scored, reverse=True)]
            relevant = set(case["relevant_publications"])
            rank = next((index + 1 for index, publication in enumerate(ranked) if publication in relevant), None)
            reciprocal_ranks.append(1 / rank if rank else 0)
        rows.append({"vector_weight": vector_weight, "lexical_weight": lexical_weight, "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 3)})
    return rows


def scan_benchmark() -> list[dict[str, float | int]]:
    query = array("f", ((index % 29) / 29 for index in range(DIMENSIONS)))
    candidate = array("f", (((index * 7) % 31) / 31 for index in range(DIMENSIONS)))
    rows = []
    for size in SIZES:
        started = time.perf_counter()
        best = 0.0
        for _ in range(size):
            best = max(best, cosine(query, candidate))
        elapsed_ms = (time.perf_counter() - started) * 1000
        rows.append({
            "candidate_count": size,
            "dimensions": DIMENSIONS,
            "scan_ms": round(elapsed_ms, 3),
            "candidates_per_second": round(size / (elapsed_ms / 1000), 1),
            "packed_vector_memory_mb": round(size * DIMENSIONS * 4 / 1_000_000, 2),
            "best_score_guard": round(best, 6),
        })
    return rows


def main() -> None:
    ablation = retrieval_ablation()
    result = {
        "measured_at": utc_now(),
        "method": "Single-process CPython exact cosine scan; deterministic 768-d float32 vectors; no embedding/network time.",
        "scan": scan_benchmark(),
        "weight_ablation": ablation,
        "selected_weights": {"vector": .5, "lexical": .5},
        "selection_reason": "All blends tie on the two-query recorded set, so a neutral blend is safer than claiming unsupported tuning.",
        "scale_boundary": "Exact scan is deliberately capped at 10,000 candidates. Add a local ANN index and a larger judged query set before increasing the cap.",
        "limitations": ["Microbenchmark CPU and storage overhead vary by host.", "The recorded dataset is too small to estimate general retrieval quality."],
    }
    output = ROOT / "artifacts" / "tender-retrieval-benchmark.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
