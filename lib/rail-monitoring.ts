import type { DigitrafficTimeTableRow, DigitrafficTrain } from "./rail-live";

export type RailMonitorMode = "live" | "24h" | "historical";
export type RailRegionStatus = "normal" | "elevated" | "serious" | "no-data" | "no-service";
export const RAIL_DELAY_THRESHOLDS = [5, 10, 15, 30] as const;
export type RailDelayThreshold = (typeof RAIL_DELAY_THRESHOLDS)[number];
export type RailThresholdValues<T> = Record<RailDelayThreshold, T>;

export type RailStationLookup = Record<
  string,
  {
    name: string;
    passengerTraffic: boolean;
    longitude: number | null;
    latitude: number | null;
    regionCode: string | null;
  }
>;

export type RailRegionDefinition = {
  code: string;
  nameFi: string;
  nameSv: string;
  nameEn: string;
  year: number;
};

export type RailProblemItem = {
  key: string;
  label: string;
  observations: number;
  delayed: number;
  severe: number;
  cancellations: number;
  averageDelayMinutes: number | null;
};

export type RailRegionMetric = {
  code: string;
  nameFi: string;
  nameEn: string;
  passengerStations: number;
  hasRailService: boolean;
  observedTrains: number;
  measuredTrains: number;
  delayedTrains: number;
  delayedShare: number | null;
  delayedTrainsByThreshold: RailThresholdValues<number>;
  delayedShareByThreshold: RailThresholdValues<number | null>;
  averageDelayMinutes: number | null;
  severeDelays: number;
  cancellations: number;
  cancellationShare: number | null;
  disruptionScore: number | null;
  reliabilityScore: number | null;
  status: RailRegionStatus;
  disruptionScoreByThreshold: RailThresholdValues<number | null>;
  reliabilityScoreByThreshold: RailThresholdValues<number | null>;
  statusByThreshold: RailThresholdValues<RailRegionStatus>;
  problemStations: RailProblemItem[];
  problemRoutes: RailProblemItem[];
  problemStationsByThreshold: RailThresholdValues<RailProblemItem[]>;
  problemRoutesByThreshold: RailThresholdValues<RailProblemItem[]>;
};

export type RegionalRailSnapshot = {
  mode: RailMonitorMode;
  retrievedAt: string;
  windowStart: string;
  windowEnd: string;
  source: string;
  sourceUrl: string;
  definitions: {
    delayed: string;
    severe: string;
    observedTrain: string;
    score: string;
    thresholds: readonly RailDelayThreshold[];
  };
  network: Omit<
    RailRegionMetric,
    "code" | "nameFi" | "nameEn" | "passengerStations" | "hasRailService" |
    "problemStations" | "problemRoutes" | "problemStationsByThreshold" | "problemRoutesByThreshold"
  >;
  regions: RailRegionMetric[];
};

type LookupPayload = {
  regions: RailRegionDefinition[];
  stations: RailStationLookup;
};

type Aggregate = {
  observed: number;
  measured: number;
  delayedByThreshold: RailThresholdValues<number>;
  severe: number;
  cancelled: number;
  delaySum: number;
  stations: Map<string, ProblemAggregate>;
  routes: Map<string, ProblemAggregate>;
};

type ProblemAggregate = {
  label: string;
  observations: number;
  delayedByThreshold: RailThresholdValues<number>;
  severe: number;
  cancellations: number;
  delaySum: number;
  measured: number;
};

const PASSENGER_CATEGORIES = new Set(["Long-distance", "Commuter"]);
const MINUTE = 60_000;

function thresholdValues<T>(factory: (threshold: RailDelayThreshold) => T): RailThresholdValues<T> {
  return Object.fromEntries(
    RAIL_DELAY_THRESHOLDS.map((threshold) => [threshold, factory(threshold)]),
  ) as RailThresholdValues<T>;
}

function timestamp(value: string | undefined): number | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function rowDelay(row: DigitrafficTimeTableRow, allowEstimate: boolean): number | null {
  if (!row.actualTime && !(allowEstimate && row.liveEstimateTime)) return null;
  if (Number.isFinite(row.differenceInMinutes)) return row.differenceInMinutes as number;
  const scheduled = timestamp(row.scheduledTime);
  const observed = timestamp(row.actualTime ?? (allowEstimate ? row.liveEstimateTime : undefined));
  if (scheduled == null || observed == null) return null;
  return Math.round((observed - scheduled) / MINUTE);
}

