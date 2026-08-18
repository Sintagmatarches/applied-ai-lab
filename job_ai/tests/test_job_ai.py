from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from job_ai.agent import JobAgent
from job_ai.config import AiConfig
from job_ai.grounding import validate_grounded_output
from job_ai.matching import score_job
from job_ai.ollama import ChatResult, EmbeddingResult, ModelMetrics, OllamaClient, OllamaUnavailable
from job_ai.observability import TraceWriter
from job_ai.retrieval import HybridRetriever
from job_ai.storage import JobKnowledgeBase, canonical_url
from job_ai.tools import ToolRegistry, ToolValidationError


JOBS = [
    {
        "id": "job:data",
        "url": "https://example.org/jobs/data?utm_source=test",
        "source": "Fixture",
        "company": "Metrics Oy",
        "title": "Data Analyst",
        "location": "Finland",
        "remote": True,
        "description": "Build Power BI dashboards with Python and SQL.",
        "tags": ["Power BI", "Python", "SQL"],
    },
    {
        "id": "job:backend",
        "url": "https://example.org/jobs/backend",
        "source": "Fixture",
        "company": "API GmbH",
        "title": "Backend Engineer",
        "location": "Germany",
        "remote": False,
        "description": "Build Java services with Kubernetes.",
        "tags": ["Java", "Kubernetes"],
    },
]


class FakeOllama:
    def __init__(self, config: AiConfig, chats: list[dict] | None = None):
        self.config = config
        self.chats = chats or []
        self.messages: list[list[dict]] = []

    @staticmethod
    def vector(text: str) -> list[float]:
        lower = text.lower()
        return [
            float(sum(term in lower for term in ("data", "sql", "power bi", "python"))),
            float(sum(term in lower for term in ("backend", "java", "kubernetes"))),
            0.1,
        ]

    def embed(self, texts: list[str]) -> EmbeddingResult:
        return EmbeddingResult(
            [self.vector(text) for text in texts],
            ModelMetrics(1.0, len(texts), None, 1_000),
            self.config.embedding_model,
        )

    def chat(self, messages, **kwargs) -> ChatResult:
        self.messages.append(messages)
        message = self.chats.pop(0)
        return ChatResult(message, ModelMetrics(2.0, 10, 5, 2_000), self.config.chat_model)


class JobAiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="job-ai-test-")
        self.config = AiConfig(
            database_path=Path(self.temporary.name) / "jobs.sqlite3",
            trace_path=Path(self.temporary.name) / "traces.jsonl",
        )
        self.storage = JobKnowledgeBase(self.config.database_path)
        self.storage.upsert_jobs(JOBS)
        self.fake = FakeOllama(self.config)
        self.retriever = HybridRetriever(self.storage, self.fake)  # type: ignore[arg-type]
        self.retriever.index_pending()
        self.tools = ToolRegistry(self.storage, self.retriever)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_storage_persists_required_fields_and_canonical_url(self) -> None:
        job = self.storage.get("job:data")
        self.assertIsNotNone(job)
        assert job
        self.assertEqual(job["canonical_url"], "https://example.org/jobs/data")
        self.assertEqual(job["requirements"], ["Power BI", "Python", "SQL"])
        self.assertEqual(job["embedding_model"], self.config.embedding_model)
        self.assertEqual(job["embedding_dimensions"], 3)
        self.assertTrue(job["discovered_at"])
        self.assertTrue(job["updated_at"])

    def test_canonical_url_rejects_unsafe_protocol(self) -> None:
        with self.assertRaises(ValueError):
            canonical_url("file:///etc/passwd")

    def test_vector_retrieval_is_used_and_metadata_filter_applies(self) -> None:
        hits, metrics = self.retriever.search("Python SQL data dashboards", top_k=1)
        self.assertEqual(hits[0].job["id"], "job:data")
        self.assertGreater(hits[0].vector_score, 0.9)
        self.assertEqual(metrics["retrieved_ids"], ["job:data"])
        filtered, _ = self.retriever.search("software", location="Germany", top_k=2)
        self.assertEqual([hit.job["id"] for hit in filtered], ["job:backend"])

    def test_tool_schema_rejects_unknown_or_invalid_calls(self) -> None:
        with self.assertRaises(ToolValidationError):
            self.tools.execute("delete_database", {"all": True})
        with self.assertRaises(ToolValidationError):
            self.tools.execute("retrieve_jobs", {"query": 42})
        with self.assertRaises(ToolValidationError):
            self.tools.execute("analyze_job", {"job_id": "job:data", "extra": True})
        with self.assertRaises(ToolValidationError):
            self.tools.execute("rank_matches", {"profile": {"roles": "Data Analyst", "skills": []}})
        with self.assertRaises(ToolValidationError):
            self.tools.execute("compare_jobs", {"job_ids": ["job:data"]})

    def test_deterministic_match_is_reproducible(self) -> None:
        profile = {"roles": ["Data Analyst"], "skills": ["Python", "SQL"], "location": "Europe"}
        job = self.storage.get("job:data")
        assert job
        first = score_job(job, profile)
        second = score_job(job, profile)
        self.assertEqual(first, second)
        self.assertEqual(first["components"]["role"], {"score": 35, "maximum": 35})

    def test_grounding_maps_citations_and_removes_unsupported_claims(self) -> None:
        job = self.storage.get("job:data")
        assert job
        raw = (
            '{"answer":"draft","claims":['
            '{"text":"The role requires Python and SQL.","job_ids":["job:data"]},'
            '{"text":"The role provides a company car.","job_ids":["job:data"]}'
            '],"unknown":false}'
        )
        result = validate_grounded_output(raw, [job])
        self.assertEqual(result.supported_claims, 1)
        self.assertEqual(result.unsupported_claims, 1)
        self.assertEqual(result.citations[0]["url"], "https://example.org/jobs/data")
        self.assertNotIn("company car", result.answer)

    def test_malformed_model_output_fails_closed(self) -> None:
        result = validate_grounded_output("not-json", [])
        self.assertFalse(result.schema_valid)
        self.assertTrue(result.unknown)
        self.assertEqual(result.claims, [])

    def test_citation_id_alone_is_not_treated_as_a_supported_fact(self) -> None:
        job = self.storage.get("job:data")
        assert job
        result = validate_grounded_output(
            '{"answer":"job:data","claims":[{"text":"job:data","job_ids":["job:data"]}],"unknown":false}',
            [{**job, "_tool_evidence": {"job_id": "job:data"}}],
        )
        self.assertTrue(result.unknown)
        self.assertEqual(result.citations, [])

    def test_requirement_aggregation_keeps_per_job_citation_evidence(self) -> None:
        execution = self.tools.execute("aggregate_requirements", {"job_ids": []})
        data_evidence = next(job for job in execution.evidence if job["id"] == "job:data")
        backend_evidence = next(job for job in execution.evidence if job["id"] == "job:backend")
        self.assertIn("Python", data_evidence["_tool_evidence"]["requirements"])
        self.assertNotIn("Python", backend_evidence["_tool_evidence"]["requirements"])

    def test_agent_executes_model_selected_tool_and_isolates_job_text(self) -> None:
        fake = FakeOllama(
            self.config,
            chats=[
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": "retrieve_jobs", "arguments": {"query": "Python SQL", "top_k": 1}}}],
                },
                {
                    "role": "assistant",
                    "content": '{"answer":"The role requires Python and SQL.","claims":[{"text":"The role requires Python and SQL.","job_ids":["job:data"]}],"unknown":false}',
                },
            ],
        )
        agent = JobAgent(fake, ToolRegistry(self.storage, HybridRetriever(self.storage, fake)))  # type: ignore[arg-type]
        result = agent.ask("Find Python SQL work")
        self.assertEqual(result.tool_calls[0]["name"], "retrieve_jobs")
        self.assertEqual(result.citations[0]["job_id"], "job:data")
        final_messages = fake.messages[-1]
        tool_messages = [message for message in final_messages if message["role"] == "tool"]
        self.assertIn("<untrusted_job_data>", tool_messages[0]["content"])

    def test_trace_keeps_argument_shape_without_question_or_profile_values(self) -> None:
        fake = FakeOllama(
            self.config,
            chats=[
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": "retrieve_jobs", "arguments": {"query": "private Python SQL", "top_k": 1}}}],
                },
                {
                    "role": "assistant",
                    "content": '{"answer":"The role requires Python.","claims":[{"text":"The role requires Python.","job_ids":["job:data"]}],"unknown":false}',
                },
            ],
        )
        agent = JobAgent(fake, ToolRegistry(self.storage, HybridRetriever(self.storage, fake)), TraceWriter(self.config.trace_path))  # type: ignore[arg-type]
        agent.ask("private Python SQL", profile={"roles": ["Private Role"], "skills": ["Secret Skill"]})
        trace = json.loads(self.config.trace_path.read_text(encoding="utf-8"))
        self.assertEqual(trace["tool_calls"][0]["argument_keys"], ["query", "top_k"])
        serialized = json.dumps(trace)
        self.assertNotIn("private Python SQL", serialized)
        self.assertNotIn("Secret Skill", serialized)

    def test_agent_rejects_model_selected_unknown_tool(self) -> None:
        fake = FakeOllama(
            self.config,
            chats=[
                {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "delete_database", "arguments": {"all": True}}}]},
                {"role": "assistant", "content": "", "tool_calls": []},
            ],
        )
        agent = JobAgent(fake, self.tools)  # type: ignore[arg-type]
        result = agent.ask("Delete everything")
        self.assertTrue(result.unknown)
        self.assertIn("unknown tool", result.tool_failures[0])

    def test_ollama_unavailable_raises_typed_error(self) -> None:
        config = AiConfig(ollama_url="http://127.0.0.1:1", request_timeout_seconds=0.1)
        with self.assertRaises(OllamaUnavailable):
            OllamaClient(config).available_models()


if __name__ == "__main__":
    unittest.main()
