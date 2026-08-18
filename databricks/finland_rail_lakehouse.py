# Databricks notebook source
# MAGIC %md
# MAGIC # Finland Rail incremental Lakehouse
# MAGIC Run from a Databricks Git folder containing this repository. The notebook reuses the active Databricks Spark/Delta session and calls the same orchestrator used locally and in CI.

# COMMAND ----------

dbutils.widgets.text("start_date", "2026-07-31")
dbutils.widgets.text("end_date", "2026-07-31")
dbutils.widgets.text("source_cache", "/Volumes/main/default/finland_rail/source")
dbutils.widgets.text("lakehouse", "/Volumes/main/default/finland_rail/lakehouse")
dbutils.widgets.dropdown("refresh_source", "false", ["false", "true"])
dbutils.widgets.dropdown("force_transform", "false", ["false", "true"])

# COMMAND ----------

from rail.lakehouse.orchestrate import main

arguments = [
    "--start", dbutils.widgets.get("start_date"),
    "--end", dbutils.widgets.get("end_date"),
    "--source-cache", dbutils.widgets.get("source_cache"),
    "--lakehouse", dbutils.widgets.get("lakehouse"),
]
if dbutils.widgets.get("refresh_source") == "true":
    arguments.append("--refresh-source")
if dbutils.widgets.get("force_transform") == "true":
    arguments.append("--force-transform")

exit_code = main(arguments)
if exit_code:
    raise RuntimeError(f"Finland Rail Lakehouse failed with exit code {exit_code}")
