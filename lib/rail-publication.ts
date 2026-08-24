import regionsLookup from "../artifacts/rail-station-regions.json";
import { RAIL_OPERATIONAL_POLICY, sampleSupport, wilsonInterval } from "./rail-operational";
import { RAIL_DELAY_THRESHOLDS, type RegionalRailSnapshot } from "./rail-monitoring";

export const RAIL_PUBLICATION_MANIFEST_URL =
  "https://raw.githubusercontent.com/Sintagmatarches/applied-ai-lab/rail-publications/manifest.json";
const PUBLICATION_BASE_URL =
  "https://raw.githubusercontent.com/Sintagmatarches/applied-ai-lab/rail-publications/";
const MANIFEST_SCHEMA_VERSION = "rail-publication-manifest-v1";
const CACHE_MILLISECONDS = 5 * 60_000;
const REQUEST_TIMEOUT_MILLISECONDS = 8_000;

export type RailPublicationManifest = {
  schemaVersion: string;
  publicationId: string;
  generatedAt: string;
  windowStart: string;
  windowEnd: string;
  latestCompletePartition: string;
  coverageStatus: string;
  source: string;
  snapshotPath: string;
  snapshotSha256: string;
  kpiDefinitionVersion: string;
  sampleSupportPolicyVersion: string;
  freshnessPolicyVersion: string;
  snapshotSchemaVersion: string;
};

export class RailPublicationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RailPublicationError";
  }
}

type RemotePublication = { manifest: RailPublicationManifest; snapshot: RegionalRailSnapshot };
type Fetcher = typeof fetch;
let cache: { expiresAt: number; value: RemotePublication } | null = null;

function fail(message: string): never {
  throw new RailPublicationError(message);
}

function record(value: unknown, path: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(`${path} must be an object`);
  return value as Record<string, unknown>;
}

function string(value: unknown, path: string): string {
  if (typeof value !== "string") fail(`${path} must be a string`);
  return value;
}

function integer(value: unknown, path: string): number {
  if (!Number.isInteger(value) || (value as number) < 0) fail(`${path} must be a non-negative integer`);
  return value as number;
}

function close(left: unknown, right: number | null): boolean {
  if (right == null) return left === null;
  return typeof left === "number" && Number.isFinite(left) && Math.abs(left - right) <= 1e-10;
}

function timestamp(value: unknown, path: string): number {
  const raw = string(value, path);
  if (!/T.*(?:Z|[+-]\d{2}:\d{2})$/.test(raw)) fail(`${path} must include an explicit timezone`);
  const parsed = Date.parse(raw);
  if (!Number.isFinite(parsed)) fail(`${path} must be an ISO timestamp`);
  return parsed;
}

function expectedDates(startValue: unknown, endValue: unknown): string[] {
  const start = timestamp(startValue, "snapshot.windowStart");
  const end = timestamp(endValue, "snapshot.windowEnd");
  const values: string[] = [];
  for (let current = new Date(start); current.getTime() <= end; current = new Date(current.getTime() + 86_400_000)) {
    values.push(current.toISOString().slice(0, 10));
  }
  return values;
}

function sameStrings(value: unknown, expected: string[], path: string): void {
  if (!Array.isArray(value) || value.length !== expected.length ||
      value.some((item, index) => item !== expected[index])) fail(`${path} is incompatible`);
}

function validateMetric(value: unknown, path: string, hasRailService = true): void {
  const metric = record(value, path);
  const observed = integer(metric.observedTrains, `${path}.observedTrains`);
  const measured = integer(metric.measuredTrains, `${path}.measuredTrains`);
  const severe = integer(metric.severeDelays, `${path}.severeDelays`);
  const cancellations = integer(metric.cancellations, `${path}.cancellations`);
  if (measured > observed || severe > measured || cancellations > observed) fail(`${path} counts do not reconcile`);
  const delayed = record(metric.delayedTrainsByThreshold, `${path}.delayedTrainsByThreshold`);
  const shares = record(metric.delayedShareByThreshold, `${path}.delayedShareByThreshold`);
  const intervals = record(metric.delayedShareInterval95ByThreshold, `${path}.delayedShareInterval95ByThreshold`);
  let previous = Number.POSITIVE_INFINITY;
  for (const threshold of RAIL_DELAY_THRESHOLDS) {
    const key = String(threshold);
    const count = integer(delayed[key], `${path}.delayedTrainsByThreshold.${key}`);
    if (count > measured || count > previous) fail(`${path} threshold counts do not reconcile`);
    previous = count;
    const share = measured ? count / measured : null;
    if (!close(shares[key], share)) fail(`${path}.delayedShareByThreshold.${key} does not reconcile`);
    const interval = wilsonInterval(count, measured);
    if (interval == null) {
      if (intervals[key] !== null) fail(`${path}.delayedShareInterval95ByThreshold.${key} must be null`);
    } else {
      const actual = record(intervals[key], `${path}.delayedShareInterval95ByThreshold.${key}`);
      if (!close(actual.lower, interval.lower) || !close(actual.upper, interval.upper)) fail(`${path} Wilson interval does not reconcile`);
    }
  }
  if (metric.delayedTrains !== delayed["5"] || !close(metric.delayedShare, shares["5"] as number | null)) {
    fail(`${path} five-minute aliases do not reconcile`);
  }
  const expectedSupport = sampleSupport("7d", observed, measured, hasRailService);
  if (JSON.stringify(metric.sampleSupport) !== JSON.stringify(expectedSupport)) fail(`${path}.sampleSupport violates policy`);
}

