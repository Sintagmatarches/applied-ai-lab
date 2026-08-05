import modelJson from "../artifacts/olist-model.json";

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

type CountRecord = [number, number];
type OutcomeRecord = [number, number, number];

type GroupHistory = {
  orders: CountRecord[];
  outcomes: OutcomeRecord[];
};

type ModelArtifact = {
  model_version: string;
  model_type: string;
  display_mode: "risk_score" | "probability";
  feature_count: number;
  feature_contract: {
    version: number;
    timestamp: string;
    calendar_timezone: string;
    weekday: string;
    route: string;
    history_granularity: string;
    history_cutoff: string;
    order_count_event: string;
    outcome_event: string;
  };
  prediction_domain: {
    purchase_timestamp_min: string;
    purchase_timestamp_max: string;
    policy: string;
  };
  numeric: Record<string, NumericTransform>;
  categorical: Record<string, CategoryTransform>;
  linear: {
    intercept: number;
    coefficients: number[];
  };
  calibration:
    | { type: "identity" }
    | { type: "platt"; slope: number; intercept: number }
    | { type: "isotonic"; x: number[]; y: number[] };
  risk_score_probability_quantiles: number[];
  risk_levels: {
    medium_score: number;
    high_score: number;
  };
  history: {
    granularity: string;
    cutoff: string;
    global_outcomes: OutcomeRecord[];
    groups: {
      seller_state: Record<string, GroupHistory>;
      route: Record<string, GroupHistory>;
      primary_category: Record<string, GroupHistory>;
    };
    constants: {
      seconds_per_day: number;
      default_late_prior: number;
      prior_strength: number;
      window_prior_strength: number;
    };
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
  risk_score: number;
  risk_level: "low" | "medium" | "high";
  decision: "top risk group" | "below top risk group";
  factors: Array<{
    name: string;
    effect: "higher than reference" | "lower than reference";
    risk_score_point_change: number;
    explanation: string;
  }>;
  model_version: string;
  high_risk_score: number;
  display_note: string;
  disclaimer: string;
};

export type OlistModelScore = {
  feature_vector: number[];
  raw_score: number;
  probability: number;
  risk_score: number;
};

export class PredictionInputError extends Error {
  readonly issues: string[];

  constructor(issues: string[]) {
    super("Invalid prediction input");
    this.issues = issues;
  }
}

const model = modelJson as unknown as ModelArtifact;

function assertModelContract(): void {
  const expected = {
    version: 1,
    calendar_timezone: "UTC",
    weekday: "ISO-8601 Monday=1 through Sunday=7",
    route: "seller_state + ' → ' + customer_state",
    history_granularity: "UTC calendar day",
    history_cutoff: "event day strictly before prediction day",
  };
  for (const [name, value] of Object.entries(expected)) {
    if (model.feature_contract[name as keyof typeof expected] !== value) {
      throw new Error(`Unsupported Olist feature contract: ${name}`);
    }
  }
  if (model.history.granularity !== "utc_day") {
    throw new Error("Unsupported Olist history granularity");
  }
  if (model.linear.coefficients.length !== model.feature_count) {
    throw new Error("Olist coefficient count does not match feature count");
  }
}

assertModelContract();

const millisecondsPerDay = model.history.constants.seconds_per_day * 1_000;
const minimumPurchaseTime = Date.parse(
  model.prediction_domain.purchase_timestamp_min,
);
const maximumPurchaseTime = Date.parse(
  model.prediction_domain.purchase_timestamp_max,
);

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
  purchase_timestamp: "2018-05-03T15:00:00.000Z",
};

