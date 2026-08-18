from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class AiConfig:
    ollama_url: str = "http://127.0.0.1:11434"
    chat_model: str = "qwen2.5:3b-instruct"
    embedding_model: str = "nomic-embed-text:latest"
    request_timeout_seconds: float = 45.0
    embedding_timeout_seconds: float = 90.0
    top_k: int = 5
    database_path: Path = Path("data/tender-ai/tenders.sqlite3")
    trace_path: Path = Path("artifacts/tender-ai-traces.jsonl")

    @classmethod
    def from_env(cls) -> "AiConfig":
        return cls(
            ollama_url=os.getenv("OLLAMA_URL", cls.ollama_url).rstrip("/"),
            chat_model=os.getenv("TENDER_AI_CHAT_MODEL", cls.chat_model),
            embedding_model=os.getenv("TENDER_AI_EMBEDDING_MODEL", cls.embedding_model),
            request_timeout_seconds=float(os.getenv("TENDER_AI_LLM_TIMEOUT_SECONDS", cls.request_timeout_seconds)),
            embedding_timeout_seconds=float(os.getenv("TENDER_AI_EMBEDDING_TIMEOUT_SECONDS", cls.embedding_timeout_seconds)),
            top_k=max(1, min(20, int(os.getenv("TENDER_AI_TOP_K", cls.top_k)))),
            database_path=Path(os.getenv("TENDER_AI_DATABASE_PATH", str(cls.database_path))),
            trace_path=Path(os.getenv("TENDER_AI_TRACE_PATH", str(cls.trace_path))),
        )