function isPassengerRow(row: DigitrafficTimeTableRow, stations: RailStationLookup): boolean {
  const station = row.stationShortCode ? stations[row.stationShortCode] : undefined;
  return Boolean(
    station?.passengerTraffic &&
      station.regionCode &&
      row.commercialStop &&
      row.trainStopping !== false,
  );
}

function cleanStationName(value: string): string {
  return value.replace(/ asema$/i, "");
}

function routeLabel(train: DigitrafficTrain, stations: RailStationLookup): { key: string; label: string } {
  const rows = (train.timeTableRows ?? []).filter((row) => isPassengerRow(row, stations));
  const originCode = rows[0]?.stationShortCode ?? "?";
  const destinationCode = rows.at(-1)?.stationShortCode ?? "?";
  const origin = stations[originCode];
  const destination = stations[destinationCode];
  return {
    key: `${originCode}--${destinationCode}`,
    label: `${cleanStationName(origin?.name ?? originCode)} → ${cleanStationName(destination?.name ?? destinationCode)}`,
  };
}

function newAggregate(): Aggregate {
  return {
    observed: 0,
    measured: 0,
    delayedByThreshold: thresholdValues(() => 0),
    severe: 0,
    cancelled: 0,
    delaySum: 0,
    stations: new Map(),
    routes: new Map(),
  };
}

function addProblem(
  target: Map<string, ProblemAggregate>,
  key: string,
  label: string,
  delay: number | null,
  cancelled = false,
): void {
  const item = target.get(key) ?? {
    label,
    observations: 0,
    delayedByThreshold: thresholdValues(() => 0),
    severe: 0,
    cancellations: 0,
    delaySum: 0,
    measured: 0,
  };
  item.observations += 1;
  if (cancelled) item.cancellations += 1;
  if (delay != null) {
    item.measured += 1;
    item.delaySum += delay;
    for (const threshold of RAIL_DELAY_THRESHOLDS) {
      if (delay > threshold) item.delayedByThreshold[threshold] += 1;
    }
    if (delay > 15) item.severe += 1;
  }
  target.set(key, item);
}

function topProblems(items: Map<string, ProblemAggregate>, threshold: RailDelayThreshold): RailProblemItem[] {
  return [...items.entries()]
    .map(([key, item]) => ({
      key,
      label: item.label,
      observations: item.observations,
      delayed: item.delayedByThreshold[threshold],
      severe: item.severe,
      cancellations: item.cancellations,
      averageDelayMinutes: item.measured ? item.delaySum / item.measured : null,
    }))
    .filter((item) => item.delayed > 0 || item.severe > 0 || item.cancellations > 0)
    .sort(
      (left, right) =>
        right.severe - left.severe ||
        right.cancellations - left.cancellations ||
        right.delayed - left.delayed ||
        (right.averageDelayMinutes ?? -Infinity) - (left.averageDelayMinutes ?? -Infinity),
    )
    .slice(0, 5);
}

function disruptionScoreFor(
  delayedShare: number | null,
  severeShare: number,
  cancellationShare: number | null,
  averageDelayMinutes: number | null,
  observed: number,
  measured: number,
  cancelled: number,
): number | null {
  if (!observed || (!measured && !cancelled)) return null;
  return Math.round(
    Math.max(
      0,
      Math.min(
        100,
        45 * (delayedShare ?? 0) +
          25 * severeShare +
          20 * (cancellationShare ?? 0) +
          10 * Math.min(Math.max(averageDelayMinutes ?? 0, 0) / 30, 1),
      ),
    ) * 10,
  ) / 10;
}

function statusFor(score: number | null, observed: number, hasRailService: boolean): RailRegionStatus {
  if (!hasRailService) return "no-service";
  if (!observed || score == null) return "no-data";
  if (score >= 25) return "serious";
  if (score >= 10) return "elevated";
  return "normal";
}

