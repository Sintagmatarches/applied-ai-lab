import modelJson from "../artifacts/olist-model.json";

type TreeNode = {
  nodeid: number;
  split?: string;
  split_condition?: number;
  yes?: number;
  no?: number;
  missing?: number;
  leaf?: number;
  children?: TreeNode[];
};

type NumericTransform = {
  index: number;
  median: number;
  mean: number;
  scale: number;
};

type CategoryTransform = {
  default: string;
  indices: Record<string, number>;
};

type ModelArtifact = {
  model_version: string;
  feature_count: number;
  numeric: Record<string, NumericTransform>;
  categorical: Record<string, CategoryTransform>;
  trees: TreeNode[];
  raw_margin_intercept: number;
  calibration: {
    slope: number;
    intercept: number;
  };
  thresholds: {
    standard: number;
    working: number;
    working_alert_cap_on_validation: number;
    low_medium_boundary: number;
  };
  limitations: string[];
};

export type OlistPredictionInput = {
  seller_state: string;
  customer_state: string;
  promised_delivery_days: number;
  primary_category: string;
  item_count: number;
  total_item_value: number;
  total_freight_value: number;
  distance_km: number;
  total_weight_g: number;
  total_volume_cm3: number;
  primary_payment_type: string;
  payment_installments: number;
  purchase_timestamp: string;
};

export type OlistPrediction = {
  probability: number;
  probability_percent: number;
  risk_level: "low" | "medium" | "high";
  decision: "elevated delay risk" | "no elevated delay risk";
  factors: Array<{
    name: string;
    effect: "raises risk" | "lowers risk";
    probability_point_change: number;
    explanation: string;
  }>;
  model_version: string;
  threshold: number;
  disclaimer: string;
};

export class PredictionInputError extends Error {
  readonly issues: string[];

  constructor(issues: string[]) {
    super("Invalid prediction input");
    this.issues = issues;
  }
}

const model = modelJson as unknown as ModelArtifact;

const referenceInput: OlistPredictionInput = {
  seller_state: model.categorical.seller_state.default,
  customer_state: model.categorical.customer_state.default,
  promised_delivery_days: model.numeric.promised_delivery_days.median,
  primary_category: model.categorical.primary_category.default,
  item_count: model.numeric.item_count.median,
  total_item_value: model.numeric.total_item_value.median,
  total_freight_value: model.numeric.total_freight_value.median,
  distance_km: model.numeric.distance_km.median,
  total_weight_g: model.numeric.total_weight_g.median,
  total_volume_cm3: model.numeric.total_volume_cm3.median,
  primary_payment_type: model.categorical.primary_payment_type.default,
  payment_installments: model.numeric.payment_installments.median,
  purchase_timestamp: "2017-05-03T15:00:00.000Z",
};

const factorGroups: Array<{
  name: string;
  keys: Array<keyof OlistPredictionInput>;
  explanation: string;
}> = [
  {
    name: "Route and states",
    keys: ["seller_state", "customer_state"],
    explanation: "seller and customer location pattern",
  },
  {
    name: "Promised delivery window",
    keys: ["promised_delivery_days"],
    explanation: "days available before the promised date",
  },
  {
    name: "Distance",
    keys: ["distance_km"],
    explanation: "user-supplied shipping distance",
  },
  {
    name: "Order timing",
    keys: ["purchase_timestamp"],
    explanation: "year, month, weekday and hour of purchase",
  },
  {
    name: "Product category",
    keys: ["primary_category"],
    explanation: "historical pattern for the selected category",
  },
  {
    name: "Order size",
    keys: ["item_count"],
    explanation: "number of items in the order",
  },
  {
    name: "Order value",
    keys: ["total_item_value", "total_freight_value"],
    explanation: "item and freight values",
  },
  {
    name: "Parcel size",
    keys: ["total_weight_g", "total_volume_cm3"],
    explanation: "parcel weight and volume",
  },
  {
    name: "Payment",
    keys: ["primary_payment_type", "payment_installments"],
    explanation: "payment method and installment count",
  },
];

