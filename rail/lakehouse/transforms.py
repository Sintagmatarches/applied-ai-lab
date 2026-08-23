from __future__ import annotations

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F


PASSENGER_CATEGORIES = ("Long-distance", "Commuter")
THRESHOLDS = (5, 10, 15, 30)


def normalize(raw: DataFrame, stations: DataFrame, source_hashes: DataFrame, run_id: str) -> tuple[DataFrame, DataFrame]:
    trains = (
        raw.filter(F.col("trainCategory").isin(*PASSENGER_CATEGORIES))
        .join(source_hashes, F.col("departureDate") == F.col("source_departure_date"), "left")
        .drop("source_departure_date")
        .withColumnRenamed("cancelled", "train_cancelled")
        .withColumn("journey_key", F.concat_ws(":", "departureDate", F.col("trainNumber").cast("string")))
    )
    rows = (
        trains.select(
            "journey_key", "departureDate", "trainNumber", "trainType", "trainCategory", "commuterLineID",
            "train_cancelled", "source_content_sha256",
            F.posexplode_outer("timeTableRows").alias("event_index", "event"),
        )
        .select("*", "event.*")
        .drop("event")
        .filter(F.col("commercialStop") & F.col("trainStopping"))
        .join(F.broadcast(stations), F.col("stationShortCode") == F.col("station_code"), "inner")
        .filter(F.col("passenger_traffic") & (F.col("country_code") == "FI"))
        .withColumn("scheduled_ts", F.to_timestamp("scheduledTime"))
        .withColumn("actual_ts", F.to_timestamp("actualTime"))
        .withColumn(
            "delay_minutes",
            F.coalesce(
                F.col("differenceInMinutes").cast("int"),
                F.round((F.unix_timestamp("actual_ts") - F.unix_timestamp("scheduled_ts")) / 60).cast("int"),
            ),
        )
    )
    first_departures = (
        rows.filter(F.col("type") == "DEPARTURE")
        .withColumn("rank", F.row_number().over(Window.partitionBy("journey_key").orderBy("event_index")))
        .filter(F.col("rank") == 1)
        .select(
            "journey_key", F.col("stationShortCode").alias("origin_code"),
            F.col("scheduled_ts").alias("scheduled_departure_utc"),
            F.col("cancelled").alias("origin_cancelled"), F.col("delay_minutes").alias("departure_delay_minutes"),
        )
    )
    final_arrivals = (
        rows.filter(F.col("type") == "ARRIVAL")
        .withColumn("rank", F.row_number().over(Window.partitionBy("journey_key").orderBy(F.col("event_index").desc())))
        .filter(F.col("rank") == 1)
        .select(
            "journey_key", F.col("stationShortCode").alias("destination_code"),
            F.col("cancelled").alias("final_arrival_cancelled"), F.col("delay_minutes").alias("final_delay_raw"),
        )
    )
    partial = rows.groupBy("journey_key").agg(F.max(F.col("cancelled").cast("int")).cast("boolean").alias("any_event_cancelled"))
    local_departure = F.from_utc_timestamp("scheduled_departure_utc", "Europe/Helsinki")
    journeys = (
        trains.join(first_departures, "journey_key", "inner").join(final_arrivals, "journey_key", "inner").join(partial, "journey_key", "left")
        .select(
            "journey_key", F.to_date("departureDate").alias("departure_date"), F.col("trainNumber").cast("long").alias("train_number"),
            F.coalesce("trainType", F.lit("Unknown")).alias("train_type"), F.col("trainCategory").alias("category"),
            F.coalesce("commuterLineID", F.lit("")).alias("commuter_line"), "origin_code", "destination_code",
            "scheduled_departure_utc", F.date_format(local_departure, "yyyy-MM").alias("month"),
            ((F.dayofweek(local_departure) + 5) % 7).alias("weekday"), F.hour(local_departure).alias("departure_hour"),
            F.concat_ws("--", F.least("origin_code", "destination_code"), F.greatest("origin_code", "destination_code")).alias("route_key"),
            F.col("train_cancelled").cast("boolean").alias("cancelled"),
            ((~F.col("train_cancelled")) & F.col("any_event_cancelled")).alias("partial_cancelled"),
            F.col("final_arrival_cancelled").cast("boolean"),
            F.when(~F.col("train_cancelled") & ~F.col("final_arrival_cancelled"), F.col("final_delay_raw")).cast("int").alias("final_delay_minutes"),
            F.when(~F.col("train_cancelled") & ~F.col("origin_cancelled"), F.col("departure_delay_minutes")).cast("int").alias("departure_delay_minutes"),
            "source_content_sha256", F.current_timestamp().alias("processed_at"), F.lit(run_id).alias("run_id"),
        )
    )
    arrivals = (
        rows.filter(F.col("type") == "ARRIVAL")
        .select(
            F.concat_ws(":", "journey_key", "stationShortCode", F.col("event_index").cast("string")).alias("arrival_key"),
            "journey_key", F.to_date("departureDate").alias("departure_date"), F.col("stationShortCode").alias("station_code"),
            F.col("station_name"), F.col("region_code"), F.col("scheduled_ts").alias("scheduled_time_utc"),
            (F.col("train_cancelled") | F.col("cancelled")).alias("cancelled"),
            F.when(~F.col("train_cancelled") & ~F.col("cancelled"), F.col("delay_minutes")).cast("int").alias("delay_minutes"),
            "source_content_sha256", F.current_timestamp().alias("processed_at"), F.lit(run_id).alias("run_id"),
        )
    )
    return journeys, arrivals


