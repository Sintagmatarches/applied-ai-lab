import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const fixtures = JSON.parse(
  readFileSync(new URL("../artifacts/parity-fixtures.json", import.meta.url), "utf8"),
);
const exampleCase = fixtures.cases.find((entry) => entry.name === "monday_cross_state");

async function getWorker() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}-${Math.random()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker;
}

async function postPrediction(payload) {
  const worker = await getWorker();
  return worker.fetch(
    new Request("https://lab.example/api/olist/predict", {
      method: "POST",
      headers: { "content-type": "application/json", host: "lab.example" },
      body: JSON.stringify(payload),
    }),
    {
      ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) },
    },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("scores one order through the built Worker with the Python fixture", async () => {
  const response = await postPrediction(exampleCase.input);
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "no-store");
  const result = await response.json();
  assert.ok(Math.abs(result.risk_score - exampleCase.expected.risk_score) < 1e-10);
  assert.equal(result.model_version, fixtures.model_version);
  assert.equal(result.factors.length, 3);
  assert.match(result.display_note, /not an exact probability/i);
  assert.match(result.disclaimer, /not causal explanations/i);
});

test("handles an unknown future product category", async () => {
  const fixture = fixtures.cases.find((entry) => entry.name === "unknown_category");
  const response = await postPrediction(fixture.input);
  assert.equal(response.status, 200);
  const result = await response.json();
  assert.ok(Math.abs(result.risk_score - fixture.expected.risk_score) < 1e-10);
});

test("rejects impossible form values without scoring", async () => {
  const response = await postPrediction({
    ...exampleCase.input,
    promised_delivery_days: -4,
    distance_km: -10,
    item_count: 1.5,
  });
  assert.equal(response.status, 422);
  const result = await response.json();
  assert.ok(result.issues.length >= 3);
});

test("rejects malformed and out-of-domain timestamps as validation errors", async () => {
  for (const purchase_timestamp of ["not-a-date", "2026-08-05T12:00:00Z"]) {
    const response = await postPrediction({
      ...exampleCase.input,
      purchase_timestamp,
    });
    assert.equal(response.status, 422);
    const result = await response.json();
    assert.match(result.issues.join(" "), /purchase_timestamp/i);
  }
});
