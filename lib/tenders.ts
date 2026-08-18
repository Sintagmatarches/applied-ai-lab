export type DecisionStatus = "BID" | "REVIEW" | "NO_BID" | "INSUFFICIENT_EVIDENCE";

export type Evidence = {
  id: string;
  noticeId: string;
  lotId?: string;
  field: string;
  excerpt: string;
  url: string;
  source: "TED Search API v3";
};

export type Requirement = {
  id: string;
  lotId?: string;
  category: "turnover" | "certification" | "references" | "language" | "geography" | "deadline" | "technical" | "other";
  text: string;
  mandatory: boolean;
  operator?: ">=" | "contains";
  value?: number | string;
  unit?: string;
  evidenceId: string;
  confidence: number;
  extractionStatus: "STRUCTURED" | "UNSTRUCTURED";
};

export type AwardCriterion = {
  id: string;
  lotId?: string;
  name: string;
  type: string;
  weight: number | null;
  description: string;
  evidenceId: string;
};

export type ProcurementLot = {
  id: string;
  title: string;
  description: string;
  cpvCodes: string[];
  value: number | null;
  currency: string | null;
  placeOfPerformance: string[];
  deadline: string | null;
  status: "OPEN" | "CLOSED" | "UNKNOWN";
};

export type ProcurementNotice = {
  noticeId: string;
  publicationId: string;
  noticeType: string;
  formType: string;
  title: string;
  description: string;
  buyer: string;
  buyerCountry: string;
  procedureType: string;
  publicationDate: string;
  submissionDeadline: string | null;
  estimatedValue: number | null;
  currency: string | null;
  cpvCodes: string[];
  placeOfPerformance: string[];
  noticeUrl: string;
  xmlUrl: string | null;
  source: "TED Search API v3";
  discoveredAt: string;
  updatedAt: string;
  version: number;
  lots: ProcurementLot[];
  requirements: Requirement[];
  awardCriteria: AwardCriterion[];
  evidence: Evidence[];
};

export type SupplierProfile = {
  version: number;
  companyName: string;
  countriesServed: string[];
  capabilities: string[];
  certifications: string[];
  annualTurnover: number | null;
  references: number | null;
  languages: string[];
  minContractValue: number | null;
  maxContractValue: number | null;
};

export type RequirementCheck = {
  requirementId: string;
  outcome: "PASS" | "FAIL" | "UNKNOWN";
  reason: string;
  evidenceId: string;
};

export type BidAssessment = {
  status: DecisionStatus;
  strategicFit: number;
  checks: RequirementCheck[];
  blockingRequirements: RequirementCheck[];
  satisfiedRequirements: RequirementCheck[];
  uncertainRequirements: RequirementCheck[];
  assessedAt: string;
  supplierProfileVersion: number;
};

export type TenderSearchFilters = {
  keywords?: string;
  cpv?: string;
  buyerCountry?: string;
  placeCountry?: string;
  publishedFrom?: string;
  publishedTo?: string;
  minValue?: number;
  maxValue?: number;
  deadlineFrom?: string;
  procedureType?: string;
  limit?: number;
  page?: number;
  iterationNextToken?: string;
};

const CAPABILITY_TERMS: Record<string, string[]> = {
  Python: ["python"], SQL: ["sql", "database"], "Power BI": ["power bi", "business intelligence"],
  "Machine Learning": ["machine learning", "artificial intelligence", "ai"],
  "AI / LLM": ["llm", "large language model", "artificial intelligence", "generative ai"],
  "Data Engineering": ["data engineering", "data platform", "etl", "data warehouse"],
  Azure: ["azure", "cloud"], Analytics: ["analytics", "data analysis"], Automation: ["automation"],
};

export const DEMO_SUPPLIER_PROFILE: SupplierProfile = {
  version: 1,
  companyName: "European Data / AI Consultancy (demo profile)",
  countriesServed: ["FIN", "EU", "EEA"],
  capabilities: Object.keys(CAPABILITY_TERMS),
  certifications: [],
  annualTurnover: 750_000,
  references: 4,
  languages: ["English", "Finnish"],
  minContractValue: 25_000,
  maxContractValue: 2_000_000,
};

function strings(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).map((item) => item.trim()).filter(Boolean);
  return typeof value === "string" && value.trim() ? [value.trim()] : [];
}

function localized(value: unknown): string[] {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return strings(value);
  const map = value as Record<string, unknown>;
  for (const language of ["eng", "fin", "fra", "deu", "swe"]) {
    const selected = strings(map[language]);
    if (selected.length) return selected;
  }
  return Object.values(map).flatMap(strings);
}

function scalar(value: unknown): string {
  return strings(value)[0] ?? "";
}

