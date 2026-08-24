from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from rail.publication import (
    PublicationValidationError,
    build_manifest,
    prepare_publication,
    validate_manifest,
    validate_snapshot,
)
from rail.publication_dates import resolve_publication_window


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "artifacts/rail-regional-7d.json"


class PublicationDataPlaneTests(unittest.TestCase):
    def snapshot(self) -> dict:
        return json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    def test_valid_snapshot_manifest_digest_and_bounded_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            manifest = prepare_publication(SNAPSHOT, target, retention=2)
            snapshot_path = target / manifest["snapshotPath"]
            self.assertTrue(snapshot_path.is_file())
            self.assertEqual(validate_manifest(json.loads((target / "manifest.json").read_text()), snapshot_path.read_bytes(), self.snapshot()), manifest)
            for name in ("2026-01-01-old.json", "2026-01-02-old.json", "2026-01-03-old.json"):
                (target / "snapshots" / name).write_text("{}", encoding="utf-8")
            prepare_publication(SNAPSHOT, target, retention=2)
            self.assertLessEqual(len(list((target / "snapshots").glob("*.json"))), 2)

    def test_manifest_detects_snapshot_tampering(self):
        payload = SNAPSHOT.read_bytes()
        snapshot = self.snapshot()
        manifest = build_manifest(payload, snapshot)
        with self.assertRaisesRegex(PublicationValidationError, "snapshotSha256"):
            validate_manifest(manifest, payload + b" ", snapshot)

    def test_snapshot_rejects_contract_coverage_mode_and_region_defects(self):
        cases = [
            ("schemaVersion", "wrong", "schemaVersion"),
            ("kpiDefinitionVersion", "wrong", "kpiDefinitionVersion"),
            ("sampleSupportPolicyVersion", "wrong", "sampleSupportPolicyVersion"),
            ("freshnessPolicyVersion", "wrong", "freshnessPolicyVersion"),
            ("mode", "24h", "mode"),
        ]
        for field, value, message in cases:
            with self.subTest(field=field):
                snapshot = self.snapshot()
                snapshot[field] = value
                with self.assertRaisesRegex(PublicationValidationError, message):
                    validate_snapshot(snapshot)
        incomplete = self.snapshot()
        incomplete["coverage"]["status"] = "partial"
        with self.assertRaisesRegex(PublicationValidationError, "complete"):
            validate_snapshot(incomplete)
        missing = self.snapshot()
        missing["coverage"]["availableDates"] = missing["coverage"]["availableDates"][:-1]
        with self.assertRaisesRegex(PublicationValidationError, "seven available"):
            validate_snapshot(missing)
        regions = self.snapshot()
        regions["regions"] = regions["regions"][:-1]
        with self.assertRaisesRegex(PublicationValidationError, "19 regions"):
            validate_snapshot(regions)

    def test_helsinki_completed_date_is_explicit_and_dst_independent(self):
        spring = datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc)
        autumn = datetime(2026, 10, 25, 22, 30, tzinfo=timezone.utc)
        self.assertEqual(tuple(day.isoformat() for day in resolve_publication_window(now=spring)), ("2026-03-22", "2026-03-28"))
        self.assertEqual(tuple(day.isoformat() for day in resolve_publication_window(now=autumn)), ("2026-10-19", "2026-10-25"))
        self.assertEqual(tuple(day.isoformat() for day in resolve_publication_window(requested_end="2026-01-01")), ("2025-12-26", "2026-01-01"))


if __name__ == "__main__":
    unittest.main()
