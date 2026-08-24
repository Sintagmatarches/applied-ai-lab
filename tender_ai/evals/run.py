from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tender_ai.operational_report import build as build_operational_report
from tender_ai.storage import utc_now

from .agent_eval import evaluate as evaluate_agent
from .datasets import EVAL_DIR, DatasetContractError, digest, load_evaluation_inputs, load_json
from .extraction_eval import evaluate as evaluate_extraction
from .grounding_eval import evaluate as evaluate_grounding
from .retrieval_eval import RECORDED_SIMILARITY_PATH, evaluate as evaluate_retrieval
from .security_eval import evaluate as evaluate_security


ROOT = Path(__file__).parents[2]
CONTRACT_PATH = EVAL_DIR / "evaluation_contract.json"
BASELINE_PATH = EVAL_DIR / "evaluation_baseline.json"
OUTPUT_PATH = ROOT / "artifacts" / "tender-evaluation.json"
FAILURE_PATH = ROOT / "artifacts" / "tender-evaluation-failures.json"


def _get(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        current = current[part]
    return current


def _protected_metrics(result: dict[str, Any]) -> list[dict[str, Any]]:
    selected = result["retrieval"]["selection"]["selectedForHoldout"]
    return [
        {"path":"datasets.recordedReal.noticeCount","operator":"eq","baseline":result["datasets"]["recordedReal"]["noticeCount"],"allowedTolerance":0,"reason":"corpus size/version is explicit"},
        {"path":"datasets.recordedReal.queryCount","operator":"eq","baseline":result["datasets"]["recordedReal"]["queryCount"],"allowedTolerance":0,"reason":"query-set version is explicit"},
        {"path":f"retrieval.methods.{selected}.holdout.recallAt1.value","operator":"gte","baseline":_get(result, f"retrieval.methods.{selected}.holdout.recallAt1.value"),"allowedTolerance":0,"reason":"protected holdout ranking floor"},
        {"path":f"retrieval.methods.{selected}.holdout.mrr","operator":"gte","baseline":_get(result, f"retrieval.methods.{selected}.holdout.mrr"),"allowedTolerance":0,"reason":"protected holdout reciprocal-rank floor"},
        {"path":f"retrieval.methods.{selected}.holdout.ndcgAt5","operator":"gte","baseline":_get(result, f"retrieval.methods.{selected}.holdout.ndcgAt5"),"allowedTolerance":0,"reason":"protected holdout graded-ranking floor"},
        {"path":"extraction.fieldExactMatch.lotIdSequence.value","operator":"eq","baseline":1.0,"allowedTolerance":0,"reason":"lot identity is deterministic"},
        {"path":"extraction.fieldExactMatch.lotCount.value","operator":"eq","baseline":1.0,"allowedTolerance":0,"reason":"lot cardinality is deterministic"},
        {"path":"extraction.fieldExactMatch.buyerCountry.value","operator":"eq","baseline":1.0,"allowedTolerance":0,"reason":"buyer country is mechanical"},
        {"path":"extraction.fieldExactMatch.submissionLanguages.value","operator":"eq","baseline":1.0,"allowedTolerance":0,"reason":"submission-language extraction is mechanical"},
        {"path":"extraction.fieldExactMatch.awardCriterionCount.value","operator":"eq","baseline":1.0,"allowedTolerance":0,"reason":"award-criterion cardinality is mechanical"},
        {"path":"extraction.fieldExactMatch.deadlineSequence.value","operator":"eq","baseline":1.0,"allowedTolerance":0,"reason":"deadline extraction is mechanical"},
        {"path":"extraction.fieldExactMatch.missingFieldBehavior.value","operator":"eq","baseline":1.0,"allowedTolerance":0,"reason":"missing deadline fields must remain missing"},
        {"path":"extraction.lotIdItems.recall","operator":"eq","baseline":1.0,"allowedTolerance":0,"reason":"all expected lot IDs remain represented"},
        {"path":"extraction.cpvExtraction.recall","operator":"eq","baseline":1.0,"allowedTolerance":0,"reason":"all expected CPV values remain represented"},
        {"path":"extraction.mandatoryBooleanCoverage.value","operator":"eq","baseline":1.0,"allowedTolerance":0,"reason":"mandatory boolean remains present; this is coverage, not classification accuracy"},
        {"path":"extraction.requirementExtraction.recall","operator":"gte","baseline":result["extraction"]["requirementExtraction"]["recall"],"allowedTolerance":0.01,"reason":"aggregate source-derived category coverage"},
        {"path":"extraction.requirementLotAssignment.recall","operator":"gte","baseline":result["extraction"]["requirementLotAssignment"]["recall"],"allowedTolerance":0.01,"reason":"lot association coverage"},
        {"path":"extraction.awardWeightExtraction.recall","operator":"gte","baseline":result["extraction"]["awardWeightExtraction"]["recall"],"allowedTolerance":0.01,"reason":"known current gap remains visible and cannot silently worsen"},
        {"path":"grounding.passed","operator":"eq","baseline":result["grounding"]["caseCount"],"allowedTolerance":0,"reason":"all deterministic grounding cases pass"},
        {"path":"grounding.unsupportedClaimsAfterGate","operator":"eq","baseline":0,"allowedTolerance":0,"reason":"central publication safety invariant"},
        {"path":"agent.passed","operator":"eq","baseline":result["agent"]["caseCount"],"allowedTolerance":0,"reason":"all agent/tool boundary cases pass"},
        {"path":"security.passed","operator":"eq","baseline":result["security"]["caseCount"],"allowedTolerance":0,"reason":"all security boundary regressions pass"},
    ]


def build_result() -> dict[str, Any]:
    corpus, query_set, manifest = load_evaluation_inputs()
    contract = load_json(CONTRACT_PATH)
    recorded = load_json(RECORDED_SIMILARITY_PATH)
    if contract["recordedRealDatasetDigest"] != manifest["corpusDigest"]:
        raise DatasetContractError("evaluation contract corpus digest mismatch")
    if contract["relevantModelFingerprints"]["embedding"]["digest"] != recorded["model"]["digest"]:
        raise DatasetContractError("evaluation contract embedding fingerprint mismatch")
    synthetic = load_json(EVAL_DIR / "dataset.json")
    result = {
        "evaluationSchemaVersion": "2.0.0",
        "evaluationVersion": contract["evaluationVersion"],
        "generatedAt": utc_now(),
        "evidenceClasses": {
            "deterministicSyntheticRegression":"edge cases and exact CI behavior; not real-world quality estimation",
            "recordedRealTed":"public TED notices with source-derived expectations; not independently human-labelled",
            "modelDependentLiveOrRecorded":"actual local-model behavior and runtime metrics; informational and non-gating",
        },
        "datasets": {
            "syntheticRegression":{"version":synthetic["dataset"],"caseCount":len(synthetic["cases"])},
            "recordedReal":{"version":manifest["datasetVersion"],"digest":manifest["corpusDigest"],"noticeCount":manifest["noticeCount"],"queryCount":manifest["queryCount"],"querySetDigest":manifest["querySetDigest"],"splitVersion":manifest["evaluationSplitVersion"],"labelMethod":manifest["labelMethod"]},
        },
        "contract":{"schemaVersion":contract["schemaVersion"],"digest":digest(contract),"path":"tender_ai/evals/evaluation_contract.json"},
        "retrieval":evaluate_retrieval(corpus, query_set, manifest, recorded),
        "extraction":evaluate_extraction(corpus),
        "grounding":evaluate_grounding(),
        "agent":evaluate_agent(corpus),
        "security":evaluate_security(corpus),
        "operational":build_operational_report(ROOT / "artifacts" / "tender-ai-traces.jsonl"),
        "modelDependent":{"ciGate":False,"liveArtifact":"artifacts/tender-live-verification.json","note":"Live/model evidence is never fabricated or required by normal CI."},
        "limitations":[
            "Fifteen selected notices and thirty correlated scenarios are a portfolio corpus, not a representative sample of all EU procurement.",
            "The corpus does not cover every EU language, eForms version, procurement category or legal interpretation.",
            "Recorded similarities bind one actual local embedding model digest to this corpus; they do not estimate all model versions or hosts.",
            "High holdout scores on fourteen curated queries do not establish a production hallucination rate or general commercial quality.",
            "Source-derived expectations are not independent human labels.",
        ],
    }
    return result


def check_baseline(result: dict[str, Any], baseline: dict[str, Any]) -> list[dict[str, Any]]:
    current_inputs = {
        "contractDigest":result["contract"]["digest"],
        "corpusDigest":result["datasets"]["recordedReal"]["digest"],
        "querySetDigest":result["datasets"]["recordedReal"]["querySetDigest"],
        "embeddingDigest":result["retrieval"]["recordedModel"]["digest"],
    }
    regressions = []
    for key, baseline_value in baseline["inputs"].items():
        if current_inputs.get(key) != baseline_value:
            regressions.append({"metric":f"inputs.{key}","baseline":baseline_value,"current":current_inputs.get(key),"allowedTolerance":0,"delta":None,"affectedScenarios":[],"reason":"evaluation input changed; explicit baseline/version update required"})
    for policy in baseline["protectedMetrics"]:
        current = _get(result, policy["path"])
        baseline_value, tolerance = policy["baseline"], policy["allowedTolerance"]
        passed = current == baseline_value if policy["operator"] == "eq" else current >= baseline_value - tolerance
        if not passed:
            regressions.append({"metric":policy["path"],"baseline":baseline_value,"current":current,"allowedTolerance":tolerance,"delta":round(current - baseline_value, 6) if isinstance(current, (int, float)) else None,"affectedScenarios":[item["queryId"] for item in result["retrieval"]["failures"]] if policy["path"].startswith("retrieval.") else [],"reason":policy["reason"]})
    return regressions


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic Tender evals-as-code.")
    parser.add_argument("--check-baseline", action="store_true")
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--release-note", help="required explanation for an intentional baseline update")
    args = parser.parse_args()
    if args.update_baseline and not args.release_note:
        parser.error("--update-baseline requires --release-note")
    result = build_result()
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    regressions: list[dict[str, Any]] = []
    if args.update_baseline:
        baseline = {
            "baselineSchemaVersion":"1.0.0","baselineVersion":"tender-eval-baseline-v2.0.0","updatedAt":utc_now(),"releaseNote":args.release_note,
            "inputs":{"contractDigest":result["contract"]["digest"],"corpusDigest":result["datasets"]["recordedReal"]["digest"],"querySetDigest":result["datasets"]["recordedReal"]["querySetDigest"],"embeddingDigest":result["retrieval"]["recordedModel"]["digest"]},
            "protectedMetrics":_protected_metrics(result),
        }
        BASELINE_PATH.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.check_baseline:
        if not BASELINE_PATH.exists():
            raise SystemExit("evaluation baseline is missing; use an explicit --update-baseline with a release note")
        regressions = check_baseline(result, load_json(BASELINE_PATH))
        FAILURE_PATH.write_text(json.dumps({"evaluationVersion":result["evaluationVersion"],"regressionCount":len(regressions),"regressions":regressions}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evaluationVersion":result["evaluationVersion"],"datasets":result["datasets"],"retrieval":result["retrieval"],"extraction":result["extraction"],"grounding":result["grounding"],"agent":result["agent"],"security":result["security"],"regressions":regressions,"limitations":result["limitations"]}, ensure_ascii=False, indent=2))
    if regressions:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
