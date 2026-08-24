from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tender_ai.evals.datasets import DatasetContractError, expected_manifest, load_evaluation_inputs, validate_corpus, validate_queries
from tender_ai.evals.extraction_eval import _pr, evaluate as evaluate_extraction
from tender_ai.evals.grounding_eval import evaluate as evaluate_grounding
from tender_ai.evals.run import BASELINE_PATH, build_result, check_baseline
from tender_ai.evals.security_eval import evaluate as evaluate_security
from tender_ai.observability import TRACE_SCHEMA_VERSION, TraceSchemaError, TraceWriter, safe_query_metadata, safe_tool_arguments
from tender_ai.ollama import OllamaClient
from tender_ai.operational_report import build as build_operational_report


class DatasetAndEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus, cls.queries, cls.manifest = load_evaluation_inputs()

    def test_dataset_manifest_digest(self):
        self.assertEqual(expected_manifest(self.corpus, self.queries), self.manifest)

    def test_duplicate_notice_id_rejected(self):
        value = copy.deepcopy(self.corpus)
        value["notices"].append(copy.deepcopy(value["notices"][0]))
        with self.assertRaises(DatasetContractError):
            validate_corpus(value)

    def test_malformed_expected_labels_rejected(self):
        value = copy.deepcopy(self.corpus)
        value["notices"][0]["expected"]["lotIds"] = "LOT-0000"
        with self.assertRaises(DatasetContractError):
            validate_corpus(value)

    def test_tuning_holdout_overlap_rejected(self):
        value = copy.deepcopy(self.queries)
        value["queries"][16]["relevance"] = copy.deepcopy(value["queries"][0]["relevance"])
        with self.assertRaisesRegex(DatasetContractError, "publication overlap"):
            validate_queries(value, set(self.manifest["noticeIds"]))

    def test_missing_relevance_rejected(self):
        value = copy.deepcopy(self.queries)
        value["queries"][0]["relevance"] = {}
        with self.assertRaises(DatasetContractError):
            validate_queries(value, set(self.manifest["noticeIds"]))

    def test_extra_extraction_value_penalizes_precision(self):
        self.assertEqual(_pr(1, 2, 1)["precision"], .5)

    def test_missing_extraction_value_penalizes_recall(self):
        self.assertEqual(_pr(1, 1, 2)["recall"], .5)

    def test_missing_field_and_mandatory_metrics_do_not_overclaim(self):
        result = evaluate_extraction(self.corpus)
        self.assertEqual(result["fieldExactMatch"]["missingFieldBehavior"]["cases"], 5)
        self.assertNotIn("mandatoryClassification", result)
        self.assertEqual(result["mandatoryBooleanCoverage"]["cases"], 111)

    def test_grounding_suite_covers_cross_scope_and_zero_post_gate(self):
        result = evaluate_grounding()
        self.assertEqual(result["passed"], result["caseCount"])
        self.assertEqual(result["unsupportedClaimsAfterGate"], 0)
        self.assertTrue({"cross-notice", "cross-lot", "wrong-deadline", "forged-citation"} <= {item["caseId"] for item in result["cases"]})

    def test_baseline_check_passes_current_result(self):
        result = build_result()
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(check_baseline(result, baseline), [])

    def test_normal_baseline_check_cannot_overwrite_baseline(self):
        before = BASELINE_PATH.read_bytes()
        completed = subprocess.run(
            [sys.executable, "-m", "tender_ai.evals.run", "--check-baseline"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(BASELINE_PATH.read_bytes(), before)

    def test_dataset_version_mismatch_has_explicit_diff(self):
        result = build_result()
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        baseline["inputs"]["corpusDigest"] = "old-corpus"
        regressions = check_baseline(result, baseline)
        self.assertEqual(regressions[0]["metric"], "inputs.corpusDigest")
        self.assertIn("explicit baseline/version update", regressions[0]["reason"])

    def test_retrieval_regression_diff_names_metric(self):
        result = build_result()
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        policy = next(item for item in baseline["protectedMetrics"] if "holdout.recallAt1" in item["path"])
        current = result["retrieval"]["methods"]["hybrid-50-50"]["holdout"]["recallAt1"]
        current["value"] = 0.0
        regressions = check_baseline(result, baseline)
        self.assertTrue(any(item["metric"] == policy["path"] and item["delta"] == -1.0 for item in regressions))

    def test_security_matrix_all_passes(self):
        result = evaluate_security(self.corpus)
        self.assertEqual(result["passed"], result["caseCount"])
        self.assertGreaterEqual(result["caseCount"], 12)


class TraceAndOperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "trace.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def _write_request(self, trace_id: str, *, status: str = "succeeded", duration: float = 10, fallback: bool = False):
        writer = TraceWriter(self.path)
        writer.write({"trace_id":trace_id,"stage":"request","status":"started",**safe_query_metadata("private question")})
        writer.write({"trace_id":trace_id,"stage":"request","status":status,"duration_ms":duration,"prompt_tokens":10,"completion_tokens":5,"total_tokens":15,"fallback_used":fallback,"fallback_reason":"DETERMINISTIC_FALLBACK" if fallback else None})

    def test_schema_version_and_unique_event_ids(self):
        self._write_request("trace-a")
        rows = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(all(item["schema_version"] == TRACE_SCHEMA_VERSION for item in rows))
        self.assertEqual(len({item["event_id"] for item in rows}), 2)
        self.assertEqual({item["trace_id"] for item in rows}, {"trace-a"})

    def test_query_hashing_omits_raw_query(self):
        self._write_request("trace-a")
        text = self.path.read_text(encoding="utf-8")
        self.assertNotIn("private question", text)
        self.assertIn(safe_query_metadata("private question")["query_sha256"], text)

    def test_supplier_profile_and_raw_query_are_rejected(self):
        writer = TraceWriter(self.path)
        with self.assertRaises(TraceSchemaError):
            writer.write({"trace_id":"x","stage":"request","status":"started","supplier_profile":{"turnover":1}})
        with self.assertRaises(TraceSchemaError):
            writer.write({"trace_id":"x","stage":"request","status":"started","query":"secret"})

    def test_safe_tool_arguments_hashes_query(self):
        value = safe_tool_arguments("retrieve_tenders", {"query":"secret tender", "country":"FIN"})
        self.assertNotIn("secret tender", json.dumps(value))
        self.assertEqual(value["arguments"]["country"], "FIN")

    def test_unknown_future_field_is_preserved(self):
        event = TraceWriter(self.path).write({"trace_id":"x","stage":"future-stage","status":"succeeded","future_counter":3})
        self.assertEqual(event["future_counter"], 3)

    def test_model_metrics_complete_payload(self):
        value = OllamaClient._metrics({"prompt_eval_count":10,"eval_count":5,"total_duration":2_000_000,"load_duration":1_000_000,"prompt_eval_duration":500_000,"eval_duration":1_000_000_000,"done_reason":"stop"}, 3.5)
        self.assertEqual(value.public()["model_load_duration_ms"], 1.0)
        self.assertEqual(value.generation_tokens_per_second, 5.0)
        self.assertEqual(value.done_reason, "stop")

    def test_model_metrics_partial_embedding_payload(self):
        value = OllamaClient._metrics({"prompt_eval_count":8,"total_duration":14,"load_duration":2}, 1)
        self.assertIsNone(value.completion_tokens)
        self.assertIsNone(value.generation_tokens_per_second)
        self.assertIsNone(value.done_reason)

    def test_zero_eval_duration_has_no_throughput(self):
        value = OllamaClient._metrics({"eval_count":5,"eval_duration":0}, 1)
        self.assertIsNone(value.generation_tokens_per_second)

    def test_empty_trace_report(self):
        report = build_operational_report(self.path)
        self.assertEqual(report["eventCount"], 0)
        self.assertEqual(report["traceCount"], 0)
        self.assertEqual(report["fallback"]["rate"], 0.0)

    def test_multiple_trace_percentiles_tokens_and_fallbacks(self):
        self._write_request("a", duration=10)
        self._write_request("b", duration=100, fallback=True)
        report = build_operational_report(self.path)
        self.assertEqual(report["traceCount"], 2)
        self.assertEqual(report["latencyMs"]["total"]["p50"], 10.0)
        self.assertEqual(report["latencyMs"]["total"]["p95"], 100.0)
        self.assertEqual(report["tokens"]["total"], 30)
        self.assertEqual(report["fallback"]["count"], 1)

    def test_one_request_trace_is_aggregated_without_synthetic_samples(self):
        self._write_request("only", duration=25)
        report = build_operational_report(self.path)
        self.assertEqual(report["traceCount"], 1)
        self.assertEqual(report["latencyMs"]["total"], {"p50": 25.0, "p95": 25.0, "eventCount": 1})

    def test_corrupt_and_legacy_lines_are_accounted(self):
        self.path.write_text('{"event":"legacy"}\n{broken\n', encoding="utf-8")
        report = build_operational_report(self.path)
        self.assertEqual(report["corruptLineCount"], 1)
        self.assertEqual(report["unsupportedSchemaEventCount"], 1)
        self.assertEqual(report["schemaVersions"]["legacy-or-missing"], 1)

    def test_tool_failure_category_aggregation(self):
        writer = TraceWriter(self.path)
        writer.write({"trace_id":"x","stage":"tool","status":"failed","tool_name":"get_notice","tool_success":False,"tool_failure_category":"ARGUMENT_VALIDATION","duration_ms":4})
        report = build_operational_report(self.path)
        self.assertEqual(report["tools"]["failureCount"], 1)
        self.assertEqual(report["tools"]["failuresByCategory"]["ARGUMENT_VALIDATION"], 1)


if __name__ == "__main__":
    unittest.main()
