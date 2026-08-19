from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def percentile(values: list[float], value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(len(ordered) * value) - 1))]


def build(path: Path) -> dict:
    events, corrupt = [], 0
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                corrupt += 1
    latencies = [float(item.get("metrics", {}).get("total_latency_ms")) for item in events if isinstance(item.get("metrics", {}).get("total_latency_ms"), (int, float))]
    tool_latencies = [float(call["latency_ms"]) for item in events for call in item.get("tool_calls", []) if isinstance(call.get("latency_ms"), (int, float))]
    fallbacks = sum(bool(item.get("metrics", {}).get("fallback_used")) for item in events)
    failures = [failure for item in events for failure in item.get("tool_failures", [])]
    return {"event_count": len(events), "corrupt_lines": corrupt, "latency_ms": {"p50": percentile(latencies, .5), "p95": percentile(latencies, .95)}, "tool_latency_ms": {"p50": percentile(tool_latencies, .5), "p95": percentile(tool_latencies, .95)}, "fallback_rate": fallbacks / len(events) if events else 0.0, "tool_failure_rate": len(failures) / max(1, sum(len(item.get("tool_calls", [])) for item in events)), "models": sorted({item.get("model") for item in events if item.get("model")}), "prompt_versions": sorted({item.get("prompt_version") for item in events if item.get("prompt_version")})}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, default=Path("artifacts/tender-ai-traces.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/tender-operational-report.json"))
    args = parser.parse_args()
    result = build(args.trace)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
