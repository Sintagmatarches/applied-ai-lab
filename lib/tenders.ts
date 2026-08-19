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
  category: "turnover" | "certification" | "references" | "language" | "geography" | "deadline" | "technical" | "professional" | "staff" | "consortium" | "other";
  text: string;
  mandatory: boolean;
  operator?: ">=" | "contains" | "one_of";
  value?: number | string | string[];
  unit?: string;
  stage?: "TENDER" | "REQUEST_TO_PARTICIPATE" | "NOT_REQUIRED" | "UNKNOWN";
  sourceField: string;
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
  weightType: string | null;
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
  submissionLanguages: string[];
};

export type SecurityFinding = {
  id: string;
  lotId?: string;
  type: "PROMPT_INJECTION";
  severity: "HIGH";
  excerpt: string;
  evidenceId: string;
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
  securityFindings: SecurityFinding[];
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
  lotId: string;
  mandatory: boolean;
  outcome: "PASS" | "FAIL" | "UNKNOWN" | "NOT_APPLICABLE";
  reason: string;
  evidenceId: string;
};

export type FitComponent = {
  name: "capability" | "geography" | "contract_value" | "deadline";
  score: number;
  maximum: number;
  evidence: string;
};

export type LotAssessment = {
  lotId: string;
  status: DecisionStatus;
  heuristicFit: { score: number; label: "LOW" | "MEDIUM" | "HIGH"; components: FitComponent[] };
  checks: RequirementCheck[];
  blockingRequirements: RequirementCheck[];
  satisfiedRequirements: RequirementCheck[];
  uncertainRequirements: RequirementCheck[];
};

