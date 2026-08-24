from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

from tender_ai.agent import TenderAgent
from tender_ai.domain import DEMO_PROFILE
from tender_ai.observability import TraceWriter
from tender_ai.storage import TenderKnowledgeBase
from tender_ai.ted import normalize
from tender_ai.tools import ToolRegistry, ToolValidationError


class _Retriever:
    def search(self, *args, **kwargs):
        return [], {"scan_strategy": "fixture"}


class _Ollama:
    config = type("Config", (), {"chat_model": "deterministic-not-executed"})()


def _rejects(call) -> bool:
    try:
        call()
    except ToolValidationError:
        return True
    return False


def evaluate(corpus: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        storage = TenderKnowledgeBase(Path(directory) / "agent-contract.sqlite3")
        notice = normalize(corpus["notices"][0]["raw"], corpus["notices"][0]["retrievedAt"])
        storage.ingest([notice], DEMO_PROFILE)
        tools = ToolRegistry(storage, _Retriever(), DEMO_PROFILE)
        agent = TenderAgent(_Ollama(), tools, TraceWriter(Path(directory) / "trace.jsonl"))
        cases = [
            {"caseId":"allowed-tool-set","passed":len(tools.definitions) == 14,"detail":{"toolCount":len(tools.definitions)}},
            {"caseId":"unknown-tool-rejected","passed":_rejects(lambda: tools.execute("delete_everything", {}))},
            {"caseId":"unknown-argument-rejected","passed":_rejects(lambda: tools.execute("get_notice", {"notice_id":notice["notice_id"], "admin":True}))},
            {"caseId":"tool-argument-smuggling-rejected","passed":_rejects(lambda: tools.execute("retrieve_tenders", {"query":"data", "url":"http://127.0.0.1"}))},
            {"caseId":"trusted-profile-boundary","passed":_rejects(lambda: tools.execute("assess_supplier_fit", {"notice_id":notice["notice_id"], "annual_turnover":999999999}))},
            {"caseId":"bounded-rounds","passed":agent.max_steps == 4 and agent.max_tool_calls == 6 and agent.max_seconds == 180.0,"detail":{"maxSteps":agent.max_steps,"maxToolCalls":agent.max_tool_calls,"maxSeconds":agent.max_seconds}},
            {"caseId":"tool-result-provenance","passed":all(item.get("evidence_id") and item.get("notice_id") == notice["notice_id"] for item in tools.execute("get_notice", {"notice_id":notice["notice_id"]}).evidence)},
        ]
    return {"evidenceClass":"deterministic agent/tool software contract; no model intelligence claim","suiteVersion":"agent-contract-v2.0.0","caseCount":len(cases),"passed":sum(item["passed"] for item in cases),"cases":cases,"modelDependent":{"status":"reported only by live verification","ciGate":False}}
