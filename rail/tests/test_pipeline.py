from __future__ import annotations

import unittest
from datetime import datetime, timezone

from rail.pipeline import (
    extract_journey,
    extract_lahti_helsinki_segment,
    nearest_weather,
    parse_weather_xml,
    reliability_metrics,
)


STATIONS = {
    "HKI": {"stationName": "Helsinki asema", "passengerTraffic": True, "countryCode": "FI"},
    "LH": {"stationName": "Lahti", "passengerTraffic": True, "countryCode": "FI"},
    "ILR": {"stationName": "Ilmala ratapiha", "passengerTraffic": False, "countryCode": "FI"},
}


def row(code, event_type, scheduled, actual, delay, *, cancelled=False):
    return {
        "stationShortCode": code,
        "type": event_type,
        "trainStopping": True,
        "commercialStop": True,
        "cancelled": cancelled,
        "scheduledTime": scheduled,
        "actualTime": actual,
        "differenceInMinutes": delay,
    }


class RailPipelineTest(unittest.TestCase):
    def test_extracts_journey_and_local_calendar_without_imputation(self):
        train = {
            "departureDate": "2026-01-15",
            "trainNumber": 1,
            "trainType": "IC",
            "trainCategory": "Long-distance",
            "cancelled": False,
            "timeTableRows": [
                row("HKI", "DEPARTURE", "2026-01-15T21:30:00Z", "2026-01-15T21:33:00Z", 3),
                row("LH", "ARRIVAL", "2026-01-15T22:20:00Z", None, None),
            ],
        }
        journey, arrivals, quality = extract_journey(train, STATIONS)
        self.assertIsNotNone(journey)
        self.assertEqual(journey.route_label, "Helsinki ↔ Lahti")
        self.assertEqual(journey.departure_date, "2026-01-15")
        self.assertEqual(journey.hour, 23)
        self.assertIsNone(journey.final_delay)
        self.assertEqual(quality["trains_missing_final_actual"], 1)
        self.assertIsNone(arrivals[0].delay)

    def test_extracts_direct_lahti_helsinki_segment_from_a_longer_train(self):
        train = {
            "departureDate": "2026-02-01",
            "trainNumber": 72,
            "trainType": "IC",
            "trainCategory": "Long-distance",
            "cancelled": False,
            "timeTableRows": [
                row("LH", "ARRIVAL", "2026-02-01T08:00:00Z", "2026-02-01T08:02:00Z", 2),
                row("LH", "DEPARTURE", "2026-02-01T08:03:00Z", "2026-02-01T08:05:00Z", 2),
                row("HKI", "ARRIVAL", "2026-02-01T09:00:00Z", "2026-02-01T09:08:00Z", 8),
            ],
        }
        segment = extract_lahti_helsinki_segment(train)
        self.assertEqual(segment.direction, "Lahti → Helsinki")
        self.assertEqual(segment.arrival_delay, 8)
        self.assertEqual(segment.departure_delay, 2)

    def test_service_location_is_not_used_as_a_passenger_destination(self):
        train = {
            "departureDate": "2026-02-01",
            "trainNumber": 99,
            "trainType": "HL",
            "trainCategory": "Commuter",
            "cancelled": False,
            "timeTableRows": [
                row("LH", "DEPARTURE", "2026-02-01T08:00:00Z", "2026-02-01T08:00:00Z", 0),
                row("HKI", "ARRIVAL", "2026-02-01T09:00:00Z", "2026-02-01T09:02:00Z", 2),
                row("ILR", "ARRIVAL", "2026-02-01T09:10:00Z", "2026-02-01T09:30:00Z", 20),
            ],
        }
        journey, arrivals, _ = extract_journey(train, STATIONS)
        self.assertEqual(journey.destination_code, "HKI")
        self.assertEqual(journey.final_delay, 2)
        self.assertEqual([arrival.station_code for arrival in arrivals], ["HKI"])

    def test_cancelled_train_is_not_counted_as_a_completed_arrival(self):
        metrics = reliability_metrics([0, 5, 6, 31], scheduled=5, cancelled=1)
        self.assertEqual(metrics["completed"], 4)
        self.assertEqual(metrics["on_time"]["5"]["count"], 2)
        self.assertEqual(metrics["on_time"]["5"]["rate"], 0.5)
        self.assertEqual(metrics["cancelled_rate"], 0.2)

    def test_weather_parser_and_nearest_match_have_a_strict_tolerance(self):
        xml = b'''<?xml version="1.0"?><wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:BsWfs="http://xml.fmi.fi/schema/wfs/2.0"><wfs:member><BsWfs:BsWfsElement><BsWfs:Location><gml:Point><gml:pos>60.1 24.9</gml:pos></gml:Point></BsWfs:Location><BsWfs:Time>2026-01-01T10:00:00Z</BsWfs:Time><BsWfs:ParameterName>t2m</BsWfs:ParameterName><BsWfs:ParameterValue>-4.2</BsWfs:ParameterValue></BsWfs:BsWfsElement></wfs:member></wfs:FeatureCollection>'''
        observations = parse_weather_xml(xml)
        timestamps = [datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00")) for item in observations]
        self.assertEqual(observations[0]["t2m"], -4.2)
        self.assertIsNotNone(nearest_weather(timestamps, observations, datetime(2026, 1, 1, 10, 40, tzinfo=timezone.utc)))
        self.assertIsNone(nearest_weather(timestamps, observations, datetime(2026, 1, 1, 10, 46, tzinfo=timezone.utc)))


if __name__ == "__main__":
    unittest.main()
