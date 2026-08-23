import assert from "node:assert/strict";
import test from "node:test";

import { freshnessContract, sampleSupport, wilsonInterval } from "../lib/rail-operational";

test("sample support uses mode-specific count and coverage boundaries", () => {
  assert.equal(sampleSupport("live", 7, 7).status, "low-sample");
  assert.equal(sampleSupport("live", 8, 8).status, "sufficient");
  assert.equal(sampleSupport("24h", 30, 19).status, "low-sample");
  assert.equal(sampleSupport("24h", 25, 20).status, "sufficient");
  assert.equal(sampleSupport("historical", 0, 0, false).status, "not-applicable");
});

test("Wilson intervals cover empty, extreme and interior proportions", () => {
  assert.equal(wilsonInterval(0, 0), null);
  assert.ok(wilsonInterval(1, 1)!.lower > 0);
  assert.ok(wilsonInterval(1, 100)!.lower < 0.01);
  assert.ok(wilsonInterval(99, 100)!.upper > 0.99);
  const interior = wilsonInterval(50, 100)!;
  assert.ok(interior.lower < 0.5 && interior.upper > 0.5);
});

test("freshness follows publication evidence rather than process activity", () => {
  const now = new Date("2026-08-23T12:00:00Z");
  const atAge = (minutes: number) => new Date(now.getTime() - minutes * 60_000).toISOString();
  assert.equal(freshnessContract({
    mode: "live", now, sourceRetrievedAt: atAge(5), validatedAt: atAge(5), goldPublishedAt: atAge(5),
  }).state, "fresh");
  assert.equal(freshnessContract({
    mode: "live", now, sourceRetrievedAt: atAge(6), validatedAt: atAge(6), goldPublishedAt: atAge(6),
  }).state, "warning");
  assert.equal(freshnessContract({
    mode: "live", now, sourceRetrievedAt: atAge(16), validatedAt: atAge(16), goldPublishedAt: atAge(16),
  }).state, "stale");
  assert.equal(freshnessContract({
    mode: "7d", now, sourceRetrievedAt: atAge(1), validatedAt: atAge(1), goldPublishedAt: null,
  }).state, "stale");
  assert.equal(freshnessContract({
    mode: "7d", now, sourceRetrievedAt: atAge(1), validatedAt: atAge(1), goldPublishedAt: atAge(1), coverageStatus: "partial",
  }).state, "stale");
});
