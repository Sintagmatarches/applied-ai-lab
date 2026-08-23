from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from typing import Any

from rail.pipeline import Journey, StationArrival, reliability_metrics, summarise_routes, summarise_stations


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = Path(__file__).with_name("fixtures") / "kpi-regression-v1.json"


def expand_delays(delay_counts: list[list[int | None]]) -> list[int | None]:
    return [delay for delay, count in delay_counts for _ in range(count)]


def contract_hash(fixture: dict[str, Any]) -> str:
    approved = {"input": fixture["input"], "expected": fixture["expected"]}
    payload = json.dumps(approved, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def differences(expected: Any, actual: Any, path: str = "") -> list[str]:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected object, actual {type(actual).__name__}"]
        result: list[str] = []
        for key, value in expected.items():
            child = f"{path}.{key}" if path else key
            if key not in actual:
                result.append(f"{child}: expected {value!r}, actual <missing>")
            else:
                result.extend(differences(value, actual[key], child))
        return result
    if expected != actual:
        return [f"{path}: expected {expected!r}, actual {actual!r}"]
    return []


def assert_contract(test_case: unittest.TestCase, label: str, expected: Any, actual: Any) -> None:
    diff = differences(expected, actual, label)
    if diff:
        test_case.fail("Rail KPI regression:\n" + "\n".join(f"- {line}" for line in diff))


class RailKpiRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_approved_fixture_has_a_reviewable_release_note(self):
        digest = contract_hash(self.fixture)
        approval = self.fixture["approval"]
        self.assertEqual(approval["fixture_sha256"], digest)
        release_note = ROOT / approval["release_note"]
        self.assertTrue(release_note.is_file(), f"Missing KPI contract release note: {release_note}")
        contents = release_note.read_text(encoding="utf-8")
        self.assertIn(f"KPI contract: {self.fixture['contract_id']}", contents)
        self.assertIn(f"Fixture SHA-256: {digest}", contents)

    def test_overall_threshold_contract(self):
        spec = self.fixture["input"]["overall"]
        delays = [delay for delay in expand_delays(spec["delay_counts"]) if delay is not None]
        actual = reliability_metrics(delays, spec["scheduled"], spec["cancelled"])
        assert_contract(self, "overall", self.fixture["expected"]["overall"], actual)

    def test_route_kpi_contract(self):
        spec = self.fixture["input"]["route"]
        delays = expand_delays(spec["delay_counts"])
        journeys = [
            Journey(
                key=f"fixture-route-{index}",
                departure_date="2026-01-15",
                month=spec["month"],
                weekday=3,
                hour=12,
                train_type="IC",
                category="Long-distance",
                commuter_line="",
                route_key=spec["route_key"],
                route_label=spec["route"],
                origin_code="HKI",
                destination_code="LH",
                scheduled_departure="2026-01-15T10:00:00Z",
                cancelled=delay is None and index >= len(delays) - spec["cancelled"],
                partial_cancelled=False,
                final_arrival_cancelled=False,
                final_delay=delay,
                departure_delay=0 if delay is not None else None,
            )
            for index, delay in enumerate(delays)
        ]
        actual = summarise_routes(journeys)[0]
        assert_contract(self, "route.HKI|LH", self.fixture["expected"]["route"], actual)

    def test_station_kpi_contract(self):
        spec = self.fixture["input"]["station"]
        delays = expand_delays(spec["delay_counts"])
        arrivals = [
            StationArrival(
                month="2026-01",
                station_code=spec["station_code"],
                station_name=spec["station"],
                cancelled=delay is None and index >= len(delays) - spec["cancelled"],
                delay=delay,
            )
            for index, delay in enumerate(delays)
        ]
        actual = summarise_stations(arrivals)[0]
        assert_contract(self, "station.LH", self.fixture["expected"]["station"], actual)


if __name__ == "__main__":
    unittest.main()
