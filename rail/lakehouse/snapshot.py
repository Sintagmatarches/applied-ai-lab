"""Bind validation and provenance to the exact immutable bytes Spark will read."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
from datetime import date
from pathlib import Path

from rail.pipeline import validate_train_partition


def snapshot_partition(source: Path, root: Path, day: date, expected_hash: str):
    directory = root / f"bronze/digitraffic_trains/departure_date={day.isoformat()}"
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix="snapshot-", suffix=".gz", dir=directory)
    temporary = Path(temporary_name)
    try:
        digest = hashlib.sha256()
        with os.fdopen(descriptor, "wb") as target, source.open("rb") as origin:
            for block in iter(lambda: origin.read(1024 * 1024), b""):
                target.write(block)
                digest.update(block)
        if digest.hexdigest() != expected_hash:
            raise ValueError("Source changed after planning; rerun to plan the new partition")
        with gzip.open(temporary, "rt", encoding="utf-8") as handle:
            payload = validate_train_partition(day, json.load(handle))
        immutable = directory / f"content_sha256={expected_hash}/trains.json.gz"
        immutable.parent.mkdir(parents=True, exist_ok=True)
        if immutable.exists():
            existing = hashlib.sha256()
            with immutable.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    existing.update(block)
            if existing.hexdigest() != expected_hash:
                raise ValueError("Immutable Bronze snapshot is corrupt; restore it before rerunning")
        else:
            # Pipeline writers are serialized by orchestration. Atomic rename
            # prevents readers seeing partially copied snapshots.
            temporary.replace(immutable)
        return payload, expected_hash, immutable
    finally:
        temporary.unlink(missing_ok=True)
