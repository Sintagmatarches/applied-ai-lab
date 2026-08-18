from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import AiConfig


class OllamaUnavailable(RuntimeError):
    """Raised when the configured local Ollama runtime cannot serve a request."""


@dataclass(frozen=True)
class ModelMetrics:
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    total_duration_ns: int | None


@dataclass(frozen=True)
class ChatResult:
    message: dict[str, Any]
    metrics: ModelMetrics
    model: str


@dataclass(frozen=True)
class EmbeddingResult:
    embeddings: list[list[float]]
    metrics: ModelMetrics
    model: str


class OllamaClient:
    def __init__(self, config: AiConfig):
        self.config = config

    def _post(self, path: str, payload: dict[str, Any], timeout: float) -> tuple[dict[str, Any], float]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.config.ollama_url}{path}",
            data=body,
            headers={"content-type": "application/json", "accept": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise OllamaUnavailable(
                f"Ollama request to {path} failed: {type(error).__name__}"
            ) from error
        return result, (time.perf_counter() - started) * 1000

    @staticmethod
    def _metrics(payload: dict[str, Any], latency_ms: float) -> ModelMetrics:
        return ModelMetrics(
            latency_ms=round(latency_ms, 3),
            prompt_tokens=payload.get("prompt_eval_count"),
            completion_tokens=payload.get("eval_count"),
            total_duration_ns=payload.get("total_duration"),
        )

    def available_models(self) -> list[str]:
        request = Request(f"{self.config.ollama_url}/api/tags", headers={"accept": "application/json"})
        try:
            with urlopen(request, timeout=min(5.0, self.config.request_timeout_seconds)) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise OllamaUnavailable("Ollama model list is unavailable") from error
        return [str(model.get("name")) for model in payload.get("models", [])]

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        output_format: dict[str, Any] | str | None = None,
        temperature: float = 0.0,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": self.config.chat_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if tools:
            payload["tools"] = tools
        if output_format is not None:
            payload["format"] = output_format
        result, latency = self._post(
            "/api/chat", payload, self.config.request_timeout_seconds
        )
        message = result.get("message")
        if not isinstance(message, dict):
            raise OllamaUnavailable("Ollama returned no assistant message")
        return ChatResult(
            message=message,
            metrics=self._metrics(result, latency),
            model=str(result.get("model", self.config.chat_model)),
        )

    def embed(self, texts: list[str]) -> EmbeddingResult:
        result, latency = self._post(
            "/api/embed",
            {"model": self.config.embedding_model, "input": texts},
            self.config.embedding_timeout_seconds,
        )
        embeddings = result.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise OllamaUnavailable("Ollama returned an invalid embedding batch")
        return EmbeddingResult(
            embeddings=embeddings,
            metrics=self._metrics(result, latency),
            model=str(result.get("model", self.config.embedding_model)),
        )