const factorGroups: Array<{
  name: string;
  keys: Array<keyof OlistPredictionInput>;
  explanation: string;
}> = [
  {
    name: "Route and prior route history",
    keys: ["seller_state", "customer_state"],
    explanation:
      "state-level history and outcomes already observed before this order day",
  },
  {
    name: "Promised delivery window",
    keys: ["promised_delivery_days"],
    explanation: "days promised relative to the supplied distance",
  },
  {
    name: "Distance",
    keys: ["distance_km"],
    explanation: "user-supplied shipping distance",
  },
  {
    name: "Order timing",
    keys: ["purchase_timestamp"],
    explanation: "UTC season, year, month, ISO weekday and purchase hour",
  },
  {
    name: "Category history",
    keys: ["primary_category"],
    explanation: "category outcomes available before this order day",
  },
  {
    name: "Order size",
    keys: ["item_count"],
    explanation: "number of items in the order",
  },
  {
    name: "Order value",
    keys: ["total_item_value", "total_freight_value"],
    explanation: "item value, freight value and their ratio",
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

export function validatePredictionInput(payload: unknown): OlistPredictionInput {
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
  const purchaseTime = Date.parse(purchaseTimestamp);
  const validTimestamp = purchaseTimestamp.length > 0 && Number.isFinite(purchaseTime);
  if (!validTimestamp) {
    issues.push("purchase_timestamp must be a valid ISO-8601 date and time.");
  } else if (
    purchaseTime < minimumPurchaseTime ||
    purchaseTime > maximumPurchaseTime
  ) {
    issues.push(
      `purchase_timestamp must be within the historical model range ${model.prediction_domain.purchase_timestamp_min} to ${model.prediction_domain.purchase_timestamp_max}.`,
    );
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
    item_count: readFiniteNumber(body.item_count, "item_count", 1, 50, issues),
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
    purchase_timestamp: validTimestamp
      ? new Date(purchaseTime).toISOString()
      : "",
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

function orderDay(timestamp: string): number {
  return Math.floor(Date.parse(timestamp) / millisecondsPerDay);
}

function historyTotals(
  records: Array<CountRecord | OutcomeRecord> | undefined,
  day: number,
  windowDays?: number,
): { count: number; late: number; firstDay: number } {
  let count = 0;
  let late = 0;
  let firstDay = day;
  if (!records) {
    return { count, late, firstDay };
  }
  const minimumDay = windowDays === undefined ? -Infinity : day - windowDays;
  for (const record of records) {
    const [recordDay, recordCount] = record;
    if (recordDay >= day) break;
    if (firstDay === day) firstDay = recordDay;
    if (recordDay < minimumDay) continue;
    count += recordCount;
    late += record.length === 3 ? record[2] : 0;
  }
  return { count, late, firstDay };
}

function smoothedRate(
  late: number,
  count: number,
  prior: number,
  strength: number,
): number {
  return (late + strength * prior) / (count + strength);
}

function season(month: number): string {
  if ([12, 1, 2].includes(month)) return "summer";
  if ([3, 4, 5].includes(month)) return "autumn";
  if ([6, 7, 8].includes(month)) return "winter";
  return "spring";
}

export function prepareRawFeatures(
  input: OlistPredictionInput,
): Record<string, number | string> {
  const timestamp = new Date(input.purchase_timestamp);
  const day = orderDay(input.purchase_timestamp);
  const route = `${input.seller_state} → ${input.customer_state}`;
  const global = historyTotals(model.history.global_outcomes, day);
  const globalPrior =
    global.count > 0
      ? global.late / global.count
      : model.history.constants.default_late_prior;
  const groups = model.history.groups;
  const seller = groups.seller_state[input.seller_state];
  const routeHistory = groups.route[route];
  const category = groups.primary_category[input.primary_category];
  const sellerOrders = historyTotals(seller?.orders, day);
  const sellerOutcomes = historyTotals(seller?.outcomes, day);
  const seller30 = historyTotals(seller?.outcomes, day, 30);
  const seller90 = historyTotals(seller?.outcomes, day, 90);
  const routeOutcomes = historyTotals(routeHistory?.outcomes, day);
  const route7 = historyTotals(routeHistory?.orders, day, 7);
  const route30Orders = historyTotals(routeHistory?.orders, day, 30);
  const route30Outcomes = historyTotals(routeHistory?.outcomes, day, 30);
  const route90Outcomes = historyTotals(routeHistory?.outcomes, day, 90);
  const categoryOutcomes = historyTotals(category?.outcomes, day);
  const priorStrength = model.history.constants.prior_strength;
  const windowStrength = model.history.constants.window_prior_strength;

  return {
    purchase_year: timestamp.getUTCFullYear(),
    purchase_month: timestamp.getUTCMonth() + 1,
    purchase_day_of_week: ((timestamp.getUTCDay() + 6) % 7) + 1,
    purchase_hour: timestamp.getUTCHours(),
    promised_delivery_days: input.promised_delivery_days,
    same_state: input.seller_state === input.customer_state ? 1 : 0,
    distance_km: input.distance_km,
    item_count: input.item_count,
    total_item_value: input.total_item_value,
    total_freight_value: input.total_freight_value,
    total_weight_g: input.total_weight_g,
    total_volume_cm3: input.total_volume_cm3,
    payment_installments: input.payment_installments,
    prior_global_late_rate: globalPrior,
    seller_state_prior_late_rate: smoothedRate(
      sellerOutcomes.late,
      sellerOutcomes.count,
      globalPrior,
      priorStrength,
    ),
    seller_state_prior_order_count_log: Math.log1p(sellerOrders.count),
    seller_state_late_rate_30d: smoothedRate(
      seller30.late,
      seller30.count,
      globalPrior,
      windowStrength,
    ),
    seller_state_late_rate_90d: smoothedRate(
      seller90.late,
      seller90.count,
      globalPrior,
      windowStrength,
    ),
    seller_state_experience_days_log: Math.log1p(
      Math.max(day - sellerOrders.firstDay, 0),
    ),
    route_prior_late_rate: smoothedRate(
      routeOutcomes.late,
      routeOutcomes.count,
      globalPrior,
      priorStrength,
    ),
    route_order_count_7d_log: Math.log1p(route7.count),
    route_order_count_30d_log: Math.log1p(route30Orders.count),
    route_late_rate_30d: smoothedRate(
      route30Outcomes.late,
      route30Outcomes.count,
      globalPrior,
      windowStrength,
    ),
    route_late_rate_90d: smoothedRate(
      route90Outcomes.late,
      route90Outcomes.count,
      globalPrior,
      windowStrength,
    ),
    category_prior_late_rate: smoothedRate(
      categoryOutcomes.late,
      categoryOutcomes.count,
      globalPrior,
      priorStrength,
    ),
    freight_item_ratio: Math.min(
      input.total_freight_value / Math.max(input.total_item_value, 1),
      10,
    ),
    promised_days_per_500km:
      input.promised_delivery_days / Math.max(input.distance_km / 500, 1),
    seller_state: input.seller_state,
    customer_state: input.customer_state,
    route,
    primary_category: input.primary_category,
    primary_payment_type: input.primary_payment_type,
    season: season(timestamp.getUTCMonth() + 1),
  };
}

export function prepareFeatureVector(input: OlistPredictionInput): number[] {
  const vector = Array<number>(model.feature_count).fill(0);
  const features = prepareRawFeatures(input);
  for (const [name, transform] of Object.entries(model.numeric)) {
    const raw = Number(features[name]);
    const safeValue = Number.isFinite(raw) ? raw : transform.median;
    vector[transform.index] = (safeValue - transform.mean) / transform.scale;
  }
  for (const [name, transform] of Object.entries(model.categorical)) {
    const raw = String(features[name] ?? transform.default);
    const index = transform.indices[raw];
    if (index !== undefined) vector[index] = 1;
  }
  return vector;
}

function interpolateIsotonic(value: number, x: number[], y: number[]): number {
  if (value <= x[0]) return y[0];
  if (value >= x[x.length - 1]) return y[y.length - 1];
  let upper = 1;
  while (upper < x.length && x[upper] < value) upper += 1;
  const lower = upper - 1;
  const width = x[upper] - x[lower];
  if (width === 0) return y[upper];
  return y[lower] + ((value - x[lower]) / width) * (y[upper] - y[lower]);
}

function sigmoid(value: number): number {
  if (value >= 0) {
    const inverse = Math.exp(-value);
    return 1 / (1 + inverse);
  }
  const exponential = Math.exp(value);
  return exponential / (1 + exponential);
}

function calibratedProbability(rawScore: number): number {
  if (model.calibration.type === "platt") {
    return sigmoid(
      model.calibration.slope * rawScore + model.calibration.intercept,
    );
  }
  if (model.calibration.type === "isotonic") {
    return interpolateIsotonic(
      rawScore,
      model.calibration.x,
      model.calibration.y,
    );
  }
  return sigmoid(rawScore);
}

function probabilityToRiskScore(probability: number): number {
  const quantiles = model.risk_score_probability_quantiles;
  if (probability <= quantiles[0]) return 0;
  if (probability >= quantiles[quantiles.length - 1]) return 100;
  let upper = 1;
  while (upper < quantiles.length && quantiles[upper] < probability) upper += 1;
  const lower = upper - 1;
  const width = quantiles[upper] - quantiles[lower];
  const fraction = width === 0 ? 0 : (probability - quantiles[lower]) / width;
  return Math.min(100, Math.max(0, lower + fraction));
}

export function scoreOlistModel(input: OlistPredictionInput): OlistModelScore {
  const featureVector = prepareFeatureVector(input);
  const rawScore = model.linear.coefficients.reduce(
    (sum, coefficient, index) => sum + coefficient * featureVector[index],
    model.linear.intercept,
  );
  const probability = calibratedProbability(rawScore);
  return {
    feature_vector: featureVector,
    raw_score: rawScore,
    probability,
    risk_score: probabilityToRiskScore(probability),
  };
}

function factorImpacts(
  input: OlistPredictionInput,
  riskScore: number,
): OlistPrediction["factors"] {
  return factorGroups
    .map((group) => {
      const counterfactual = { ...input };
      for (const key of group.keys) {
        Object.assign(counterfactual, { [key]: referenceInput[key] });
      }
      const comparison = scoreOlistModel(counterfactual).risk_score;
      const change = riskScore - comparison;
      return {
        name: group.name,
        effect: (change >= 0
          ? "higher than reference"
          : "lower than reference") as
          | "higher than reference"
          | "lower than reference",
        risk_score_point_change: Math.abs(change),
        explanation: group.explanation,
      };
    })
    .sort(
      (left, right) =>
        right.risk_score_point_change - left.risk_score_point_change,
    )
    .slice(0, 3);
}

export function predictOlistDelay(input: OlistPredictionInput): OlistPrediction {
  const result = scoreOlistModel(input);
  const riskLevel =
    result.risk_score >= model.risk_levels.high_score
      ? "high"
      : result.risk_score >= model.risk_levels.medium_score
        ? "medium"
        : "low";
  return {
    risk_score: result.risk_score,
    risk_level: riskLevel,
    decision:
      result.risk_score >= model.risk_levels.high_score
        ? "top risk group"
        : "below top risk group",
    factors: factorImpacts(input, result.risk_score),
    model_version: model.model_version,
    high_risk_score: model.risk_levels.high_score,
    display_note:
      "Relative score from 0 to 100. It ranks this order against the model calibration period; it is not an exact probability.",
    disclaimer:
      "Historical Olist demonstration (2016–2018). Sensitivity scenarios are comparisons with a fixed reference order, not causal explanations or delivery guarantees.",
  };
}

export const olistModelMetadata = {
  version: model.model_version,
  modelType: model.model_type,
  displayMode: model.display_mode,
  featureContract: model.feature_contract,
  predictionDomain: model.prediction_domain,
  limitations: model.limitations,
};
