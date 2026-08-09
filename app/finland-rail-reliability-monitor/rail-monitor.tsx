"use client";

import { useEffect, useMemo, useState } from "react";
import type { LiveRailService } from "../../lib/rail-live";

type Reliability = {
  scheduled: number;
  completed: number;
  cancelled: number;
  cancelled_rate: number | null;
  completion_rate: number | null;
  on_time: Record<string, { count: number; rate: number | null }>;
  median_delay_minutes: number | null;
  p90_delay_minutes: number | null;
  p95_delay_minutes: number | null;
  mean_delay_minutes: number | null;
};

type RailSummary = {
  meta: {
    coverage_start: string;
    coverage_end: string;
    retrieved_at: string;
    coverage_days: number;
    available_thresholds_minutes: number[];
  };
  overall: Reliability & {
    partial_cancelled: number;
    partial_cancelled_rate: number | null;
    missing_final_actual: number;
    missing_final_actual_rate: number | null;
    delay_distribution: Array<{ label: string; count: number }>;
  };
  monthly: Array<{ month: string } & Reliability>;
  weekday: Array<{ weekday: string; weekday_number: number } & Reliability>;
  hour: Array<{ hour: number } & Reliability>;
  train_types: Array<{ train_type: string } & Reliability>;
  routes: Array<
    {
      route_key: string;
      route: string;
      monthly_on_time_5_stddev: number;
      unreliable_month_share: number | null;
    } & Reliability
  >;
  stations: Array<{ station_code: string; station: string } & Reliability>;
  lahti_helsinki: {
    overall: Reliability & {
      median_delay_change_minutes: number | null;
      share_gaining_over_5_minutes: number | null;
    };
    directions: Array<
      { direction: string; median_delay_change_minutes: number | null } & Reliability
    >;
    monthly: Array<{ month: string } & Reliability>;
    time_of_day: Array<{ period: string } & Reliability>;
    weather: {
      matched_journeys?: number;
      conditions?: Array<{ condition: string } & Reliability>;
      observation_locations?: Record<
        string,
        { requested_place: string; latitude: number; longitude: number; observations: number }
      >;
      status?: string;
    };
  };
};

type LiveResponse = {
  retrievedAt: string;
  source: string;
  sourceUrl: string;
  services: LiveRailService[];
};

function percent(value: number | null | undefined, digits = 1) {
  return value == null ? "—" : `${(value * 100).toFixed(digits)}%`;
}

function number(value: number) {
  return value.toLocaleString("en-FI");
}

function monthLabel(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", year: "2-digit" }).format(
    new Date(`${value}-01T00:00:00Z`),
  );
}

