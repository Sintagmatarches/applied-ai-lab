import assert from "node:assert/strict";
import test from "node:test";

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
      headers: {
        "content-type": "application/json",
        host: "lab.example",
      },
      body: JSON.stringify(payload),
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

const exampleOrder = {
  seller_state: "SP",
  customer_state: "RJ",
  promised_delivery_days: 18,
  primary_category: "health_beauty",
  item_count: 2,
  total_item_value: 149.9,
  total_freight_value: 24.9,
  distance_km: 430,
  total_weight_g: 1600,
  total_volume_cm3: 12000,
  primary_payment_type: "credit_card",
  payment_installments: 4,
  purchase_timestamp: "2018-07-16T14:30:00.000Z",
};

test("scores one order with the exported server-side model", async () => {
  const response = await postPrediction(exampleOrder);
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "no-store");

  const result = await response.json();
  assert.ok(Math.abs(result.probability - 0.15583432) < 0.00001);
  assert.equal(result.model_version, "olist-xgb-2026-07-27.1");
  assert.equal(result.risk_level, "high");
  assert.equal(result.factors.length, 3);
  assert.match(result.disclaimer, /historical Olist orders/i);
});

test("handles an unknown future product category", async () => {
  const response = await postPrediction({
    ...exampleOrder,
    primary_category: "future_category",
  });
  assert.equal(response.status, 200);
  const result = await response.json();
  assert.equal(typeof result.probability, "number");
  assert.ok(result.probability >= 0 && result.probability <= 1);
});

test("rejects impossible form values without scoring", async () => {
  const response = await postPrediction({
    ...exampleOrder,
    promised_delivery_days: -4,
    distance_km: -10,
    item_count: 1.5,
  });
  assert.equal(response.status, 422);
  const result = await response.json();
  assert.ok(result.issues.length >= 3);
});