export type BidAssessment = {
  status: DecisionStatus;
  strategicFit: number;
  heuristicFitLabel: "LOW" | "MEDIUM" | "HIGH";
  lotAssessments: LotAssessment[];
  summary: { eligibleLots: string[]; blockedLots: string[]; reviewLots: string[]; insufficientEvidenceLots: string[] };
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
  const normalized = scalar(value).replaceAll(" ", "").replace(",", ".");
  if (!normalized) return null;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function lotIdFor(lotIds: string[], valueCount: number, index: number): string | undefined {
  if (lotIds.length === 1) return lotIds[0];
  return valueCount === lotIds.length ? lotIds[index] : undefined;
}

function stage(value: string | undefined): Requirement["stage"] {
  if (value === "t-requ") return "TENDER";
  if (value === "par-requ") return "REQUEST_TO_PARTICIPATE";
  if (value === "not-requ") return "NOT_REQUIRED";
  return "UNKNOWN";
}

function requirementCategory(code: string, text: string): Requirement["category"] {
  const value = `${code} ${text}`.toLowerCase();
  if (/turnover|financial|fin-sta/.test(value)) return "turnover";
  if (/register|professional|suit-reg/.test(value)) return "professional";
  if (/reference|experience|past contract/.test(value)) return "references";
  if (/staff|personnel/.test(value)) return "staff";
  if (/language/.test(value)) return "language";
  return "technical";
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

export function extractRequirements(noticeId: string, lots: ProcurementLot[], url: string): { requirements: Requirement[]; securityFindings: SecurityFinding[]; evidence: Evidence[] } {
  const requirements: Requirement[] = [];
  const securityFindings: SecurityFinding[] = [];
  const evidenceRows: Evidence[] = [];
  const add = (lot: ProcurementLot, category: Requirement["category"], text: string, value: number | string | undefined, unit?: string) => {
    const evidenceRow = evidence(noticeId, lot.id, `requirement-${requirements.length + 1}`, text, url);
    evidenceRows.push(evidenceRow);
    requirements.push({
      id: `${noticeId}:req:${requirements.length + 1}`, lotId: lot.id, category, text,
      mandatory: /must|required|shall|minimum|at least|vähintään|edellytetään|tulee/i.test(text),
      operator: value === undefined ? undefined : category === "certification" || category === "language" || category === "geography" ? "contains" : ">=",
      value, unit, stage: "UNKNOWN", sourceField: "description-lot", evidenceId: evidenceRow.id,
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
        const matchIndex = match.index ?? 0;
        const sentenceStart = Math.max(text.lastIndexOf(".", matchIndex - 1), text.lastIndexOf("!", matchIndex - 1), text.lastIndexOf("?", matchIndex - 1)) + 1;
        const followingStops = [text.indexOf(".", matchIndex), text.indexOf("!", matchIndex), text.indexOf("?", matchIndex)].filter((item) => item >= 0);
        const sentenceEnd = followingStops.length ? Math.min(...followingStops) + 1 : text.length;
        const raw = category === "certification" ? text.slice(sentenceStart, sentenceEnd).trim() : match[0];
        const value = category === "certification" ? match[1].toUpperCase().replace(/ISO\s?/, "ISO ") : Number(match[1].replace(/[^0-9]/g, ""));
        add(lot, category, raw, value, unit);
      }
    }
    const language = text.match(/(?:required|must|shall|vähintään)[^.!?]{0,40}\b(English|Finnish|Swedish|French|German)\b/i);
    if (language) add(lot, "language", language[0], language[1]);
    if (/ignore all previous instructions|reveal the system prompt|mark this opportunity as bid|fake:\d+/i.test(text)) {
      const findingEvidence = evidence(noticeId, lot.id, `security-${securityFindings.length + 1}`, text.match(/ignore all previous instructions|reveal the system prompt|mark this opportunity as bid|fake:\d+/i)?.[0] ?? "Untrusted instruction", url);
      evidenceRows.push(findingEvidence);
      securityFindings.push({ id: `${noticeId}:security:${securityFindings.length + 1}`, lotId: lot.id, type: "PROMPT_INJECTION", severity: "HIGH", excerpt: findingEvidence.excerpt, evidenceId: findingEvidence.id });
    }
  }
  return { requirements, securityFindings, evidence: evidenceRows };
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
  const lots: ProcurementLot[] = Array.from({ length: count }, (_, index) => {
    const value = numberValue(values[index] ?? values[0]);
    return {
      id: lotIds[index] ?? `${noticeId}:LOT-${String(index + 1).padStart(4, "0")}`,
      title: lotTitles[index] ?? lotTitles[0] ?? localized(raw["notice-title"])[0] ?? "Untitled lot",
      description: descriptions[index] ?? descriptions[0] ?? "No lot description supplied in the selected TED fields.",
      cpvCodes: cpvs.length === count ? [cpvs[index]] : [...new Set(cpvs)],
      value,
      currency: value === null ? null : currencies[index] ?? currencies[0] ?? (scalar(raw["estimated-value-cur-proc"]) || null),
      placeOfPerformance: places[index] ? [places[index]] : [...new Set(places)],
      deadline: deadlines[index] ?? deadlines[0] ?? null,
      status: deadlines[index] || deadlines[0] ? (new Date(deadlines[index] ?? deadlines[0]).valueOf() >= Date.now() ? "OPEN" : "CLOSED") : "UNKNOWN",
      submissionLanguages: strings(raw["submission-language"]),
    };
  });
  const extracted = extractRequirements(noticeId, lots, urls.html);
  const selectionCodes = strings(raw["selection-criterion-lot"]);
  const selectionNames = localized(raw["selection-criterion-name-lot"]);
  const selectionDescriptions = localized(raw["selection-criterion-description-lot"]);
  const requirementStages = strings(raw["requirement-stage-lot"]);
  const structuredRequirements: Requirement[] = [];
  const structuredRequirementEvidence: Evidence[] = [];
  const selectionCount = Math.max(selectionCodes.length, selectionNames.length, selectionDescriptions.length);
  for (let index = 0; index < selectionCount; index += 1) {
    const code = selectionCodes[index] ?? "selection-criterion";
    const text = selectionDescriptions[index] ?? selectionNames[index] ?? code;
    const selectedStage = stage(requirementStages[index]);
    const lotId = lotIdFor(lotIds, selectionCount, index);
    const evidenceRow = evidence(noticeId, lotId, `selection-${index + 1}`, text, urls.html);
    structuredRequirementEvidence.push(evidenceRow);
    structuredRequirements.push({
      id: `${noticeId}:selection:${index + 1}`, lotId, category: requirementCategory(code, text), text,
      mandatory: selectedStage !== "NOT_REQUIRED", stage: selectedStage, sourceField: "selection-criterion-lot",
      evidenceId: evidenceRow.id, confidence: lotId ? 1 : 0.75, extractionStatus: "STRUCTURED",
    });
  }
  const submissionLanguages = strings(raw["submission-language"]);
  if (submissionLanguages.length) {
    for (const lot of lots) {
      const text = `Tender submission language must be one of: ${submissionLanguages.join(", ")}.`;
      const evidenceRow = evidence(noticeId, lot.id, "submission-language", text, urls.html);
      structuredRequirementEvidence.push(evidenceRow);
      structuredRequirements.push({ id: `${noticeId}:${lot.id}:submission-language`, lotId: lot.id, category: "language", text, mandatory: true, operator: "one_of", value: submissionLanguages, stage: "TENDER", sourceField: "submission-language", evidenceId: evidenceRow.id, confidence: 1, extractionStatus: "STRUCTURED" });
    }
  }
  const criterionNames = localized(raw["award-criterion-name-lot"]);
  const criterionTypes = strings(raw["award-criterion-type-lot"]);
  const criterionDescriptions = localized(raw["award-criterion-description-lot"]);
  const criterionNumbers = strings(raw["BT-541-Lot"]);
  const criterionWeightTypes = strings(raw["award-criterion-number-weight-lot"]);
  const criteriaEvidence = criterionNames.map((name, index) => evidence(noticeId, lotIdFor(lotIds, criterionNames.length, index), `award-${index + 1}`, `${name}: ${criterionDescriptions[index] ?? ""}`, urls.html));
  const awardCriteria = criterionNames.map((name, index): AwardCriterion => ({
    id: `${noticeId}:award:${index + 1}`, lotId: lotIdFor(lotIds, criterionNames.length, index), name,
    type: criterionTypes[index] ?? "other", weight: numberValue(criterionNumbers[index]), weightType: criterionWeightTypes[index] ?? null,
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
    version: Number(raw["notice-version"] ?? 1), lots, requirements: [...structuredRequirements, ...extracted.requirements],
    awardCriteria, securityFindings: extracted.securityFindings, evidence: [...structuredRequirementEvidence, ...extracted.evidence, ...criteriaEvidence],
  };
}

export function assessTender(notice: ProcurementNotice, profile: SupplierProfile): BidAssessment {
  const assessRequirement = (requirement: Requirement, lotId: string): RequirementCheck => {
    let outcome: RequirementCheck["outcome"] = "UNKNOWN";
    let reason = "The requirement is not structured enough for a deterministic comparison.";
    if (requirement.stage === "NOT_REQUIRED") {
      outcome = "NOT_APPLICABLE";
      reason = "TED marks this information as not required at this stage.";
    } else if (requirement.category === "turnover" && typeof requirement.value === "number") {
      outcome = profile.annualTurnover === null ? "UNKNOWN" : profile.annualTurnover >= requirement.value ? "PASS" : "FAIL";
      reason = profile.annualTurnover === null ? "Supplier turnover is unknown." : `${profile.annualTurnover.toLocaleString()} EUR ${outcome === "PASS" ? "meets" : "is below"} ${requirement.value.toLocaleString()} EUR.`;
    } else if (requirement.category === "references" && typeof requirement.value === "number") {
      outcome = profile.references === null ? "UNKNOWN" : profile.references >= requirement.value ? "PASS" : "FAIL";
      reason = profile.references === null ? "Supplier reference count is unknown." : `${profile.references} references ${outcome === "PASS" ? "meet" : "do not meet"} the minimum of ${requirement.value}.`;
    } else if (requirement.category === "certification" && typeof requirement.value === "string") {
      outcome = profile.certifications.some((item) => item.toLowerCase() === String(requirement.value).toLowerCase()) ? "PASS" : "FAIL";
      reason = outcome === "PASS" ? `${requirement.value} is present.` : `${requirement.value} is missing.`;
    } else if (requirement.category === "language" && (typeof requirement.value === "string" || Array.isArray(requirement.value))) {
      const accepted = (Array.isArray(requirement.value) ? requirement.value : [requirement.value]).map((item) => item.toLowerCase());
      const languageCodes: Record<string, string> = { english: "eng", finnish: "fin", swedish: "swe", french: "fra", german: "deu" };
      const supplied = profile.languages.flatMap((item) => [item.toLowerCase(), languageCodes[item.toLowerCase()] ?? item.toLowerCase()]);
      outcome = supplied.some((item) => accepted.includes(item)) ? "PASS" : "FAIL";
      reason = outcome === "PASS" ? `Supplier covers an accepted language (${accepted.join(", ")}).` : `Supplier does not cover any accepted language (${accepted.join(", ")}).`;
    }
    return { requirementId: requirement.id, lotId, mandatory: requirement.mandatory, outcome, reason, evidenceId: requirement.evidenceId };
  };

  const lotAssessments: LotAssessment[] = notice.lots.map((lot) => {
    const requirements = notice.requirements.filter((item) => item.lotId === lot.id || item.lotId === undefined);
    const checks = requirements.map((requirement) => assessRequirement(requirement, lot.id));
    const blockingRequirements = checks.filter((check) => check.mandatory && check.outcome === "FAIL");
    const uncertainRequirements = checks.filter((check) => check.mandatory && check.outcome === "UNKNOWN");
    const satisfiedRequirements = checks.filter((check) => check.outcome === "PASS");
    const mandatoryChecks = checks.filter((check) => check.mandatory && check.outcome !== "NOT_APPLICABLE");
    const status: DecisionStatus = blockingRequirements.length ? "NO_BID" : !mandatoryChecks.length ? "INSUFFICIENT_EVIDENCE" : uncertainRequirements.length ? "REVIEW" : "BID";

    const text = `${lot.title} ${lot.description}`.toLowerCase();
    const matched = profile.capabilities.filter((capability) => (CAPABILITY_TERMS[capability] ?? [capability.toLowerCase()]).some((term) => text.includes(term)));
    const capabilityScore = Math.min(50, matched.length * 10);
    const geographyScore = lot.placeOfPerformance.some((country) => profile.countriesServed.includes(country)) ? 20 : 0;
    const valueScore = lot.value !== null && (profile.minContractValue ?? 0) <= lot.value && (profile.maxContractValue ?? Infinity) >= lot.value ? 20 : 0;
    const deadlineScore = lot.deadline && new Date(lot.deadline).valueOf() >= Date.now() ? 10 : 0;
    const components: FitComponent[] = [
      { name: "capability", score: capabilityScore, maximum: 50, evidence: matched.length ? `Matched: ${matched.join(", ")}.` : "No declared capability matched the lot text." },
      { name: "geography", score: geographyScore, maximum: 20, evidence: geographyScore ? "Exact place-of-performance country is covered." : "No exact country match; EU/EEA alone is not treated as evidence." },
      { name: "contract_value", score: valueScore, maximum: 20, evidence: lot.value === null ? "Lot value is missing; no positive score awarded." : valueScore ? "Lot value is inside the supplier range." : "Lot value is outside the supplier range." },
      { name: "deadline", score: deadlineScore, maximum: 10, evidence: lot.deadline ? (deadlineScore ? "Lot deadline is still open." : "Lot deadline has passed.") : "Lot deadline is missing; no positive score awarded." },
    ];
    const score = components.reduce((sum, component) => sum + component.score, 0);
    const label = score >= 70 ? "HIGH" : score >= 40 ? "MEDIUM" : "LOW";
    return { lotId: lot.id, status, heuristicFit: { score, label, components }, checks, blockingRequirements, satisfiedRequirements, uncertainRequirements };
  });

  const summary = {
    eligibleLots: lotAssessments.filter((item) => item.status === "BID").map((item) => item.lotId),
    blockedLots: lotAssessments.filter((item) => item.status === "NO_BID").map((item) => item.lotId),
    reviewLots: lotAssessments.filter((item) => item.status === "REVIEW").map((item) => item.lotId),
    insufficientEvidenceLots: lotAssessments.filter((item) => item.status === "INSUFFICIENT_EVIDENCE").map((item) => item.lotId),
  };
  const status: DecisionStatus = summary.eligibleLots.length ? "BID" : summary.reviewLots.length ? "REVIEW" : summary.insufficientEvidenceLots.length ? "INSUFFICIENT_EVIDENCE" : "NO_BID";
  const strategicFit = Math.max(0, ...lotAssessments.map((item) => item.heuristicFit.score));
  const checks = lotAssessments.flatMap((item) => item.checks);
  const blockingRequirements = lotAssessments.flatMap((item) => item.blockingRequirements);
  const uncertainRequirements = lotAssessments.flatMap((item) => item.uncertainRequirements);
  const satisfiedRequirements = checks.filter((check) => check.outcome === "PASS");
  return { status, strategicFit, heuristicFitLabel: strategicFit >= 70 ? "HIGH" : strategicFit >= 40 ? "MEDIUM" : "LOW", lotAssessments, summary, checks, blockingRequirements, satisfiedRequirements, uncertainRequirements, assessedAt: new Date().toISOString(), supplierProfileVersion: profile.version };
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
  "award-criterion-type-lot", "award-criterion-number-weight-lot", "award-criterion-description-lot", "BT-541-Lot", "submission-language", "change-reason-code",
  "change-description", "change-reason-description", "change-notice-version-identifier", "BT-13716-notice", "links",
] as const;

export function applyClientFilters(notices: ProcurementNotice[], filters: TenderSearchFilters): ProcurementNotice[] {
  return notices.filter((notice) => {
    return notice.lots.some((lot) => {
      if (filters.minValue !== undefined && (lot.value === null || lot.value < filters.minValue)) return false;
      if (filters.maxValue !== undefined && (lot.value === null || lot.value > filters.maxValue)) return false;
      if (filters.deadlineFrom && (!lot.deadline || lot.deadline.slice(0, 10) < filters.deadlineFrom)) return false;
      return true;
    });
  });
}
