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


def fresh_aggregate() -> dict[str, Any]:
    return {
        "observed": 0,
        "measured": 0,
        "delayed": 0,
        "severe": 0,
        "cancelled": 0,
        "delaySum": 0,
        "stations": defaultdict(fresh_problem),
        "routes": defaultdict(fresh_problem),
    }


def fresh_problem() -> dict[str, Any]:
    return {"label": "", "observations": 0, "measured": 0, "delayed": 0, "severe": 0, "cancellations": 0, "delaySum": 0}


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
        problem["delayed"] += delay > 5
        problem["severe"] += delay > 15


def finish_problem(key: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": key,
        "label": item["label"],
        "observations": item["observations"],
        "delayed": item["delayed"],
        "severe": item["severe"],
        "cancellations": item["cancellations"],
        "averageDelayMinutes": item["delaySum"] / item["measured"] if item["measured"] else None,
    }


def finish_aggregate(aggregate: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    delayed_share = aggregate["delayed"] / aggregate["measured"] if aggregate["measured"] else None
    severe_share = aggregate["severe"] / aggregate["measured"] if aggregate["measured"] else 0
    average = aggregate["delaySum"] / aggregate["measured"] if aggregate["measured"] else None
    cancelled_share = aggregate["cancelled"] / aggregate["observed"] if aggregate["observed"] else None
    score = None
    if aggregate["observed"]:
        score = round(
            max(
                0,
                min(
                    100,
                    45 * (delayed_share or 0)
                    + 25 * severe_share
                    + 20 * (cancelled_share or 0)
                    + 10 * min(max(average or 0, 0) / 30, 1),
                ),
            ),
            1,
        )
    if not identity["hasRailService"]:
        status = "no-service"
    elif score is None:
        status = "no-data"
    elif score >= 25:
        status = "serious"
    elif score >= 10:
        status = "elevated"
    else:
        status = "normal"

    def top(source: dict[str, Any]) -> list[dict[str, Any]]:
        rows = [finish_problem(key, item) for key, item in source.items()]
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

    return {
        **identity,
        "observedTrains": aggregate["observed"],
        "measuredTrains": aggregate["measured"],
        "delayedTrains": aggregate["delayed"],
        "delayedShare": delayed_share,
        "averageDelayMinutes": average,
        "severeDelays": aggregate["severe"],
        "cancellations": aggregate["cancelled"],
        "cancellationShare": cancelled_share,
        "disruptionScore": score,
        "reliabilityScore": 100 - score if score is not None else None,
        "status": status,
        "problemStations": top(aggregate["stations"]),
        "problemRoutes": top(aggregate["routes"]),
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
                    aggregate["delayed"] += delay > 5
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
        for field in ("observed", "measured", "delayed", "severe", "cancelled", "delaySum"):
            network[field] += aggregate[field]
    network_finished = finish_aggregate(
        network,
        {"code": "FI", "nameFi": "Suomi", "nameEn": "Finland", "passengerStations": 0, "hasRailService": True},
    )
    for field in ("code", "nameFi", "nameEn", "passengerStations", "hasRailService", "problemStations", "problemRoutes"):
        network_finished.pop(field)

    payload = {
        "mode": "historical",
        "retrievedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "windowStart": f"{start.isoformat()}T00:00:00.000Z",
        "windowEnd": f"{end.isoformat()}T23:59:59.999Z",
        "source": "Fintraffic / Digitraffic",
        "sourceUrl": "https://www.digitraffic.fi/en/railway-traffic/",
        "definitions": {
            "delayed": "More than 5 whole minutes late at a commercial passenger stop in the region.",
            "severe": "More than 15 whole minutes late.",
            "observedTrain": "One passenger train per region with at least one commercial stop; a train crossing regions is counted once in each region.",
            "score": "Disruption score (0 best, 100 worst): 45% delayed share, 25% severe-delay share, 20% cancellation share and 10% average positive delay capped at 30 minutes.",
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
