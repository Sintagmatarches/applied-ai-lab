"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  RailDelayThreshold,
  RailMonitorMode,
  RailProblemItem,
  RailRegionMetric,
  RegionalRailSnapshot,
} from "../../lib/rail-monitoring";
import { RAIL_DELAY_THRESHOLDS } from "../../lib/rail-monitoring";

type Coordinate = [number, number];
type RegionFeature = {
  id: string;
  properties: { code: string; nameFi: string; nameEn: string };
  geometry: { type: "MultiPolygon"; coordinates: Coordinate[][][] };
};
type RegionGeoJson = { type: "FeatureCollection"; features: RegionFeature[] };

const CACHE_VERSION = "20260818-data-platform-1";
const MODES: Array<{ value: RailMonitorMode; label: string; description: string }> = [
  { value: "live", label: "LIVE", description: "Current 3-hour operating window" },
  { value: "24h", label: "24 HOURS", description: "Rolling previous 24 hours" },
  { value: "historical", label: "HISTORICAL", description: "Committed 12-month snapshot" },
];

function percentage(value: number | null): string {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function delay(value: number | null): string {
  if (value == null) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)} min`;
}

function localTime(value: string): string {
  return new Intl.DateTimeFormat("en-FI", {
    timeZone: "Europe/Helsinki",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function windowLabel(snapshot: RegionalRailSnapshot): string {
  if (snapshot.mode === "historical") {
    return `${snapshot.windowStart.slice(0, 10)} → ${snapshot.windowEnd.slice(0, 10)}`;
  }
  return `${localTime(snapshot.windowStart)} → ${localTime(snapshot.windowEnd)}`;
}

function allPoints(features: RegionFeature[]): Coordinate[] {
  return features.flatMap((feature) =>
    feature.geometry.coordinates.flatMap((polygon) => polygon.flatMap((ring) => ring)),
  );
}

function featurePath(
  feature: RegionFeature,
  bounds: { minX: number; maxX: number; minY: number; maxY: number },
): string {
  const width = 470;
  const height = 700;
  const padding = 10;
  const project = ([longitude, latitude]: Coordinate): Coordinate => [
    padding + ((longitude - bounds.minX) / (bounds.maxX - bounds.minX)) * (width - padding * 2),
    padding + ((bounds.maxY - latitude) / (bounds.maxY - bounds.minY)) * (height - padding * 2),
  ];
  return feature.geometry.coordinates
    .flatMap((polygon) =>
      polygon.map((ring) =>
        ring
          .map((point, index) => {
            const [x, y] = project(point);
            return `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
          })
          .join(" ") + " Z",
      ),
    )
    .join(" ");
}

function statusLabel(status: RailRegionMetric["status"]): string {
  if (status === "no-service") return "No rail service";
  if (status === "no-data") return "No current observations";
  if (status === "serious") return "Serious disruption";
  if (status === "elevated") return "Elevated disruption";
  return "Normal operation";
}

function thresholdValue<T>(
  values: Partial<Record<RailDelayThreshold, T>> | undefined,
  threshold: RailDelayThreshold,
  fiveMinuteFallback: T,
): T {
  return values?.[threshold] ?? fiveMinuteFallback;
}

function regionalView(region: RailRegionMetric, threshold: RailDelayThreshold) {
  const problemStations = thresholdValue(region.problemStationsByThreshold, threshold, region.problemStations);
  const problemRoutes = thresholdValue(region.problemRoutesByThreshold, threshold, region.problemRoutes);
  return {
    delayedTrains: thresholdValue(region.delayedTrainsByThreshold, threshold, region.delayedTrains),
    delayedShare: thresholdValue(region.delayedShareByThreshold, threshold, region.delayedShare),
    disruptionScore: thresholdValue(region.disruptionScoreByThreshold, threshold, region.disruptionScore),
    reliabilityScore: thresholdValue(region.reliabilityScoreByThreshold, threshold, region.reliabilityScore),
    status: thresholdValue(region.statusByThreshold, threshold, region.status),
    problemStations,
    problemRoutes,
  };
}

function ProblemList({ items, threshold }: { items: RailProblemItem[]; threshold: RailDelayThreshold }) {
  if (!items.length) return <p>No observations exceeded {threshold} minutes in this window.</p>;
  return (
    <ol>
      {items.slice(0, 3).map((item) => (
        <li key={item.key}>
          <span>{item.label}</span>
          <strong>{item.severe} serious · {item.delayed} delayed · {item.cancellations} cancelled</strong>
        </li>
      ))}
    </ol>
  );
}

