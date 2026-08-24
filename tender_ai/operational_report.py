from __future__ import annotations

from collections import Counter
import argparse
import json
import math
from pathlib import Path
from typing import Any

from .observability import TRACE_SCHEMA_VERSION


def percentile(values: list[float], value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, min(len(ordered) - 1, math.ceil(len(ordered) * value) - 1))], 3)


def _latency(events: list[dict[str, Any]], predicate) -> dict[str, Any]:
    values = [float(item["duration_ms"]) for item in events if predicate(item) and isinstance(item.get("duration_ms"), (int, float))]
    return {"p50": percentile(values, .5), "p95": percentile(values, .95), "eventCount": len(values)}


def build(path: Path) -> dict[str, Any]:
    parsed, corrupt = [], 0
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    parsed.append(value)
                else:
                    corrupt += 1
            except json.JSONDecodeError:
                corrupt += 1
    schema_versions = Counter(str(item.get("schema_version", "legacy-or-missing")) for item in parsed)
    events = [item for item in parsed if item.get("schema_version") == TRACE_SCHEMA_VERSION]
    unsupported = len(parsed) - len(events)
    completed = [item for item in events if item.get("stage") == "request" and item.get("status") != "started"]
    tools = [item for item in events if item.get("stage") == "tool"]
    model_events = [item for item in events if item.get("stage") == "model"]
    grounding = [item for item in events if item.get("stage") == "grounding"]
    prompt_tokens = sum(int(item.get("prompt_tokens", 0)) for item in completed if isinstance(item.get("prompt_tokens"), int))
    completion_tokens = sum(int(item.get("completion_tokens", 0)) for item in completed if isinstance(item.get("completion_tokens"), int))
    generation_tokens = sum(int(item.get("completion_tokens", 0)) for item in model_events if isinstance(item.get("completion_tokens"), int))
    generation_ms = sum(float(item.get("generation_duration_ms", 0)) for item in model_events if isinstance(item.get("generation_duration_ms"), (int, float)))
    fallbacks = [item for item in completed if item.get("fallback_used")]
    tool_failures = [item for item in tools if not item.get("tool_success")]
    request_failures = [item for item in completed if item.get("status") == "failed"]
    security = [item for item in events if item.get("security_rejection")]
    fingerprints = sorted({str(item["model_fingerprint"]["digest"]) for item in events if isinstance(item.get("model_fingerprint"), dict) and item["model_fingerprint"].get("digest")})
    return {
        "operationalReportSchemaVersion": "2.0.0",
        "traceSchemaVersion": TRACE_SCHEMA_VERSION,
        "eventCount": len(events),
        "traceCount": len({item.get("trace_id") for item in events if item.get("trace_id")}),
        "corruptLineCount": corrupt,
        "unsupportedSchemaEventCount": unsupported,
        "schemaVersions": dict(sorted(schema_versions.items())),
        "latencyMs": {
            "total": _latency(events, lambda item: item.get("stage") == "request" and item.get("status") != "started"),
            "retrieval": _latency(events, lambda item: item.get("stage") in {"tool", "retrieval"} and item.get("retrieval_strategy")),
            "embedding": _latency(events, lambda item: item.get("stage") == "embedding"),
            "llm": _latency(events, lambda item: item.get("stage") == "model"),
            "tool": _latency(events, lambda item: item.get("stage") == "tool"),
        },
        "tokens": {"prompt": prompt_tokens, "completion": completion_tokens, "total": prompt_tokens + completion_tokens, "generationTokensPerSecond": round(generation_tokens / (generation_ms / 1000), 3) if generation_tokens > 0 and generation_ms > 0 else None},
        "apiMonetaryCost": "not applicable / not measured for local Ollama runtime",
        "fallback": {"count": len(fallbacks), "requests": len(completed), "rate": round(len(fallbacks) / len(completed), 4) if completed else 0.0, "reasons": dict(Counter(str(item.get("fallback_reason") or "UNCLASSIFIED") for item in fallbacks))},
        "tools": {"callCount": len(tools), "successCount": len(tools) - len(tool_failures), "failureCount": len(tool_failures), "successRate": round((len(tools) - len(tool_failures)) / len(tools), 4) if tools else None, "failuresByCategory": dict(Counter(str(item.get("tool_failure_category") or "UNCLASSIFIED") for item in tool_failures))},
        "requestFailures": {"count":len(request_failures),"byCategory":dict(Counter(str(item.get("grounding_status") or "UNCLASSIFIED") for item in request_failures))},
        "grounding": {"eventCount": len(grounding), "rejectionCount": sum(item.get("status") == "rejected" for item in grounding), "postGateUnsupportedClaimCount": sum(int(item.get("post_gate_unsupported_claim_count", 0)) for item in grounding if isinstance(item.get("post_gate_unsupported_claim_count"), int))},
        "security": {"rejectionCount": len(security), "categories": dict(Counter(str(item.get("security_category") or "UNCLASSIFIED") for item in security))},
        "models": sorted({str(item["model"]) for item in events if item.get("model")}),
        "modelFingerprints": fingerprints,
        "promptVersions": sorted({str(item["prompt_version"]) for item in events if item.get("prompt_version")}),
        "evaluationVersions": sorted({str(item["evaluation_version"]) for item in events if item.get("evaluation_version")}),
        "legacyPolicy": "Events without the exact v2 schema are counted but not silently reinterpreted.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, default=Path("artifacts/tender-ai-traces.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/tender-operational-report.json"))
    args = parser.parse_args()
    result = build(args.trace)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
