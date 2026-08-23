from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import date
from pathlib import Path

from rail.lakehouse.contracts import ContractRegistry
from rail.lakehouse.planning import affected_complete_windows, select_partitions
from rail.lakehouse.quality import row_count_anomaly


ROOT = Path(__file__).resolve().parents[3]


class ContractTests(unittest.TestCase):
    def test_contracts_are_executable_and_reject_missing_required_columns(self):
        registry = ContractRegistry(ROOT / "rail/contracts/data_contracts.json")
        contract = registry.table("gold.fact_train_journey")
        self.assertEqual(contract.business_key, ("journey_key",))
        with self.assertRaisesRegex(ValueError, "missing columns"):
            registry.validate_columns("gold.fact_train_journey", ["journey_key"])


class PlanningTests(unittest.TestCase):
    def test_same_hash_is_idempotently_skipped_and_force_reprocesses(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            path = source / "2026-01-01.json.gz"
            path.write_bytes(b"trusted bytes")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            same = select_partitions(
                date(2026, 1, 1), date(2026, 1, 1), source,
                {"2026-01-01": digest}, {"2026-01-01": digest},
            )
            forced = select_partitions(
                date(2026, 1, 1), date(2026, 1, 1), source,
                {"2026-01-01": digest}, {"2026-01-01": digest}, force=True,
            )
        self.assertEqual(same[0].action, "skip")
        self.assertEqual(forced[0].action, "process")

    def test_changed_hash_is_selected_as_late_reprocessed_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / "2026-01-01.json.gz").write_bytes(b"new")
            decision = select_partitions(
                date(2026, 1, 1), date(2026, 1, 1), source,
                {"2026-01-01": "new-hash"}, {"2026-01-01": "old-hash"},
            )[0]
        self.assertEqual(decision.reason, "source content changed")

    def test_late_correction_rebuilds_only_complete_affected_seven_day_windows(self):
        available = {date(2026, 1, day) for day in range(1, 11)}
        self.assertEqual(
            affected_complete_windows(available, {date(2026, 1, 4)}),
            [date(2026, 1, day) for day in range(7, 11)],
        )
        self.assertEqual(
            affected_complete_windows({date(2026, 1, day) for day in range(1, 7)}, {date(2026, 1, 4)}),
            [],
        )

    def test_row_count_gate_rejects_extreme_partition(self):
        result = row_count_anomaly(10, [1000] * 10)
        self.assertEqual(result.status, "FAIL")


if __name__ == "__main__":
    unittest.main()