function readFiniteNumber(
  value: unknown,
  field: string,
  minimum: number,
  maximum: number,
  issues: string[],
): number {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number) || number < minimum || number > maximum) {
    issues.push(`${field} must be between ${minimum} and ${maximum}.`);
    return minimum;
  }
  return number;
}

function readText(
  value: unknown,
  field: string,
  pattern: RegExp,
  issues: string[],
): string {
  const text = String(value ?? "").trim();
  if (!pattern.test(text)) {
    issues.push(`${field} has an invalid value.`);
  }
  return text;
}

export function validatePredictionInput(
  payload: unknown,
): OlistPredictionInput {
  const body =
    payload && typeof payload === "object"
      ? (payload as Record<string, unknown>)
      : {};
  const issues: string[] = [];
  const sellerState = readText(
    body.seller_state,
    "seller_state",
    /^[A-Za-z]{2}$/,
    issues,
  ).toUpperCase();
  const customerState = readText(
    body.customer_state,
    "customer_state",
    /^[A-Za-z]{2}$/,
    issues,
  ).toUpperCase();
  const category = readText(
    body.primary_category,
    "primary_category",
    /^[A-Za-z0-9_]{1,80}$/,
    issues,
  ).toLowerCase();
  const paymentType = readText(
    body.primary_payment_type,
    "primary_payment_type",
    /^[A-Za-z0-9_]{1,40}$/,
    issues,
  ).toLowerCase();
  const purchaseTimestamp = String(body.purchase_timestamp ?? "");
  const purchaseDate = new Date(purchaseTimestamp);
  if (!purchaseTimestamp || Number.isNaN(purchaseDate.getTime())) {
    issues.push("purchase_timestamp must be a valid date and time.");
  }

  const input: OlistPredictionInput = {
    seller_state: sellerState,
    customer_state: customerState,
    promised_delivery_days: readFiniteNumber(
      body.promised_delivery_days,
      "promised_delivery_days",
      1,
      180,
      issues,
    ),
    primary_category: category,
    item_count: readFiniteNumber(
      body.item_count,
      "item_count",
      1,
      50,
      issues,
    ),
    total_item_value: readFiniteNumber(
      body.total_item_value,
      "total_item_value",
      0,
      50_000,
      issues,
    ),
    total_freight_value: readFiniteNumber(
      body.total_freight_value,
      "total_freight_value",
      0,
      5_000,
      issues,
    ),
    distance_km: readFiniteNumber(
      body.distance_km,
      "distance_km",
      0,
      10_000,
      issues,
    ),
    total_weight_g: readFiniteNumber(
      body.total_weight_g,
      "total_weight_g",
      0,
      250_000,
      issues,
    ),
    total_volume_cm3: readFiniteNumber(
      body.total_volume_cm3,
      "total_volume_cm3",
      0,
      2_000_000,
      issues,
    ),
    primary_payment_type: paymentType,
    payment_installments: readFiniteNumber(
      body.payment_installments,
      "payment_installments",
      0,
      36,
      issues,
    ),
    purchase_timestamp: purchaseDate.toISOString(),
  };

  if (!Number.isInteger(input.item_count)) {
    issues.push("item_count must be a whole number.");
  }
  if (!Number.isInteger(input.payment_installments)) {
    issues.push("payment_installments must be a whole number.");
  }
  if (issues.length) {
    throw new PredictionInputError(issues);
  }
  return input;
}

function rawFeatures(input: OlistPredictionInput): Record<string, number | string> {
  const timestamp = new Date(input.purchase_timestamp);
  return {
    purchase_year: timestamp.getUTCFullYear(),
    purchase_month: timestamp.getUTCMonth() + 1,
    purchase_day_of_week: timestamp.getUTCDay() + 1,
    purchase_hour: timestamp.getUTCHours(),
    promised_delivery_days: input.promised_delivery_days,
    seller_state: input.seller_state,
    customer_state: input.customer_state,
    route: `${input.seller_state} → ${input.customer_state}`,
    same_state: input.seller_state === input.customer_state ? 1 : 0,
    distance_km: input.distance_km,
    item_count: input.item_count,
    primary_category: input.primary_category,
    total_item_value: input.total_item_value,
    total_freight_value: input.total_freight_value,
    total_weight_g: input.total_weight_g,
    total_volume_cm3: input.total_volume_cm3,
    primary_payment_type: input.primary_payment_type,
    payment_installments: input.payment_installments,
  };
}

