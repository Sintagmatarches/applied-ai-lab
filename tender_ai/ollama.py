from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import AiConfig


class OllamaUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelMetrics:
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    total_duration_ns: int | None
    load_duration_ns: int | None = None
    prompt_eval_duration_ns: int | None = None
    eval_duration_ns: int | None = None
    done_reason: str | None = None

    @property
    def generation_tokens_per_second(self) -> float | None:
        if not self.completion_tokens or not self.eval_duration_ns or self.eval_duration_ns <= 0:
            return None
        return round(self.completion_tokens / (self.eval_duration_ns / 1_000_000_000), 3)

    def public(self) -> dict[str, Any]:
        return {
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": (self.prompt_tokens + self.completion_tokens) if self.prompt_tokens is not None and self.completion_tokens is not None else None,
            "model_total_duration_ms": _ns_to_ms(self.total_duration_ns),
            "model_load_duration_ms": _ns_to_ms(self.load_duration_ns),
            "prompt_eval_duration_ms": _ns_to_ms(self.prompt_eval_duration_ns),
            "generation_duration_ms": _ns_to_ms(self.eval_duration_ns),
            "generation_tokens_per_second": self.generation_tokens_per_second,
            "done_reason": self.done_reason,
        }


@dataclass(frozen=True)
class ChatResult:
    message: dict[str, Any]
    metrics: ModelMetrics
    model: str


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _ns_to_ms(value: int | None) -> float | None:
    return round(value / 1_000_000, 3) if value is not None else None


class OllamaClient:
    """Model-independent Ollama HTTP adapter; models are environment-configurable."""
    def __init__(self, config: AiConfig): self.config = config

    def _post(self, path: str, payload: dict[str, Any], timeout: float) -> tuple[dict[str, Any], float]:
        started = time.perf_counter()
        request = Request(f"{self.config.ollama_url}{path}", data=json.dumps(payload, ensure_ascii=False).encode(), headers={"content-type": "application/json", "accept": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=timeout) as response: result = json.loads(response.read().decode())
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise OllamaUnavailable(f"Ollama request to {path} failed: {type(error).__name__}") from error
        return result, (time.perf_counter() - started) * 1000

    @staticmethod
    def _metrics(payload: dict[str, Any], latency: float) -> ModelMetrics:
        return ModelMetrics(
            round(latency, 3),
            _optional_int(payload.get("prompt_eval_count")),
            _optional_int(payload.get("eval_count")),
            _optional_int(payload.get("total_duration")),
            _optional_int(payload.get("load_duration")),
            _optional_int(payload.get("prompt_eval_duration")),
            _optional_int(payload.get("eval_duration")),
            str(payload["done_reason"]) if payload.get("done_reason") is not None else None,
        )

    def model_details(self) -> list[dict[str, Any]]:
        try:
            with urlopen(Request(f"{self.config.ollama_url}/api/tags", headers={"accept": "application/json"}), timeout=5) as response:
                payload = json.loads(response.read().decode())
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise OllamaUnavailable("Ollama model list is unavailable") from error
        return [item for item in payload.get("models", []) if isinstance(item, dict)]

    def available_models(self) -> list[str]:
        return [str(model.get("name")) for model in self.model_details()]

    def model_fingerprint(self, configured_name: str) -> dict[str, Any]:
        match = next((item for item in self.model_details() if item.get("name") == configured_name or item.get("model") == configured_name), None)
        return {
            "configuredModel": configured_name,
            "resolvedModel": str(match.get("model") or match.get("name")) if match else None,
            "digest": str(match.get("digest")) if match and match.get("digest") else None,
            "modifiedAt": str(match.get("modified_at")) if match and match.get("modified_at") else None,
        }

    def chat(self, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]] | None = None, output_format: dict[str, Any] | str | None = None, temperature: float = 0.0) -> ChatResult:
        payload: dict[str, Any] = {"model": self.config.chat_model, "messages": messages, "stream": False, "options": {"temperature": temperature}}
        if tools: payload["tools"] = tools
        if output_format is not None: payload["format"] = output_format
        result, latency = self._post("/api/chat", payload, self.config.request_timeout_seconds)
        if not isinstance(result.get("message"), dict): raise OllamaUnavailable("Ollama returned no assistant message")
        return ChatResult(result["message"], self._metrics(result, latency), str(result.get("model", self.config.chat_model)))

    def embed(self, texts: list[str]) -> tuple[list[list[float]], ModelMetrics]:
        result, latency = self._post("/api/embed", {"model": self.config.embedding_model, "input": texts}, self.config.embedding_timeout_seconds)
        embeddings = result.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts): raise OllamaUnavailable("Ollama returned an invalid embedding batch")
        return embeddings, self._metrics(result, latency)
