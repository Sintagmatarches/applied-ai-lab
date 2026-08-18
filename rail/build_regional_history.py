"""Create the committed regional historical rail-monitor snapshot."""

from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PASSENGER_CATEGORIES = {"Long-distance", "Commuter"}
DELAY_THRESHOLDS = (5, 10, 15, 30)


def empty_threshold_counts() -> dict[str, int]:
    return {str(threshold): 0 for threshold in DELAY_THRESHOLDS}


def fresh_aggregate() -> dict[str, Any]:
    return {
        "observed": 0,
        "measured": 0,
        "delayedByThreshold": empty_threshold_counts(),
        "severe": 0,
        "cancelled": 0,
        "delaySum": 0,
        "stations": defaultdict(fresh_problem),
        "routes": defaultdict(fresh_problem),
    }


def fresh_problem() -> dict[str, Any]:
    return {
        "label": "",
        "observations": 0,
        "measured": 0,
        "delayedByThreshold": empty_threshold_counts(),
        "severe": 0,
        "cancellations": 0,
        "delaySum": 0,
    }


def is_passenger_row(row: dict[str, Any], stations: dict[str, Any]) -> bool:
    station = stations.get(row.get("stationShortCode"), {})
    return bool(
        station.get("passengerTraffic")
        and station.get("regionCode")
        and row.get("commercialStop")
        and row.get("trainStopping", True)
    )


def actual_delay(row: dict[str, Any]) -> int | None:
    if not row.get("actualTime"):
        return None
    value = row.get("differenceInMinutes")
    return int(value) if isinstance(value, (int, float)) else None


def clean_name(value: str) -> str:
    return value[:-6] if value.lower().endswith(" asema") else value


def add_problem(problem: dict[str, Any], label: str, delay: int | None, cancelled: bool = False) -> None:
    problem["label"] = label
    problem["observations"] += 1
    problem["cancellations"] += cancelled
    if delay is not None:
        problem["measured"] += 1
        problem["delaySum"] += delay
        for threshold in DELAY_THRESHOLDS:
            problem["delayedByThreshold"][str(threshold)] += delay > threshold
        problem["severe"] += delay > 15


def finish_problem(key: str, item: dict[str, Any], threshold: int) -> dict[str, Any]:
    return {
        "key": key,
        "label": item["label"],
        "observations": item["observations"],
        "delayed": item["delayedByThreshold"][str(threshold)],
        "severe": item["severe"],
        "cancellations": item["cancellations"],
        "averageDelayMinutes": item["delaySum"] / item["measured"] if item["measured"] else None,
    }


