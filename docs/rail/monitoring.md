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

`7 DAYS` resolves the stable manifest on the dedicated `rail-publications` branch, verifies the immutable snapshot SHA-256 and contract, then serves exactly seven validated, completed daily partitions. It never fans seven large source requests out from the public edge and does not require a website rebuild after the daily pipeline. The UI exposes remote-vs-fallback provenance, source/validation/Gold timestamps, latest complete partition and coverage count.

`HISTORICAL` is a committed snapshot covering 1 August 2025 through 31 July 2026. `python -m rail.build_regional_history` rebuilds it from all 365 cached daily source partitions. It is clearly dated in the UI and never substituted for failed live data.

The serverless API reads only a compact governed artifact. The executable Spark/Delta path persists daily and rolling Gold tables; the publication builder reconciles the same seven validated source partitions before an atomic branch update. This keeps raw payloads and large on-demand parsing outside the edge runtime.

## Sample support, uncertainty and freshness

Operational state and analytical support are separate. A region can be operationally normal/elevated/serious and still carry `Low sample`. Support requires mode-specific measured counts (8/20/100/400) and 80% measurement coverage, calibrated against the committed 365-day regional distribution. `No data` means a rail-served region has no observations; `No rail service` is a domain fact (Åland). The displayed 95% Wilson interval belongs only to the selected delayed share.

Freshness states are `fresh`, `warning`, `stale` and historical `not-applicable`. `LIVE` uses source retrieval (5/15 minutes), `24 HOURS` validation (30/120 minutes), and `7 DAYS` successful Gold publication (36/60 hours). Incomplete coverage is always stale even if a process recently ran.

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

Live and 24-hour API errors return HTTP 502 with `no-store`. The browser shows an explicit unavailable message and never manufactures or relabels historical data as live. The last successful in-session snapshot may remain visible while a background refresh fails. For `7 DAYS`, remote publication failure serves the validated bundled last-known-good snapshot with an explicit warning and forced `stale` state; it is never reported as fresh. Map geometry is a versioned public asset derived from the official source. LIVE responses use a one-minute edge cache with stale-while-revalidate; the remote 7-day publication uses a five-minute application/edge cache; fallback uses one minute; the immutable historical snapshot uses one day.

## Limitations

- Metrics count trains, not passengers or seat capacity.
- A train crossing regions appears in multiple regional counts; regional totals are not unique national trains.
- A route label uses the first and final passenger endpoints of the full train, even when the selected region covers an intermediate segment.
- Current estimates can be revised, and cancellation status can change.
- Delay cause codes and infrastructure incidents are not yet complete enough in this implementation to claim causality.
- The public runtime consumes the compact seven-day publication; raw event retention and the Delta transaction log remain in the pipeline runtime, not in Git.
- Comparing scores across screenshots requires the same delay threshold; the UI exposes the active policy to prevent an unlabeled comparison.
