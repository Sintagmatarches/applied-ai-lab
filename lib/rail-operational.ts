import policy from "../rail/contracts/operational_policy.json";

export type OperationalRailMode = "live" | "24h" | "7d" | "historical";
export type SampleSupportStatus = "sufficient" | "low-sample" | "not-applicable";
export type FreshnessState = "fresh" | "warning" | "stale" | "not-applicable";
export type CoverageState = "complete" | "partial" | "unavailable";

export type SampleSupport = {
  status: SampleSupportStatus;
  observedCount: number;
  measuredCount: number;
  measurementCoverage: number | null;
  requiredMinimumMeasured: number;
  minimumMeasurementCoverage: number;
  policyVersion: string;
  rationale: string;
};

export type CoverageContract = {
  status: CoverageState;
  expectedDates: string[];
  availableDates: string[];
  missingDates: string[];
  failedDates: string[];
  duplicatePartitions: number;
  coverageRatio: number;
};

export type FreshnessContract = {
  state: FreshnessState;
  evaluatedAt: string;
  ageMinutes: number | null;
  basis: "sourceRetrievedAt" | "validatedAt" | "goldPublishedAt";
  policyVersion: string;
  reason: string;
  sourceRetrievedAt: string | null;
  validatedAt: string | null;
  goldPublishedAt: string | null;
};

type FreshnessBasis = FreshnessContract["basis"];

export const RAIL_OPERATIONAL_POLICY = policy;

export function wilsonInterval(successes: number, observations: number): { lower: number; upper: number } | null {
  if (observations <= 0) return null;
  if (successes < 0 || successes > observations) throw new Error("Wilson successes must be between zero and observations");
  const z = policy.sampleSupport.wilsonZ;
  const proportion = successes / observations;
  const denominator = 1 + (z * z) / observations;
  const centre = (proportion + (z * z) / (2 * observations)) / denominator;
  const halfWidth = z * Math.sqrt(
    (proportion * (1 - proportion)) / observations + (z * z) / (4 * observations * observations),
  ) / denominator;
  return { lower: Math.max(0, centre - halfWidth), upper: Math.min(1, centre + halfWidth) };
}

export function sampleSupport(
  mode: OperationalRailMode,
  observedCount: number,
  measuredCount: number,
  hasRailService = true,
): SampleSupport {
  const modePolicy = policy.sampleSupport.modes[mode];
  const measurementCoverage = observedCount ? measuredCount / observedCount : null;
  const status: SampleSupportStatus = !hasRailService || !observedCount
    ? "not-applicable"
    : measuredCount >= modePolicy.minimumMeasured &&
        measurementCoverage != null &&
        measurementCoverage >= policy.sampleSupport.minimumMeasurementCoverage
      ? "sufficient"
      : "low-sample";
  return {
    status,
    observedCount,
    measuredCount,
    measurementCoverage,
    requiredMinimumMeasured: modePolicy.minimumMeasured,
    minimumMeasurementCoverage: policy.sampleSupport.minimumMeasurementCoverage,
    policyVersion: policy.sampleSupport.version,
    rationale: modePolicy.rationale,
  };
}

function iso(value: Date | string | null): string | null {
  if (value == null) return null;
  const parsed = value instanceof Date ? value : new Date(value);
  if (!Number.isFinite(parsed.getTime())) throw new Error("Invalid freshness timestamp");
  return parsed.toISOString();
}

export function freshnessContract(args: {
  mode: OperationalRailMode;
  now: Date;
  sourceRetrievedAt: string | null;
  validatedAt: string | null;
  goldPublishedAt: string | null;
  coverageStatus?: CoverageState;
}): FreshnessContract {
  const modePolicy = policy.freshness.modes[args.mode];
  const source = iso(args.sourceRetrievedAt);
  const validated = iso(args.validatedAt);
  const gold = iso(args.goldPublishedAt);
  const evaluatedAt = args.now.toISOString();
  if (args.mode === "historical") {
    return {
      state: "not-applicable", evaluatedAt, ageMinutes: null, basis: modePolicy.basis as FreshnessBasis,
      policyVersion: policy.freshness.version, reason: modePolicy.rationale,
      sourceRetrievedAt: source, validatedAt: validated, goldPublishedAt: gold,
    };
  }
  const sourceTime = source ? Date.parse(source) : null;
  const validatedTime = validated ? Date.parse(validated) : null;
  const goldTime = gold ? Date.parse(gold) : null;
  let state: FreshnessState;
  let reason: string;
  let ageMinutes: number | null = null;
  if (
    (sourceTime != null && validatedTime != null && sourceTime > validatedTime) ||
    (validatedTime != null && goldTime != null && validatedTime > goldTime)
  ) {
    state = "stale";
    reason = "Freshness timestamps violate source ≤ validation ≤ Gold ordering.";
  } else if ((args.coverageStatus ?? "complete") !== "complete") {
    state = "stale";
    reason = "The requested governed window is incomplete.";
  } else {
    const basis = modePolicy.basis as FreshnessBasis;
    const basisValue = { sourceRetrievedAt: sourceTime, validatedAt: validatedTime, goldPublishedAt: goldTime }[basis];
    if (basisValue == null) {
      state = "stale";
      reason = `Required ${modePolicy.basis} evidence is unavailable.`;
    } else {
      ageMinutes = Math.round(Math.max(0, (args.now.getTime() - basisValue) / 60_000) * 10) / 10;
      if (ageMinutes <= (modePolicy.warningAfterMinutes as number)) {
        state = "fresh";
        reason = "The governed publication is within its operating target.";
      } else if (ageMinutes <= (modePolicy.staleAfterMinutes as number)) {
        state = "warning";
        reason = "The publication missed its normal target but remains inside the stale boundary.";
      } else {
        state = "stale";
        reason = "The publication is older than the allowed stale boundary.";
      }
    }
  }
  return {
    state, evaluatedAt, ageMinutes, basis: modePolicy.basis as FreshnessBasis, policyVersion: policy.freshness.version,
    reason, sourceRetrievedAt: source, validatedAt: validated, goldPublishedAt: gold,
  };
}