def finish_aggregate(aggregate: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    severe_share = aggregate["severe"] / aggregate["measured"] if aggregate["measured"] else 0
    average = aggregate["delaySum"] / aggregate["measured"] if aggregate["measured"] else None
    cancelled_share = aggregate["cancelled"] / aggregate["observed"] if aggregate["observed"] else None
    delayed_shares = {
        str(threshold): aggregate["delayedByThreshold"][str(threshold)] / aggregate["measured"]
        if aggregate["measured"] else None
        for threshold in DELAY_THRESHOLDS
    }

    def calculate_score(threshold: int) -> float | None:
        if not aggregate["observed"] or not (aggregate["measured"] or aggregate["cancelled"]):
            return None
        return round(
            max(
                0,
                min(
                    100,
                    45 * (delayed_shares[str(threshold)] or 0)
                    + 25 * severe_share
                    + 20 * (cancelled_share or 0)
                    + 10 * min(max(average or 0, 0) / 30, 1),
                ),
            ),
            1,
        )

    scores = {str(threshold): calculate_score(threshold) for threshold in DELAY_THRESHOLDS}
    reliability_scores = {
        key: 100 - score if score is not None else None for key, score in scores.items()
    }

    def calculate_status(score: float | None) -> str:
        if not identity["hasRailService"]:
            return "no-service"
        if score is None:
            return "no-data"
        if score >= 25:
            return "serious"
        if score >= 10:
            return "elevated"
        return "normal"

    statuses = {key: calculate_status(score) for key, score in scores.items()}

    def top(source: dict[str, Any], threshold: int) -> list[dict[str, Any]]:
        rows = [finish_problem(key, item, threshold) for key, item in source.items()]
        rows = [row for row in rows if row["delayed"] or row["severe"] or row["cancellations"]]
        return sorted(
            rows,
            key=lambda row: (
                -row["severe"],
                -row["cancellations"],
                -row["delayed"],
                -(row["averageDelayMinutes"] or -10_000),
            ),
        )[:5]

    problem_stations = {str(threshold): top(aggregate["stations"], threshold) for threshold in DELAY_THRESHOLDS}
    problem_routes = {str(threshold): top(aggregate["routes"], threshold) for threshold in DELAY_THRESHOLDS}
    return {
        **identity,
        "observedTrains": aggregate["observed"],
        "measuredTrains": aggregate["measured"],
        "delayedTrains": aggregate["delayedByThreshold"]["5"],
        "delayedShare": delayed_shares["5"],
        "delayedTrainsByThreshold": aggregate["delayedByThreshold"],
        "delayedShareByThreshold": delayed_shares,
        "averageDelayMinutes": average,
        "severeDelays": aggregate["severe"],
        "cancellations": aggregate["cancelled"],
        "cancellationShare": cancelled_share,
        "disruptionScore": scores["5"],
        "reliabilityScore": reliability_scores["5"],
        "status": statuses["5"],
        "disruptionScoreByThreshold": scores,
        "reliabilityScoreByThreshold": reliability_scores,
        "statusByThreshold": statuses,
        "problemStations": problem_stations["5"],
        "problemRoutes": problem_routes["5"],
        "problemStationsByThreshold": problem_stations,
        "problemRoutesByThreshold": problem_routes,
    }


def build(args: argparse.Namespace) -> None:
    lookup = json.loads(Path(args.lookup).read_text(encoding="utf-8"))
    stations = lookup["stations"]
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    aggregates = {region["code"]: fresh_aggregate() for region in lookup["regions"]}
    files = sorted(Path(args.train_dir).glob("*.json.gz"))
    selected = [path for path in files if start <= date.fromisoformat(path.stem.removesuffix(".json")) <= end]
    if not selected:
        raise RuntimeError("No cached train partitions matched the requested historical period")

    for index, path in enumerate(selected, start=1):
        with gzip.open(path, "rt", encoding="utf-8") as source:
            trains = json.load(source)
        for train in trains:
            if train.get("trainCategory") not in PASSENGER_CATEGORIES:
                continue
            rows = [row for row in train.get("timeTableRows", []) if is_passenger_row(row, stations)]
            if not rows:
                continue
            origin_code = rows[0]["stationShortCode"]
            destination_code = rows[-1]["stationShortCode"]
            route_key = f"{origin_code}--{destination_code}"
            route_label = f"{clean_name(stations[origin_code]['name'])} → {clean_name(stations[destination_code]['name'])}"
            by_region: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in rows:
                by_region[stations[row["stationShortCode"]]["regionCode"]].append(row)
            for region_code, region_rows in by_region.items():
                aggregate = aggregates[region_code]
                aggregate["observed"] += 1
                cancelled = bool(train.get("cancelled") or any(row.get("cancelled") for row in region_rows))
                aggregate["cancelled"] += cancelled
                delays = [delay for row in region_rows if (delay := actual_delay(row)) is not None]
                delay = max(delays) if delays else None
                if not cancelled and delay is not None:
                    aggregate["measured"] += 1
                    aggregate["delaySum"] += delay
                    for threshold in DELAY_THRESHOLDS:
                        aggregate["delayedByThreshold"][str(threshold)] += delay > threshold
                    aggregate["severe"] += delay > 15
                add_problem(aggregate["routes"][route_key], route_label, None if cancelled else delay, cancelled)
                station_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
                for row in region_rows:
                    station_rows[row["stationShortCode"]].append(row)
                for code, grouped_rows in station_rows.items():
                    station_delays = [value for row in grouped_rows if (value := actual_delay(row)) is not None]
                    add_problem(
                        aggregate["stations"][code],
                        clean_name(stations[code]["name"]),
                        max(station_delays) if station_delays else None,
                        cancelled or any(row.get("cancelled") for row in grouped_rows),
                    )
        if index % 30 == 0 or index == len(selected):
            print(f"Processed {index}/{len(selected)} partitions", flush=True)

    regions = []
    for region in lookup["regions"]:
        station_count = sum(
            station["passengerTraffic"] and station["regionCode"] == region["code"]
            for station in stations.values()
        )
        regions.append(
            finish_aggregate(
                aggregates[region["code"]],
                {
                    "code": region["code"],
                    "nameFi": region["nameFi"],
                    "nameEn": region["nameEn"],
                    "passengerStations": station_count,
                    "hasRailService": station_count > 0,
                },
            )
        )

    network = fresh_aggregate()
    for aggregate in aggregates.values():
        for field in ("observed", "measured", "severe", "cancelled", "delaySum"):
            network[field] += aggregate[field]
        for threshold in DELAY_THRESHOLDS:
            network["delayedByThreshold"][str(threshold)] += aggregate["delayedByThreshold"][str(threshold)]
    network_finished = finish_aggregate(
        network,
        {"code": "FI", "nameFi": "Suomi", "nameEn": "Finland", "passengerStations": 0, "hasRailService": True},
    )
    for field in (
        "code", "nameFi", "nameEn", "passengerStations", "hasRailService",
        "problemStations", "problemRoutes", "problemStationsByThreshold", "problemRoutesByThreshold",
    ):
        network_finished.pop(field)

    payload = {
        "mode": "historical",
        "retrievedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "windowStart": f"{start.isoformat()}T00:00:00.000Z",
        "windowEnd": f"{end.isoformat()}T23:59:59.999Z",
        "source": "Fintraffic / Digitraffic",
        "sourceUrl": "https://www.digitraffic.fi/en/railway-traffic/",
        "definitions": {
            "delayed": "More whole minutes late than the selected 5, 10, 15 or 30-minute policy threshold at a commercial passenger stop in the region.",
            "severe": "More than 15 whole minutes late.",
            "observedTrain": "One passenger train per region with at least one commercial stop; a train crossing regions is counted once in each region.",
            "score": "Threshold-adjusted disruption score (0 best, 100 worst): 45% selected-threshold delayed share, 25% severe-delay share, 20% cancellation share and 10% average positive delay capped at 30 minutes.",
            "thresholds": DELAY_THRESHOLDS,
        },
        "network": network_finished,
        "regions": regions,
    }
    output = Path(args.output)
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {output} ({output.stat().st_size:,} bytes)")


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--lookup", default="artifacts/rail-station-regions.json")
    cli.add_argument("--train-dir", default="data/rail/trains")
    cli.add_argument("--start", default="2025-08-01")
    cli.add_argument("--end", default="2026-07-31")
    cli.add_argument("--output", default="artifacts/rail-regional-history.json")
    return cli


if __name__ == "__main__":
    build(parser().parse_args())
