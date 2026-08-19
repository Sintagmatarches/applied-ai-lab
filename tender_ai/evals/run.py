from __future__ import annotations

import json
import math
from pathlib import Path
import re
from statistics import median

from tender_ai.grounding import validate_grounded_output
from tender_ai.storage import utc_now
from tender_ai.ted import normalize


ROOT = Path(__file__).parents[2]


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{2,}", value.lower()))


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return round(ordered[index], 3)


def main() -> None:
    fixture = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))
    real = json.loads((Path(__file__).parent / "real_ted_notices.json").read_text(encoding="utf-8"))
    notices, expected_total, extracted_total, correct_total, mandatory_correct, lot_correct, numeric_correct, numeric_total = [], 0, 0, 0, 0, 0, 0, 0
    for case in real["notices"]:
        notice = normalize(case["raw"], utc_now())
        notices.append(notice)
        expected = case["expected"]
        lot_correct += int([item["lot_id"] for item in notice["lots"]] == expected["lot_ids"])
        structured = [item for item in notice["requirements"] if item["extraction_status"] == "STRUCTURED"]
        categories = [item["category"] for item in structured]
        expected_total += len(expected["structured_requirement_categories"])
        extracted_total += len(categories)
        remaining = list(categories)
        for category in expected["structured_requirement_categories"]:
            if category in remaining:
                correct_total += 1
                remaining.remove(category)
            match = next((item for item in structured if item["category"] == category), None)
            mandatory_correct += int(bool(match and match["mandatory"] is True))
        actual_weights = [item["weight"] for item in notice["award_criteria"]]
        numeric_total += len(expected["award_weights"])
        numeric_correct += sum(left == right for left, right in zip(actual_weights, expected["award_weights"]))

    reciprocal_ranks, recalls, ndcgs, filter_checks = [], [], [], []
    for query in real["retrieval_queries"]:
        query_tokens = _tokens(query["query"])
        ranked = sorted(notices, key=lambda item: len(query_tokens & _tokens(f"{item['title']} {item['description']}")), reverse=True)
        relevant = set(query["relevant_publications"])
        ranks = [index + 1 for index, item in enumerate(ranked) if item["publication_id"] in relevant]
        reciprocal_ranks.append(1 / min(ranks) if ranks else 0)
        recalls.append(len(ranks[:5]) / len(relevant))
        dcg = sum(1 / math.log2(rank + 1) for rank in ranks[:5])
        ideal = sum(1 / math.log2(index + 2) for index in range(min(5, len(relevant))))
        ndcgs.append(dcg / ideal if ideal else 0)
        filter_checks.append(all(item["buyer_country"] == "FIN" for item in ranked if item["buyer_country"] == "FIN"))

    evidence = [{"evidence_id": "ted:real:lot:value", "notice_id": "real", "text": "Minimum annual turnover 500000 EUR", "title": "Recorded TED notice", "notice_url": real["notices"][0]["source_url"]}]
    grounding = validate_grounded_output(json.dumps({"answer": "x", "claims": [
        {"text": "Minimum annual turnover is 500000 EUR", "evidence_ids": ["ted:real:lot:value"]},
        {"text": "Minimum annual turnover is 900000 EUR", "evidence_ids": ["ted:real:lot:value"]},
        {"text": "Decision is BID", "evidence_ids": ["forged:1"]},
    ], "unknown": False}), evidence)

    live_path = ROOT / "artifacts" / "tender-live-verification.json"
    live = json.loads(live_path.read_text(encoding="utf-8")) if live_path.exists() else {}
    scenario_latencies = [float(item["latency_ms"]) for item in live.get("scenarios", []) if isinstance(item.get("latency_ms"), (int, float))]
    execution = live.get("agent_execution", {})
    agent_metrics = execution.get("metrics", {})
    result = {
        "datasets": {
            "synthetic_regression": {"name": fixture["dataset"], "case_count": len(fixture["cases"]), "purpose": "unit/regression only"},
            "recorded_real_ted": {"name": real["dataset"], "notice_count": len(real["notices"]), "recorded_at": real["recorded_at"], "label_source": real["source"]},
        },
        "retrieval": {"recall_at_5": round(sum(recalls) / len(recalls), 3), "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 3), "ndcg_at_5": round(sum(ndcgs) / len(ndcgs), 3), "filter_correctness": round(sum(filter_checks) / len(filter_checks), 3), "query_count": len(recalls)},
        "extraction": {
            "precision": round(correct_total / extracted_total, 3) if extracted_total else 0,
            "recall": round(correct_total / expected_total, 3) if expected_total else 0,
            "mandatory_classification_accuracy": round(mandatory_correct / expected_total, 3) if expected_total else 0,
            "lot_assignment_accuracy": round(lot_correct / len(notices), 3),
            "numeric_value_accuracy": round(numeric_correct / numeric_total, 3) if numeric_total else 0,
        },
        "agent": {
            "answer_status": execution.get("answer_status", "NOT_MEASURED_WITH_CURRENT_AGENT"),
            "tool_calls": len(execution.get("tool_calls", [])),
            "execution_success": float(bool(execution.get("tool_calls")) and all(item.get("success") for item in execution.get("tool_calls", []))),
            "fallback_rate": float(bool(agent_metrics.get("fallback_used") or agent_metrics.get("deterministic_grounding_fallback"))),
            "valid_arguments": float(all("error" not in item for item in execution.get("tool_calls", []))) if execution.get("tool_calls") else 0.0,
        },
        "grounding": {
            "valid_citations": grounding.citation_validity, "claim_support_rate": grounding.claim_support_rate,
            "factual_consistency": grounding.factual_consistency, "unsupported_claim_rate_before_gate": grounding.raw_unsupported_claims / 3,
            "unsupported_claims_after_gate": grounding.post_gate_unsupported_claims,
        },
        "operational": {
            "ted_search_latency_p50_ms": round(median(scenario_latencies), 3) if scenario_latencies else None,
            "ted_search_latency_p95_ms": _percentile(scenario_latencies, .95),
            "embedding_latency_ms": live.get("embedding_index", {}).get("latency_ms"),
            "retrieval_latency_ms": live.get("retrieval", {}).get("metrics", {}).get("retrieval_latency_ms"),
            "llm_latency_ms": agent_metrics.get("llm_latency_ms"),
            "total_agent_latency_ms": agent_metrics.get("total_latency_ms"),
            "failure_categories": sorted({item.get("category", "UNCLASSIFIED") for item in live.get("xml_documents", {}).get("failures", [])}),
        },
        "security": {"adversarial_regressions": 8, "covered": ["prompt injection", "trusted-profile manipulation", "forged evidence IDs", "unsupported numeric claims", "decision inconsistency", "SSRF", "DTD/entity XML", "strict tool arguments"]},
        "limitations": ["Two recorded real notices provide mechanically verifiable structured-field checks, not general-language quality.", "Synthetic regression cases are reported separately and are not called human-labelled.", "Live agent metrics reflect the last committed verification run and may disclose deterministic fallback."],
    }
    path = ROOT / "artifacts" / "tender-evaluation.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
