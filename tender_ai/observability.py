from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


TRACE_SCHEMA_VERSION = "2.0.0"
SENSITIVE_KEYS = {"query", "question", "raw_query", "supplier_profile", "profile", "prompt", "messages", "authorization", "environment"}


class TraceSchemaError(ValueError):
    pass


def _contains_sensitive(value: Any) -> bool:
    if isinstance(value, dict):
        return any(str(key).lower() in SENSITIVE_KEYS or _contains_sensitive(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_sensitive(item) for item in value)
    return False


class TraceWriter:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(event.get("trace_id"), str) or not event["trace_id"]:
            raise TraceSchemaError("trace_id is required")
        if not isinstance(event.get("stage"), str) or not event["stage"]:
            raise TraceSchemaError("stage is required")
        if event.get("status") not in {"started", "succeeded", "failed", "rejected", "fallback"}:
            raise TraceSchemaError("status is invalid")
        if _contains_sensitive(event):
            raise TraceSchemaError("trace event contains a raw sensitive field")
        envelope = {"schema_version": TRACE_SCHEMA_VERSION, "event_id": str(uuid4()), "timestamp": datetime.now(timezone.utc).isoformat(), **event}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n")
        return envelope


def safe_query_metadata(query: str) -> dict[str, Any]:
    return {"query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(), "query_length": len(query)}


def safe_tool_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"argument_keys": sorted(arguments)}
    for key, value in arguments.items():
        if key == "query" and isinstance(value, str):
            result["query_metadata"] = safe_query_metadata(value)
        elif key in {"notice_id", "from_version", "to_version", "top_k", "limit", "country", "cpv"}:
            result[key] = value
        elif isinstance(value, list):
            result[f"{key}_count"] = len(value)
        elif isinstance(value, str):
            result[f"{key}_length"] = len(value)
    return {"tool_name": name, "arguments": result}
