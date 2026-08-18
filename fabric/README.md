# Microsoft Fabric implementation

This directory contains an import-ready engineering design for moving the reproducible public Python pipeline into Microsoft Fabric. It is deliberately not labelled as deployed: a Fabric tenant, capacity, workspace and Lakehouse connection are external requirements unavailable to this repository environment.

> **Portfolio simulation.** The workspace roles and delivery workflow are simulated. Notebook source, partition quality gates and pipeline contract are real repository artifacts; tenant execution is not claimed.

Use [`pipeline-spec.md`](pipeline-spec.md) for parameters, activity dependencies, watermark/idempotency, quality gates, audit schema, Dev/Test/Prod promotion and recovery. Use [`docs/manual-tasks/fabric.md`](../docs/manual-tasks/fabric.md) for the remaining credentialed actions.

## Workspace objects

Create these objects in one Fabric workspace:

1. Lakehouse `lh_finland_rail`.
2. Notebook from `notebooks/01_ingest_digitraffic.py`.
3. Notebook from `notebooks/02_transform_quality.py`.
4. Data Factory pipeline `pl_finland_rail_daily` with parameters `p_start_date`, `p_end_date`, `p_refresh_recent_days`.
5. Direct Lake semantic model using the measures and relationships in `../power-bi/`.

The daily pipeline should calculate yesterday in `Europe/Helsinki`, call ingestion for yesterday and the preceding three dates, then call transformation only after acquisition succeeds. Use retry/backoff at the activity level and send failure notifications; do not advance the watermark on a partial run.

After importing each source file as a Fabric notebook, mark the cell containing `p_start_date` and `p_end_date` as the notebook's parameter cell. Fabric's Notebook activity then discovers those base parameters for pipeline execution.

## Lakehouse layers

- `Files/rail/bronze/digitraffic/departure_date=YYYY-MM-DD/trains.json.gz`
- `Files/rail/bronze/fmi/place=Helsinki|Lahti/week_start=YYYY-MM-DD/observations.xml.gz`
- `Tables/rail_silver_train_journey`
- `Tables/rail_silver_station_arrival`
- `Tables/rail_silver_weather_observation`
- `Tables/rail_gold_fact_train_journey`
- `Tables/rail_gold_fact_station_arrival`
- `Tables/rail_gold_fact_lahti_helsinki_weather`
- `Tables/rail_gold_dim_date`, `rail_gold_dim_station`, `rail_gold_dim_route`
- `Tables/rail_control_ingestion`

## Required external configuration

- Fabric capacity and a workspace where the owner can create Lakehouse, Notebook, Pipeline and Semantic Model items.
- Lakehouse attached to both notebooks; replace the documented `abfss://` placeholder only if the default attached-Lakehouse path is not used.
- Pipeline schedule and owner/failure notification.
- Power BI credentials/permissions and optional app workspace for sharing.
- A deliberate sharing decision. `Publish to web` is not required and should not be enabled casually because it makes the report and its data publicly accessible.

The public Applied AI Lab page is the safe interactive delivery until a tenant-controlled Power BI report is configured. If an approved public embed is later available, add its URL through a reviewed application configuration rather than committing a token or secret.

## Official implementation references

- [Develop, execute and parameterize Fabric notebooks](https://learn.microsoft.com/en-us/fabric/data-engineering/author-execute-notebook)
- [Run a notebook from a Data Factory pipeline](https://learn.microsoft.com/en-us/fabric/data-factory/notebook-activity)
- [Direct Lake semantic-model overview](https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-overview)
- [Fabric notebook source control and deployment](https://learn.microsoft.com/en-us/fabric/data-engineering/notebook-source-control-deployment)
