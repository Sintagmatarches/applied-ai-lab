import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  RAIL_PUBLICATION_MANIFEST_URL,
  clearRailPublicationCacheForTests,
  fetchRailPublication,
  sha256Hex,
  validateRailPublicationSnapshot,
  type RailPublicationManifest,
} from "../lib/rail-publication.ts";

const SNAPSHOT_PATH = new URL("../artifacts/rail-regional-7d.json", import.meta.url);

async function fixture(snapshotOverride?: (value: Record<string, unknown>) => void) {
  const original = JSON.parse(await readFile(SNAPSHOT_PATH, "utf8")) as Record<string, unknown>;
  snapshotOverride?.(original);
  const bytes = new TextEncoder().encode(JSON.stringify(original));
  const digest = await sha256Hex(bytes.buffer);
  const coverage = original.coverage as Record<string, unknown>;
  const manifest: RailPublicationManifest = {
    schemaVersion: "rail-publication-manifest-v1",
    publicationId: `${original.latestCompletePartition}-${digest.slice(0, 12)}`,
    generatedAt: original.goldPublishedAt as string,
    windowStart: original.windowStart as string,
    windowEnd: original.windowEnd as string,
    latestCompletePartition: original.latestCompletePartition as string,
    coverageStatus: coverage.status as string,
    source: original.source as string,
    snapshotPath: `snapshots/${original.latestCompletePartition}-${digest.slice(0, 12)}.json`,
    snapshotSha256: digest,
    kpiDefinitionVersion: original.kpiDefinitionVersion as string,
    sampleSupportPolicyVersion: original.sampleSupportPolicyVersion as string,
    freshnessPolicyVersion: original.freshnessPolicyVersion as string,
    snapshotSchemaVersion: original.schemaVersion as string,
  };
  return { bytes, manifest, snapshot: original };
}

function fetcher(manifestBody: BodyInit, snapshotBody: BodyInit, statuses = [200, 200]): typeof fetch {
  return (async (input: string | URL | Request) => {
    const url = String(input);
    if (url === RAIL_PUBLICATION_MANIFEST_URL) return new Response(manifestBody, { status: statuses[0] });
    return new Response(snapshotBody, { status: statuses[1] });
  }) as typeof fetch;
}

test("remote publication validates manifest, exact digest and governed snapshot", async () => {
  const { bytes, manifest } = await fixture();
  clearRailPublicationCacheForTests();
  const result = await fetchRailPublication({
    fetcher: fetcher(JSON.stringify(manifest), bytes), useCache: false,
  });
  assert.equal(result.manifest.publicationId, manifest.publicationId);
  assert.equal(result.snapshot.regions.length, 19);
  assert.equal(result.snapshot.coverage.status, "complete");
});

test("remote publication rejects malformed JSON, HTTP failure and timeout", async () => {
  const { bytes, manifest } = await fixture();
  await assert.rejects(fetchRailPublication({ fetcher: fetcher("{", bytes), useCache: false }), /manifest is not valid JSON/);
  await assert.rejects(fetchRailPublication({ fetcher: fetcher(JSON.stringify(manifest), bytes, [503, 200]), useCache: false }), /returned 503/);
  const timeoutFetcher = (async () => { throw new DOMException("timed out", "TimeoutError"); }) as typeof fetch;
  await assert.rejects(fetchRailPublication({ fetcher: timeoutFetcher, useCache: false }), /TimeoutError/);
});

test("remote publication rejects digest mismatch", async () => {
  const { bytes, manifest } = await fixture();
  manifest.snapshotSha256 = "0".repeat(64);
  manifest.publicationId = `${manifest.latestCompletePartition}-${manifest.snapshotSha256.slice(0, 12)}`;
  manifest.snapshotPath = `snapshots/${manifest.publicationId}.json`;
  await assert.rejects(
    fetchRailPublication({ fetcher: fetcher(JSON.stringify(manifest), bytes), useCache: false }),
    /SHA-256 does not match/,
  );
});

test("snapshot validation rejects policy, mode, coverage, date and region defects", async () => {
  const cases: Array<[string, (value: Record<string, unknown>) => void, RegExp]> = [
    ["schema", (value) => { value.schemaVersion = "wrong"; }, /schemaVersion/],
    ["KPI", (value) => { value.kpiDefinitionVersion = "wrong"; }, /kpiDefinitionVersion/],
    ["sample", (value) => { value.sampleSupportPolicyVersion = "wrong"; }, /sampleSupportPolicyVersion/],
    ["freshness", (value) => { value.freshnessPolicyVersion = "wrong"; }, /freshnessPolicyVersion/],
    ["mode", (value) => { value.mode = "24h"; }, /identity/],
    ["coverage", (value) => { (value.coverage as Record<string, unknown>).status = "partial"; }, /complete/],
    ["date", (value) => { (value.coverage as Record<string, unknown>).availableDates = []; }, /availableDates/],
    ["timezone", (value) => { value.goldPublishedAt = "2026-08-23T12:41:19"; }, /timezone/],
    ["region", (value) => { (value.regions as unknown[]).pop(); }, /19 regions/],
  ];
  for (const [name, mutate, expected] of cases) {
    const { snapshot } = await fixture(mutate);
    assert.throws(() => validateRailPublicationSnapshot(snapshot), expected, name);
  }
});

test("7d API exposes verified remote provenance", async () => {
  const { bytes, manifest } = await fixture();
  const originalFetch = globalThis.fetch;
  globalThis.fetch = fetcher(JSON.stringify(manifest), bytes);
  try {
    clearRailPublicationCacheForTests();
    const { GET } = await import("../app/api/rail/monitor/route.ts");
    const response = await GET(new Request("https://example.test/api/rail/monitor?mode=7d"));
    const body = await response.json() as Record<string, unknown>;
    assert.equal(response.status, 200);
    assert.equal(body.publicationSource, "remote-governed");
    assert.equal(body.publicationId, manifest.publicationId);
    assert.equal(body.publicationDigest, manifest.snapshotSha256);
    assert.equal(body.publicationWarning, undefined);
  } finally {
    clearRailPublicationCacheForTests();
    globalThis.fetch = originalFetch;
  }
});