function RegionDetail({ region, threshold }: { region: RailRegionMetric; threshold: RailDelayThreshold }) {
  if (!region.hasRailService) {
    return (
      <aside className="region-detail region-no-service" aria-live="polite">
        <p className="eyebrow">Selected region</p>
        <h3>{region.nameEn}</h3>
        <strong>No rail service</strong>
        <p>Åland has no railway passenger network, so it is excluded from reliability and disruption scoring.</p>
      </aside>
    );
  }
  const view = regionalView(region, threshold);
  return (
    <aside className="region-detail" aria-live="polite">
      <div className="region-detail-heading">
        <div>
          <p className="eyebrow">Selected region · {region.nameFi}</p>
          <h3>{region.nameEn}</h3>
        </div>
        <span className={`region-status region-status-${view.status}`}>{statusLabel(view.status)}</span>
      </div>
      <dl className="region-metrics">
        <div><dt>Observed trains</dt><dd>{region.observedTrains.toLocaleString("en-FI")}</dd></div>
        <div><dt>Delayed &gt;{threshold} min</dt><dd>{view.delayedTrains.toLocaleString("en-FI")} <small>{percentage(view.delayedShare)}</small></dd></div>
        <div><dt>Average delay</dt><dd>{delay(region.averageDelayMinutes)}</dd></div>
        <div><dt>Serious &gt;15 min</dt><dd>{region.severeDelays.toLocaleString("en-FI")}</dd></div>
        <div><dt>Cancellations</dt><dd>{region.cancellations.toLocaleString("en-FI")} <small>{percentage(region.cancellationShare)}</small></dd></div>
        <div><dt>Reliability score</dt><dd>{view.reliabilityScore?.toFixed(1) ?? "—"}<small> / 100</small></dd></div>
      </dl>
      <div className="region-problems">
        <div>
          <h4>Problem stations</h4>
          <ProblemList items={view.problemStations} threshold={threshold} />
        </div>
        <div>
          <h4>Problem routes</h4>
          <ProblemList items={view.problemRoutes} threshold={threshold} />
        </div>
      </div>
    </aside>
  );
}

