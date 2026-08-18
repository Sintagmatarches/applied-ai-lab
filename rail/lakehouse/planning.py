from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class PartitionDecision:
    departure_date: date
    source_path: Path
    source_sha256: str
    action: str
    reason: str


def date_range(start: date, end: date):
    if end < start:
        raise ValueError("end date must not precede start date")
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def select_partitions(
    start: date,
    end: date,
    source_dir: Path,
    source_hashes: Mapping[str, str],
    successful_hashes: Mapping[str, str],
    *,
    force: bool = False,
) -> list[PartitionDecision]:
    decisions: list[PartitionDecision] = []
    for day in date_range(start, end):
        key = day.isoformat()
        path = source_dir / f"{key}.json.gz"
        if not path.is_file():
            raise FileNotFoundError(f"Missing trusted Digitraffic partition: {path}")
        digest = source_hashes[key]
        previous = successful_hashes.get(key)
        if force:
            action, reason = "process", "forced backfill/recovery"
        elif previous is None:
            action, reason = "process", "no successful watermark"
        elif previous != digest:
            action, reason = "process", "source content changed"
        else:
            action, reason = "skip", "same source hash already committed"
        decisions.append(PartitionDecision(day, path, digest, action, reason))
    return decisions
