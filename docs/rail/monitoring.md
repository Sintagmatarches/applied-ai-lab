# Finland Rail Monitoring System

## Operational question

The first screen answers one question: where is Finland's passenger-rail network operating normally now, and where are delays or cancellations concentrated? It preserves the existing route, station, calendar, weather and Lahti–Helsinki historical analysis below the new regional view.

## Sources and spatial join

- Train schedules, actual times, live estimates, cancellations, the `runningCurrently` flag and station coordinates come from Fintraffic / Digitraffic Railway API.
- Region polygons are the 2026 `maakunta1000k` WFS layer from Statistics Finland, requested as GeoJSON in EPSG:4326.
- `python -m rail.build_regions --refresh-stations` validates that the layer contains 19 features, fetches current official station metadata, simplifies only geometry presentation, and assigns every Finnish station coordinate against the unsimplified official polygon with a hole-aware point-in-polygon test. Omitting the flag deliberately reuses the cached metadata snapshot for offline reproduction.
- Passenger monitoring accepts only commercial stopping rows at Finnish stations where Digitraffic metadata says `passengerTraffic=true`. Depots, junctions and service locations cannot create a regional passenger observation.

The committed lookup has 552 Finnish stations, including 209 passenger stations. All passenger stations match exactly one region. Åland has none and therefore has `No rail service`, not a reliability classification. The raw metadata response also includes 11 non-Finnish stations, which are outside the map contract.

## Time modes

`LIVE` calls `/api/v1/live-trains`, refreshes the UI once a minute and uses timetable rows scheduled in the 90 minutes before or after retrieval. For a train marked `runningCurrently`, the nearest previous and next passenger stops are retained even when the train's delay moved them outside the normal window. Current Digitraffic estimates are allowed in this view and are explicitly mutable.

`24 HOURS` requests the current and previous Digitraffic departure-date partitions, de-duplicates `(departureDate, trainNumber)`, and then applies an exact rolling 24-hour filter. Only actual times count as measured timing in this completed/recent view. The regional response is cached for 15 minutes at the edge.

`HISTORICAL` is a committed snapshot covering 1 August 2025 through 31 July 2026. `python -m rail.build_regional_history` rebuilds it from all 365 cached daily source partitions. It is clearly dated in the UI and never substituted for failed live data.

A dynamic seven-day view is intentionally omitted from the current serverless implementation. Digitraffic returns roughly 19 MB of compressed JSON for one busy departure day, so fetching and parsing seven full partitions on demand would create an unsafe public edge workload. Persistent incremental storage in the documented Fabric target is the correct base-level implementation for that window.

## Regional grain and metrics

The grain is one unique passenger train per region per selected window. Multiple commercial stops by the same train in one region do not inflate the observed-train count. A train that crosses regions contributes once to each affected region, so national totals are labelled regional train observations rather than unique trains.

For a train-region observation:

- regional delay is the maximum known actual delay (or current estimate in `LIVE`) among qualifying regional stops;
- delayed means more than the user-selected 5, 10, 15 or 30 whole minutes; the API and historical artifact carry all four counts/shares in one snapshot so switching does not refetch the source;
- serious means more than 15 whole minutes;
- a train-level cancellation or cancelled qualifying row marks the regional observation cancelled;
- cancelled and unobserved trains are not included in the measured-delay denominator;
- missing actual/current estimate is not converted to zero and yields `No current observations` if a region has no measured or cancelled train.

The Disruption Score is transparent and bounded from 0 (best) to 100 (worst):

```text
45 × selected-threshold delayed share
+ 25 × serious-delay share
+ 20 × cancellation share
+ 10 × min(max(average delay, 0) / 30, 1)
```

Reliability Score is `100 - Disruption Score`. Map status thresholds are normal below 10, elevated from 10 through 24.9, and serious from 25. The selected delay policy can therefore change the map score/status, while the `>15` serious-event count remains fixed. These project-defined thresholds make a rapidly readable operating picture; they are not official Fintraffic classifications or passenger-weighted service levels.

## Failure handling and caching

Live and 24-hour API errors return HTTP 502 with `no-store`. The browser shows an explicit unavailable message and never manufactures or relabels historical data as live. The last successful in-session snapshot may remain visible while a background refresh fails. Map geometry is a versioned public asset derived from the official source. LIVE responses use a one-minute edge cache with stale-while-revalidate; 24-hour responses use 15 minutes; the immutable historical snapshot uses one day.

## Limitations

- Metrics count trains, not passengers or seat capacity.
- A train crossing regions appears in multiple regional counts; regional totals are not unique national trains.
- A route label uses the first and final passenger endpoints of the full train, even when the selected region covers an intermediate segment.
- Current estimates can be revised, and cancellation status can change.
- Delay cause codes and infrastructure incidents are not yet complete enough in this implementation to claim causality.
- The public runtime has no durable seven-day event store. That period belongs in the incremental Fabric/Lakehouse path rather than an expensive on-demand workaround.
- Comparing scores across screenshots requires the same delay threshold; the UI exposes the active policy to prevent an unlabeled comparison.
