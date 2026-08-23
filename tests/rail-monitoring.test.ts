import assert from "node:assert/strict";
import test from "node:test";

import type { DigitrafficTrain } from "../lib/rail-live.ts";
import { buildRegionalRailSnapshot } from "../lib/rail-monitoring.ts";

const lookup = {
  regions: [
    { code: "01", nameFi: "Uusimaa", nameSv: "Nyland", nameEn: "Uusimaa", year: 2026 },
    { code: "07", nameFi: "Päijät-Häme", nameSv: "Päijänne-Tavastland", nameEn: "Päijät-Häme", year: 2026 },
    { code: "21", nameFi: "Ahvenanmaa", nameSv: "Åland", nameEn: "Åland", year: 2026 },
  ],
  stations: {
    HKI: { name: "Helsinki asema", passengerTraffic: true, longitude: 24.94, latitude: 60.17, regionCode: "01" },
    LH: { name: "Lahti", passengerTraffic: true, longitude: 25.66, latitude: 60.98, regionCode: "07" },
    ILR: { name: "Ilmala ratapiha", passengerTraffic: false, longitude: 24.92, latitude: 60.21, regionCode: "01" },
  },
};

function train(number: number, delay: number | null, options: { cancelled?: boolean; actual?: boolean } = {}): DigitrafficTrain {
  const observed = options.actual === false ? undefined : "2026-08-12T11:10:00Z";
  return {
    departureDate: "2026-08-12",
    trainNumber: number,
    trainType: "IC",
    trainCategory: "Long-distance",
    cancelled: options.cancelled,
    timeTableRows: [
      {
        stationShortCode: "HKI",
        type: "DEPARTURE",
        commercialStop: true,
        trainStopping: true,
        scheduledTime: "2026-08-12T11:00:00Z",
        actualTime: observed,
        liveEstimateTime: observed ? undefined : "2026-08-12T11:10:00Z",
        differenceInMinutes: delay ?? undefined,
      },
      {
        stationShortCode: "ILR",
        type: "ARRIVAL",
        commercialStop: true,
        trainStopping: true,
        scheduledTime: "2026-08-12T11:15:00Z",
        actualTime: "2026-08-12T11:15:00Z",
        differenceInMinutes: 0,
      },
      {
        stationShortCode: "LH",
        type: "ARRIVAL",
        commercialStop: true,
        trainStopping: true,
        scheduledTime: "2026-08-12T11:55:00Z",
        actualTime: delay == null ? undefined : `2026-08-12T12:${String(Math.max(0, delay - 5)).padStart(2, "0")}:00Z`,
        differenceInMinutes: delay ?? undefined,
        cancelled: options.cancelled,
      },
    ],
  };
}

test("counts each train once per region and excludes non-passenger service locations", () => {
  const snapshot = buildRegionalRailSnapshot(
    [train(1, 18)],
    lookup,
    "live",
    new Date("2026-08-12T12:00:00Z"),
  );
  const uusimaa = snapshot.regions.find((region) => region.code === "01")!;
  const paijatHame = snapshot.regions.find((region) => region.code === "07")!;
  assert.equal(uusimaa.observedTrains, 1);
  assert.equal(paijatHame.observedTrains, 1);
  assert.equal(uusimaa.problemStations.some((station) => station.key === "ILR"), false);
  assert.equal(paijatHame.severeDelays, 1);
  assert.equal(paijatHame.delayedShare, 1);
});

test("publishes policy-threshold metrics while severe delay stays fixed at over 15 minutes", () => {
  const snapshot = buildRegionalRailSnapshot(
    [train(10, 12), train(11, 18)],
    lookup,
    "live",
    new Date("2026-08-12T12:00:00Z"),
  );
  const region = snapshot.regions.find((item) => item.code === "07")!;
  assert.deepEqual(region.delayedTrainsByThreshold, { 5: 2, 10: 2, 15: 1, 30: 0 });
  assert.deepEqual(region.delayedShareByThreshold, { 5: 1, 10: 1, 15: 0.5, 30: 0 });
  assert.equal(region.severeDelays, 1);
  assert.ok(region.disruptionScoreByThreshold[5]! > region.disruptionScoreByThreshold[15]!);
  assert.ok(region.disruptionScoreByThreshold[15]! > region.disruptionScoreByThreshold[30]!);
  assert.equal(region.problemStationsByThreshold[30][0].delayed, 0);
  assert.equal(region.problemStationsByThreshold[30][0].severe, 1);
  assert.equal(region.problemRoutesByThreshold[15][0].delayed, 1);
  assert.deepEqual(snapshot.definitions.thresholds, [5, 10, 15, 30]);
});