function finishAggregate(
  aggregate: Aggregate,
  identity: Pick<RailRegionMetric, "code" | "nameFi" | "nameEn" | "passengerStations" | "hasRailService">,
): RailRegionMetric {
  const averageDelayMinutes = aggregate.measured ? aggregate.delaySum / aggregate.measured : null;
  const cancellationShare = aggregate.observed ? aggregate.cancelled / aggregate.observed : null;
  const severeShare = aggregate.measured ? aggregate.severe / aggregate.measured : 0;
  const delayedShareByThreshold = thresholdValues((threshold) =>
    aggregate.measured ? aggregate.delayedByThreshold[threshold] / aggregate.measured : null,
  );
  const disruptionScoreByThreshold = thresholdValues((threshold) =>
    disruptionScoreFor(
      delayedShareByThreshold[threshold],
      severeShare,
      cancellationShare,
      averageDelayMinutes,
      aggregate.observed,
      aggregate.measured,
      aggregate.cancelled,
    ),
  );
  const reliabilityScoreByThreshold = thresholdValues((threshold) => {
    const score = disruptionScoreByThreshold[threshold];
    return score == null ? null : 100 - score;
  });
  const statusByThreshold = thresholdValues((threshold) =>
    statusFor(disruptionScoreByThreshold[threshold], aggregate.observed, identity.hasRailService),
  );
  const problemStationsByThreshold = thresholdValues((threshold) => topProblems(aggregate.stations, threshold));
  const problemRoutesByThreshold = thresholdValues((threshold) => topProblems(aggregate.routes, threshold));
  const defaultThreshold: RailDelayThreshold = 5;
  return {
    ...identity,
    observedTrains: aggregate.observed,
    measuredTrains: aggregate.measured,
    delayedTrains: aggregate.delayedByThreshold[defaultThreshold],
    delayedShare: delayedShareByThreshold[defaultThreshold],
    delayedTrainsByThreshold: { ...aggregate.delayedByThreshold },
    delayedShareByThreshold,
    averageDelayMinutes,
    severeDelays: aggregate.severe,
    cancellations: aggregate.cancelled,
    cancellationShare,
    disruptionScore: disruptionScoreByThreshold[defaultThreshold],
    reliabilityScore: reliabilityScoreByThreshold[defaultThreshold],
    status: statusByThreshold[defaultThreshold],
    disruptionScoreByThreshold,
    reliabilityScoreByThreshold,
    statusByThreshold,
    problemStations: problemStationsByThreshold[defaultThreshold],
    problemRoutes: problemRoutesByThreshold[defaultThreshold],
    problemStationsByThreshold,
    problemRoutesByThreshold,
  };
}

function rowInWindow(row: DigitrafficTimeTableRow, start: number, end: number): boolean {
  const scheduled = timestamp(row.scheduledTime);
  return scheduled != null && scheduled >= start && scheduled <= end;
}

