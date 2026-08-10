from __future__ import annotations

import argparse
import bisect
import csv
import gzip
import json
import math
import statistics
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo


DIGITRAFFIC_BASE = "https://rata.digitraffic.fi/api/v1"
FMI_WFS = "https://opendata.fmi.fi/wfs"
DIGITRAFFIC_USER = "AppliedAILab/RailReliabilityMonitor 1.0"
PASSENGER_CATEGORIES = {"Long-distance", "Commuter"}
THRESHOLDS = (5, 10, 15, 30)
HELSINKI = "HKI"
LAHTI = "LH"
LOCAL_TZ = ZoneInfo("Europe/Helsinki")
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
WEATHER_PLACES = {HELSINKI: "Helsinki", LAHTI: "Lahti"}
WEATHER_PARAMETERS = ("t2m", "r_1h", "ws_10min", "vis")


@dataclass(frozen=True)
class Journey:
    key: str
    departure_date: str
    month: str
    weekday: int
    hour: int
    train_type: str
    category: str
    commuter_line: str
    route_key: str
    route_label: str
    origin_code: str
    destination_code: str
    scheduled_departure: str
    cancelled: bool
    partial_cancelled: bool
    final_arrival_cancelled: bool
    final_delay: int | None
    departure_delay: int | None


@dataclass(frozen=True)
class StationArrival:
    month: str
    station_code: str
    station_name: str
    cancelled: bool
    delay: int | None


@dataclass(frozen=True)
class SegmentJourney:
    key: str
    direction: str
    month: str
    weekday: int
    hour: int
    train_type: str
    commuter_line: str
    scheduled_departure: str
    cancelled: bool
    arrival_delay: int | None
    departure_delay: int | None


def iter_dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def round_delay_minutes(scheduled: str | None, actual: str | None) -> int | None:
    scheduled_dt = parse_iso(scheduled)
    actual_dt = parse_iso(actual)
    if not scheduled_dt or not actual_dt:
        return None
    return round((actual_dt - scheduled_dt).total_seconds() / 60)


def row_delay(row: dict[str, Any]) -> int | None:
    value = row.get("differenceInMinutes")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return round_delay_minutes(row.get("scheduledTime"), row.get("actualTime"))


def is_commercial_stop(row: dict[str, Any]) -> bool:
    return bool(row.get("commercialStop") and row.get("trainStopping"))


def station_label(station: dict[str, Any] | None, code: str) -> str:
    if not station:
        return code
    name = str(station.get("stationName") or code)
    return name.removesuffix(" asema")


