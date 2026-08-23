from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class TableContract:
    name: str
    grain: str
    business_key: tuple[str, ...]
    required: tuple[str, ...]
    partition_by: tuple[str, ...]
    metrics: dict[str, str]
    expected_freshness_hours: int | None


class ContractRegistry:
    """Small, executable contract registry used by pipeline gates and tests."""

    def __init__(self, path: Path):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("contractVersion") not in {"1.0.0", "2.0.0"} or not raw.get("tables"):
            raise ValueError("Unsupported or empty Finland Rail data contract")
        self.version = raw["contractVersion"]
        self.owner = raw["owner"]
        self.source = raw["source"]
        self._tables = {
            name: TableContract(
                name=name,
                grain=value["grain"],
                business_key=tuple(value["businessKey"]),
                required=tuple(value["required"]),
                partition_by=tuple(value.get("partitionBy", [])),
                metrics=dict(value.get("metrics", {})),
                expected_freshness_hours=value.get("expectedFreshnessHours"),
            )
            for name, value in raw["tables"].items()
        }

    def table(self, name: str) -> TableContract:
        try:
            return self._tables[name]
        except KeyError as error:
            raise KeyError(f"No data contract for {name}") from error

    def validate_columns(self, name: str, columns: Iterable[str]) -> None:
        actual = set(columns)
        missing = sorted(set(self.table(name).required) - actual)
        if missing:
            raise ValueError(f"{name} violates contract; missing columns: {', '.join(missing)}")

    def as_dict(self) -> dict[str, Any]:
        return {name: contract.__dict__ for name, contract in self._tables.items()}
