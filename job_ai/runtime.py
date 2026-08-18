from __future__ import annotations

from dataclasses import dataclass

from .agent import JobAgent
from .config import AiConfig
from .observability import TraceWriter
from .ollama import OllamaClient
from .retrieval import HybridRetriever
from .storage import JobKnowledgeBase
from .tools import ToolRegistry


@dataclass(frozen=True)
class Runtime:
    config: AiConfig
    ollama: OllamaClient
    storage: JobKnowledgeBase
    retriever: HybridRetriever
    tools: ToolRegistry
    agent: JobAgent


def create_runtime(config: AiConfig | None = None) -> Runtime:
    selected = config or AiConfig.from_env()
    storage = JobKnowledgeBase(selected.database_path)
    ollama = OllamaClient(selected)
    retriever = HybridRetriever(storage, ollama)
    tools = ToolRegistry(storage, retriever)
    agent = JobAgent(ollama, tools, TraceWriter(selected.trace_path))
    return Runtime(selected, ollama, storage, retriever, tools, agent)