export function RegionalRailMonitor() {
  const [mode, setMode] = useState<RailMonitorMode>("live");
  const [threshold, setThreshold] = useState<RailDelayThreshold>(5);
  const [snapshots, setSnapshots] = useState<Partial<Record<RailMonitorMode, RegionalRailSnapshot>>>({});
  const [geoJson, setGeoJson] = useState<RegionGeoJson | null>(null);
  const [selectedCode, setSelectedCode] = useState("01");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/rail/finland-maakunta.geojson?v=${CACHE_VERSION}`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Map geometry unavailable");
        setGeoJson((await response.json()) as RegionGeoJson);
      })
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError("The official regional map could not be loaded.");
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    let active = true;
    let controller = new AbortController();
    const load = async (background = false) => {
      if (!background) setLoading(true);
      setError(null);
      controller.abort();
      controller = new AbortController();
      try {
        const response = await fetch(`/api/rail/monitor?mode=${mode}&v=${CACHE_VERSION}`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Monitoring API unavailable");
        const snapshot = (await response.json()) as RegionalRailSnapshot;
        if (active) setSnapshots((current) => ({ ...current, [mode]: snapshot }));
      } catch (caught) {
        if (active && !(caught instanceof DOMException && caught.name === "AbortError")) {
          setError("Current Digitraffic data is temporarily unavailable. No synthetic fallback is shown.");
        }
      } finally {
        if (active) setLoading(false);
      }
    };
    void load(Boolean(snapshots[mode]));
    const refresh = mode === "live" ? window.setInterval(() => void load(true), 60_000) : null;
    return () => {
      active = false;
      controller.abort();
      if (refresh != null) window.clearInterval(refresh);
    };
    // A cached snapshot is deliberately not a dependency: switching mode controls loading.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const snapshot = snapshots[mode];
  const regionByCode = useMemo(
    () => new Map(snapshot?.regions.map((region) => [region.code, region]) ?? []),
    [snapshot],
  );
  const selected = regionByCode.get(selectedCode) ?? snapshot?.regions[0];
  const paths = useMemo(() => {
    if (!geoJson) return [];
    const points = allPoints(geoJson.features);
    const bounds = {
      minX: Math.min(...points.map(([x]) => x)),
      maxX: Math.max(...points.map(([x]) => x)),
      minY: Math.min(...points.map(([, y]) => y)),
      maxY: Math.max(...points.map(([, y]) => y)),
    };
    return geoJson.features.map((feature) => ({ feature, path: featurePath(feature, bounds) }));
  }, [geoJson]);

  return (
    <section className="regional-monitor" aria-labelledby="regional-monitor-title">
      <div className="regional-monitor-intro">
        <div>
          <p className="eyebrow">National operating picture</p>
          <h2 id="regional-monitor-title">Live rail health by region</h2>
          <p>Official train events are linked to Statistics Finland regions through station coordinates. Select a time window, then choose a maakunta for its operating detail.</p>
        </div>
        <div className="monitor-mode-control" aria-label="Monitoring period">
          {MODES.map((item) => (
            <button
              type="button"
              key={item.value}
              className={mode === item.value ? "is-selected" : ""}
              aria-pressed={mode === item.value}
              title={item.description}
              onClick={() => setMode(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="monitor-threshold-row">
        <div>
          <span className="eyebrow">Delay policy</span>
          <strong>Flag when more than</strong>
        </div>
        <div className="monitor-mode-control" aria-label="Delay threshold in minutes">
          {RAIL_DELAY_THRESHOLDS.map((minutes) => (
            <button
              type="button"
              key={minutes}
              className={threshold === minutes ? "is-selected" : ""}
              aria-pressed={threshold === minutes}
              onClick={() => setThreshold(minutes)}
            >
              {minutes} MIN
            </button>
          ))}
        </div>
        <small>Serious disruption remains fixed at more than 15 minutes.</small>
      </div>

      {snapshot ? (
        <>
          <div className="monitor-freshness" role="status">
            <span className={mode === "live" ? "live-pulse" : "snapshot-dot"} aria-hidden="true" />
            <strong>{mode === "live" ? "Live Digitraffic" : mode === "24h" ? "Rolling window" : "Dated historical snapshot"}</strong>
            <span>{windowLabel(snapshot)}</span>
            <span>Updated {localTime(snapshot.retrievedAt)}</span>
          </div>
          <dl className="monitor-network-kpis" aria-label="National regional observations">
            <div><dt>Regional train observations</dt><dd>{snapshot.network.observedTrains.toLocaleString("en-FI")}</dd></div>
            <div><dt>Delayed &gt;{threshold} min</dt><dd>{percentage(thresholdValue(snapshot.network.delayedShareByThreshold, threshold, snapshot.network.delayedShare))}</dd></div>
            <div><dt>Average delay</dt><dd>{delay(snapshot.network.averageDelayMinutes)}</dd></div>
            <div><dt>Serious delays</dt><dd>{snapshot.network.severeDelays.toLocaleString("en-FI")}</dd></div>
            <div><dt>Cancellations</dt><dd>{snapshot.network.cancellations.toLocaleString("en-FI")}</dd></div>
          </dl>
        </>
      ) : null}

      {error ? <p className="monitor-error" role="alert">{error}</p> : null}
      {loading && !snapshot ? <p className="monitor-loading" role="status">Linking current train events to Finland’s 19 regions…</p> : null}

      <div className="regional-map-layout" aria-busy={loading && !snapshot}>
        <div className="regional-map-panel">
          <svg className="finland-region-map" viewBox="0 0 470 700" role="img" aria-labelledby="map-title map-description">
            <title id="map-title">Rail disruption by Finnish region</title>
            <desc id="map-description">Interactive choropleth of Finland’s 19 maakunta regions. Darker warm colours indicate more disruption.</desc>
            {paths.map(({ feature, path }) => {
              const region = regionByCode.get(feature.properties.code);
              const view = region ? regionalView(region, threshold) : null;
              const status = view?.status ?? "no-data";
              const label = region
                ? `${region.nameEn}: ${statusLabel(status)} at the ${threshold}-minute threshold${view?.disruptionScore == null ? "" : `, disruption score ${view.disruptionScore}`}`
                : feature.properties.nameEn;
              return (
                <path
                  key={feature.id}
                  d={path}
                  className={`region-shape region-shape-${status} ${selected?.code === feature.properties.code ? "is-selected" : ""}`}
                  fillRule="evenodd"
                  role="button"
                  tabIndex={0}
                  aria-label={label}
                  onClick={() => setSelectedCode(feature.properties.code)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedCode(feature.properties.code);
                    }
                  }}
                >
                  <title>{label}</title>
                </path>
              );
            })}
          </svg>
          <div className="map-legend" aria-label="Map status legend">
            <span><i className="legend-normal" />Normal</span>
            <span><i className="legend-elevated" />Elevated</span>
            <span><i className="legend-serious" />Serious</span>
            <span><i className="legend-no-data" />No data</span>
            <span><i className="legend-no-service" />No rail service</span>
          </div>
          <p className="map-source">Boundaries: Statistics Finland, maakunta 1:1M ({geoJson?.features.length ?? 19} regions), CC BY 4.0.</p>
        </div>
        {selected ? <RegionDetail region={selected} threshold={threshold} /> : <div className="region-detail region-detail-empty">Select a region on the map.</div>}
      </div>

      {snapshot ? (
        <details className="monitor-method-note">
          <summary>How to read this monitor</summary>
          <p>{snapshot.definitions.observedTrain}</p>
          <p>{snapshot.definitions.delayed} {snapshot.definitions.severe}</p>
          <p>{snapshot.definitions.score}</p>
          <p>Delay shares use trains with actual or current estimated timing; scheduled trains without an observation remain visible in the observed count but are not silently treated as on time.</p>
        </details>
      ) : null}
    </section>
  );
}
