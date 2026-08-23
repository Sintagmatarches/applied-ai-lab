from __future__ import annotations

import argparse
import gzip
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from rail.build_regional_history import build


ROOT = Path(__file__).resolve().parents[2]


def train(day: date, number: int) -> dict:
    value = day.isoformat()
    return {
        "trainNumber": number, "departureDate": value, "trainType": "IC",
        "trainCategory": "Long-distance", "cancelled": False,
        "timeTableRows": [
            {"type": "DEPARTURE", "stationShortCode": "HKI", "countryCode": "FI",
             "commercialStop": True, "trainStopping": True, "cancelled": False,
             "scheduledTime": f"{value}T08:00:00Z", "actualTime": f"{value}T08:02:00Z", "differenceInMinutes": 2},
            {"type": "ARRIVAL", "stationShortCode": "LH", "countryCode": "FI",
             "commercialStop": True, "trainStopping": True, "cancelled": False,
             "scheduledTime": f"{value}T09:00:00Z", "actualTime": f"{value}T09:12:00Z", "differenceInMinutes": 12},
        ],
    }


class RegionalPublicationTests(unittest.TestCase):
    def _write(self, folder: Path, day: date, payload: list[dict]) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        with gzip.open(folder / f"{day.isoformat()}.json.gz", "wt", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def _args(self, folder: Path, output: Path, start: date, end: date) -> argparse.Namespace:
        return argparse.Namespace(
            lookup=str(ROOT / "artifacts/rail-station-regions.json"), train_dir=str(folder),
            start=start.isoformat(), end=end.isoformat(), output=str(output), mode="7d",
            allow_partial=False, source_retrieved_at="2026-01-08T01:00:00Z",
            published_at="2026-01-08T01:05:00Z",
        )

    def test_exact_seven_partitions_publish_idempotently_and_reconcile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            start = date(2026, 1, 1)
            for offset in range(7):
                day = start + timedelta(days=offset)
                self._write(root / "source", day, [train(day, offset + 1)])
            args = self._args(root / "source", root / "snapshot.json", start, start + timedelta(days=6))
            first = build(args)
            first_bytes = (root / "snapshot.json").read_bytes()
            second = build(args)
            self.assertEqual(first_bytes, (root / "snapshot.json").read_bytes())
            self.assertEqual(first, second)
            self.assertEqual(first["coverage"]["status"], "complete")
            self.assertEqual(len(first["regions"]), 19)
            self.assertEqual(first["latestCompletePartition"], "2026-01-07")
            self.assertTrue(all(region["measuredTrains"] <= region["observedTrains"] for region in first["regions"]))

    def test_six_eight_and_invalid_windows_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            start = date(2026, 1, 1)
            for offset in range(6):
                day = start + timedelta(days=offset)
                self._write(root, day, [train(day, offset + 1)])
            with self.assertRaisesRegex(RuntimeError, "Governed window is partial"):
                build(self._args(root, root / "six.json", start, start + timedelta(days=6)))
            with self.assertRaisesRegex(RuntimeError, "exactly seven"):
                build(self._args(root, root / "eight.json", start, start + timedelta(days=7)))
            bad_day = start + timedelta(days=6)
            self._write(root, bad_day, [])
            with self.assertRaisesRegex(RuntimeError, "failed"):
                build(self._args(root, root / "invalid.json", start, bad_day))


if __name__ == "__main__":
    unittest.main()
