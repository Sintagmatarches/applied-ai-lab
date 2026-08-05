import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  scoreOlistModel,
  validatePredictionInput,
} from "../lib/olist-model.ts";

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
