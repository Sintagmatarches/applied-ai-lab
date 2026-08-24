from __future__ import annotations

from array import array
import json
from pathlib import Path
import time

from .retrieval import cosine
from .storage import utc_now


ROOT = Path(__file__).parents[1]
DIMENSIONS = 768  # nomic-embed-text output dimension
SIZES = (1_000, 5_000, 10_000)
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
    result = {
        "benchmarkSchemaVersion": "2.0.0",
        "measured_at": utc_now(),
        "evidenceClass": "informational synthetic performance microbenchmark; never semantic retrieval quality",
        "method": "Single-process CPython exact cosine scan over deterministic 768-d float32 vectors; excludes embedding and network time.",
        "scan": scan_benchmark(),
        "selected_weights": {"vector": .5, "lexical": .5},
        "quality_evidence": "artifacts/tender-evaluation.json retrieval block; actual nomic-embed-text similarity matrix with tuning/holdout separation",
        "selection_reason": "The real recorded-model tuning evaluation ties 25/75, 50/50 and 75/25; the frozen tie-break preserves neutral 50/50. This microbenchmark does not select weights.",
        "scale_boundary": "Exact scan is deliberately capped at 10,000 candidates. Add a local ANN index and a larger judged query set before increasing the cap.",
        "limitations": ["Microbenchmark timing varies by host.", "Synthetic vectors measure scan cost only and make no semantic-quality claim."],
    }
    output = ROOT / "artifacts" / "tender-retrieval-benchmark.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
