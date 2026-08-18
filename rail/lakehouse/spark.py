from __future__ import annotations

from pathlib import Path


def build_spark(app_name: str = "finland-rail-lakehouse", master: str | None = None):
    """Create a Delta-enabled Spark session for local, CI, Fabric, or Databricks use."""
    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession

    active = SparkSession.getActiveSession()
    if active is not None:
        return active
    builder = SparkSession.builder.appName(app_name)
    if master:
        builder = builder.master(master)
    builder = (
        builder.config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.databricks.delta.schema.autoMerge.enabled", "true")
        .config("spark.ui.enabled", "false")
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()


def delta_exists(spark, path: Path) -> bool:
    from delta.tables import DeltaTable

    return path.exists() and DeltaTable.isDeltaTable(spark, str(path))


def replace_partitions(frame, path: Path, partition: str, values: list[str]) -> None:
    """Atomically replace only selected partitions; never rewrite unaffected history."""
    if not values:
        return
    predicate = " OR ".join(f"{partition} = '{value}'" for value in sorted(set(values)))
    writer = frame.write.format("delta").mode("overwrite").option("replaceWhere", predicate)
    if not (path / "_delta_log").exists():
        writer = writer.partitionBy(partition)
    writer.save(str(path))
