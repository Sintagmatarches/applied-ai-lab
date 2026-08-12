# Railway monitoring and reliability methodology

The live regional monitoring definitions, spatial join, score formula, time modes and runtime failure policy are documented separately in [`monitoring.md`](monitoring.md). The historical definitions below remain unchanged.

## Question and coverage

The monitor asks how reliably Finnish passenger trains reach commercial stops and final destinations, where delay rates are concentrated, and how the direct Lahti–Helsinki segment behaves. The committed public snapshot covers 1 August 2025 through 31 July 2026: twelve fully completed operating months retrieved from the official Fintraffic / Digitraffic railway API.

The primary population is trains whose `trainCategory` is `Long-distance` or `Commuter`. Freight, locomotive, test, shunting and maintenance traffic are excluded.

## Analytical grains

- **Train journey:** one unique `(departureDate, trainNumber)`, from its first commercial departure to its final commercial arrival at Finnish stations marked `passengerTraffic=true` in official metadata.
- **Station arrival:** one commercial, stopping `ARRIVAL` timetable row at a Finnish passenger station. Depot/service locations are excluded before aggregation.
- **Lahti–Helsinki service:** one train calling at both `LH` and `HKI` in a valid order, measured between the departure row at the origin city and arrival row at the destination city. The train may continue beyond either city; no transfer journeys are inferred.
- **Weather match:** the nearest hourly FMI observation to the scheduled segment departure, at the departure city, within 45 minutes.

## Reliability definitions

The default “on-time” definition is a completed final commercial arrival no more than five whole minutes after `scheduledTime`. Early arrivals count as on time. The interface also exposes 10-, 15- and 30-minute thresholds; the denominator is always journeys with a recorded final actual arrival.

Whole-train cancellation uses Digitraffic's train-level `cancelled` field. A non-cancelled train with a cancelled commercial row is counted separately as a partial cancellation. Cancellation rates use scheduled journeys as the denominator.

Missing final `actualTime` is never converted to zero delay and is not counted as on time. It is reported as a data-quality rate. Digitraffic's `differenceInMinutes` is used when present; the pipeline independently compares it with the difference between actual and scheduled timestamps and records discrepancies over one minute.

## Routes, stations and consistency

End-to-end routes combine both directions under a canonical station-code pair. Route tables require at least 200 scheduled trains in the snapshot. Station comparisons require at least 500 scheduled commercial arrivals. These floors reduce rankings driven by tiny samples but do not make unlike service patterns fully comparable.

“Unreliable months” is the share of observed months in which no more than 90% of completed arrivals were within five minutes. It distinguishes persistent underperformance from a small number of extreme incidents. It is descriptive and is not a service-level agreement.

## Weather scope

Weather is intentionally limited to the Lahti–Helsinki profile. FMI hourly observations requested for Helsinki and Lahti are joined by scheduled departure time. Displayed conditions are:

- freezing temperature at or below 0 °C;
- precipitation of at least 0.2 mm in the reported hourly observation;
- visibility below 5 km;
- wind speed at or above 10 m/s;
- none of those selected conditions.

Condition groups can overlap. The comparison is unadjusted for season, infrastructure work, incidents, train type or traffic volume. It demonstrates a reproducible association study and must not be interpreted as a causal weather effect.

## Data-quality treatment

The run audits duplicate train keys, missing route endpoints, missing scheduled departure, missing final actual arrival, unknown station codes, delays over 12 hours, and reported-versus-calculated delay mismatches. No missing actual is imputed. Extreme values remain in counts and percentile calculations unless the source record is structurally invalid; they are surfaced for review rather than silently winsorized.

The historical endpoint is called with its default `include_deleted=false`. Digitraffic describes deleted trains as trains cancelled ten days before departure; they are outside the committed snapshot. This means the reported cancellation rate is not a complete measure of all services withdrawn far in advance.

## Limitations

- Results count trains, not passengers; every service has equal weight.
- Final-destination reliability and intermediate-station reliability answer different questions.
- Combining route directions can hide directional differences; the local Lahti–Helsinki profile keeps directions separate.
- Timetable and actual data can be revised after the first retrieval, hence the recommended rolling three-day refresh in Fabric.
- Cause codes are not analysed because completeness must be assessed separately before causal or operational conclusions are presented.
- The snapshot covers one recent year, so it supports seasonal comparison inside that year but not a long-run trend claim.

## Attribution

Railway source: Fintraffic / digitraffic.fi, licensed under Creative Commons Attribution 4.0. The project transforms the source into analytical journey, station, route and time aggregates.

Weather source: Finnish Meteorological Institute open data, licensed under Creative Commons Attribution 4.0.
