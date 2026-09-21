import gzip
import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from rail.lakehouse.snapshot import snapshot_partition


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.gz"
        self.payload = [{"trainNumber": 1, "departureDate": "2026-01-01", "trainCategory": "Long-distance", "timeTableRows": []}]
        self.source.write_bytes(gzip.compress(json.dumps(self.payload).encode(), mtime=0))
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()

    def snapshot(self):
        return snapshot_partition(self.source, self.root, date(2026, 1, 1), self.digest)

    def test_rerun_preserves_exact_bytes_and_original_snapshot_after_correction(self):
        payload, digest, path = self.snapshot()
        original = path.read_bytes()
        self.assertEqual(payload, self.payload)
        self.assertEqual(digest, hashlib.sha256(original).hexdigest())
        self.assertEqual(self.snapshot()[2], path)
        self.payload[0]["trainNumber"] = 2
        self.source.write_bytes(gzip.compress(json.dumps(self.payload).encode(), mtime=0))
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        corrected = self.snapshot()[2]
        self.assertNotEqual(path, corrected)
        self.assertEqual(path.read_bytes(), original)

    def test_changed_source_is_rejected_before_publication(self):
        self.source.write_bytes(b"changed during planning")
        with self.assertRaisesRegex(ValueError, "changed after planning"):
            self.snapshot()
        self.assertEqual(list(self.root.rglob("trains.json.gz")), [])
        self.assertEqual(list(self.root.rglob("snapshot-*")), [])

    def test_corrupt_existing_snapshot_is_not_silently_reused(self):
        path = self.snapshot()[2]
        path.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "snapshot is corrupt"):
            self.snapshot()

    def test_wrong_partition_date_is_rejected(self):
        with self.assertRaises(ValueError):
            snapshot_partition(self.source, self.root, date(2026, 1, 2), self.digest)
        self.assertEqual(list(self.root.rglob("trains.json.gz")), [])
