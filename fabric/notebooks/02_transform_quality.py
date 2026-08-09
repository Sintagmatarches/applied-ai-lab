# Fabric notebook source
# Attach Lakehouse: lh_finland_rail

from pyspark.sql import functions as F
from pyspark.sql.window import Window


p_start_date = "2025-08-01"
p_end_date = "2025-08-01"

train_paths = [
    row.bronze_path
    for row in (
        spark.table("rail_control_ingestion")
        .where(F.col("source") == "digitraffic_trains")
        .where((F.col("partition_date") >= p_start_date) & (F.col("partition_date") <= p_end_date))
        .where(F.col("status") == "complete")
        .select("partition_date", "bronze_path")
        .dropDuplicates(["partition_date"])
        .collect()
    )
]
if not train_paths:
    raise RuntimeError("No completed Bronze partitions found for the requested dates")

train_paths = [f"/lakehouse/default/{path}" for path in train_paths]
trains = spark.read.option("multiline", True).json(train_paths)
passenger = trains.where(F.col("trainCategory").isin("Long-distance", "Commuter"))

station_metadata_path = (
    spark.table("rail_control_ingestion")
    .where((F.col("source") == "digitraffic_stations") & (F.col("status") == "complete"))
    .orderBy(F.col("retrieved_at").desc())
    .select("bronze_path")
    .first()
)
if station_metadata_path is None:
    raise RuntimeError("No completed Digitraffic station metadata snapshot found")

stations = spark.read.option("multiline", True).json(
    f"/lakehouse/default/{station_metadata_path.bronze_path}"
)
passenger_stations = (
    stations.where((F.col("passengerTraffic") == True) & (F.col("countryCode") == "FI"))
    .select(F.col("stationShortCode").alias("passenger_station_code"))
    .dropDuplicates()
)

duplicate_keys = (
    passenger.groupBy("departureDate", "trainNumber")
    .count()
    .where(F.col("count") > 1)
    .count()
)
if duplicate_keys:
    raise RuntimeError(f"Duplicate departureDate/trainNumber keys: {duplicate_keys}")

rows = (
    passenger
    .select(
        "departureDate",
        "trainNumber",
        "trainType",
        "trainCategory",
        "commuterLineID",
        F.col("cancelled").alias("train_cancelled"),
        F.posexplode("timeTableRows").alias("row_index", "row"),
    )
    .where((F.col("row.commercialStop") == True) & (F.col("row.trainStopping") == True))
    .join(
        F.broadcast(passenger_stations),
        F.col("row.stationShortCode") == F.col("passenger_station_code"),
        "inner",
    )
    .drop("passenger_station_code")
)

station_arrival = (
    rows.where(F.col("row.type") == "ARRIVAL")
    .select(
        F.concat_ws(":", "departureDate", "trainNumber").alias("journey_key"),
        "departureDate",
        "trainNumber",
        F.col("row.stationShortCode").alias("station_code"),
        F.to_timestamp("row.scheduledTime").alias("scheduled_time_utc"),
        F.to_timestamp("row.actualTime").alias("actual_time_utc"),
        F.col("row.differenceInMinutes").cast("int").alias("delay_minutes"),
        (F.col("train_cancelled") | F.col("row.cancelled")).alias("cancelled"),
        "row_index",
    )
)

departures = rows.where(F.col("row.type") == "DEPARTURE")
first_departure = (
    departures.withColumn("rank", F.row_number().over(
        Window.partitionBy("departureDate", "trainNumber").orderBy("row_index")
    ))
    .where(F.col("rank") == 1)
)
final_arrival = (
    rows.where(F.col("row.type") == "ARRIVAL")
    .withColumn("rank", F.row_number().over(
        Window.partitionBy("departureDate", "trainNumber").orderBy(F.col("row_index").desc())
    ))
    .where(F.col("rank") == 1)
)

journey = (
    first_departure.alias("d")
    .join(final_arrival.alias("a"), ["departureDate", "trainNumber"], "inner")
    .select(
        F.concat_ws(":", "departureDate", "trainNumber").alias("journey_key"),
        "departureDate",
        "trainNumber",
        F.col("d.trainType").alias("train_type"),
        F.col("d.trainCategory").alias("train_category"),
        F.col("d.commuterLineID").alias("commuter_line"),
        F.col("d.row.stationShortCode").alias("origin_code"),
        F.col("a.row.stationShortCode").alias("destination_code"),
        F.to_timestamp("d.row.scheduledTime").alias("scheduled_departure_utc"),
        F.col("a.row.differenceInMinutes").cast("int").alias("final_delay_minutes"),
        F.col("d.row.differenceInMinutes").cast("int").alias("departure_delay_minutes"),
        F.col("d.train_cancelled").alias("cancelled"),
    )
    .withColumn("local_departure", F.from_utc_timestamp("scheduled_departure_utc", "Europe/Helsinki"))
    .withColumn("local_date", F.to_date("local_departure"))
    .withColumn("departure_hour", F.hour("local_departure"))
    .withColumn("route_key", F.concat_ws("--", F.array_sort(F.array("origin_code", "destination_code"))))
)

missing_endpoints = journey.where(F.col("origin_code").isNull() | F.col("destination_code").isNull()).count()
if missing_endpoints:
    raise RuntimeError(f"Journeys without route endpoints: {missing_endpoints}")

for frame, table in (
    (journey, "rail_silver_train_journey"),
    (station_arrival, "rail_silver_station_arrival"),
):
    (
        frame.write.format("delta")
        .mode("overwrite")
        .option("replaceWhere", f"departureDate >= '{p_start_date}' AND departureDate <= '{p_end_date}'")
        .saveAsTable(table)
    )

(
    stations.where((F.col("passengerTraffic") == True) & (F.col("countryCode") == "FI"))
    .write.format("delta")
    .mode("overwrite")
    .saveAsTable("rail_silver_station")
)

# Gold tables retain stable grains and additive flags for Direct Lake measures.
gold_journey = (
    spark.table("rail_silver_train_journey")
    .withColumn("completed", (~F.col("cancelled") & F.col("final_delay_minutes").isNotNull()).cast("int"))
    .withColumn("on_time_5", (~F.col("cancelled") & (F.col("final_delay_minutes") <= 5)).cast("int"))
    .withColumn("on_time_10", (~F.col("cancelled") & (F.col("final_delay_minutes") <= 10)).cast("int"))
    .withColumn("on_time_15", (~F.col("cancelled") & (F.col("final_delay_minutes") <= 15)).cast("int"))
    .withColumn("on_time_30", (~F.col("cancelled") & (F.col("final_delay_minutes") <= 30)).cast("int"))
)
gold_journey.write.format("delta").mode("overwrite").saveAsTable("rail_gold_fact_train_journey")