def canonical_route(
    origin_code: str,
    destination_code: str,
    stations: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    if origin_code == destination_code:
        name = station_label(stations.get(origin_code), origin_code)
        return f"{origin_code}--{destination_code}", f"{name} ring service"
    codes = sorted((origin_code, destination_code))
    names = [station_label(stations.get(code), code) for code in codes]
    return "--".join(codes), " ↔ ".join(names)


def extract_journey(
    train: dict[str, Any], stations: dict[str, dict[str, Any]]
) -> tuple[Journey | None, list[StationArrival], dict[str, int]]:
    quality = defaultdict(int)
    all_commercial_rows = [
        row for row in train.get("timeTableRows", []) if is_commercial_stop(row)
    ]
    for row in all_commercial_rows:
        if str(row.get("stationShortCode") or "") not in stations:
            quality["unknown_station_rows"] += 1
    rows = [
        row
        for row in all_commercial_rows
        if (
            (station := stations.get(str(row.get("stationShortCode") or "")))
            and station.get("passengerTraffic") is True
            and station.get("countryCode") == "FI"
        )
    ]
    arrivals = [row for row in rows if row.get("type") == "ARRIVAL"]
    departures = [row for row in rows if row.get("type") == "DEPARTURE"]
    if not arrivals or not departures:
        quality["trains_without_route_endpoints"] += 1
        return None, [], dict(quality)

    first_departure = departures[0]
    final_arrival = arrivals[-1]
    origin_code = str(first_departure.get("stationShortCode") or "")
    destination_code = str(final_arrival.get("stationShortCode") or "")
    if not origin_code or not destination_code:
        quality["trains_without_route_endpoints"] += 1
        return None, [], dict(quality)

    scheduled_departure = parse_iso(first_departure.get("scheduledTime"))
    if not scheduled_departure:
        quality["trains_missing_scheduled_departure"] += 1
        return None, [], dict(quality)
    local_departure = scheduled_departure.astimezone(LOCAL_TZ)
    route_key, route_label = canonical_route(origin_code, destination_code, stations)
    cancelled = bool(train.get("cancelled"))
    partial_cancelled = (not cancelled) and any(bool(row.get("cancelled")) for row in rows)
    final_arrival_cancelled = bool(final_arrival.get("cancelled"))
    final_delay = None if cancelled or final_arrival_cancelled else row_delay(final_arrival)
    departure_delay = None if cancelled or first_departure.get("cancelled") else row_delay(first_departure)

    if final_delay is None and not cancelled and not final_arrival.get("cancelled"):
        quality["trains_missing_final_actual"] += 1
    if final_delay is not None and abs(final_delay) > 720:
        quality["extreme_final_delays_over_12h"] += 1
    for row in rows:
        calculated = round_delay_minutes(row.get("scheduledTime"), row.get("actualTime"))
        reported = row.get("differenceInMinutes")
        if calculated is not None and isinstance(reported, (int, float)) and abs(calculated - int(reported)) > 1:
            quality["reported_delay_mismatches_over_1m"] += 1

    station_arrivals = []
    for row in arrivals:
        code = str(row.get("stationShortCode") or "")
        station_arrivals.append(
            StationArrival(
                month=local_departure.strftime("%Y-%m"),
                station_code=code,
                station_name=station_label(stations.get(code), code),
                cancelled=bool(cancelled or row.get("cancelled")),
                delay=None if cancelled or row.get("cancelled") else row_delay(row),
            )
        )

    journey = Journey(
        key=f"{train.get('departureDate')}:{train.get('trainNumber')}",
        departure_date=str(train.get("departureDate")),
        month=local_departure.strftime("%Y-%m"),
        weekday=local_departure.weekday(),
        hour=local_departure.hour,
        train_type=str(train.get("trainType") or "Unknown"),
        category=str(train.get("trainCategory") or "Unknown"),
        commuter_line=str(train.get("commuterLineID") or ""),
        route_key=route_key,
        route_label=route_label,
        origin_code=origin_code,
        destination_code=destination_code,
        scheduled_departure=scheduled_departure.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        cancelled=cancelled,
        partial_cancelled=partial_cancelled,
        final_arrival_cancelled=final_arrival_cancelled,
        final_delay=final_delay,
        departure_delay=departure_delay,
    )
    return journey, station_arrivals, dict(quality)


def _find_event(rows: Sequence[dict[str, Any]], code: str, event_type: str) -> tuple[int, dict[str, Any]] | None:
    for index, row in enumerate(rows):
        if (
            row.get("stationShortCode") == code
            and row.get("type") == event_type
            and is_commercial_stop(row)
        ):
            return index, row
    return None


def extract_lahti_helsinki_segment(train: dict[str, Any]) -> SegmentJourney | None:
    rows = list(train.get("timeTableRows", []))
    hki_departure = _find_event(rows, HELSINKI, "DEPARTURE")
    hki_arrival = _find_event(rows, HELSINKI, "ARRIVAL")
    lh_departure = _find_event(rows, LAHTI, "DEPARTURE")
    lh_arrival = _find_event(rows, LAHTI, "ARRIVAL")
    segment: tuple[str, tuple[int, dict[str, Any]], tuple[int, dict[str, Any]]] | None = None
    if hki_departure and lh_arrival and hki_departure[0] < lh_arrival[0]:
        segment = ("Helsinki → Lahti", hki_departure, lh_arrival)
    elif lh_departure and hki_arrival and lh_departure[0] < hki_arrival[0]:
        segment = ("Lahti → Helsinki", lh_departure, hki_arrival)
    if not segment:
        return None

    direction, (_, departure_row), (_, arrival_row) = segment
    scheduled = parse_iso(departure_row.get("scheduledTime"))
    if not scheduled:
        return None
    local_departure = scheduled.astimezone(LOCAL_TZ)
    cancelled = bool(train.get("cancelled") or departure_row.get("cancelled") or arrival_row.get("cancelled"))
    return SegmentJourney(
        key=f"{train.get('departureDate')}:{train.get('trainNumber')}:{direction}",
        direction=direction,
        month=local_departure.strftime("%Y-%m"),
        weekday=local_departure.weekday(),
        hour=local_departure.hour,
        train_type=str(train.get("trainType") or "Unknown"),
        commuter_line=str(train.get("commuterLineID") or ""),
        scheduled_departure=scheduled.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        cancelled=cancelled,
        arrival_delay=None if cancelled else row_delay(arrival_row),
        departure_delay=None if cancelled else row_delay(departure_row),
    )


def percentile(values: Sequence[int], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def safe_rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def reliability_metrics(delays: Sequence[int], scheduled: int, cancelled: int) -> dict[str, Any]:
    completed = len(delays)
    return {
        "scheduled": scheduled,
        "completed": completed,
        "cancelled": cancelled,
        "cancelled_rate": safe_rate(cancelled, scheduled),
        "completion_rate": safe_rate(completed, scheduled),
        "on_time": {
            str(threshold): {
                "count": sum(delay <= threshold for delay in delays),
                "rate": safe_rate(sum(delay <= threshold for delay in delays), completed),
            }
            for threshold in THRESHOLDS
        },
        "median_delay_minutes": round(statistics.median(delays), 1) if delays else None,
        "p90_delay_minutes": round(percentile(delays, 0.9) or 0, 1) if delays else None,
        "p95_delay_minutes": round(percentile(delays, 0.95) or 0, 1) if delays else None,
        "mean_delay_minutes": round(statistics.fmean(delays), 2) if delays else None,
    }


def group_journeys(journeys: Sequence[Journey], key_fn) -> list[tuple[Any, dict[str, Any]]]:
    groups: dict[Any, list[Journey]] = defaultdict(list)
    for journey in journeys:
        groups[key_fn(journey)].append(journey)
    result = []
    for key, group in groups.items():
        delays = [item.final_delay for item in group if item.final_delay is not None]
        result.append((key, reliability_metrics(delays, len(group), sum(item.cancelled for item in group))))
    return result


def summarise_routes(journeys: Sequence[Journey]) -> list[dict[str, Any]]:
    groups: dict[str, list[Journey]] = defaultdict(list)
    for journey in journeys:
        groups[journey.route_key].append(journey)
    rows = []
    for route_key, group in groups.items():
        if len(group) < 200:
            continue
        delays = [item.final_delay for item in group if item.final_delay is not None]
        metrics = reliability_metrics(delays, len(group), sum(item.cancelled for item in group))
        months: dict[str, list[int]] = defaultdict(list)
        for item in group:
            if item.final_delay is not None:
                months[item.month].append(item.final_delay)
        monthly_rates = [safe_rate(sum(value <= 5 for value in values), len(values)) for values in months.values() if values]
        rows.append(
            {
                "route_key": route_key,
                "route": group[0].route_label,
                **metrics,
                "months_observed": len(monthly_rates),
                "monthly_on_time_5_stddev": round(statistics.pstdev(monthly_rates), 4) if len(monthly_rates) > 1 else 0,
                "unreliable_month_share": safe_rate(sum(rate < 0.9 for rate in monthly_rates), len(monthly_rates)),
            }
        )
    return sorted(rows, key=lambda row: (-row["scheduled"], row["route"]))


def summarise_stations(arrivals: Sequence[StationArrival]) -> list[dict[str, Any]]:
    groups: dict[str, list[StationArrival]] = defaultdict(list)
    for arrival in arrivals:
        groups[arrival.station_code].append(arrival)
    rows = []
    for code, group in groups.items():
        if len(group) < 500:
            continue
        delays = [item.delay for item in group if item.delay is not None]
        metrics = reliability_metrics(delays, len(group), sum(item.cancelled for item in group))
        rows.append({"station_code": code, "station": group[0].station_name, **metrics})
    return sorted(rows, key=lambda row: (-row["scheduled"], row["station"]))


def summarise_segment(segments: Sequence[SegmentJourney]) -> dict[str, Any]:
    def metrics_for(group: Sequence[SegmentJourney]) -> dict[str, Any]:
        delays = [item.arrival_delay for item in group if item.arrival_delay is not None]
        accumulations = [
            item.arrival_delay - item.departure_delay
            for item in group
            if item.arrival_delay is not None and item.departure_delay is not None
        ]
        return {
            **reliability_metrics(delays, len(group), sum(item.cancelled for item in group)),
            "median_delay_change_minutes": round(statistics.median(accumulations), 1) if accumulations else None,
            "share_gaining_over_5_minutes": safe_rate(sum(value > 5 for value in accumulations), len(accumulations)),
        }

    directions = []
    for direction in ("Lahti → Helsinki", "Helsinki → Lahti"):
        group = [item for item in segments if item.direction == direction]
        directions.append({"direction": direction, **metrics_for(group)})
    monthly = []
    for month in sorted({item.month for item in segments}):
        group = [item for item in segments if item.month == month]
        monthly.append({"month": month, **metrics_for(group)})
    by_hour = []
    for start, end in ((0, 5), (6, 9), (10, 15), (16, 19), (20, 23)):
        group = [item for item in segments if start <= item.hour <= end]
        by_hour.append({"period": f"{start:02d}:00–{end:02d}:59", **metrics_for(group)})
    return {"overall": metrics_for(segments), "directions": directions, "monthly": monthly, "time_of_day": by_hour}


def parse_weather_xml(content: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(content)
    namespace = {"b": "http://xml.fmi.fi/schema/wfs/2.0", "g": "http://www.opengis.net/gml/3.2"}
    observations: dict[tuple[str, float, float], dict[str, Any]] = {}
    for element in root.findall(".//b:BsWfsElement", namespace):
        timestamp = element.findtext("b:Time", default="", namespaces=namespace)
        parameter = element.findtext("b:ParameterName", default="", namespaces=namespace)
        value_text = element.findtext("b:ParameterValue", default="", namespaces=namespace)
        position_text = element.findtext(".//g:pos", default="", namespaces=namespace)
        if not timestamp or parameter not in WEATHER_PARAMETERS or not value_text or value_text == "NaN":
            continue
        try:
            latitude, longitude = (float(value) for value in position_text.split())
            value = float(value_text)
        except (ValueError, TypeError):
            continue
        key = (timestamp, latitude, longitude)
        observation = observations.setdefault(
            key,
            {"timestamp": timestamp, "latitude": latitude, "longitude": longitude},
        )
        observation[parameter] = value
    return sorted(observations.values(), key=lambda item: item["timestamp"])


def nearest_weather(
    timestamps: Sequence[datetime], observations: Sequence[dict[str, Any]], target: datetime
) -> dict[str, Any] | None:
    if not timestamps:
        return None
    position = bisect.bisect_left(timestamps, target)
    candidates = [index for index in (position - 1, position) if 0 <= index < len(timestamps)]
    if not candidates:
        return None
    index = min(candidates, key=lambda candidate: abs((timestamps[candidate] - target).total_seconds()))
    if abs((timestamps[index] - target).total_seconds()) > 45 * 60:
        return None
    return observations[index]


def attach_weather(
    segments: Sequence[SegmentJourney], weather: dict[str, list[dict[str, Any]]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indexed = {
        code: ([parse_iso(item["timestamp"]) for item in items], items)
        for code, items in weather.items()
    }
    joined = []
    for segment in segments:
        origin = LAHTI if segment.direction.startswith("Lahti") else HELSINKI
        target = parse_iso(segment.scheduled_departure)
        if target is None or origin not in indexed:
            continue
        timestamps, observations = indexed[origin]
        matched = nearest_weather(timestamps, observations, target)
        if not matched:
            continue
        joined.append({"segment": segment, "weather": matched, "origin": origin})

    conditions = [
        ("All matched journeys", lambda weather: True),
        ("Freezing (temperature ≤ 0°C)", lambda weather: weather.get("t2m", 999) <= 0),
        ("Precipitation (≥ 0.2 mm/h)", lambda weather: weather.get("r_1h", 0) >= 0.2),
        ("Low visibility (< 5 km)", lambda weather: weather.get("vis", 999999) < 5000),
        ("Strong wind (≥ 10 m/s)", lambda weather: weather.get("ws_10min", 0) >= 10),
        (
            "No selected adverse condition",
            lambda weather: weather.get("t2m", 999) > 0
            and weather.get("r_1h", 0) < 0.2
            and weather.get("vis", 999999) >= 5000
            and weather.get("ws_10min", 0) < 10,
        ),
    ]
    summary = []
    for label, predicate in conditions:
        group = [item for item in joined if predicate(item["weather"])]
        delays = [item["segment"].arrival_delay for item in group if item["segment"].arrival_delay is not None]
        summary.append({"condition": label, **reliability_metrics(delays, len(group), sum(item["segment"].cancelled for item in group))})

    station_metadata = {}
    for code, items in weather.items():
        if items:
            station_metadata[code] = {
                "requested_place": WEATHER_PLACES[code],
                "latitude": items[0]["latitude"],
                "longitude": items[0]["longitude"],
                "observations": len(items),
            }
    return joined, {"matched_journeys": len(joined), "conditions": summary, "observation_locations": station_metadata}


def build_summary(
    trains_by_day: Iterable[list[dict[str, Any]]],
    stations: dict[str, dict[str, Any]],
    coverage_start: date,
    coverage_end: date,
    retrieved_at: str,
    weather: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, list[dict[str, Any]]]]:
    journeys: list[Journey] = []
    arrivals: list[StationArrival] = []
    segments: list[SegmentJourney] = []
    quality = defaultdict(int)
    seen: set[str] = set()
    source_train_records = 0
    passenger_train_records = 0

    for trains in trains_by_day:
        source_train_records += len(trains)
        for train in trains:
            if train.get("trainCategory") not in PASSENGER_CATEGORIES:
                continue
            passenger_train_records += 1
            key = f"{train.get('departureDate')}:{train.get('trainNumber')}"
            if key in seen:
                quality["duplicate_train_keys"] += 1
                continue
            seen.add(key)
            journey, station_arrivals, train_quality = extract_journey(train, stations)
            for name, value in train_quality.items():
                quality[name] += value
            if journey:
                journeys.append(journey)
                arrivals.extend(station_arrivals)
            segment = extract_lahti_helsinki_segment(train)
            if segment:
                segments.append(segment)

    delays = [journey.final_delay for journey in journeys if journey.final_delay is not None]
    overall = reliability_metrics(delays, len(journeys), sum(journey.cancelled for journey in journeys))
    overall["partial_cancelled"] = sum(journey.partial_cancelled for journey in journeys)
    overall["partial_cancelled_rate"] = safe_rate(overall["partial_cancelled"], len(journeys))
    overall["missing_final_actual"] = sum(
        journey.final_delay is None
        and not journey.cancelled
        and not journey.final_arrival_cancelled
        for journey in journeys
    )
    overall["missing_final_actual_rate"] = safe_rate(overall["missing_final_actual"], len(journeys))
    overall["delay_distribution"] = [
        {"label": "Early / no delay", "count": sum(delay <= 0 for delay in delays)},
        {"label": "1–5 min", "count": sum(1 <= delay <= 5 for delay in delays)},
        {"label": "6–10 min", "count": sum(6 <= delay <= 10 for delay in delays)},
        {"label": "11–15 min", "count": sum(11 <= delay <= 15 for delay in delays)},
        {"label": "16–30 min", "count": sum(16 <= delay <= 30 for delay in delays)},
        {"label": "31+ min", "count": sum(delay >= 31 for delay in delays)},
    ]

    monthly = [
        {"month": key, **metrics}
        for key, metrics in sorted(group_journeys(journeys, lambda item: item.month))
    ]
    weekday = [
        {"weekday": WEEKDAY_NAMES[key], "weekday_number": key + 1, **metrics}
        for key, metrics in sorted(group_journeys(journeys, lambda item: item.weekday))
    ]
    hour = [
        {"hour": key, **metrics}
        for key, metrics in sorted(group_journeys(journeys, lambda item: item.hour))
    ]
    train_types = [
        {"train_type": key, **metrics}
        for key, metrics in sorted(
            group_journeys(journeys, lambda item: item.train_type),
            key=lambda item: -item[1]["scheduled"],
        )
        if metrics["scheduled"] >= 100
    ]
    categories = [
        {"category": key, **metrics}
        for key, metrics in sorted(group_journeys(journeys, lambda item: item.category))
    ]
    routes = summarise_routes(journeys)
    station_summary = summarise_stations(arrivals)
    segment_summary = summarise_segment(segments)
    joined_weather: list[dict[str, Any]] = []
    if weather:
        joined_weather, weather_summary = attach_weather(segments, weather)
    else:
        weather_summary = {
            "status": "not_run",
            "explanation": "Run the pipeline without --skip-weather to reproduce the scoped FMI association study.",
        }
    segment_summary["weather"] = weather_summary

    quality_report = {
        "retrieved_at": retrieved_at,
        "coverage": {"start": coverage_start.isoformat(), "end": coverage_end.isoformat()},
        "source_train_records": source_train_records,
        "passenger_train_records": passenger_train_records,
        "modelled_journeys": len(journeys),
        "commercial_station_arrivals": len(arrivals),
        "lahti_helsinki_direct_services": len(segments),
        "checks": dict(sorted(quality.items())),
        "definitions": {
            "passenger_scope": "trainCategory is Long-distance or Commuter",
            "journey_grain": "one unique departureDate + trainNumber, using first commercial departure and last commercial arrival at Finnish passengerTraffic=true stations",
            "on_time": "final actual arrival is no more than the selected number of whole minutes after schedule; early arrivals count as on time",
            "cancelled": "Digitraffic whole-train cancelled flag; cancelled commercial rows are also counted separately as partial cancellations",
            "missing_actuals": "not imputed and excluded from punctuality denominators",
            "time_zone": "Digitraffic UTC converted with Europe/Helsinki IANA rules for local month, weekday and hour",
        },
    }
    summary = {
        "meta": {
            "title": "Finland Rail Reliability Monitor",
            "coverage_start": coverage_start.isoformat(),
            "coverage_end": coverage_end.isoformat(),
            "retrieved_at": retrieved_at,
            "coverage_days": (coverage_end - coverage_start).days + 1,
            "default_threshold_minutes": 5,
            "available_thresholds_minutes": list(THRESHOLDS),
            "source": "Fintraffic / Digitraffic railway API",
            "source_url": "https://www.digitraffic.fi/en/railway-traffic/",
            "source_license": "CC BY 4.0",
            "source_license_url": "https://creativecommons.org/licenses/by/4.0/",
            "weather_source": "Finnish Meteorological Institute open data",
            "weather_source_url": "https://en.ilmatieteenlaitos.fi/open-data",
            "weather_license": "CC BY 4.0",
        },
        "overall": overall,
        "monthly": monthly,
        "weekday": weekday,
        "hour": hour,
        "train_types": train_types,
        "categories": categories,
        "routes": routes,
        "stations": station_summary,
        "lahti_helsinki": segment_summary,
        "quality": quality_report,
    }
    bi_rows = build_bi_rows(journeys, arrivals, routes, joined_weather)
    return summary, quality_report, bi_rows


def build_bi_rows(
    journeys: Sequence[Journey],
    arrivals: Sequence[StationArrival],
    routes: Sequence[dict[str, Any]],
    joined_weather: Sequence[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    route_lookup = {row["route_key"]: row["route"] for row in routes}
    fact_journeys = []
    for item in journeys:
        fact_journeys.append(
            {
                "journey_key": item.key,
                "departure_date": item.departure_date,
                "month": item.month,
                "weekday_number": item.weekday + 1,
                "departure_hour": item.hour,
                "train_type": item.train_type,
                "train_category": item.category,
                "commuter_line": item.commuter_line,
                "route_key": item.route_key,
                "route": route_lookup.get(item.route_key, item.route_label),
                "origin_code": item.origin_code,
                "destination_code": item.destination_code,
                "cancelled": int(item.cancelled),
                "partial_cancelled": int(item.partial_cancelled),
                "final_arrival_cancelled": int(item.final_arrival_cancelled),
                "final_delay_minutes": item.final_delay,
                "departure_delay_minutes": item.departure_delay,
            }
        )
    station_month: dict[tuple[str, str, str], list[StationArrival]] = defaultdict(list)
    for item in arrivals:
        station_month[(item.month, item.station_code, item.station_name)].append(item)
    station_rows = []
    for (month, code, name), group in sorted(station_month.items()):
        delays = [item.delay for item in group if item.delay is not None]
        metrics = reliability_metrics(delays, len(group), sum(item.cancelled for item in group))
        station_rows.append(
            {
                "month": month,
                "station_code": code,
                "station": name,
                "scheduled_arrivals": metrics["scheduled"],
                "completed_arrivals": metrics["completed"],
                "cancelled_arrivals": metrics["cancelled"],
                "on_time_5_arrivals": metrics["on_time"]["5"]["count"],
                "median_delay_minutes": metrics["median_delay_minutes"],
                "p90_delay_minutes": metrics["p90_delay_minutes"],
            }
        )
    weather_rows = []
    for item in joined_weather:
        segment: SegmentJourney = item["segment"]
        observation = item["weather"]
        weather_rows.append(
            {
                "journey_key": segment.key,
                "direction": segment.direction,
                "scheduled_departure_utc": segment.scheduled_departure,
                "weather_origin_code": item["origin"],
                "temperature_c": observation.get("t2m"),
                "precipitation_mm_h": observation.get("r_1h"),
                "wind_speed_ms": observation.get("ws_10min"),
                "visibility_m": observation.get("vis"),
                "arrival_delay_minutes": segment.arrival_delay,
                "cancelled": int(segment.cancelled),
            }
        )
    return {
        "fact_train_journey": fact_journeys,
        "agg_station_month": station_rows,
        "fact_lahti_helsinki_weather": weather_rows,
    }


class SourceClient:
    def __init__(self, cache_dir: Path, refresh: bool = False):
        self.cache_dir = cache_dir
        self.refresh = refresh
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _request(self, url: str, *, accept: str = "application/json") -> bytes:
        request = urllib.request.Request(
            url,
            headers={
                "Digitraffic-User": DIGITRAFFIC_USER,
                "Accept": accept,
                "Accept-Encoding": "gzip",
                "Connection": "close",
            },
        )
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    content = response.read()
                    if response.headers.get("Content-Encoding") == "gzip":
                        content = gzip.decompress(content)
                    return content
            except Exception as error:  # network retries are intentionally broad
                last_error = error
                time.sleep(2**attempt)
        raise RuntimeError(f"Source request failed after retries: {url}") from last_error

    def _cached_json(self, relative_path: Path, url: str) -> Any:
        path = self.cache_dir / relative_path
        if path.exists() and not self.refresh:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                return json.load(handle)
        content = self._request(url)
        parsed = json.loads(content)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with gzip.open(temporary, "wt", encoding="utf-8") as handle:
            json.dump(parsed, handle, ensure_ascii=False, separators=(",", ":"))
        temporary.replace(path)
        return parsed

    def stations(self) -> list[dict[str, Any]]:
        return self._cached_json(Path("metadata/stations.json.gz"), f"{DIGITRAFFIC_BASE}/metadata/stations")

    def cache_trains(self, day: date) -> Path:
        path = self.cache_dir / f"trains/{day.isoformat()}.json.gz"
        if path.exists() and not self.refresh:
            return path
        content = self._request(f"{DIGITRAFFIC_BASE}/trains/{day.isoformat()}")
        parsed = json.loads(content)
        if not isinstance(parsed, list):
            raise ValueError(f"Digitraffic {day.isoformat()} response is not a train array")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with gzip.open(temporary, "wb") as handle:
            handle.write(content)
        temporary.replace(path)
        return path

    def read_trains(self, day: date) -> list[dict[str, Any]]:
        path = self.cache_dir / f"trains/{day.isoformat()}.json.gz"
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            trains = json.load(handle)
        if not isinstance(trains, list):
            raise ValueError(f"Cached Digitraffic {day.isoformat()} response is not a train array")
        return trains

    def weather(self, code: str, start: date, end: date) -> list[dict[str, Any]]:
        place = WEATHER_PLACES[code]
        chunks = []
        current = start
        while current <= end:
            chunk_end = min(current + timedelta(days=6), end)
            relative_path = Path(f"weather/{code}/{current.isoformat()}_{chunk_end.isoformat()}.xml.gz")
            path = self.cache_dir / relative_path
            if path.exists() and not self.refresh:
                with gzip.open(path, "rb") as handle:
                    content = handle.read()
            else:
                params = {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "getFeature",
                    "storedquery_id": "fmi::observations::weather::simple",
                    "place": place,
                    "starttime": f"{current.isoformat()}T00:00:00Z",
                    "endtime": f"{chunk_end.isoformat()}T23:59:59Z",
                    "timestep": "60",
                    "parameters": ",".join(WEATHER_PARAMETERS),
                }
                content = self._request(f"{FMI_WFS}?{urllib.parse.urlencode(params)}", accept="text/xml")
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(path.suffix + ".tmp")
                with gzip.open(temporary, "wb") as handle:
                    handle.write(content)
                temporary.replace(path)
            chunks.extend(parse_weather_xml(content))
            current = chunk_end + timedelta(days=1)
        unique = {(item["timestamp"], item["latitude"], item["longitude"]): item for item in chunks}
        return sorted(unique.values(), key=lambda item: item["timestamp"])


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def run_pipeline(args: argparse.Namespace) -> None:
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start > end:
        raise ValueError("--start must be on or before --end")
    client = SourceClient(Path(args.cache_dir), refresh=args.refresh)
    station_rows = client.stations()
    stations = {str(row["stationShortCode"]): row for row in station_rows}
    days = list(iter_dates(start, end))
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_days = {executor.submit(client.cache_trains, day): day for day in days}
        for completed, future in enumerate(as_completed(future_days), start=1):
            future.result()
            if completed == len(days) or completed % 25 == 0:
                print(f"Digitraffic: {completed}/{len(days)} days cached", flush=True)

    weather = None
    if not args.skip_weather:
        weather = {}
        for code in (HELSINKI, LAHTI):
            weather[code] = client.weather(code, start, end)
            print(f"FMI: {code} {len(weather[code])} hourly observations cached", flush=True)

    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    summary, quality, bi_rows = build_summary(
        (client.read_trains(day) for day in days), stations, start, end, retrieved_at, weather
    )
    write_json(Path(args.output), summary)
    write_json(Path(args.quality_output), quality)
    bi_dir = Path(args.bi_output_dir)
    for name, rows in bi_rows.items():
        write_csv(bi_dir / f"{name}.csv", rows)
    print(
        f"Wrote {args.output}: {summary['overall']['scheduled']:,} passenger train journeys, "
        f"{summary['lahti_helsinki']['overall']['scheduled']:,} Lahti–Helsinki services",
        flush=True,
    )


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="Build the Finland Rail Reliability Monitor analytical snapshot")
    cli.add_argument("--start", default="2025-08-01")
    cli.add_argument("--end", default="2026-07-31")
    cli.add_argument("--cache-dir", default="data/rail")
    cli.add_argument("--output", default="artifacts/rail-summary.json")
    cli.add_argument("--quality-output", default="artifacts/rail-quality.json")
    cli.add_argument("--bi-output-dir", default="data/rail/curated")
    cli.add_argument("--workers", type=int, default=4)
    cli.add_argument("--refresh", action="store_true")
    cli.add_argument("--skip-weather", action="store_true")
    return cli


if __name__ == "__main__":
    run_pipeline(parser().parse_args())
