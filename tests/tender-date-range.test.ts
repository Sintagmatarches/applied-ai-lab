import assert from "node:assert/strict";
import test from "node:test";
import { createTenderDateRange } from "../lib/tender-date-range";

function assertPlausibleYears(publishedFrom: string, publishedTo: string) {
  assert.ok(Number(publishedFrom.slice(0, 4)) >= 2020, `Implausible Published from year: ${publishedFrom}`);
  assert.ok(Number(publishedTo.slice(0, 4)) >= 2020, `Implausible Published to year: ${publishedTo}`);
}

test("creates a plausible 90-day UTC TED date window", () => {
  const range = createTenderDateRange(new Date("2026-08-18T21:30:00+03:00"));
  assert.deepEqual(range, { publishedFrom: "2026-05-20", publishedTo: "2026-08-18" });
  assertPlausibleYears(range.publishedFrom, range.publishedTo);
});

test("crosses a year boundary without falling back to the Unix epoch", () => {
  const range = createTenderDateRange(new Date("2026-01-01T00:30:00Z"));
  assert.deepEqual(range, { publishedFrom: "2025-10-03", publishedTo: "2026-01-01" });
  assertPlausibleYears(range.publishedFrom, range.publishedTo);
});

test("uses the UTC calendar date when the positive timezone is on the next local day", () => {
  const range = createTenderDateRange(new Date("2026-01-01T00:30:00+14:00"));
  assert.deepEqual(range, { publishedFrom: "2025-10-02", publishedTo: "2025-12-31" });
  assertPlausibleYears(range.publishedFrom, range.publishedTo);
});

test("uses the UTC calendar date when the negative timezone is on the previous local day", () => {
  const range = createTenderDateRange(new Date("2025-12-31T23:30:00-12:00"));
  assert.deepEqual(range, { publishedFrom: "2025-10-03", publishedTo: "2026-01-01" });
  assertPlausibleYears(range.publishedFrom, range.publishedTo);
});

test("handles a leap-year month boundary using UTC calendar arithmetic", () => {
  const range = createTenderDateRange(new Date("2024-03-01T00:00:00Z"));
  assert.deepEqual(range, { publishedFrom: "2023-12-02", publishedTo: "2024-03-01" });
  assertPlausibleYears(range.publishedFrom, range.publishedTo);
});

test("rejects invalid dates and invalid windows", () => {
  assert.throws(() => createTenderDateRange(new Date("invalid")), /valid current date/);
  assert.throws(() => createTenderDateRange(new Date("2026-08-18T00:00:00Z"), -1), /non-negative integer/);
  assert.throws(() => createTenderDateRange(new Date("2026-08-18T00:00:00Z"), 1.5), /non-negative integer/);
});
