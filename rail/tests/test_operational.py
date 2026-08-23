from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from rail.operational import coverage_contract, freshness_contract, sample_support, wilson_interval


UTC = timezone.utc


class SampleSupportTests(unittest.TestCase):
    def test_live_boundary_counts_remain_separate_from_operational_status(self):
        self.assertEqual(sample_support("live", 7, 7)["status"], "low-sample")
        self.assertEqual(sample_support("live", 8, 8)["status"], "sufficient")
        self.assertEqual(sample_support("live", 9, 9)["status"], "sufficient")

    def test_coverage_and_domain_absence_are_explicit(self):
        self.assertEqual(sample_support("24h", 30, 0)["status"], "low-sample")
        self.assertEqual(sample_support("24h", 30, 19)["status"], "low-sample")
        self.assertEqual(sample_support("24h", 25, 20)["status"], "sufficient")
        self.assertEqual(sample_support("historical", 0, 0)["status"], "not-applicable")
        self.assertEqual(sample_support("historical", 0, 0, has_service=False)["status"], "not-applicable")

    def test_wilson_interval_handles_boundaries_without_claiming_score_uncertainty(self):
        self.assertIsNone(wilson_interval(0, 0))
        one = wilson_interval(1, 1)
        near_zero = wilson_interval(1, 100)
        near_one = wilson_interval(99, 100)
        interior = wilson_interval(50, 100)
        self.assertAlmostEqual(one["upper"], 1.0)
        self.assertGreater(one["lower"], 0)
        self.assertLess(near_zero["lower"], 0.01)
        self.assertGreater(near_one["upper"], 0.99)
        self.assertLess(interior["lower"], 0.5)
        self.assertGreater(interior["upper"], 0.5)


class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)

    def _live(self, age_minutes: int):
        timestamp = self.now - timedelta(minutes=age_minutes)
        return freshness_contract(
            "live", now=self.now, source_retrieved_at=timestamp,
            validated_at=timestamp, gold_published_at=timestamp,
        )

    def test_fresh_warning_and_stale_boundaries_are_deterministic(self):
        self.assertEqual(self._live(5)["state"], "fresh")
        self.assertEqual(self._live(6)["state"], "warning")
        self.assertEqual(self._live(15)["state"], "warning")
        self.assertEqual(self._live(16)["state"], "stale")

    def test_attempt_or_source_success_cannot_mask_failed_publication(self):
        recent = self.now - timedelta(minutes=1)
        old_gold = self.now - timedelta(hours=70)
        self.assertEqual(freshness_contract(
            "7d", now=self.now, source_retrieved_at=recent,
            validated_at=recent, gold_published_at=None,
        )["state"], "stale")
        self.assertEqual(freshness_contract(
            "7d", now=self.now, source_retrieved_at=old_gold,
            validated_at=old_gold, gold_published_at=old_gold,
        )["state"], "stale")
        recovered = freshness_contract(
            "7d", now=self.now, source_retrieved_at=recent,
            validated_at=recent, gold_published_at=recent,
        )
        self.assertEqual(recovered["state"], "fresh")

    def test_missing_partition_and_invalid_timestamp_order_are_stale(self):
        recent = self.now - timedelta(minutes=1)
        self.assertEqual(freshness_contract(
            "7d", now=self.now, source_retrieved_at=recent,
            validated_at=recent, gold_published_at=recent, coverage_status="partial",
        )["state"], "stale")
        self.assertEqual(freshness_contract(
            "24h", now=self.now, source_retrieved_at=self.now,
            validated_at=self.now - timedelta(minutes=1), gold_published_at=self.now,
        )["state"], "stale")
        self.assertEqual(freshness_contract(
            "historical", now=self.now, source_retrieved_at=recent,
            validated_at=recent, gold_published_at=recent,
        )["state"], "not-applicable")


class CoverageTests(unittest.TestCase):
    def test_complete_partial_unavailable_and_duplicate_windows(self):
        expected = [f"2026-08-{day:02d}" for day in range(16, 23)]
        self.assertEqual(coverage_contract(expected, expected)["status"], "complete")
        partial = coverage_contract(expected, expected[:-1])
        self.assertEqual(partial["status"], "partial")
        self.assertEqual(partial["missingDates"], ["2026-08-22"])
        self.assertEqual(coverage_contract(expected, [expected[0], expected[0]])["duplicatePartitions"], 1)
        self.assertEqual(coverage_contract(expected, [])["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
