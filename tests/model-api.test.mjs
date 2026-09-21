import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createHash } from "node:crypto";

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
  assert.equal(result.schema_version, 1);
  assert.equal(result.factors.length, 3);
  assert.match(result.display_note, /not an exact probability/i);
  assert.match(result.disclaimer, /not causal explanations/i);
});

test("metadata identifies the exact bundled artifact without exposing history", async () => {
  const worker = await getWorker();
  const response = await worker.fetch(new Request("https://lab.example/api/olist/model"),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} });
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "no-store");
  const metadata = await response.json();
  const artifact = JSON.parse(readFileSync(new URL("../artifacts/olist-model.json", import.meta.url), "utf8"));
  assert.equal(metadata.artifactSha256, createHash("sha256").update(JSON.stringify(artifact)).digest("hex"));
  assert.equal(metadata.version, fixtures.model_version);
  assert.equal(metadata.schemaVersion, 1);
  assert.equal(metadata.history, undefined);
  assert.deepEqual(metadata.featureContract, artifact.feature_contract);
});

test("accepts explicit v1 and rejects unsupported prediction contracts", async () => {
  assert.equal((await postPrediction({ ...exampleCase.input, schema_version: 1 })).status, 200);
  for (const schema_version of [2, "1", null]) {
    const response = await postPrediction({ ...exampleCase.input, schema_version });
    assert.equal(response.status, 422);
    assert.match((await response.json()).issues.join(" "), /schema_version/);
  }
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
  assert.equal(result.error, "Please review the order details listed below.");
  assert.doesNotMatch(result.error, /highlighted/i);
});

test("rejects invented states and payment methods", async () => {
  const response = await postPrediction({
    ...exampleCase.input,
    seller_state: "ZZ",
    customer_state: "XX",
    primary_payment_type: "cash",
  });
  assert.equal(response.status, 422);
  const result = await response.json();
  assert.match(result.issues.join(" "), /seller_state.*Brazilian state/i);
  assert.match(result.issues.join(" "), /customer_state.*Brazilian state/i);
  assert.match(result.issues.join(" "), /primary_payment_type.*credit_card/i);
});

test("requires a real ISO timestamp with an explicit timezone", async () => {
  for (const purchase_timestamp of [
    "not-a-date",
    "2018-07-16T14:30:00",
    "2018-07-16 14:30:00Z",
    "2018-02-30T14:30:00Z",
    "2018-07-16T14:30:00+15:00",
    "2026-08-05T12:00:00Z",
  ]) {
    const response = await postPrediction({
      ...exampleCase.input,
      purchase_timestamp,
    });
    assert.equal(response.status, 422);
    const result = await response.json();
    assert.match(result.issues.join(" "), /purchase_timestamp/i);
  }
});
