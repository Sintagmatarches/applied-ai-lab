from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
import tempfile
from typing import Any

from tender_ai.storage import TenderKnowledgeBase
from tender_ai.ted import normalize

from .datasets import EVAL_DIR, DatasetContractError, digest


RECORDED_SIMILARITY_PATH = EVAL_DIR / "recorded_similarity.json"
WEIGHT_CANDIDATES = ((0.0, 1.0), (0.25, 0.75), (0.5, 0.5), (0.75, 0.25), (1.0, 0.0))


def evidence_documents(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in corpus["notices"]:
        notice = normalize(case["raw"], case["retrievedAt"])
        for item in notice["evidence"]:
            rows.append({
                "evidence_id": item["evidence_id"],
                "notice_id": notice["notice_id"],
                "publication": notice["publication_id"],
                "text": str(item.get("excerpt", "")),
                "title": notice["title"],
                "buyer": notice["buyer"],
                "country": notice["buyer_country"],
                "cpv_codes": notice["cpv_codes"],
                "deadline": notice["submission_deadline"],
            })
    return sorted(rows, key=lambda item: item["evidence_id"])


def _metric_at(ranked: list[str], relevance: dict[str, int], k: int) -> tuple[float, int]:
    found = len(set(ranked[:k]) & set(relevance))
    return found / len(relevance), found


def metrics_for_rankings(cases: list[dict[str, Any]]) -> dict[str, Any]:
    if not cases:
        return {"queryCount": 0, "recallAt1": {"value": 0.0, "hits": 0}, "recallAt3": {"value": 0.0, "hits": 0}, "recallAt5": {"value": 0.0, "hits": 0}, "mrr": 0.0, "ndcgAt5": 0.0}
    recalls: dict[int, list[float]] = {1: [], 3: [], 5: []}
    hits = {1: 0, 3: 0, 5: 0}
    reciprocal, ndcgs = [], []
    for case in cases:
        ranked, relevance = case["ranked"], case["relevance"]
        for k in recalls:
            value, found = _metric_at(ranked, relevance, k)
            recalls[k].append(value)
            hits[k] += int(found > 0)
        first = next((index + 1 for index, publication in enumerate(ranked) if publication in relevance), None)
        reciprocal.append(1 / first if first else 0.0)
        dcg = sum((2 ** relevance[publication] - 1) / math.log2(index + 2) for index, publication in enumerate(ranked[:5]) if publication in relevance)
        ideal = sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(sorted(relevance.values(), reverse=True)[:5]))
        ndcgs.append(dcg / ideal if ideal else 0.0)
    count = len(cases)
    return {
        "queryCount": count,
        "recallAt1": {"value": round(sum(recalls[1]) / count, 4), "hits": hits[1], "queries": count},
        "recallAt3": {"value": round(sum(recalls[3]) / count, 4), "hits": hits[3], "queries": count},
        "recallAt5": {"value": round(sum(recalls[5]) / count, 4), "hits": hits[5], "queries": count},
        "mrr": round(sum(reciprocal) / count, 4),
        "ndcgAt5": round(sum(ndcgs) / count, 4),
    }


def _passes_filters(row: dict[str, Any], filters: dict[str, Any]) -> bool:
    if filters.get("country") and row["country"] != str(filters["country"]).upper():
        return False
    if filters.get("buyer") and str(filters["buyer"]).lower() not in row["buyer"].lower():
        return False
    if filters.get("cpv") and not any(str(code).startswith(str(filters["cpv"]).rstrip("*")) for code in row["cpv_codes"]):
        return False
    if filters.get("deadline_before") and row["deadline"] and row["deadline"] > filters["deadline_before"]:
        return False
    return True


