from __future__ import annotations

import gzip
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from rail.lakehouse.pipeline import LakehousePipeline
from rail.lakehouse.spark import build_spark


ROOT = Path(__file__).resolve().parents[3]


def train(number: int, *, day: date = date(2026, 1, 1), duplicate: bool = False):
    day_text = day.isoformat()
    return {
        "trainNumber": number,
        "departureDate": day_text,
        "trainType": "IC",
        "trainCategory": "Long-distance",
        "commuterLineID": "",
        "cancelled": False,
        "timeTableRows": [
            {
                "type": "DEPARTURE", "stationShortCode": "HKI", "countryCode": "FI",
                "commercialStop": True, "trainStopping": True, "cancelled": False,
                "scheduledTime": f"{day_text}T08:00:00Z", "actualTime": f"{day_text}T08:02:00Z", "differenceInMinutes": 2,
            },
            {
                "type": "ARRIVAL", "stationShortCode": "LH", "countryCode": "FI",
                "commercialStop": True, "trainStopping": True, "cancelled": False,
                "scheduledTime": f"{day_text}T09:00:00Z", "actualTime": f"{day_text}T09:12:00Z", "differenceInMinutes": 12,
            },
        ],
    }


@unittest.skipUnless(os.environ.get("RAIL_SPARK_TESTS") == "1", "set RAIL_SPARK_TESTS=1 for Delta integration tests")
class SparkPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = build_spark("rail-lakehouse-tests", "local[2]")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def _write_partition(self, source: Path, payload, day: date = date(2026, 1, 1)):
        source.mkdir(parents=True, exist_ok=True)
        with gzip.open(source / f"{day.isoformat()}.json.gz", "wt", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def test_end_to_end_rerun_is_idempotent_and_force_recovers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, lakehouse = root / "source", root / "lakehouse"
            self._write_partition(source, [train(1)])
            pipeline = LakehousePipeline(self.spark, lakehouse, source, ROOT / "artifacts/rail-station-regions.json")
            first = pipeline.process(date(2026, 1, 1), date(2026, 1, 1))
            second = pipeline.process(date(2026, 1, 1), date(2026, 1, 1))
            recovered = pipeline.process(date(2026, 1, 1), date(2026, 1, 1), force=True)
            facts = self.spark.read.format("delta").load(str(lakehouse / "gold/fact_train_journey"))
            row = facts.select("final_delay_minutes", "on_time_5", "on_time_15").first()
            self.assertEqual((first["processedPartitions"], second["skippedPartitions"], recovered["processedPartitions"]), (1, 1, 1))
            self.assertEqual(facts.count(), 1)
            self.assertEqual((row.final_delay_minutes, row.on_time_5, row.on_time_15), (12, False, True))

    def test_duplicate_partition_is_rejected_without_watermark(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, lakehouse = root / "source", root / "lakehouse"
            self._write_partition(source, [train(1), train(1)])
            pipeline = LakehousePipeline(self.spark, lakehouse, source, ROOT / "artifacts/rail-station-regions.json")
            with self.assertRaisesRegex(ValueError, "duplicate_source_business_keys"):
                pipeline.process(date(2026, 1, 1), date(2026, 1, 1))
            self.assertEqual(pipeline.successful_hashes(), {})

    def test_seven_daily_partitions_publish_reconciled_region_semantics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, lakehouse = root / "source", root / "lakehouse"
            start = date(2026, 1, 1)
            for offset in range(7):
                day = start + timedelta(days=offset)
                self._write_partition(source, [train(offset + 1, day=day)], day)
            pipeline = LakehousePipeline(self.spark, lakehouse, source, ROOT / "artifacts/rail-station-regions.json")
            result = pipeline.process(start, start + timedelta(days=6))
            daily = self.spark.read.format("delta").load(str(lakehouse / "gold/mart_regional_performance_daily"))
            rolling = self.spark.read.format("delta").load(str(lakehouse / "gold/mart_regional_performance_7d"))
            bridge = self.spark.read.format("delta").load(str(lakehouse / "gold/bridge_station_region"))
            self.assertEqual(result["rolling7dWindows"], ["2026-01-07"])
            self.assertNotIn("threshold_minutes", daily.columns)
            self.assertEqual(rolling.count(), 19)
            self.assertEqual(rolling.filter("component_partitions != 7").count(), 0)
            self.assertEqual(bridge.groupBy("station_region_key").count().filter("count != 1").count(), 0)


if __name__ == "__main__":
    unittest.main()