export function buildRegionalRailSnapshot(
  trains: DigitrafficTrain[],
  lookup: LookupPayload,
  mode: Exclude<RailMonitorMode, "historical">,
  now = new Date(),
): RegionalRailSnapshot {
  const end = now.getTime();
  const start = mode === "live" ? end - 90 * MINUTE : end - 24 * 60 * MINUTE;
  const liveFuture = mode === "live" ? end + 90 * MINUTE : end;
  const aggregates = new Map(lookup.regions.map((region) => [region.code, newAggregate()]));

  for (const train of trains) {
    if (!PASSENGER_CATEGORIES.has(train.trainCategory ?? "")) continue;
    const passengerRows = (train.timeTableRows ?? []).filter((row) => isPassengerRow(row, lookup.stations));
    if (!passengerRows.length) continue;
    const route = routeLabel(train, lookup.stations);
    const rowsByRegion = new Map<string, DigitrafficTimeTableRow[]>();
    const candidateRows = passengerRows.filter((row) => rowInWindow(row, start, liveFuture));
    if (mode === "live" && train.runningCurrently) {
      const timed = passengerRows
        .map((row) => ({ row, time: timestamp(row.scheduledTime) }))
        .filter((item): item is { row: DigitrafficTimeTableRow; time: number } => item.time != null)
        .sort((left, right) => left.time - right.time);
      const previous = [...timed].reverse().find((item) => item.time <= end)?.row;
      const next = timed.find((item) => item.time > end)?.row;
      if (previous && !candidateRows.includes(previous)) candidateRows.push(previous);
      if (next && !candidateRows.includes(next)) candidateRows.push(next);
    }
    for (const row of candidateRows) {
      const regionCode = lookup.stations[row.stationShortCode!]?.regionCode;
      if (!regionCode) continue;
      const rows = rowsByRegion.get(regionCode) ?? [];
      rows.push(row);
      rowsByRegion.set(regionCode, rows);
    }

    for (const [regionCode, regionRows] of rowsByRegion) {
      const aggregate = aggregates.get(regionCode);
      if (!aggregate) continue;
      aggregate.observed += 1;
      const cancelled = Boolean(train.cancelled || regionRows.some((row) => row.cancelled));
      if (cancelled) aggregate.cancelled += 1;
      const delays = regionRows
        .map((row) => rowDelay(row, mode === "live"))
        .filter((delay): delay is number => delay != null);
      const delay = delays.length ? Math.max(...delays) : null;
      if (!cancelled && delay != null) {
        aggregate.measured += 1;
        aggregate.delaySum += delay;
        for (const threshold of RAIL_DELAY_THRESHOLDS) {
          if (delay > threshold) aggregate.delayedByThreshold[threshold] += 1;
        }
        if (delay > 15) aggregate.severe += 1;
      }
      addProblem(aggregate.routes, route.key, route.label, cancelled ? null : delay, cancelled);

      const stationRows = new Map<string, DigitrafficTimeTableRow[]>();
      for (const row of regionRows) {
        const code = row.stationShortCode!;
        const rows = stationRows.get(code) ?? [];
        rows.push(row);
        stationRows.set(code, rows);
      }
      for (const [code, rows] of stationRows) {
        const stationDelays = rows
          .map((row) => rowDelay(row, mode === "live"))
          .filter((value): value is number => value != null);
        addProblem(
          aggregate.stations,
          code,
          cleanStationName(lookup.stations[code]?.name ?? code),
          stationDelays.length ? Math.max(...stationDelays) : null,
          cancelled || rows.some((row) => row.cancelled),
        );
      }
    }
  }

  const regions = lookup.regions.map((region) => {
    const passengerStations = Object.values(lookup.stations).filter(
      (station) => station.passengerTraffic && station.regionCode === region.code,
    ).length;
    return finishAggregate(aggregates.get(region.code)!, {
      code: region.code,
      nameFi: region.nameFi,
      nameEn: region.nameEn,
      passengerStations,
      hasRailService: passengerStations > 0,
    });
  });
  const networkAggregate = newAggregate();
  for (const aggregate of aggregates.values()) {
    networkAggregate.observed += aggregate.observed;
    networkAggregate.measured += aggregate.measured;
    for (const threshold of RAIL_DELAY_THRESHOLDS) {
      networkAggregate.delayedByThreshold[threshold] += aggregate.delayedByThreshold[threshold];
    }
    networkAggregate.severe += aggregate.severe;
    networkAggregate.cancelled += aggregate.cancelled;
    networkAggregate.delaySum += aggregate.delaySum;
  }
  const network = finishAggregate(networkAggregate, {
    code: "FI",
    nameFi: "Suomi",
    nameEn: "Finland",
    passengerStations: 0,
    hasRailService: true,
  });
  const networkMetrics: RegionalRailSnapshot["network"] = {
    observedTrains: network.observedTrains,
    measuredTrains: network.measuredTrains,
    delayedTrains: network.delayedTrains,
    delayedShare: network.delayedShare,
    delayedTrainsByThreshold: network.delayedTrainsByThreshold,
    delayedShareByThreshold: network.delayedShareByThreshold,
    averageDelayMinutes: network.averageDelayMinutes,
    severeDelays: network.severeDelays,
    cancellations: network.cancellations,
    cancellationShare: network.cancellationShare,
    disruptionScore: network.disruptionScore,
    reliabilityScore: network.reliabilityScore,
    status: network.status,
    disruptionScoreByThreshold: network.disruptionScoreByThreshold,
    reliabilityScoreByThreshold: network.reliabilityScoreByThreshold,
    statusByThreshold: network.statusByThreshold,
  };

  return {
    mode,
    retrievedAt: now.toISOString(),
    windowStart: new Date(start).toISOString(),
    windowEnd: new Date(mode === "live" ? liveFuture : end).toISOString(),
    source: "Fintraffic / Digitraffic",
    sourceUrl: "https://www.digitraffic.fi/en/railway-traffic/",
    definitions: {
      delayed: "More whole minutes late than the selected 5, 10, 15 or 30-minute policy threshold at a commercial passenger stop in the region.",
      severe: "More than 15 whole minutes late.",
      observedTrain: "One passenger train per region when a commercial stop falls inside the selected time window; a train crossing regions is counted once in each region.",
      score: "Threshold-adjusted disruption score (0 best, 100 worst): 45% selected-threshold delayed share, 25% severe-delay share, 20% cancellation share and 10% average positive delay capped at 30 minutes.",
      thresholds: RAIL_DELAY_THRESHOLDS,
    },
    network: networkMetrics,
    regions,
  };
}
