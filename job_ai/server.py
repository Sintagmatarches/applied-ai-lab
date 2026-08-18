from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agent import as_json, unavailable_result
from .ollama import OllamaUnavailable
from .runtime import create_runtime


runtime = create_runtime()
app = FastAPI(title="Applied AI Lab · Local Job AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)


class IngestRequest(BaseModel):
    jobs: list[dict[str, Any]] = Field(max_length=100)


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1_000)
    profile: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        models = runtime.ollama.available_models()
        connected = runtime.config.chat_model in models and runtime.config.embedding_model in models
        error = None
    except OllamaUnavailable as unavailable:
        connected = False
        models = []
        error = str(unavailable)
    return {
        "connected": connected,
        "chat_model": runtime.config.chat_model,
        "embedding_model": runtime.config.embedding_model,
        "available_models": models,
        "knowledge_base": runtime.storage.stats(),
        "error": error,
        "boundary": "local-only",
    }


@app.post("/ingest")
def ingest(request: IngestRequest) -> dict[str, Any]:
    saved = runtime.storage.upsert_jobs(request.jobs)
    try:
        indexing = runtime.retriever.index_pending()
    except OllamaUnavailable as error:
        indexing = {"indexed": 0, "error": str(error)}
    return {"saved": saved, "indexing": indexing, "knowledge_base": runtime.storage.stats()}


@app.post("/ask")
def ask(request: AskRequest) -> dict[str, Any]:
    try:
        return as_json(runtime.agent.ask(request.question, profile=request.profile))
    except OllamaUnavailable as error:
        return as_json(unavailable_result(error, runtime.config.chat_model))
