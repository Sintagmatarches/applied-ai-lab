import json
import sqlite3
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from tender_ai import server
from tender_ai.ollama import OllamaUnavailable
from tender_ai.telemetry import Telemetry


class OperationsTests(unittest.TestCase):
    def test_liveness_has_no_dependency_and_readiness_reports_outage(self):
        with patch.object(server.runtime.ollama, "available_models", side_effect=OllamaUnavailable("secret")) as dependency:
            client = TestClient(server.app)
            self.assertEqual(client.get("/live").status_code, 200)
            dependency.assert_not_called()
            response = client.get("/ready")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("secret", response.text)

    def test_readiness_requires_both_models_and_database(self):
        with patch.object(server.runtime.ollama, "available_models", return_value=[server.runtime.config.chat_model]):
            self.assertEqual(TestClient(server.app).get("/ready").status_code, 503)
        with patch.object(server.runtime.ollama, "available_models", return_value=[server.runtime.config.chat_model, server.runtime.config.embedding_model]):
            self.assertEqual(TestClient(server.app).get("/ready").status_code, 200)
            with patch.object(server.runtime.storage, "connection", side_effect=sqlite3.OperationalError("private path")):
                self.assertEqual(TestClient(server.app).get("/ready").status_code, 503)

    def test_request_logs_exclude_body_path_query_and_headers(self):
        with self.assertLogs("tender.operations", level="INFO") as captured:
            response = TestClient(server.app).post(
                "/private-question?secret=token", json={"question": "private profile"},
                headers={"authorization": "secret-token", "x-request-id": "private-profile"},
            )
        event = json.loads(captured.records[-1].message)
        self.assertEqual(event["route"], "other")
        self.assertEqual(event["status_code"], 404)
        self.assertEqual(response.headers["x-request-id"], event["request_id"])
        self.assertEqual(len(event["request_id"]), 32)
        self.assertNotIn("private", captured.records[-1].message)
        self.assertNotIn("secret", captured.records[-1].message)

    def test_unexpected_failure_returns_correlated_safe_500(self):
        with patch.object(server.runtime.agent, "ask", side_effect=RuntimeError("private supplier")):
            with self.assertLogs("tender.operations", level="INFO") as logs:
                response = TestClient(server.app).post("/ask", json={"question": "private question"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("x-request-id", response.headers)
        self.assertNotIn("private", response.text + str(logs.output))

    def test_real_otel_export_contains_no_exception_text_or_unbounded_labels(self):
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        reader = InMemoryMetricReader()
        meters = MeterProvider(metric_readers=[reader])
        telemetry = Telemetry(provider.get_tracer("test"), meters.get_meter("test"))
        try:
            with telemetry.operation("http", "/ask"):
                with self.assertRaises(RuntimeError):
                    with telemetry.operation("user-supplied-tool", "secret-route"):
                        raise RuntimeError("secret-question-and-profile")
            spans = exporter.get_finished_spans()
            self.assertEqual(len(spans), 2)
            self.assertEqual(spans[0].parent.span_id, spans[1].context.span_id)
            self.assertEqual(spans[0].attributes["operation"], "other")
            self.assertEqual(spans[0].attributes["outcome"], "failure")
            self.assertEqual(spans[0].events, ())
            serialized = " ".join(span.to_json() for span in spans) + reader.get_metrics_data().to_json()
            self.assertNotIn("secret", serialized)
            self.assertNotIn("request_id", reader.get_metrics_data().to_json())
        finally:
            meters.shutdown()
            provider.shutdown()
