"""Build the official Finland maakunta map and station-to-region lookup.

The geometry comes from Statistics Finland's municipality-based statistical
areas WFS. Station coordinates come from Fintraffic / Digitraffic. The output
is deterministic for the two downloaded source snapshots and is small enough
to ship with the public monitor.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import urllib.request
from pathlib import Path
from typing import Any, Iterable


REGION_WFS_URL = (
    "https://geo.stat.fi/geoserver/tilastointialueet/wfs?service=WFS&version=2.0.0"
    "&request=GetFeature&typeNames=tilastointialueet:maakunta1000k"
    "&outputFormat=application/json&srsName=EPSG:4326"
)
STATIONS_URL = "https://rata.digitraffic.fi/api/v1/metadata/stations"
USER_AGENT = "AppliedAILab/FinlandRailMonitoringSystem github.com/Sintagmatarches"


def fetch_json(url: str, *, digitraffic: bool = False) -> Any:
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    if digitraffic:
        headers["Digitraffic-User"] = USER_AGENT
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
    return json.loads(body)


def perpendicular_distance(point: list[float], start: list[float], end: list[float]) -> float:
    if start == end:
        return math.dist(point, start)
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    projection = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / (dx * dx + dy * dy)
    closest = [start[0] + projection * dx, start[1] + projection * dy]
    return math.dist(point, closest)


def simplify_open(points: list[list[float]], tolerance: float) -> list[list[float]]:
    if len(points) <= 2:
        return points
    start, end = points[0], points[-1]
    index = -1
    maximum = 0.0
    for current, point in enumerate(points[1:-1], start=1):
        distance = perpendicular_distance(point, start, end)
        if distance > maximum:
            index, maximum = current, distance
    if maximum <= tolerance:
        return [start, end]
    left = simplify_open(points[: index + 1], tolerance)
    right = simplify_open(points[index:], tolerance)
    return left[:-1] + right


def simplify_ring(ring: list[list[float]], tolerance: float) -> list[list[float]]:
    if len(ring) < 6:
        return ring
    simplified = simplify_open(ring[:-1], tolerance)
    if len(simplified) < 3:
        return ring
    return simplified + [simplified[0]]


def ring_area(ring: list[list[float]]) -> float:
    return abs(
        sum(
            ring[index][0] * ring[index + 1][1]
            - ring[index + 1][0] * ring[index][1]
            for index in range(len(ring) - 1)
        )
        / 2
    )


def simplify_geometry(geometry: dict[str, Any], tolerance: float) -> dict[str, Any]:
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    simplified_polygons = []
    for polygon in polygons:
        exterior = polygon[0]
        # Tiny uninhabited islands add most of the payload but no useful map detail.
        if ring_area(exterior) < 0.00008:
            continue
        rings = [simplify_ring(exterior, tolerance)]
        rings.extend(simplify_ring(ring, tolerance) for ring in polygon[1:] if ring_area(ring) >= 0.00008)
        simplified_polygons.append(rings)
    return {"type": "MultiPolygon", "coordinates": simplified_polygons}


def point_in_ring(longitude: float, latitude: float, ring: list[list[float]]) -> bool:
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > latitude) != (y2 > latitude):
            crossing = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < crossing:
                inside = not inside
        previous = current
    return inside


def point_in_geometry(longitude: float, latitude: float, geometry: dict[str, Any]) -> bool:
    polygons: Iterable[list[list[list[float]]]]
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    for polygon in polygons:
        if point_in_ring(longitude, latitude, polygon[0]) and not any(
            point_in_ring(longitude, latitude, hole) for hole in polygon[1:]
        ):
            return True
    return False


def station_region(station: dict[str, Any], features: list[dict[str, Any]]) -> str | None:
    longitude = station.get("longitude")
    latitude = station.get("latitude")
    if not isinstance(longitude, (int, float)) or not isinstance(latitude, (int, float)):
        return None
    for feature in features:
        if point_in_geometry(longitude, latitude, feature["geometry"]):
            return feature["properties"]["maakunta"]
    return None


def load_stations(cache_path: Path, *, refresh: bool = False) -> list[dict[str, Any]]:
    if cache_path.exists() and not refresh:
        with gzip.open(cache_path, "rt", encoding="utf-8") as source:
            return json.load(source)
    return fetch_json(STATIONS_URL, digitraffic=True)


def build(args: argparse.Namespace) -> None:
    raw_regions = fetch_json(REGION_WFS_URL)
    features = sorted(raw_regions["features"], key=lambda item: item["properties"]["maakunta"])
    if len(features) != 19:
        raise RuntimeError(f"Expected 19 maakunta features, received {len(features)}")

    public_features = [
        {
            "type": "Feature",
            "id": feature["properties"]["maakunta"],
            "properties": {
                "code": feature["properties"]["maakunta"],
                "nameFi": feature["properties"]["nimi"],
                "nameSv": feature["properties"]["namn"],
                "nameEn": feature["properties"]["name"],
                "year": feature["properties"]["vuosi"],
            },
            "geometry": simplify_geometry(feature["geometry"], args.tolerance),
        }
        for feature in features
    ]
    map_payload = {
        "type": "FeatureCollection",
        "source": "Statistics Finland",
        "sourceUrl": REGION_WFS_URL,
        "license": "CC BY 4.0",
        "features": public_features,
    }

    stations = load_stations(Path(args.station_cache), refresh=args.refresh_stations)
    station_payload: dict[str, dict[str, Any]] = {}
    unmatched_passenger = []
    for station in stations:
        if station.get("countryCode") != "FI":
            continue
        region = station_region(station, features)
        if station.get("passengerTraffic") and region is None:
            unmatched_passenger.append(station.get("stationShortCode"))
        station_payload[station["stationShortCode"]] = {
            "name": station["stationName"],
            "passengerTraffic": bool(station.get("passengerTraffic")),
            "longitude": station.get("longitude"),
            "latitude": station.get("latitude"),
            "regionCode": region,
        }
    if unmatched_passenger:
        raise RuntimeError(f"Passenger stations outside all regions: {unmatched_passenger}")

    lookup_payload = {
        "meta": {
            "regionSource": REGION_WFS_URL,
            "stationSource": STATIONS_URL,
            "regionYear": max(feature["properties"]["vuosi"] for feature in features),
            "regionCount": len(features),
            "sourceStationCount": len(stations),
            "stationCount": len(station_payload),
            "passengerStationCount": sum(item["passengerTraffic"] for item in station_payload.values()),
        },
        "regions": [feature["properties"] for feature in public_features],
        "stations": station_payload,
    }

    for path, payload in [
        (Path(args.map_output), map_payload),
        (Path(args.lookup_output), lookup_payload),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"Wrote {path} ({path.stat().st_size:,} bytes)")


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--station-cache", default="data/rail/metadata/stations.json.gz")
    cli.add_argument(
        "--refresh-stations",
        action="store_true",
        help="Fetch the current official Digitraffic station metadata instead of reusing the local cache.",
    )
    cli.add_argument("--map-output", default="public/rail/finland-maakunta.geojson")
    cli.add_argument("--lookup-output", default="artifacts/rail-station-regions.json")
    cli.add_argument("--tolerance", type=float, default=0.004)
    return cli


if __name__ == "__main__":
    build(parser().parse_args())
