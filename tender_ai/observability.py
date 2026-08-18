from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


class TraceWriter:
    def __init__(self, path: Path | str): self.path=Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
    def write(self, event: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as handle: handle.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), **event}, ensure_ascii=False)+"\n")


def safe_query_metadata(query: str) -> dict[str, Any]:
    return {"query_sha256_12": hashlib.sha256(query.encode()).hexdigest()[:12], "query_length": len(query)}
