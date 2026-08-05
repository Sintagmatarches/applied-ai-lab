import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  scoreOlistModel,
  validatePredictionInput,
} from "../lib/olist-model.ts";
import {
  BRAZILIAN_STATE_CODES,
  OLIST_PAYMENT_TYPES,
} from "../lib/olist-input-contract.ts";

type Fixture = {
  model_version: string;
  tolerance: { vector: number; score: number };
  cases: Array<{
    name: string;
    input: Record<string, unknown>;
    expected: {
      feature_vector: number[];
      raw_score: number;
      probability: number;
      risk_score: number;
    };
  }>;
};

const fixtures = JSON.parse(
  readFileSync(new URL("../artifacts/parity-fixtures.json", import.meta.url), "utf8"),
) as Fixture;

for (const fixture of fixtures.cases) {
  test(`matches Python scoring for ${fixture.name}`, () => {
    const input = validatePredictionInput(fixture.input);
    const actual = scoreOlistModel(input);
    assert.equal(actual.feature_vector.length, fixture.expected.feature_vector.length);
    actual.feature_vector.forEach((value, index) => {
      assert.ok(
        Math.abs(value - fixture.expected.feature_vector[index]) <=
          fixtures.tolerance.vector,
        `${fixture.name} feature ${index} differs: ${value} vs ${fixture.expected.feature_vector[index]}`,
      );
    });
    for (const field of ["raw_score", "probability", "risk_score"] as const) {
      assert.ok(
        Math.abs(actual[field] - fixture.expected[field]) <=
          fixtures.tolerance.score,
        `${fixture.name} ${field} differs: ${actual[field]} vs ${fixture.expected[field]}`,
      );
    }
  });
}

test("accepts every supported state and payment value", () => {
  const baseInput = fixtures.cases[0].input;
  for (const state of BRAZILIAN_STATE_CODES) {
    assert.equal(validatePredictionInput({ ...baseInput, seller_state: state }).seller_state, state);
    assert.equal(validatePredictionInput({ ...baseInput, customer_state: state }).customer_state, state);
  }
  for (const paymentType of OLIST_PAYMENT_TYPES) {
    assert.equal(
      validatePredictionInput({
        ...baseInput,
        primary_payment_type: paymentType,
      }).primary_payment_type,
      paymentType,
    );
  }
});

test("normalizes equivalent timezone-aware timestamps", () => {
  const baseInput = fixtures.cases[0].input;
  const utc = validatePredictionInput({
    ...baseInput,
    purchase_timestamp: "2018-07-16T14:30:00Z",
  });
  const offset = validatePredictionInput({
    ...baseInput,
    purchase_timestamp: "2018-07-16T11:30:00-03:00",
  });
  assert.equal(utc.purchase_timestamp, "2018-07-16T14:30:00.000Z");
  assert.equal(offset.purchase_timestamp, utc.purchase_timestamp);
});