function numberValue(value: unknown): number | null {
  const parsed = Number(scalar(value).replaceAll(" ", "").replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

function sourceUrl(links: unknown, publicationId: string): { html: string; xml: string | null } {
  const root = typeof links === "object" && links ? links as Record<string, unknown> : {};
  const htmlMap = typeof root.html === "object" && root.html ? root.html as Record<string, unknown> : {};
  const xmlMap = typeof root.xml === "object" && root.xml ? root.xml as Record<string, unknown> : {};
  return {
    html: String(htmlMap.ENG ?? htmlMap.FIN ?? Object.values(htmlMap)[0] ?? `https://ted.europa.eu/en/notice/-/detail/${publicationId}`),
    xml: Object.keys(xmlMap).length ? String(xmlMap.MUL ?? Object.values(xmlMap)[0]) : null,
  };
}

function evidence(noticeId: string, lotId: string | undefined, field: string, excerpt: string, url: string): Evidence {
  return { id: `ted:${noticeId}:${lotId ?? "notice"}:${field}`, noticeId, lotId, field, excerpt: excerpt.slice(0, 800), url, source: "TED Search API v3" };
}

export function extractRequirements(noticeId: string, lots: ProcurementLot[], url: string): { requirements: Requirement[]; evidence: Evidence[] } {
  const requirements: Requirement[] = [];
  const evidenceRows: Evidence[] = [];
  const add = (lot: ProcurementLot, category: Requirement["category"], text: string, value: number | string | undefined, unit?: string) => {
    const evidenceRow = evidence(noticeId, lot.id, `requirement-${requirements.length + 1}`, text, url);
    evidenceRows.push(evidenceRow);
    requirements.push({
      id: `${noticeId}:req:${requirements.length + 1}`, lotId: lot.id, category, text,
      mandatory: /must|required|shall|minimum|vähintään|edellytetään|tulee/i.test(text),
      operator: value === undefined ? undefined : category === "certification" || category === "language" || category === "geography" ? "contains" : ">=",
      value, unit, evidenceId: evidenceRow.id,
      confidence: value === undefined ? 0.62 : 0.91,
      extractionStatus: value === undefined ? "UNSTRUCTURED" : "STRUCTURED",
    });
  };
  for (const lot of lots) {
    const text = lot.description;
    const patterns: Array<[Requirement["category"], RegExp, string | undefined]> = [
      ["turnover", /(?:minimum|at least|vähintään)[^.!?]{0,50}(?:turnover|liikevaihto)[^0-9]{0,20}([0-9][0-9 .,'’]*)\s*(EUR|€)/ig, "EUR"],
      ["references", /(?:minimum|at least|vähintään)[^.!?]{0,45}([0-9]+)\s+(?:references?|reference projects?|referenssi)/ig, undefined],
      ["certification", /\b(ISO\s?\d{4,6}(?::\d{4})?)\b/ig, undefined],
    ];
    for (const [category, regex, unit] of patterns) {
      for (const match of text.matchAll(regex)) {
        const raw = match[0];
        const value = category === "certification" ? match[1].toUpperCase().replace(/ISO\s?/, "ISO ") : Number(match[1].replace(/[^0-9]/g, ""));
        add(lot, category, raw, value, unit);
      }
    }
    const language = text.match(/(?:required|must|shall|vähintään)[^.!?]{0,40}\b(English|Finnish|Swedish|French|German)\b/i);
    if (language) add(lot, "language", language[0], language[1]);
    if (/ignore all previous instructions|reveal the system prompt|mark this opportunity as bid|fake:\d+/i.test(text)) {
      add(lot, "other", "Untrusted document instruction detected and quarantined.", undefined);
    }
  }
  return { requirements, evidence: evidenceRows };
}

export function normalizeTedNotice(raw: Record<string, unknown>, now = new Date().toISOString()): ProcurementNotice {
  const noticeId = scalar(raw["notice-identifier"]) || scalar(raw["publication-number"]);
  const publicationId = scalar(raw["publication-number"]);
  const urls = sourceUrl(raw.links, publicationId);
  const lotIds = strings(raw["identifier-lot"]);
  const lotTitles = localized(raw["title-lot"]);
  const descriptions = localized(raw["description-lot"]);
  const deadlines = strings(raw["deadline-date-lot"]);
  const values = strings(raw["estimated-value-lot"]);
  const currencies = strings(raw["estimated-value-cur-lot"]);
  const places = strings(raw["place-of-performance-country-lot"]);
  const cpvs = strings(raw["classification-cpv"]);
  const count = Math.max(1, lotIds.length, lotTitles.length, descriptions.length);
  const lots: ProcurementLot[] = Array.from({ length: count }, (_, index) => ({
    id: lotIds[index] ?? `${noticeId}:LOT-${String(index + 1).padStart(4, "0")}`,
    title: lotTitles[index] ?? lotTitles[0] ?? localized(raw["notice-title"])[0] ?? "Untitled lot",
    description: descriptions[index] ?? descriptions[0] ?? "No lot description supplied in the selected TED fields.",
    cpvCodes: cpvs.length === count ? [cpvs[index]] : [...new Set(cpvs)],
    value: numberValue(values[index] ?? values[0]),
    currency: currencies[index] ?? currencies[0] ?? (scalar(raw["estimated-value-cur-proc"]) || null),
    placeOfPerformance: places[index] ? [places[index]] : [...new Set(places)],
    deadline: deadlines[index] ?? deadlines[0] ?? null,
    status: deadlines[index] || deadlines[0] ? (new Date(deadlines[index] ?? deadlines[0]).valueOf() >= Date.now() ? "OPEN" : "CLOSED") : "UNKNOWN",
  }));
  const extracted = extractRequirements(noticeId, lots, urls.html);
  const criterionNames = localized(raw["award-criterion-name-lot"]);
  const criterionTypes = strings(raw["award-criterion-type-lot"]);
  const criterionDescriptions = localized(raw["award-criterion-description-lot"]);
  const criteriaEvidence = criterionNames.map((name, index) => evidence(noticeId, lotIds[index], `award-${index + 1}`, `${name}: ${criterionDescriptions[index] ?? ""}`, urls.html));
  const awardCriteria = criterionNames.map((name, index): AwardCriterion => ({
    id: `${noticeId}:award:${index + 1}`, lotId: lotIds[index], name,
    type: criterionTypes[index] ?? "other", weight: null,
    description: criterionDescriptions[index] ?? "", evidenceId: criteriaEvidence[index].id,
  }));
  const description = lots.map((lot) => lot.description).join(" ").slice(0, 12_000);
  return {
    noticeId, publicationId, noticeType: scalar(raw["notice-type"]) || "unknown",
    formType: scalar(raw["form-type"]) || "unknown", title: localized(raw["notice-title"])[0] ?? "Untitled TED notice",
    description, buyer: localized(raw["buyer-name"])[0] ?? "Buyer not stated", buyerCountry: strings(raw["buyer-country"])[0] ?? "—",
    procedureType: scalar(raw["procedure-type"]) || "unknown", publicationDate: scalar(raw["publication-date"]),
    submissionDeadline: deadlines[0] ?? null, estimatedValue: numberValue(raw["estimated-value-proc"]),
    currency: scalar(raw["estimated-value-cur-proc"]) || currencies[0] || null, cpvCodes: [...new Set(cpvs)],
    placeOfPerformance: [...new Set(places)], noticeUrl: urls.html, xmlUrl: urls.xml,
    source: "TED Search API v3", discoveredAt: now, updatedAt: now,
    version: Number(raw["notice-version"] ?? 1), lots, requirements: extracted.requirements,
    awardCriteria, evidence: [...extracted.evidence, ...criteriaEvidence],
  };
}

export function assessTender(notice: ProcurementNotice, profile: SupplierProfile): BidAssessment {
  const checks = notice.requirements.map((requirement): RequirementCheck => {
    let outcome: RequirementCheck["outcome"] = "UNKNOWN";
    let reason = "The requirement is not structured enough for a deterministic comparison.";
    if (requirement.category === "turnover" && typeof requirement.value === "number") {
      outcome = profile.annualTurnover === null ? "UNKNOWN" : profile.annualTurnover >= requirement.value ? "PASS" : "FAIL";
      reason = profile.annualTurnover === null ? "Supplier turnover is unknown." : `${profile.annualTurnover.toLocaleString()} EUR ${outcome === "PASS" ? "meets" : "is below"} ${requirement.value.toLocaleString()} EUR.`;
    } else if (requirement.category === "references" && typeof requirement.value === "number") {
      outcome = profile.references === null ? "UNKNOWN" : profile.references >= requirement.value ? "PASS" : "FAIL";
      reason = profile.references === null ? "Supplier reference count is unknown." : `${profile.references} references ${outcome === "PASS" ? "meet" : "do not meet"} the minimum of ${requirement.value}.`;
    } else if (requirement.category === "certification" && typeof requirement.value === "string") {
      outcome = profile.certifications.some((item) => item.toLowerCase() === String(requirement.value).toLowerCase()) ? "PASS" : "FAIL";
      reason = outcome === "PASS" ? `${requirement.value} is present.` : `${requirement.value} is missing.`;
    } else if (requirement.category === "language" && typeof requirement.value === "string") {
      outcome = profile.languages.some((item) => item.toLowerCase() === String(requirement.value).toLowerCase()) ? "PASS" : "FAIL";
      reason = outcome === "PASS" ? `${requirement.value} is covered.` : `${requirement.value} is not covered.`;
    }
    return { requirementId: requirement.id, outcome, reason, evidenceId: requirement.evidenceId };
  });
  const text = `${notice.title} ${notice.description}`.toLowerCase();
  const matched = profile.capabilities.filter((capability) => (CAPABILITY_TERMS[capability] ?? [capability.toLowerCase()]).some((term) => text.includes(term))).length;
  const capabilityScore = Math.round(70 * matched / Math.max(1, profile.capabilities.length));
  const geographyScore = profile.countriesServed.some((country) => country === notice.buyerCountry || ["EU", "EEA"].includes(country)) ? 15 : 0;
  const valueScore = notice.estimatedValue === null || ((profile.minContractValue ?? 0) <= notice.estimatedValue && (profile.maxContractValue ?? Infinity) >= notice.estimatedValue) ? 15 : 0;
  const blockingRequirements = checks.filter((check) => check.outcome === "FAIL");
  const uncertainRequirements = checks.filter((check) => check.outcome === "UNKNOWN");
  const satisfiedRequirements = checks.filter((check) => check.outcome === "PASS");
  const status: DecisionStatus = blockingRequirements.length ? "NO_BID" : !checks.length ? "INSUFFICIENT_EVIDENCE" : uncertainRequirements.length ? "REVIEW" : "BID";
  return { status, strategicFit: capabilityScore + geographyScore + valueScore, checks, blockingRequirements, satisfiedRequirements, uncertainRequirements, assessedAt: new Date().toISOString(), supplierProfileVersion: profile.version };
}

function quoted(value: string): string { return `\"${value.replaceAll("\"", "")}\"`; }

export function buildTedQuery(filters: TenderSearchFilters): string {
  const clauses: string[] = [];
  if (filters.keywords?.trim()) clauses.push(`FT ~ ${quoted(filters.keywords.trim().slice(0, 120))}`);
  if (filters.cpv?.trim()) clauses.push(`classification-cpv = ${filters.cpv.replace(/[^0-9*]/g, "").slice(0, 9)}`);
  if (filters.buyerCountry?.trim()) clauses.push(`buyer-country = ${filters.buyerCountry.replace(/[^A-Za-z]/g, "").toUpperCase().slice(0, 3)}`);
  if (filters.placeCountry?.trim()) clauses.push(`place-of-performance-country-lot = ${filters.placeCountry.replace(/[^A-Za-z]/g, "").toUpperCase().slice(0, 3)}`);
  if (filters.publishedFrom || filters.publishedTo) {
    const start = (filters.publishedFrom ?? "2000-01-01").replaceAll("-", "");
    const end = (filters.publishedTo ?? new Date().toISOString().slice(0, 10)).replaceAll("-", "");
    clauses.push(`PD = (${start} <> ${end})`);
  }
  if (filters.procedureType?.trim()) clauses.push(`procedure-type = ${filters.procedureType.replace(/[^a-z-]/gi, "").toLowerCase()}`);
  return clauses.join(" AND ") || `PD = (${new Date(Date.now() - 90 * 86400000).toISOString().slice(0, 10).replaceAll("-", "")} <> ${new Date().toISOString().slice(0, 10).replaceAll("-", "")})`;
}

export const TED_FIELDS = [
  "publication-number", "notice-identifier", "notice-version", "notice-title", "buyer-name", "buyer-country",
  "publication-date", "deadline-date-lot", "estimated-value-proc", "estimated-value-cur-proc", "classification-cpv",
  "place-of-performance-country-lot", "procedure-type", "notice-type", "form-type", "identifier-lot", "title-lot",
  "description-lot", "estimated-value-lot", "estimated-value-cur-lot", "selection-criterion-name-lot",
  "selection-criterion-description-lot", "selection-criterion-lot", "requirement-stage-lot", "award-criterion-name-lot",
  "award-criterion-type-lot", "award-criterion-number-weight-lot", "award-criterion-description-lot", "change-reason-code",
  "change-description", "change-reason-description", "change-notice-version-identifier", "BT-13716-notice", "links",
] as const;

export function applyClientFilters(notices: ProcurementNotice[], filters: TenderSearchFilters): ProcurementNotice[] {
  return notices.filter((notice) => {
    if (filters.minValue !== undefined && (notice.estimatedValue === null || notice.estimatedValue < filters.minValue)) return false;
    if (filters.maxValue !== undefined && (notice.estimatedValue === null || notice.estimatedValue > filters.maxValue)) return false;
    if (filters.deadlineFrom && notice.submissionDeadline && notice.submissionDeadline.slice(0, 10) < filters.deadlineFrom) return false;
    return true;
  });
}