function localTime(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-FI", {
    timeZone: "Europe/Helsinki",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function reliabilityRate(item: Reliability, threshold: number) {
  return item.on_time[String(threshold)]?.rate ?? null;
}

function RateBars({
  rows,
  threshold,
  label,
}: {
  rows: Array<{ key: string; label: string; value: number | null; detail: string }>;
  threshold: number;
  label: string;
}) {
  return (
    <div className="rail-bars" aria-label={label}>
      {rows.map((row) => (
        <div className="rail-bar-row" key={row.key}>
          <div className="rail-bar-label">
            <span>{row.label}</span>
            <small>{row.detail}</small>
          </div>
          <div className="rail-bar-track" aria-hidden="true">
            <span style={{ width: `${Math.max(0, Math.min(100, (row.value ?? 0) * 100))}%` }} />
          </div>
          <strong>{percent(row.value)}</strong>
        </div>
      ))}
      <p className="chart-caption">Share arriving within {threshold} minutes of schedule.</p>
    </div>
  );
}

function ThresholdControl({
  thresholds,
  value,
  onChange,
}: {
  thresholds: number[];
  value: number;
  onChange: (threshold: number) => void;
}) {
  return (
    <fieldset className="threshold-control">
      <legend>Arrival threshold</legend>
      <div>
        {thresholds.map((threshold) => (
          <button
            type="button"
            key={threshold}
            className={threshold === value ? "is-selected" : ""}
            aria-pressed={threshold === value}
            onClick={() => onChange(threshold)}
          >
            ≤ {threshold} min
          </button>
        ))}
      </div>
    </fieldset>
  );
}

function LiveServices() {
  const [data, setData] = useState<LiveResponse | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/rail/live", { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("live service unavailable");
        setData((await response.json()) as LiveResponse);
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          setUnavailable(true);
        }
      });
    return () => controller.abort();
  }, []);

  if (unavailable) {
    return (
      <p className="live-unavailable" role="status">
        Recent service data is temporarily unavailable. Historical analysis remains available below.
      </p>
    );
  }
  if (!data) {
    return <p className="live-loading" role="status">Checking Digitraffic for recent direct services…</p>;
  }
  const snapshotTime = new Date(data.retrievedAt).getTime();
  const recent = data.services
    .filter((service) => service.status !== "scheduled" || new Date(service.scheduledDeparture).getTime() >= snapshotTime - 3 * 60 * 60 * 1000)
    .slice(0, 8);
  return (
    <div>
      <div className="live-service-grid">
        {recent.length ? recent.map((service) => (
          <article className="live-service" key={service.key}>
            <div>
              <strong>{service.service}</strong>
              <span>{service.direction}</span>
            </div>
            <div>
              <small>Departure</small>
              <strong>{localTime(service.scheduledDeparture)}</strong>
            </div>
            <div>
              <small>{service.status === "arrived" ? "Arrived" : "Expected arrival"}</small>
              <strong>{localTime(service.expectedArrival)}</strong>
            </div>
            <span className={`service-status status-${service.status}`}>
              {service.status === "cancelled"
                ? "Cancelled"
                : service.arrivalDelayMinutes == null
                  ? service.status
                  : `${service.arrivalDelayMinutes > 0 ? "+" : ""}${service.arrivalDelayMinutes} min`}
            </span>
          </article>
        )) : (
          <p className="live-unavailable">No recent direct services were returned by Digitraffic.</p>
        )}
      </div>
      <p className="live-source-note">
        Operational snapshot retrieved {localTime(data.retrievedAt)}. Estimates can be revised; this is not a journey planner.
      </p>
    </div>
  );
}

