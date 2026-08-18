from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class QualityResult:
    layer: str
    check: str
    status: str
    observed: float | int | str | None
    detail: str

    @property
    def blocking(self) -> bool:
        return self.status == "FAIL"


def row_count_anomaly(current: int, history: list[int]) -> QualityResult:
    reference = [value for value in history[-28:] if value > 0]
    if len(reference) < 7:
        return QualityResult("bronze", "row_count_anomaly", "PASS", current, "insufficient baseline; schema gates still apply")
    median = statistics.median(reference)
    ratio = current / median if median else 0
    status = "FAIL" if ratio < 0.20 or ratio > 5.0 else "PASS"
    return QualityResult("bronze", "row_count_anomaly", status, round(ratio, 4), f"current={current}, trailing_28_median={median}")


def require_no_failures(results: list[QualityResult], stage: str) -> None:
    failures = [item for item in results if item.blocking]
    if failures:
        messages = "; ".join(f"{item.check}: {item.detail}" for item in failures)
        raise ValueError(f"{stage} quality gate rejected partition: {messages}")
