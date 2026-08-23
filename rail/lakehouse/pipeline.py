from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from delta.tables import DeltaTable
from pyspark.sql import functions as F
from pyspark.sql.types import BooleanType, DoubleType, StringType, StructField, StructType

from rail.pipeline import validate_train_partition, write_json

from .contracts import ContractRegistry
from .planning import affected_complete_windows, date_range, select_partitions
from .quality import QualityResult, require_no_failures, row_count_anomaly
from .spark import build_spark, delta_exists, replace_partitions
from .transforms import journey_fact, network_daily, normalize, regional_daily, rolling_regional_7d, route_performance, station_performance


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "rail/contracts/data_contracts.json"
DEFAULT_STATIONS = ROOT / "artifacts/rail-station-regions.json"
DEFAULT_SOURCE = ROOT / "data/rail/trains"
DEFAULT_LAKEHOUSE = ROOT / "data/rail/lakehouse"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_and_validate(path: Path, day: date) -> tuple[list[dict[str, Any]], str]:
    digest = sha256_file(path)
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    return validate_train_partition(day, payload), digest


def station_frame(spark, path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = [
        (
            code, str(value.get("name") or code), bool(value.get("passengerTraffic")), "FI",
            str(value.get("regionCode") or ""), float(value["latitude"]), float(value["longitude"]),
        )
        for code, value in raw["stations"].items()
        if value.get("regionCode")
    ]
    schema = StructType([
        StructField("station_code", StringType(), False), StructField("station_name", StringType(), False),
        StructField("passenger_traffic", BooleanType(), False), StructField("country_code", StringType(), False),
        StructField("region_code", StringType(), False), StructField("latitude", DoubleType(), False),
        StructField("longitude", DoubleType(), False),
    ])
    return spark.createDataFrame(rows, schema)


def region_frames(spark, path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    station_counts: dict[str, int] = {}
    for station in raw["stations"].values():
        if station.get("passengerTraffic") and station.get("regionCode"):
            station_counts[station["regionCode"]] = station_counts.get(station["regionCode"], 0) + 1
    dimensions = spark.createDataFrame([{
        "region_code": region["code"], "region_name_fi": region["nameFi"],
        "region_name_sv": region["nameSv"], "region_name_en": region["nameEn"],
        "region_year": int(region["year"]), "has_rail_service": station_counts.get(region["code"], 0) > 0,
        "mapping_source": raw["meta"]["regionSource"],
    } for region in raw["regions"]])
    bridge = spark.createDataFrame([{
        "station_region_key": f"{raw['meta']['regionYear']}:{code}", "station_code": code,
        "region_code": value["regionCode"], "region_year": int(raw["meta"]["regionYear"]),
        "is_active": True, "mapping_source": raw["meta"]["regionSource"],
    } for code, value in raw["stations"].items() if value.get("regionCode")])
    return dimensions, bridge


class LakehousePipeline:
    def __init__(self, spark, lakehouse: Path, source: Path, stations: Path, contracts: Path = DEFAULT_CONTRACT):
        self.spark = spark
        self.root = lakehouse
        self.source = source
        self.stations_path = stations
        self.contracts = ContractRegistry(contracts)
        self.paths = {
            "bronze_manifest": lakehouse / "control/bronze_manifest",
            "watermark": lakehouse / "control/watermark",
            "runs": lakehouse / "control/pipeline_runs",
            "quality": lakehouse / "control/quality_results",
            "silver_journeys": lakehouse / "silver/train_journey",
            "silver_arrivals": lakehouse / "silver/station_arrival",
            "gold_facts": lakehouse / "gold/fact_train_journey",
            "gold_regional": lakehouse / "gold/mart_regional_performance_daily",
            "gold_network": lakehouse / "gold/mart_network_reliability_daily",
            "gold_routes": lakehouse / "gold/mart_route_performance",
            "gold_stations": lakehouse / "gold/mart_station_performance",
            "gold_dim_region": lakehouse / "gold/dim_region",
            "gold_bridge_station_region": lakehouse / "gold/bridge_station_region",
            "gold_regional_7d": lakehouse / "gold/mart_regional_performance_7d",
            "publication": lakehouse / "control/regional_publication",
        }

    def successful_hashes(self) -> dict[str, str]:
        path = self.paths["watermark"]
        if not delta_exists(self.spark, path):
            return {}
        return {row["departure_date"].isoformat(): row["source_content_sha256"] for row in self.spark.read.format("delta").load(str(path)).collect()}

    def source_counts(self) -> list[int]:
        path = self.paths["bronze_manifest"]
        if not delta_exists(self.spark, path):
            return []
        return [int(row[0]) for row in self.spark.read.format("delta").load(str(path)).orderBy("departure_date").select("source_row_count").collect()]

    def append_rows(self, key: str, rows: list[dict[str, Any]]) -> None:
        if rows:
            self.spark.createDataFrame(rows).write.format("delta").mode("append").option("mergeSchema", "true").save(str(self.paths[key]))

    def record_run(self, run_id: str, status: str, start: str, end: str, processed: int, skipped: int, detail: str = "") -> None:
        self.append_rows("runs", [{
            "run_id": run_id, "status": status, "requested_start": start, "requested_end": end,
            "processed_partitions": processed, "skipped_partitions": skipped, "detail": detail,
            "recorded_at": datetime.now(timezone.utc),
        }])

    def record_quality(self, run_id: str, day: str, results: list[QualityResult]) -> None:
        self.append_rows("quality", [{
            "run_id": run_id, "departure_date": day, "layer": item.layer, "check_name": item.check,
            "status": item.status, "observed": str(item.observed), "detail": item.detail,
            "checked_at": datetime.now(timezone.utc),
        } for item in results])

    def commit_manifest(self, run_id: str, day: str, digest: str, raw_path: Path, row_count: int) -> None:
        row = self.spark.createDataFrame([{
            "departure_date": date.fromisoformat(day), "content_sha256": digest, "source_path": str(raw_path),
            "source_row_count": row_count, "ingested_at": datetime.now(timezone.utc), "run_id": run_id,
        }])
        self.contracts.validate_columns("bronze.train_partition", row.columns)
        target_path = self.paths["bronze_manifest"]
        if not delta_exists(self.spark, target_path):
            row.write.format("delta").mode("overwrite").save(str(target_path))
            return
        target = DeltaTable.forPath(self.spark, str(target_path))
        target.alias("t").merge(
            row.alias("s"), "t.departure_date = s.departure_date AND t.content_sha256 = s.content_sha256"
        ).whenNotMatchedInsertAll().execute()

    def advance_watermarks(self, run_id: str, processed: list[tuple[str, str]]) -> None:
        if not processed:
            return
        source = self.spark.createDataFrame([{
            "departure_date": date.fromisoformat(day), "source_content_sha256": digest,
            "committed_run_id": run_id, "committed_at": datetime.now(timezone.utc),
        } for day, digest in processed])
        path = self.paths["watermark"]
        if not delta_exists(self.spark, path):
            source.write.format("delta").mode("overwrite").save(str(path))
            return
        DeltaTable.forPath(self.spark, str(path)).alias("t").merge(
            source.alias("s"), "t.departure_date = s.departure_date"
        ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()

    def _quality(self, raw, journeys, arrivals, stations, source_count: int, historical_counts: list[int], partition_day: date) -> list[QualityResult]:
        duplicate_source = raw.groupBy("departureDate", "trainNumber").count().filter("count > 1").count()
        duplicate_journeys = journeys.groupBy("journey_key").count().filter("count > 1").count()
        duplicate_arrivals = arrivals.groupBy("arrival_key").count().filter("count > 1").count()
        critical_nulls = journeys.filter(
            F.col("journey_key").isNull() | F.col("origin_code").isNull() | F.col("destination_code").isNull() | F.col("scheduled_departure_utc").isNull()
        ).count()
        impossible_delays = journeys.filter(F.abs("final_delay_minutes") > 1440).count()
        station_codes = stations.select("station_code")
        unknown_stations = (
            raw.select(F.explode_outer("timeTableRows").alias("event")).select("event.*")
            .filter(F.col("commercialStop") & F.col("trainStopping") & (F.col("countryCode") == "FI"))
            .select(F.col("stationShortCode").alias("station_code")).distinct()
            .join(F.broadcast(station_codes), "station_code", "left_anti").count()
        )
        age_hours = (datetime.now(timezone.utc) - datetime.combine(partition_day, datetime.min.time(), tzinfo=timezone.utc)).total_seconds() / 3600
        freshness_status = "PASS" if age_hours <= 30 else "WARN"
        results = [
            row_count_anomaly(source_count, historical_counts),
            QualityResult("bronze", "freshness", freshness_status, round(age_hours, 1), "historical/backfill partitions are reported but not rejected for age"),
            QualityResult("silver", "duplicate_source_business_keys", "FAIL" if duplicate_source else "PASS", duplicate_source, "departureDate + trainNumber must be unique"),
            QualityResult("silver", "duplicate_journey_keys", "FAIL" if duplicate_journeys else "PASS", duplicate_journeys, "journey_key must be unique"),
            QualityResult("silver", "duplicate_arrival_keys", "FAIL" if duplicate_arrivals else "PASS", duplicate_arrivals, "arrival_key must be unique"),
            QualityResult("silver", "missing_critical_fields", "FAIL" if critical_nulls else "PASS", critical_nulls, "contract-required journey fields"),
            QualityResult("silver", "impossible_delay_over_24h", "FAIL" if impossible_delays else "PASS", impossible_delays, "absolute final delay must be <= 1440 minutes"),
            QualityResult("silver", "station_referential_integrity", "FAIL" if unknown_stations else "PASS", unknown_stations, "commercial Finnish station codes must exist in governed station metadata"),
            QualityResult("silver", "nonempty_modelled_partition", "PASS" if journeys.take(1) else "FAIL", journeys.count(), "at least one normalized passenger journey"),
        ]
        return results

    def process(self, start: date, end: date, *, force: bool = False) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        started = datetime.now(timezone.utc)
        source_hashes = {day.isoformat(): sha256_file(self.source / f"{day.isoformat()}.json.gz") for day in date_range(start, end)}
        decisions = select_partitions(start, end, self.source, source_hashes, self.successful_hashes(), force=force)
        selected = [item for item in decisions if item.action == "process"]
        skipped = len(decisions) - len(selected)
        processed: list[tuple[str, str]] = []
        evidence: dict[str, Any] = {
            "runId": run_id, "startedAt": started.isoformat(), "requestedRange": [start.isoformat(), end.isoformat()],
            "force": force, "partitionDecisions": [{"date": item.departure_date.isoformat(), "action": item.action, "reason": item.reason, "sha256": item.source_sha256} for item in decisions],
            "partitions": [],
        }
        try:
            stations = station_frame(self.spark, self.stations_path).cache()
            regions, station_region = region_frames(self.spark, self.stations_path)
            for decision in selected:
                day = decision.departure_date.isoformat()
                payload, digest = load_and_validate(decision.source_path, decision.departure_date)
                historical_counts = self.source_counts()
                immutable = self.root / f"bronze/digitraffic_trains/departure_date={day}/content_sha256={digest}/trains.json.gz"
                immutable.parent.mkdir(parents=True, exist_ok=True)
                if not immutable.exists():
                    temporary = immutable.with_suffix(".json.gz.tmp")
                    shutil.copyfile(decision.source_path, temporary)
                    temporary.replace(immutable)
                self.commit_manifest(run_id, day, digest, immutable, len(payload))
                raw = self.spark.read.option("multiLine", "true").json(str(immutable))
                hashes = self.spark.createDataFrame([(day, digest)], ["source_departure_date", "source_content_sha256"])
                journeys, arrivals = normalize(raw, stations, hashes, run_id)
                results = self._quality(raw, journeys, arrivals, stations, len(payload), historical_counts, decision.departure_date)
                self.record_quality(run_id, day, results)
                require_no_failures(results, "Bronze to Silver")
                self.contracts.validate_columns("silver.train_journey", journeys.columns)
                self.contracts.validate_columns("silver.station_arrival", arrivals.columns)
                replace_partitions(journeys, self.paths["silver_journeys"], "departure_date", [day])
                replace_partitions(arrivals, self.paths["silver_arrivals"], "departure_date", [day])
                facts = journey_fact(journeys)
                regional = regional_daily(arrivals)
                network = network_daily(facts)
                invalid_gold = facts.filter(
                    (F.col("on_time_5").cast("int") > F.col("on_time_10").cast("int"))
                    | (F.col("on_time_10").cast("int") > F.col("on_time_15").cast("int"))
                    | (F.col("on_time_15").cast("int") > F.col("on_time_30").cast("int"))
                    | (F.col("completed").cast("int") < F.col("on_time_30").cast("int"))
                ).count()
                gold_result = QualityResult("gold", "metric_monotonicity", "FAIL" if invalid_gold else "PASS", invalid_gold, "on_time_5 <= on_time_10 <= on_time_15 <= on_time_30 <= completed")
                self.record_quality(run_id, day, [gold_result])
                require_no_failures([gold_result], "Silver to Gold")
                results.append(gold_result)
                self.contracts.validate_columns("gold.fact_train_journey", facts.columns)
                self.contracts.validate_columns("gold.mart_regional_performance_daily", regional.columns)
                replace_partitions(facts, self.paths["gold_facts"], "departure_date", [day])
                replace_partitions(regional, self.paths["gold_regional"], "departure_date", [day])
                replace_partitions(network, self.paths["gold_network"], "departure_date", [day])
                fact_count, arrival_count = facts.count(), arrivals.count()
                network_metrics = network.drop("departure_date").first().asDict()
                evidence["partitions"].append({
                    "date": day, "sourceRows": len(payload), "silverJourneys": fact_count,
                    "silverArrivals": arrival_count, "regionalRows": regional.count(),
                    "networkMetrics": network_metrics,
                    "quality": [{"layer": item.layer, "check": item.check, "status": item.status, "observed": item.observed} for item in results],
                })
                processed.append((day, digest))
            if processed:
                all_facts = self.spark.read.format("delta").load(str(self.paths["gold_facts"]))
                all_arrivals = self.spark.read.format("delta").load(str(self.paths["silver_arrivals"]))
                route_performance(all_facts).write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(str(self.paths["gold_routes"]))
                station_performance(all_arrivals).write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(str(self.paths["gold_stations"]))
                self.contracts.validate_columns("gold.dim_region", regions.columns)
                self.contracts.validate_columns("gold.bridge_station_region", station_region.columns)
                regions.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(str(self.paths["gold_dim_region"]))
                station_region.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(str(self.paths["gold_bridge_station_region"]))
                all_regional = self.spark.read.format("delta").load(str(self.paths["gold_regional"]))
                available = {row[0] for row in all_regional.select("departure_date").distinct().collect()}
                windows = affected_complete_windows(available, {date.fromisoformat(day) for day, _ in processed})
                for window_end in windows:
                    rolling = rolling_regional_7d(all_regional, regions, window_end.isoformat())
                    self.contracts.validate_columns("gold.mart_regional_performance_7d", rolling.columns)
                    invalid_rolling = rolling.filter(
                        (F.col("component_partitions") != 7)
                        | (F.col("measured_trains") > F.col("observed_trains"))
                        | (F.col("delayed_5") < F.col("delayed_10"))
                        | (F.col("delayed_10") < F.col("delayed_15"))
                        | (F.col("delayed_15") < F.col("delayed_30"))
                    ).count()
                    if rolling.count() != 19 or invalid_rolling:
                        raise ValueError(f"regional 7d publication failed reconciliation for {window_end}")
                    replace_partitions(rolling, self.paths["gold_regional_7d"], "window_end", [window_end.isoformat()])
                    self.append_rows("publication", [{
                        "run_id": run_id, "mode": "7d", "window_end": window_end,
                        "status": "PUBLISHED", "gold_published_at": datetime.now(timezone.utc),
                        "row_count": 19, "component_partitions": 7,
                    }])
                evidence["rolling7dWindows"] = [item.isoformat() for item in windows]
                self.advance_watermarks(run_id, processed)
            self.record_run(run_id, "SUCCEEDED", start.isoformat(), end.isoformat(), len(processed), skipped)
            evidence.update({"status": "SUCCEEDED", "processedPartitions": len(processed), "skippedPartitions": skipped})
        except Exception as error:
            self.record_run(run_id, "FAILED", start.isoformat(), end.isoformat(), len(processed), skipped, str(error))
            evidence.update({"status": "FAILED", "error": str(error), "processedPartitions": len(processed), "skippedPartitions": skipped})
            raise
        finally:
            evidence["finishedAt"] = datetime.now(timezone.utc).isoformat()
        return evidence


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Incremental Finland Rail Bronze/Silver/Gold Delta pipeline")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--lakehouse", type=Path, default=DEFAULT_LAKEHOUSE)
    parser.add_argument("--stations", type=Path, default=DEFAULT_STATIONS)
    parser.add_argument("--contracts", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--force", action="store_true", help="Reprocess selected partitions for recovery or backfill")
    parser.add_argument("--master", default="local[2]")
    parser.add_argument("--evidence", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    spark = build_spark(master=args.master)
    try:
        result = LakehousePipeline(spark, args.lakehouse, args.source, args.stations, args.contracts).process(
            date.fromisoformat(args.start), date.fromisoformat(args.end), force=args.force
        )
        if args.evidence:
            write_json(args.evidence, {"sparkVersion": spark.version, "deltaVersion": "4.0.1", **result})
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