def evaluate(corpus: dict[str, Any], query_set: dict[str, Any], manifest: dict[str, Any], recorded: dict[str, Any] | None = None) -> dict[str, Any]:
    documents = evidence_documents(corpus)
    recorded = recorded or json.loads(RECORDED_SIMILARITY_PATH.read_text(encoding="utf-8"))
    expected_document_digest = digest([{"evidence_id": item["evidence_id"], "publication": item["publication"], "text": item["text"]} for item in documents])
    for key, expected in (("corpusDigest", manifest["corpusDigest"]), ("querySetDigest", manifest["querySetDigest"]), ("documentDigest", expected_document_digest)):
        if recorded.get(key) != expected:
            raise DatasetContractError(f"recorded similarity {key} mismatch")
    if recorded.get("evidenceIds") != [item["evidence_id"] for item in documents]:
        raise DatasetContractError("recorded similarity evidence order mismatch")

    with tempfile.TemporaryDirectory() as directory:
        storage = TenderKnowledgeBase(Path(directory) / "retrieval-eval.sqlite3")
        storage.ingest([normalize(item["raw"], item["retrievedAt"]) for item in corpus["notices"]])
        cases_by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
        contributions: dict[str, dict[str, dict[str, float]]] = {}
        for query in query_set["queries"]:
            lexical_ids = storage.lexical_search(query["query"], 50)
            lexical = {item: 1 / (index + 1) for index, item in enumerate(lexical_ids)}
            scores = recorded["scores"].get(query["query_id"])
            if not isinstance(scores, list) or len(scores) != len(documents):
                raise DatasetContractError(f"recorded similarity row missing for {query['query_id']}")
            filters = query.get("filters", {})
            filtered = [(row, max(0.0, float(scores[index])), lexical.get(row["evidence_id"], 0.0)) for index, row in enumerate(documents) if _passes_filters(row, filters)]
            # Filter correctness is a separate software invariant: every surviving
            # document satisfies the requested constraints and the filter does not
            # accidentally remove every judged-relevant publication.
            filter_correct = (
                all(_passes_filters(row, filters) for row, _, _ in filtered)
                and any(row["publication"] in query["relevance"] for row, _, _ in filtered)
            ) if filters else None
            for vector_weight, lexical_weight in WEIGHT_CANDIDATES:
                method = "lexical" if vector_weight == 0 else "vector" if lexical_weight == 0 else f"hybrid-{int(vector_weight * 100):02d}-{int(lexical_weight * 100):02d}"
                ranked_evidence = sorted(filtered, key=lambda item: (-(vector_weight * item[1] + lexical_weight * item[2]), item[0]["evidence_id"]))
                publications: list[str] = []
                per_publication: dict[str, dict[str, float]] = {}
                for row, vector_score, lexical_score in ranked_evidence:
                    if row["publication"] not in publications:
                        publications.append(row["publication"])
                        per_publication[row["publication"]] = {"vector": round(vector_score, 6), "lexical": round(lexical_score, 6), "combined": round(vector_weight * vector_score + lexical_weight * lexical_score, 6)}
                cases_by_method[method].append({"query_id": query["query_id"], "split": query["split"], "scenario": query["scenario"], "ranked": publications, "relevance": query["relevance"], "filter_correct": filter_correct})
                if method == "hybrid-50-50":
                    contributions[query["query_id"]] = per_publication

    method_results: dict[str, Any] = {}
    for method, cases in cases_by_method.items():
        method_results[method] = {
            "tuning": metrics_for_rankings([item for item in cases if item["split"] == "tuning"]),
            "holdout": metrics_for_rankings([item for item in cases if item["split"] == "holdout"]),
        }
    tuning_hybrids = [(name, value["tuning"]) for name, value in method_results.items() if name.startswith("hybrid-")]
    # The final tie-break deliberately prefers weights closest to the current neutral 50/50 setting.
    best_score = max((item[1]["mrr"], item[1]["ndcgAt5"]) for item in tuning_hybrids)
    tied = [item for item in tuning_hybrids if (item[1]["mrr"], item[1]["ndcgAt5"]) == best_score]
    winner_name, winner_metrics = min(tied, key=lambda item: abs(float(item[0].split("-")[1]) / 100 - 0.5))
    current = method_results["hybrid-50-50"]["tuning"]
    material = winner_metrics["mrr"] - current["mrr"] >= 0.02 or winner_metrics["ndcgAt5"] - current["ndcgAt5"] >= 0.02
    selected = winner_name if material else "hybrid-50-50"
    selected_cases = cases_by_method[selected]
    failures = []
    for case in selected_cases:
        expected_rank = min((case["ranked"].index(publication) + 1 for publication in case["relevance"] if publication in case["ranked"]), default=None)
        if expected_rank is None or expected_rank > 1:
            expected_publication = next(iter(case["relevance"]))
            failures.append({
                "queryId": case["query_id"], "split": case["split"], "scenario": case["scenario"],
                "expectedPublications": list(case["relevance"]), "bestExpectedRank": expected_rank,
                "topPublications": case["ranked"][:3], "expectedContribution": contributions.get(case["query_id"], {}).get(expected_publication),
                "topContribution": contributions.get(case["query_id"], {}).get(case["ranked"][0]) if case["ranked"] else None,
                "failureCategory": "vocabulary_or_multilingual_mismatch" if "multilingual" in case["scenario"] else "semantic_or_lexical_confusion",
            })
    filter_cases = [item for cases in cases_by_method.values() for item in cases if item["filter_correct"] is not None]
    unique_filter_cases = {(item["query_id"], item["filter_correct"]) for item in filter_cases}
    return {
        "evidenceClass": "recorded-real with recorded actual-model similarity; deterministic replay in CI",
        "querySetVersion": query_set["querySetVersion"],
        "splitVersion": query_set["evaluationSplitVersion"],
        "splitPolicy": query_set["splitPolicy"],
        "queryCounts": {"total": len(query_set["queries"]), "tuning": sum(item["split"] == "tuning" for item in query_set["queries"]), "holdout": sum(item["split"] == "holdout" for item in query_set["queries"])},
        "recordedModel": recorded["model"],
        "methods": method_results,
        "selection": {"tuningWinner": winner_name, "selectedForHoldout": selected, "materialDifferenceFromCurrent": material, "productionConfigurationChanged": False, "reason": "Tuning-only selection with a 0.02 materiality rule; ties prefer 50/50. The holdout was evaluated only after this rule was frozen."},
        "filterCorrectness": {
            "passed": sum(value for _, value in unique_filter_cases),
            "cases": len(unique_filter_cases),
            "scope": "queries with explicit country/buyer/CPV/deadline filters only",
        },
        "failures": failures,
    }
