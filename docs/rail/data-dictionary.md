# Analytical data dictionary

## `fact_train_journey`

| Column | Meaning |
| --- | --- |
| `journey_key` | Unique `departureDate:trainNumber` source key. |
| `departure_date` | Digitraffic date of the train's first departure. |
| `month` | Local Finnish departure month. |
| `weekday_number` | ISO-style Monday=1 through Sunday=7, in Finland local time. |
| `departure_hour` | First commercial scheduled departure hour, Finland local time. |
| `train_type` | Digitraffic train type such as IC, HL or S. |
| `train_category` | Included passenger category: Long-distance or Commuter. |
| `commuter_line` | Public commuter line identifier where present. |
| `route_key` | Canonical undirected origin/destination station-code pair. |
| `origin_code`, `destination_code` | First commercial departure and final commercial arrival codes. |
| `cancelled` | Whole-train cancellation indicator. |
| `partial_cancelled` | At least one commercial row cancelled while the whole train is not. |
| `final_arrival_cancelled` | Final passenger-arrival row cancelled; distinguished from a missing actual time. |
| `final_delay_minutes` | Digitraffic final arrival difference; null when unavailable/cancelled. |
| `departure_delay_minutes` | Delay at first commercial departure where available. |

## `fact_station_arrival`

Recommended Fabric Silver grain: one commercial, stopping arrival row. Keep journey key, station key, scheduled/actual/estimate timestamps, source delay, row cancellation, commercial track and quality flags. The public repository writes a smaller `agg_station_month.csv` because raw and full-grain derived datasets are intentionally excluded from Git.

## `fact_lahti_helsinki_weather`

| Column | Meaning |
| --- | --- |
| `journey_key` | Segment key including direction. |
| `direction` | Lahti → Helsinki or Helsinki → Lahti. |
| `scheduled_departure_utc` | Segment departure used for temporal matching. |
| `weather_origin_code` | `LH` or `HKI`; weather is measured at the departure side. |
| `temperature_c` | FMI hourly air temperature. |
| `precipitation_mm_h` | FMI hourly precipitation value. |
| `wind_speed_ms` | FMI 10-minute wind-speed observation exposed in the hourly sample. |
| `visibility_m` | FMI visibility observation in metres. |
| `arrival_delay_minutes` | Delay at the segment destination. |
| `cancelled` | Whole-train or segment-end cancellation. |

## Dimensions

- `dim_date`: one local calendar date with month, weekday, ISO week, quarter and season.
- `dim_station`: station code, UIC code, source name, passenger-traffic flag, type, latitude and longitude. Public station comparisons use only Finnish rows where `passengerTraffic=true`.
- `dim_route`: canonical route key, endpoint station keys and display label.
- `dim_train_service`: train type, category and commuter line.
- `delay_threshold`: disconnected rows 5, 10, 15 and 30 used by the Power BI measure.

## Regional monitoring API

`RailRegionMetric` has one record per official region and snapshot window. `observedTrains`, `measuredTrains`, `averageDelayMinutes`, `severeDelays`, `cancellations` and `cancellationShare` follow the definitions in `monitoring.md`.

- `delayedTrainsByThreshold` / `delayedShareByThreshold`: keyed by `5`, `10`, `15`, `30`; a delay must be strictly greater than the key.
- `disruptionScoreByThreshold` / `reliabilityScoreByThreshold` / `statusByThreshold`: score/state under each policy threshold; serious-share remains fixed at `>15`.
- `problemStationsByThreshold` / `problemRoutesByThreshold`: top five exceptions ranked by fixed serious count, cancellations, selected-threshold delayed count and average delay.
- legacy scalar fields without `ByThreshold` remain aliases for the 5-minute view.
- Åland has `hasRailService=false`, `statusByThreshold=no-service` and null scores for every threshold.
- `sampleSupport` carries status, measured/observed counts, measurement coverage, mode minimum and policy version; it does not modify operational status.
- `delayedShareInterval95ByThreshold` is the 95% Wilson interval for each delayed proportion, never a composite-score interval.
- snapshot provenance includes `sourceRetrievedAt`, `validatedAt`, `goldPublishedAt`, `latestCompletePartition`, `coverage` and `freshness`.

## Regional semantic Gold

- `dim_region`: all 19 official 2026 regions, multilingual names, mapping source and `has_rail_service`.
- `bridge_station_region`: one active mapping per `region_year:station_code`, linked to the governed Statistics Finland region vintage.
- `mart_regional_performance_daily`: one date × region additive row with observed/measured/cancelled, delay sum, serious `>15`, and `delayed_5/10/15/30` counts.
- `mart_regional_performance_7d`: one complete window end × region, exactly seven component partitions, the same additive measures, and 19 rows including Åland zeros.