def journey_fact(journeys: DataFrame) -> DataFrame:
    frame = journeys.withColumn("completed", F.col("final_delay_minutes").isNotNull())
    for threshold in THRESHOLDS:
        frame = frame.withColumn(f"on_time_{threshold}", F.col("completed") & (F.col("final_delay_minutes") <= threshold))
    return frame


def regional_daily(arrivals: DataFrame, thresholds: tuple[int, ...] = THRESHOLDS) -> DataFrame:
    """Additive date × region fact; threshold columns avoid fourfold denominator duplication."""
    train_region = arrivals.groupBy("departure_date", "region_code", "journey_key").agg(
        F.max("delay_minutes").alias("max_delay_minutes"),
        F.max(F.col("cancelled").cast("int")).alias("cancelled"),
    )
    return train_region.groupBy("departure_date", "region_code").agg(
        F.count("journey_key").alias("observed_trains"),
        F.sum(F.col("max_delay_minutes").isNotNull().cast("long")).alias("measured_trains"),
        F.sum("cancelled").cast("long").alias("cancelled_trains"),
        F.sum(F.coalesce("max_delay_minutes", F.lit(0))).cast("long").alias("delay_minutes_sum"),
        F.avg("max_delay_minutes").alias("average_delay_minutes"),
        F.sum((F.col("max_delay_minutes") > 15).cast("long")).alias("severe_delays"),
        *[
            F.sum((F.col("max_delay_minutes") > threshold).cast("long")).alias(f"delayed_{threshold}")
            for threshold in thresholds
        ],
    )


def rolling_regional_7d(regional: DataFrame, regions: DataFrame, window_end: str) -> DataFrame:
    """Build one complete seven-day Gold row per governed region, including no-service regions."""
    end = F.to_date(F.lit(window_end))
    filtered = regional.filter(
        (F.col("departure_date") >= F.date_sub(end, 6)) & (F.col("departure_date") <= end)
    )
    if filtered.select("departure_date").distinct().count() != 7:
        raise ValueError("rolling 7d Gold requires exactly seven complete daily partitions")
    metrics = filtered.groupBy("region_code").agg(
        *[
            F.sum(column).alias(column)
            for column in (
                "observed_trains", "measured_trains", "cancelled_trains", "delay_minutes_sum",
                "severe_delays", "delayed_5", "delayed_10", "delayed_15", "delayed_30",
            )
        ],
    )
    output = regions.join(metrics, "region_code", "left")
    count_columns = [
        "observed_trains", "measured_trains", "cancelled_trains", "delay_minutes_sum",
        "severe_delays", "delayed_5", "delayed_10", "delayed_15", "delayed_30",
    ]
    for column in count_columns:
        output = output.withColumn(column, F.coalesce(F.col(column), F.lit(0)).cast("long"))
    return (
        output.withColumn("component_partitions", F.lit(7))
        .withColumn("window_end", end)
        .withColumn("window_start", F.date_sub(end, 6))
        .withColumn("mode", F.lit("7d"))
        .withColumn("average_delay_minutes", F.when(F.col("measured_trains") > 0, F.col("delay_minutes_sum") / F.col("measured_trains")))
    )


def network_daily(facts: DataFrame) -> DataFrame:
    aggregations = [
        F.count("journey_key").alias("scheduled"), F.sum(F.col("completed").cast("long")).alias("completed"),
        F.sum(F.col("cancelled").cast("long")).alias("cancelled"), F.avg("final_delay_minutes").alias("average_delay_minutes"),
    ] + [F.sum(F.col(f"on_time_{threshold}").cast("long")).alias(f"on_time_{threshold}") for threshold in THRESHOLDS]
    return facts.groupBy("departure_date").agg(*aggregations)


def route_performance(facts: DataFrame) -> DataFrame:
    return facts.groupBy("route_key", "origin_code", "destination_code").agg(
        F.count("journey_key").alias("scheduled"), F.sum(F.col("completed").cast("long")).alias("completed"),
        F.sum(F.col("cancelled").cast("long")).alias("cancelled"), F.avg("final_delay_minutes").alias("average_delay_minutes"),
        *[F.sum(F.col(f"on_time_{threshold}").cast("long")).alias(f"on_time_{threshold}") for threshold in THRESHOLDS],
    )


def station_performance(arrivals: DataFrame) -> DataFrame:
    return arrivals.groupBy("station_code", "station_name", "region_code").agg(
        F.count("arrival_key").alias("observed_arrivals"), F.sum(F.col("delay_minutes").isNotNull().cast("long")).alias("measured_arrivals"),
        F.sum(F.col("cancelled").cast("long")).alias("cancelled_arrivals"), F.avg("delay_minutes").alias("average_delay_minutes"),
        *[F.sum((F.col("delay_minutes") <= threshold).cast("long")).alias(f"on_time_{threshold}") for threshold in THRESHOLDS],
    )
