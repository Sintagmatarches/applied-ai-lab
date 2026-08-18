from __future__ import annotations

from dataclasses import dataclass

from .agent import TenderAgent
from .config import AiConfig
from .observability import TraceWriter
from .ollama import OllamaClient
from .retrieval import HybridRetriever
from .storage import TenderKnowledgeBase
from .tools import ToolRegistry


@dataclass(frozen=True)
class Runtime:
    config: AiConfig; ollama: OllamaClient; storage: TenderKnowledgeBase
    retriever: HybridRetriever; tools: ToolRegistry; agent: TenderAgent


def create_runtime(config:AiConfig|None=None)->Runtime:
    selected=config or AiConfig.from_env(); storage=TenderKnowledgeBase(selected.database_path); ollama=OllamaClient(selected)
    retriever=HybridRetriever(storage,ollama,selected.top_k); tools=ToolRegistry(storage,retriever); agent=TenderAgent(ollama,tools,TraceWriter(selected.trace_path))
    return Runtime(selected,ollama,storage,retriever,tools,agent)