export function validateRailPublicationManifest(value: unknown): RailPublicationManifest {
  const manifest = record(value, "manifest");
  const required = [
    "schemaVersion", "publicationId", "generatedAt", "windowStart", "windowEnd", "latestCompletePartition",
    "coverageStatus", "source", "snapshotPath", "snapshotSha256", "kpiDefinitionVersion",
    "sampleSupportPolicyVersion", "freshnessPolicyVersion", "snapshotSchemaVersion",
  ];
  if (Object.keys(manifest).length !== required.length || required.some((field) => !(field in manifest))) {
    fail("manifest fields are incomplete or unexpected");
  }
  for (const field of required) string(manifest[field], `manifest.${field}`);
  if (manifest.schemaVersion !== MANIFEST_SCHEMA_VERSION) fail("manifest schemaVersion is incompatible");
  if (!/^[0-9a-f]{64}$/.test(manifest.snapshotSha256 as string)) fail("manifest snapshotSha256 is invalid");
  if (!/^snapshots\/\d{4}-\d{2}-\d{2}-[0-9a-f]{12}\.json$/.test(manifest.snapshotPath as string)) fail("manifest snapshotPath is invalid");
  if (manifest.snapshotPath !== `snapshots/${manifest.publicationId}.json`) fail("manifest publication path is not canonical");
  if (manifest.publicationId !== `${manifest.latestCompletePartition}-${(manifest.snapshotSha256 as string).slice(0, 12)}`) fail("manifest publicationId is invalid");
  timestamp(manifest.generatedAt, "manifest.generatedAt");
  return manifest as RailPublicationManifest;
}

export function validateRailPublicationSnapshot(value: unknown): RegionalRailSnapshot {
  const snapshot = record(value, "snapshot");
  const policy = RAIL_OPERATIONAL_POLICY;
  const versions: Record<string, string> = {
    schemaVersion: policy.snapshotSchemaVersion,
    kpiDefinitionVersion: policy.kpiDefinitionVersion,
    sampleSupportPolicyVersion: policy.sampleSupport.version,
    freshnessPolicyVersion: policy.freshness.version,
  };
  for (const [field, expected] of Object.entries(versions)) {
    if (snapshot[field] !== expected) fail(`snapshot ${field} is incompatible`);
  }
  if (snapshot.mode !== "7d" || snapshot.source !== "Fintraffic / Digitraffic") fail("snapshot publication identity is incompatible");
  const dates = expectedDates(snapshot.windowStart, snapshot.windowEnd);
  if (dates.length !== policy.freshness.requiredSevenDayPartitions) fail("snapshot window must contain exactly seven dates");
  if (snapshot.latestCompletePartition !== dates.at(-1)) fail("snapshot latestCompletePartition is invalid");
  const coverage = record(snapshot.coverage, "snapshot.coverage");
  if (coverage.status !== "complete" || coverage.coverageRatio !== 1 || coverage.duplicatePartitions !== 0) fail("snapshot coverage must be complete");
  sameStrings(coverage.expectedDates, dates, "snapshot.coverage.expectedDates");
  sameStrings(coverage.availableDates, dates, "snapshot.coverage.availableDates");
  sameStrings(coverage.missingDates, [], "snapshot.coverage.missingDates");
  sameStrings(coverage.failedDates, [], "snapshot.coverage.failedDates");
  const sourceTime = timestamp(snapshot.sourceRetrievedAt, "snapshot.sourceRetrievedAt");
  const validatedTime = timestamp(snapshot.validatedAt, "snapshot.validatedAt");
  const goldTime = timestamp(snapshot.goldPublishedAt, "snapshot.goldPublishedAt");
  if (sourceTime > validatedTime || validatedTime > goldTime) fail("snapshot freshness timestamp ordering is invalid");
  const freshness = record(snapshot.freshness, "snapshot.freshness");
  if (freshness.policyVersion !== policy.freshness.version || freshness.basis !== "goldPublishedAt") fail("snapshot freshness contract is incompatible");
  if (freshness.state !== "fresh" || freshness.sourceRetrievedAt !== snapshot.sourceRetrievedAt ||
      freshness.validatedAt !== snapshot.validatedAt || freshness.goldPublishedAt !== snapshot.goldPublishedAt) {
    fail("snapshot embedded freshness contract does not reconcile");
  }
  const expectedCodes = new Set(regionsLookup.regions.map((region) => region.code));
  if (!Array.isArray(snapshot.regions) || snapshot.regions.length !== expectedCodes.size) fail("snapshot must contain exactly 19 regions");
  const actualCodes = new Set<string>();
  for (const [index, value] of snapshot.regions.entries()) {
    const region = record(value, `snapshot.regions.${index}`);
    const code = string(region.code, `snapshot.regions.${index}.code`);
    if (!expectedCodes.has(code) || actualCodes.has(code)) fail("snapshot region codes are incomplete or duplicated");
    actualCodes.add(code);
    if (typeof region.hasRailService !== "boolean") fail(`snapshot.regions.${code}.hasRailService is invalid`);
    validateMetric(region, `snapshot.regions.${code}`, region.hasRailService);
    if (code === "21" && (region.hasRailService !== false || region.status !== "no-service" ||
        region.disruptionScore !== null || region.reliabilityScore !== null)) fail("snapshot Åland invariant failed");
  }
  if (actualCodes.size !== expectedCodes.size) fail("snapshot region codes are incomplete or duplicated");
  validateMetric(snapshot.network, "snapshot.network");
  return snapshot as unknown as RegionalRailSnapshot;
}