export function prepareFeatureVector(
  input: OlistPredictionInput,
): number[] {
  const vector = Array<number>(model.feature_count).fill(Number.NaN);
  const features = rawFeatures(input);

  for (const [name, transform] of Object.entries(model.numeric)) {
    const raw = Number(features[name]);
    const safeValue = Number.isFinite(raw) ? raw : transform.median;
    vector[transform.index] = Math.fround(
      (safeValue - transform.mean) / transform.scale,
    );
  }

  for (const [name, transform] of Object.entries(model.categorical)) {
    const raw = String(features[name] ?? transform.default);
    const index = transform.indices[raw];
    if (index !== undefined) {
      vector[index] = 1;
    }
  }
  return vector;
}

function evaluateTree(tree: TreeNode, vector: number[]): number {
  let node = tree;
  while (node.leaf === undefined) {
    const index = Number((node.split ?? "").replace(/^f/, ""));
    const value = vector[index];
    const nextId = Number.isNaN(value)
      ? node.missing
      : Math.fround(value) < Math.fround(Number(node.split_condition))
        ? node.yes
        : node.no;
    const next = node.children?.find((child) => child.nodeid === nextId);
    if (!next) {
      throw new Error("Model tree is malformed");
    }
    node = next;
  }
  return node.leaf;
}

function sigmoid(value: number): number {
  if (value >= 0) {
    const inverse = Math.exp(-value);
    return 1 / (1 + inverse);
  }
  const exponential = Math.exp(value);
  return exponential / (1 + exponential);
}

export function predictProbability(input: OlistPredictionInput): number {
  const vector = prepareFeatureVector(input);
  const rawMargin =
    model.raw_margin_intercept +
    model.trees.reduce(
      (sum, tree) => sum + evaluateTree(tree, vector),
      0,
    );
  return sigmoid(
    model.calibration.slope * rawMargin + model.calibration.intercept,
  );
}

function factorImpacts(
  input: OlistPredictionInput,
  probability: number,
): OlistPrediction["factors"] {
  return factorGroups
    .map((group) => {
      const counterfactual = { ...input };
      for (const key of group.keys) {
        Object.assign(counterfactual, { [key]: referenceInput[key] });
      }
      const comparison = predictProbability(counterfactual);
      const change = probability - comparison;
      return {
        name: group.name,
        effect: (change >= 0 ? "raises risk" : "lowers risk") as
          | "raises risk"
          | "lowers risk",
        probability_point_change: Math.abs(change) * 100,
        explanation: group.explanation,
      };
    })
    .sort(
      (left, right) =>
        right.probability_point_change - left.probability_point_change,
    )
    .slice(0, 3);
}

export function predictOlistDelay(
  input: OlistPredictionInput,
): OlistPrediction {
  const probability = predictProbability(input);
  const workingThreshold = model.thresholds.working;
  const riskLevel =
    probability >= workingThreshold
      ? "high"
      : probability >= model.thresholds.low_medium_boundary
        ? "medium"
        : "low";

  return {
    probability,
    probability_percent: probability * 100,
    risk_level: riskLevel,
    decision:
      probability >= workingThreshold
        ? "elevated delay risk"
        : "no elevated delay risk",
    factors: factorImpacts(input, probability),
    model_version: model.model_version,
    threshold: workingThreshold,
    disclaimer:
      "Demonstration estimate from historical Olist orders (2016–2018), not a delivery guarantee.",
  };
}

export const olistModelMetadata = {
  version: model.model_version,
  workingThreshold: model.thresholds.working,
  standardThreshold: model.thresholds.standard,
  limitations: model.limitations,
};