test("does not turn unobserved scheduled timing into an on-time result", () => {
  const service = train(2, null, { actual: false });
  service.timeTableRows![0].liveEstimateTime = undefined;
  const snapshot = buildRegionalRailSnapshot(
    [service],
    lookup,
    "24h",
    new Date("2026-08-12T12:00:00Z"),
  );
  const uusimaa = snapshot.regions.find((region) => region.code === "01")!;
  assert.equal(uusimaa.observedTrains, 1);
  assert.equal(uusimaa.measuredTrains, 0);
  assert.equal(uusimaa.delayedShare, null);
  assert.equal(uusimaa.status, "no-data");
  assert.equal(uusimaa.disruptionScore, null);
});

test("keeps Åland outside disruption scoring", () => {
  const snapshot = buildRegionalRailSnapshot(
    [train(3, 7)],
    lookup,
    "live",
    new Date("2026-08-12T12:00:00Z"),
  );
  const aland = snapshot.regions.find((region) => region.code === "21")!;
  assert.equal(aland.hasRailService, false);
  assert.equal(aland.status, "no-service");
  assert.equal(aland.disruptionScore, null);
  assert.equal(aland.reliabilityScore, null);
  assert.equal(aland.statusByThreshold[30], "no-service");
});

test("marks regional cancellations without treating them as measured delays", () => {
  const snapshot = buildRegionalRailSnapshot(
    [train(4, null, { cancelled: true, actual: false })],
    lookup,
    "live",
    new Date("2026-08-12T12:00:00Z"),
  );
  const region = snapshot.regions.find((item) => item.code === "07")!;
  assert.equal(region.cancellations, 1);
  assert.equal(region.measuredTrains, 0);
  assert.equal(region.cancellationShare, 1);
});

test("regional API rejects unsupported windows", async () => {
  const { GET } = await import("../app/api/rail/monitor/route.ts");
  const response = await GET(new Request("https://example.test/api/rail/monitor?mode=30d"));
  assert.equal(response.status, 400);
  assert.equal(response.headers.get("cache-control"), "no-store");
});

test("7d API exposes a complete governed publication with operational evidence", async () => {
  const { GET } = await import("../app/api/rail/monitor/route.ts");
  const response = await GET(new Request("https://example.test/api/rail/monitor?mode=7d"));
  const body = (await response.json()) as {
    mode: string; schemaVersion: string; latestCompletePartition: string;
    coverage: { status: string; availableDates: string[] }; regions: Array<{ sampleSupport: { status: string } }>;
  };
  assert.equal(response.status, 200);
  assert.equal(body.mode, "7d");
  assert.equal(body.schemaVersion, "rail-regional-snapshot-v2");
  assert.equal(body.coverage.status, "complete");
  assert.equal(body.coverage.availableDates.length, 7);
  assert.equal(body.latestCompletePartition, "2026-08-22");
  assert.equal(body.regions.length, 19);
  assert.ok(body.regions.every((region) => Boolean(region.sampleSupport.status)));
});

test("historical API returns all official regions and a dated source window", async () => {
  const { GET } = await import("../app/api/rail/monitor/route.ts");
  const response = await GET(new Request("https://example.test/api/rail/monitor?mode=historical"));
  const body = (await response.json()) as { mode: string; regions: Array<{ code: string; status: string }>; windowEnd: string };
  assert.equal(response.status, 200);
  assert.equal(body.mode, "historical");
  assert.equal(body.regions.length, 19);
  assert.equal(body.regions.find((region) => region.code === "21")?.status, "no-service");
  assert.match(body.windowEnd, /^2026-07-31/);
});

test("live regional API returns an honest error instead of historical fallback", async () => {
  const originalFetch = globalThis.fetch;
  const originalConsoleError = console.error;
  globalThis.fetch = async () => {
    throw new Error("source unavailable");
  };
  console.error = () => undefined;
  try {
    const { GET } = await import("../app/api/rail/monitor/route.ts");
    const response = await GET(new Request("https://example.test/api/rail/monitor?mode=live"));
    const body = (await response.json()) as { error: string };
    assert.equal(response.status, 502);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.match(body.error, /temporarily unavailable/);
  } finally {
    globalThis.fetch = originalFetch;
    console.error = originalConsoleError;
  }
});