export async function sha256Hex(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function request(fetcher: Fetcher, url: string, signal: AbortSignal): Promise<Response> {
  let response: Response;
  try {
    response = await fetcher(url, { headers: { Accept: "application/json" }, signal });
  } catch (error) {
    throw new RailPublicationError(`publication request failed: ${error instanceof Error ? error.name : "network error"}`);
  }
  if (!response.ok) fail(`publication request returned ${response.status}`);
  return response;
}

export async function fetchRailPublication(args: {
  fetcher?: Fetcher;
  nowMilliseconds?: number;
  useCache?: boolean;
} = {}): Promise<RemotePublication> {
  const now = args.nowMilliseconds ?? Date.now();
  if (args.useCache !== false && cache && cache.expiresAt > now) return cache.value;
  const fetcher = args.fetcher ?? fetch;
  const signal = AbortSignal.timeout(REQUEST_TIMEOUT_MILLISECONDS);
  const manifestResponse = await request(fetcher, RAIL_PUBLICATION_MANIFEST_URL, signal);
  let manifestValue: unknown;
  try { manifestValue = await manifestResponse.json(); } catch { fail("manifest is not valid JSON"); }
  const manifest = validateRailPublicationManifest(manifestValue);
  const snapshotResponse = await request(fetcher, `${PUBLICATION_BASE_URL}${manifest.snapshotPath}`, signal);
  const bytes = await snapshotResponse.arrayBuffer();
  const digest = await sha256Hex(bytes);
  if (digest !== manifest.snapshotSha256) fail("snapshot SHA-256 does not match manifest");
  let snapshotValue: unknown;
  try { snapshotValue = JSON.parse(new TextDecoder().decode(bytes)); } catch { fail("snapshot is not valid JSON"); }
  const snapshot = validateRailPublicationSnapshot(snapshotValue);
  const matches = snapshot.kpiDefinitionVersion === manifest.kpiDefinitionVersion &&
    snapshot.sampleSupportPolicyVersion === manifest.sampleSupportPolicyVersion &&
    snapshot.freshnessPolicyVersion === manifest.freshnessPolicyVersion &&
    snapshot.schemaVersion === manifest.snapshotSchemaVersion && snapshot.windowStart === manifest.windowStart &&
    snapshot.windowEnd === manifest.windowEnd && snapshot.latestCompletePartition === manifest.latestCompletePartition &&
    snapshot.coverage.status === manifest.coverageStatus && snapshot.source === manifest.source &&
    snapshot.goldPublishedAt === manifest.generatedAt;
  if (!matches) fail("manifest metadata does not match snapshot");
  const value = { manifest, snapshot };
  if (args.useCache !== false) cache = { expiresAt: now + CACHE_MILLISECONDS, value };
  return value;
}

export function clearRailPublicationCacheForTests(): void {
  cache = null;
}
