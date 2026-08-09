# Fabric notebook source
# Attach Lakehouse: lh_finland_rail

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import gzip
import json
import time
from pathlib import Path

import requests
from pyspark.sql import Row


DIGITRAFFIC_ROOT = "https://rata.digitraffic.fi/api/v1"
HEADERS = {
    "Digitraffic-User": "AppliedAILab/RailReliabilityMonitor 1.0",
    "Accept-Encoding": "gzip",
}

# Pipeline parameters. Fabric can overwrite notebook parameters at runtime.
p_start_date = "2025-08-01"
p_end_date = "2025-08-01"


def dates(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def get_bytes(url: str) -> bytes:
    last_error = None
    for attempt in range(4):
        try:
            response = requests.get(url, headers=HEADERS, timeout=120)
            response.raise_for_status()
            return response.content
        except requests.RequestException as error:
            last_error = error
            time.sleep(2**attempt)
    raise RuntimeError(f"Digitraffic request failed after retries: {url}") from last_error


def ingest_day(day: date) -> Row:
    url = f"{DIGITRAFFIC_ROOT}/trains/{day.isoformat()}"
    content = get_bytes(url)
    records = json.loads(content)
    compressed = gzip.compress(content, compresslevel=9)
    relative_path = f"Files/rail/bronze/digitraffic/departure_date={day.isoformat()}/trains.json.gz"
    path = Path("/lakehouse/default") / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compressed)
    return Row(
        source="digitraffic_trains",
        partition_date=day.isoformat(),
        retrieved_at=datetime.now(timezone.utc),
        source_url=url,
        record_count=len(records),
        content_sha256=sha256(content).hexdigest(),
        bronze_path=relative_path,
        status="complete",
    )


def ingest_station_metadata() -> Row:
    url = f"{DIGITRAFFIC_ROOT}/metadata/stations"
    content = get_bytes(url)
    records = json.loads(content)
    compressed = gzip.compress(content, compresslevel=9)
    relative_path = "Files/rail/bronze/digitraffic/metadata/stations.json.gz"
    path = Path("/lakehouse/default") / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compressed)
    return Row(
        source="digitraffic_stations",
        partition_date="metadata",
        retrieved_at=datetime.now(timezone.utc),
        source_url=url,
        record_count=len(records),
        content_sha256=sha256(content).hexdigest(),
        bronze_path=relative_path,
        status="complete",
    )


start = date.fromisoformat(p_start_date)
end = date.fromisoformat(p_end_date)
if start > end:
    raise ValueError("p_start_date must be on or before p_end_date")

audit_rows = [ingest_station_metadata(), *(ingest_day(day) for day in dates(start, end))]
audit_frame = spark.createDataFrame(audit_rows)
(
    audit_frame.write.format("delta")
    .mode("append")
    .saveAsTable("rail_control_ingestion")
)

failed = audit_frame.filter("status <> 'complete'").count()
if failed:
    raise RuntimeError(f"Rail ingestion completed with {failed} failed partitions")