export function RailMonitor({ summary }: { summary: RailSummary }) {
  const [threshold, setThreshold] = useState(5);
  const [routeSort, setRouteSort] = useState<"volume" | "reliability">("reliability");
  const routes = useMemo(() => {
    const copy = [...summary.routes];
    return copy
      .sort((left, right) =>
        routeSort === "volume"
          ? right.completed - left.completed
          : (reliabilityRate(right, threshold) ?? -1) -
            (reliabilityRate(left, threshold) ?? -1),
      )
      .slice(0, 12);
  }, [routeSort, summary.routes, threshold]);
  const stationRows = useMemo(
    () =>
      [...summary.stations]
        .sort(
          (left, right) =>
            (reliabilityRate(left, threshold) ?? 1) -
            (reliabilityRate(right, threshold) ?? 1),
        )
        .slice(0, 12),
    [summary.stations, threshold],
  );
  const maxDistribution = Math.max(
    ...summary.overall.delay_distribution.map((item) => item.count),
  );
  const weatherConditions = summary.lahti_helsinki.weather.conditions ?? [];
  const timePeriods = [
    { label: "00–05", start: 0, end: 5 },
    { label: "06–09", start: 6, end: 9 },
    { label: "10–15", start: 10, end: 15 },
    { label: "16–19", start: 16, end: 19 },
    { label: "20–23", start: 20, end: 23 },
  ].map((period) => {
    const hours = summary.hour.filter(
      (item) => item.hour >= period.start && item.hour <= period.end,
    );
    const completed = hours.reduce((total, item) => total + item.completed, 0);
    const onTime = hours.reduce(
      (total, item) => total + (item.on_time[String(threshold)]?.count ?? 0),
      0,
    );
    return {
      key: period.label,
      label: period.label,
      value: completed ? onTime / completed : null,
      detail: `${number(completed)} arrivals`,
    };
  });

  return (
    <>
      <section className="rail-control-panel" aria-labelledby="network-title">
        <div>
          <p className="eyebrow">Historical network view</p>
          <h2 id="network-title">Reliability depends on the threshold</h2>
          <p>
            There is no universal definition of “on time”. Change the allowed arrival delay and every rate below recalculates from the same completed journeys.
          </p>
        </div>
        <ThresholdControl
          thresholds={summary.meta.available_thresholds_minutes}
          value={threshold}
          onChange={setThreshold}
        />
      </section>

      <dl className="rail-kpi-grid" aria-label="Network reliability metrics">
        <div>
          <dt>Arrived within {threshold} min</dt>
          <dd>{percent(reliabilityRate(summary.overall, threshold))}</dd>
          <small>{number(summary.overall.on_time[String(threshold)].count)} of {number(summary.overall.completed)} completed</small>
        </div>
        <div>
          <dt>Whole-train cancellations</dt>
          <dd>{percent(summary.overall.cancelled_rate, 2)}</dd>
          <small>{number(summary.overall.cancelled)} of {number(summary.overall.scheduled)} scheduled</small>
        </div>
        <div>
          <dt>Typical final delay</dt>
          <dd>{summary.overall.median_delay_minutes?.toFixed(1)} min</dd>
          <small>90th percentile: {summary.overall.p90_delay_minutes?.toFixed(1)} min</small>
        </div>
        <div>
          <dt>Measured journeys</dt>
          <dd>{number(summary.overall.completed)}</dd>
          <small>{summary.meta.coverage_days} complete operating days</small>
        </div>
      </dl>

      <section className="rail-analysis-grid" aria-label="Time pattern analysis">
        <article className="rail-panel rail-panel-wide">
          <div className="rail-panel-heading">
            <div>
              <p className="eyebrow">Trend</p>
              <h2>Month by month</h2>
            </div>
            <span>{summary.meta.coverage_start} → {summary.meta.coverage_end}</span>
          </div>
          <RateBars
            threshold={threshold}
            label="Monthly on-time arrival rates"
            rows={summary.monthly.map((item) => ({
              key: item.month,
              label: monthLabel(item.month),
              value: reliabilityRate(item, threshold),
              detail: `${number(item.completed)} arrivals`,
            }))}
          />
        </article>

        <article className="rail-panel">
          <div className="rail-panel-heading">
            <div>
              <p className="eyebrow">Calendar</p>
              <h2>Day of week</h2>
            </div>
          </div>
          <RateBars
            threshold={threshold}
            label="On-time arrival rates by weekday"
            rows={summary.weekday.map((item) => ({
              key: item.weekday,
              label: item.weekday.slice(0, 3),
              value: reliabilityRate(item, threshold),
              detail: number(item.completed),
            }))}
          />
        </article>

        <article className="rail-panel">
          <div className="rail-panel-heading">
            <div>
              <p className="eyebrow">Local departure hour</p>
              <h2>Time of day</h2>
            </div>
          </div>
          <RateBars
            threshold={threshold}
            label="On-time arrival rates by local scheduled departure period"
            rows={timePeriods}
          />
        </article>

        <article className="rail-panel">
          <div className="rail-panel-heading">
            <div>
              <p className="eyebrow">Distribution</p>
              <h2>How late?</h2>
            </div>
          </div>
          <div className="delay-distribution" aria-label="Final arrival delay distribution">
            {summary.overall.delay_distribution.map((item) => (
              <div key={item.label}>
                <span>{item.label}</span>
                <div aria-hidden="true"><i style={{ width: `${(item.count / maxDistribution) * 100}%` }} /></div>
                <strong>{percent(item.count / summary.overall.completed)}</strong>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="rail-table-section" aria-labelledby="service-types-title">
        <div className="rail-section-heading">
          <div>
            <p className="eyebrow">Service mix</p>
            <h2 id="service-types-title">Reliability by train type</h2>
            <p>Digitraffic train types with at least 100 scheduled passenger journeys.</p>
          </div>
        </div>
        <div className="train-type-grid">
          {summary.train_types.map((trainType) => (
            <article key={trainType.train_type}>
              <div>
                <h3>{trainType.train_type}</h3>
                <span>{number(trainType.scheduled)} scheduled</span>
              </div>
              <dl>
                <div><dt>Within {threshold} min</dt><dd>{percent(reliabilityRate(trainType, threshold))}</dd></div>
                <div><dt>Cancelled</dt><dd>{percent(trainType.cancelled_rate, 2)}</dd></div>
                <div><dt>P90 delay</dt><dd>{trainType.p90_delay_minutes?.toFixed(1)} min</dd></div>
              </dl>
            </article>
          ))}
        </div>
      </section>

      <section className="rail-table-section" aria-labelledby="routes-title">
        <div className="rail-section-heading">
          <div>
            <p className="eyebrow">Route reliability</p>
            <h2 id="routes-title">Frequent end-to-end routes</h2>
            <p>Routes with at least 200 scheduled passenger trains; both directions are combined.</p>
          </div>
          <label className="rail-sort-control">
            Order routes
            <select value={routeSort} onChange={(event) => setRouteSort(event.target.value as "volume" | "reliability")}>
              <option value="reliability">Most reliable</option>
              <option value="volume">Most services</option>
            </select>
          </label>
        </div>
        <div className="rail-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Route</th>
                <th>Completed</th>
                <th>Within {threshold} min</th>
                <th>Median</th>
                <th>P90</th>
                <th>Cancelled</th>
                <th>Unreliable months*</th>
              </tr>
            </thead>
            <tbody>
              {routes.map((route) => (
                <tr key={route.route_key}>
                  <th>{route.route}</th>
                  <td>{number(route.completed)}</td>
                  <td><strong>{percent(reliabilityRate(route, threshold))}</strong></td>
                  <td>{route.median_delay_minutes?.toFixed(1)} min</td>
                  <td>{route.p90_delay_minutes?.toFixed(1)} min</td>
                  <td>{percent(route.cancelled_rate, 2)}</td>
                  <td>{percent(route.unreliable_month_share, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="table-note">* Share of observed months below 90% within five minutes, independent of the selected threshold.</p>
      </section>

      <section className="rail-table-section" aria-labelledby="stations-title">
        <div className="rail-section-heading">
          <div>
            <p className="eyebrow">Station reliability</p>
            <h2 id="stations-title">Lowest measured arrival reliability</h2>
            <p>Commercial passenger arrivals at stations with at least 500 scheduled observations.</p>
          </div>
        </div>
        <div className="station-card-grid">
          {stationRows.map((station, index) => (
            <article key={station.station_code}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div>
                <h3>{station.station}</h3>
                <p>{station.station_code} · {number(station.completed)} measured arrivals</p>
              </div>
              <strong>{percent(reliabilityRate(station, threshold))}</strong>
            </article>
          ))}
        </div>
      </section>

      <section className="lahti-profile" aria-labelledby="lahti-title">
        <div className="rail-section-heading">
          <div>
            <p className="eyebrow">Local route profile</p>
            <h2 id="lahti-title">Lahti ↔ Helsinki, direct services</h2>
            <p>Every passenger train calling at both stations, measured on the segment rather than at the train’s final destination.</p>
          </div>
          <div className="route-profile-kpi">
            <strong>{percent(reliabilityRate(summary.lahti_helsinki.overall, threshold))}</strong>
            <span>within {threshold} min</span>
          </div>
        </div>
        <div className="direction-grid">
          {summary.lahti_helsinki.directions.map((direction) => (
            <article key={direction.direction}>
              <h3>{direction.direction}</h3>
              <dl>
                <div><dt>Completed</dt><dd>{number(direction.completed)}</dd></div>
                <div><dt>Within {threshold} min</dt><dd>{percent(reliabilityRate(direction, threshold))}</dd></div>
                <div><dt>P90 delay</dt><dd>{direction.p90_delay_minutes?.toFixed(1)} min</dd></div>
                <div><dt>Median change en route</dt><dd>{direction.median_delay_change_minutes?.toFixed(1)} min</dd></div>
              </dl>
            </article>
          ))}
        </div>

        <div className="weather-analysis">
          <div>
            <p className="eyebrow">FMI observation match</p>
            <h3>Weather association, not causation</h3>
            <p>
              Hourly observations nearest the departure city are matched within 45 minutes of scheduled departure. Conditions overlap and are not adjusted for season, incidents or infrastructure work.
            </p>
          </div>
          {weatherConditions.length ? (
            <div className="weather-condition-list">
              {weatherConditions.map((condition) => (
                <div key={condition.condition}>
                  <span>{condition.condition}</span>
                  <strong>
                    {condition.completed >= 100
                      ? percent(reliabilityRate(condition, threshold))
                      : "Low sample"}
                  </strong>
                  <small>{number(condition.completed)} completed{condition.completed < 100 ? " · rate withheld" : ""}</small>
                </div>
              ))}
            </div>
          ) : (
            <p className="live-unavailable">The weather join was not produced for this snapshot.</p>
          )}
        </div>
      </section>

      <section className="recent-services" aria-labelledby="recent-title">
        <div className="rail-section-heading">
          <div>
            <p className="eyebrow">Recent conditions</p>
            <h2 id="recent-title">Lahti ↔ Helsinki service snapshot</h2>
            <p>Direct operational data from Digitraffic, separated from the completed historical period.</p>
          </div>
        </div>
        <LiveServices />
      </section>
    </>
  );
}
