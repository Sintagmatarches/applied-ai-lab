import sevenDaySnapshot from "../../../../artifacts/rail-regional-7d.json";
import historicalSnapshot from "../../../../artifacts/rail-regional-history.json";
import lookup from "../../../../artifacts/rail-station-regions.json";
import type { DigitrafficTrain } from "../../../../lib/rail-live";
import {
  buildRegionalRailSnapshot,
  type RailMonitorMode,
  type RegionalRailSnapshot,
} from "../../../../lib/rail-monitoring";
import { freshnessContract } from "../../../../lib/rail-operational";
import {
  fetchRailPublication,
  validateRailPublicationSnapshot,
} from "../../../../lib/rail-publication";

const API_ROOT = "https://rata.digitraffic.fi/api/v1";
const SOURCE_HEADER = "AppliedAILab/FinlandRailMonitoringSystem github.com/Sintagmatarches";

function isoDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

async function fetchTrains(path: string): Promise<DigitrafficTrain[]> {
  const response = await fetch(`${API_ROOT}${path}`, {
    headers: {
      Accept: "application/json",
      "Accept-Encoding": "gzip",
      "Digitraffic-User": SOURCE_HEADER,
    },
    signal: AbortSignal.timeout(25_000),
  });
  if (!response.ok) throw new Error(`Digitraffic returned ${response.status}`);
  return (await response.json()) as DigitrafficTrain[];
}

async function currentSnapshot(mode: "live" | "24h", now: Date): Promise<RegionalRailSnapshot> {
  if (mode === "live") {
    const trains = await fetchTrains("/live-trains");
    return buildRegionalRailSnapshot(trains, lookup, mode, now);
  }
  const today = new Date(now);
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1_000);
  const partitions = await Promise.all([
    fetchTrains(`/trains/${isoDate(yesterday)}`),
    fetchTrains(`/trains/${isoDate(today)}`),
  ]);
  const unique = new Map<string, DigitrafficTrain>();
  for (const train of partitions.flat()) {
    unique.set(`${train.departureDate}:${train.trainNumber}`, train);
  }
  return buildRegionalRailSnapshot([...unique.values()], lookup, mode, now);
}

export async function GET(request?: Request): Promise<Response> {
  const url = new URL(request?.url ?? "https://localhost/api/rail/monitor");
  const requestedMode = url.searchParams.get("mode") ?? "live";
  if (!(["live", "24h", "7d", "historical"] as RailMonitorMode[]).includes(requestedMode as RailMonitorMode)) {
    return Response.json(
      { error: "Unsupported monitoring mode. Use live, 24h, 7d or historical." },
      { status: 400, headers: { "cache-control": "no-store" } },
    );
  }
  if (requestedMode === "7d") {
    const now = new Date();
    try {
      const publication = await fetchRailPublication();
      const snapshot: RegionalRailSnapshot = {
        ...publication.snapshot,
        freshness: freshnessContract({
          mode: "7d",
          now,
          sourceRetrievedAt: publication.snapshot.sourceRetrievedAt,
          validatedAt: publication.snapshot.validatedAt,
          goldPublishedAt: publication.snapshot.goldPublishedAt,
          coverageStatus: publication.snapshot.coverage.status,
        }),
        publicationSource: "remote-governed",
        publicationId: publication.manifest.publicationId,
        publicationDigest: publication.manifest.snapshotSha256,
      };
      return Response.json(snapshot, {
        headers: { "cache-control": "public, max-age=300, s-maxage=300, stale-while-revalidate=600" },
      });
    } catch (error) {
      console.warn("Remote Rail publication unavailable; serving bundled last-known-good snapshot", error);
      const bundled = validateRailPublicationSnapshot(sevenDaySnapshot);
      const evaluated = freshnessContract({
        mode: "7d",
        now,
        sourceRetrievedAt: bundled.sourceRetrievedAt,
        validatedAt: bundled.validatedAt,
        goldPublishedAt: bundled.goldPublishedAt,
        coverageStatus: bundled.coverage.status,
      });
      const warning = "Remote governed publication is unavailable. This bundled last-known-good snapshot is a fallback and is not considered fresh.";
      const snapshot: RegionalRailSnapshot = {
        ...bundled,
        freshness: { ...evaluated, state: "stale", reason: warning },
        publicationSource: "bundled-fallback",
        publicationWarning: warning,
      };
      return Response.json(snapshot, {
        headers: { "cache-control": "public, max-age=30, s-maxage=60, stale-while-revalidate=120" },
      });
    }
  }
  if (requestedMode === "historical") {
    const stored = historicalSnapshot as unknown as RegionalRailSnapshot;
    const snapshot: RegionalRailSnapshot = {
      ...stored,
      freshness: freshnessContract({
        mode: "historical",
        now: new Date(),
        sourceRetrievedAt: stored.sourceRetrievedAt,
        validatedAt: stored.validatedAt,
        goldPublishedAt: stored.goldPublishedAt,
        coverageStatus: stored.coverage.status,
      }),
    };
    return Response.json(snapshot, {
      headers: { "cache-control": "public, max-age=3600, s-maxage=86400" },
    });
  }

  try {
    const snapshot = await currentSnapshot(requestedMode as "live" | "24h", new Date());
    const cacheControl = requestedMode === "live"
      ? "public, max-age=30, s-maxage=60, stale-while-revalidate=120"
      : "public, max-age=300, s-maxage=900, stale-while-revalidate=1800";
    return Response.json(snapshot, { headers: { "cache-control": cacheControl } });
  } catch (error) {
    console.error("Regional rail monitoring request failed", error);
    return Response.json(
      {
        error: "Current regional railway data is temporarily unavailable.",
        source: "Fintraffic / Digitraffic",
      },
      { status: 502, headers: { "cache-control": "no-store" } },
    );
  }
}
