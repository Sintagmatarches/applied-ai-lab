import {
  applyClientFilters,
  assessTender,
  buildTedQuery,
  DEMO_SUPPLIER_PROFILE,
  normalizeTedNotice,
  TED_FIELDS,
  type SupplierProfile,
  type TenderSearchFilters,
} from "../../../../lib/tenders";

const TED_SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search";

function cleanText(value: unknown, max = 120): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim().slice(0, max) : undefined;
}

function cleanNumber(value: unknown): number | undefined {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}

function invalidPayload(payload: Record<string, unknown>): string[] {
  const errors: string[] = [];
  for (const key of ["keywords", "cpv", "buyerCountry", "placeCountry", "publishedFrom", "publishedTo", "deadlineFrom", "procedureType", "iterationNextToken"]) {
    if (payload[key] !== undefined && typeof payload[key] !== "string") errors.push(`${key} must be a string`);
  }
  for (const key of ["minValue", "maxValue", "limit", "page"]) {
    if (payload[key] !== undefined && (typeof payload[key] === "boolean" || payload[key] === null || String(payload[key]).trim() === "" || !Number.isFinite(Number(payload[key])) || Number(payload[key]) < 0)) errors.push(`${key} must be a non-negative number`);
  }
  return errors;
}

function invalidFilters(filters: TenderSearchFilters): string[] {
  const errors: string[] = [];
  const validDate = (value: string | undefined) => {
    if (!value) return true;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const parsed = new Date(`${value}T00:00:00Z`);
    return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value;
  };
  const validCountry = (value: string | undefined) => !value || /^[A-Z]{3}$/.test(value);
  if (!validCountry(filters.buyerCountry)) errors.push("buyerCountry must be a three-letter TED country code");
  if (!validCountry(filters.placeCountry)) errors.push("placeCountry must be a three-letter TED country code");
  if (filters.cpv && !/^\d{2,8}\*?$/.test(filters.cpv)) errors.push("cpv must contain 2-8 digits with an optional trailing wildcard");
  if (!validDate(filters.publishedFrom)) errors.push("publishedFrom must be a real YYYY-MM-DD date");
  if (!validDate(filters.publishedTo)) errors.push("publishedTo must be a real YYYY-MM-DD date");
  if (!validDate(filters.deadlineFrom)) errors.push("deadlineFrom must be a real YYYY-MM-DD date");
  if (filters.publishedFrom && filters.publishedTo && filters.publishedFrom > filters.publishedTo) errors.push("publishedFrom must not be after publishedTo");
  if (filters.minValue !== undefined && filters.maxValue !== undefined && filters.minValue > filters.maxValue) errors.push("minValue must not exceed maxValue");
  if (filters.procedureType && !["open", "restricted", "neg-w-call", "comp-dial", "innovation", "neg-wo-call", "other"].includes(filters.procedureType)) errors.push("procedureType is unsupported");
  return errors;
}

function filtersFromPayload(payload: Record<string, unknown>): TenderSearchFilters {
  return {
    keywords: cleanText(payload.keywords), cpv: cleanText(payload.cpv),
    buyerCountry: cleanText(payload.buyerCountry), placeCountry: cleanText(payload.placeCountry),
    publishedFrom: cleanText(payload.publishedFrom), publishedTo: cleanText(payload.publishedTo),
    minValue: cleanNumber(payload.minValue), maxValue: cleanNumber(payload.maxValue),
    deadlineFrom: cleanText(payload.deadlineFrom), procedureType: cleanText(payload.procedureType),
    limit: Math.max(1, Math.min(50, cleanNumber(payload.limit) ?? 12)),
    page: Math.max(1, Math.min(15_000, cleanNumber(payload.page) ?? 1)),
    iterationNextToken: cleanText(payload.iterationNextToken, 500),
  };
}

function profileFromPayload(value: unknown): SupplierProfile {
  if (!value || typeof value !== "object") return DEMO_SUPPLIER_PROFILE;
  const profile = value as Partial<SupplierProfile>;
  return {
    ...DEMO_SUPPLIER_PROFILE,
    ...profile,
    version: Number.isInteger(profile.version) ? Number(profile.version) : 1,
    companyName: cleanText(profile.companyName, 120) ?? DEMO_SUPPLIER_PROFILE.companyName,
    countriesServed: Array.isArray(profile.countriesServed) ? profile.countriesServed.map(String).slice(0, 30) : DEMO_SUPPLIER_PROFILE.countriesServed,
    capabilities: Array.isArray(profile.capabilities) ? profile.capabilities.map(String).slice(0, 50) : DEMO_SUPPLIER_PROFILE.capabilities,
    certifications: Array.isArray(profile.certifications) ? profile.certifications.map(String).slice(0, 50) : [],
    languages: Array.isArray(profile.languages) ? profile.languages.map(String).slice(0, 30) : DEMO_SUPPLIER_PROFILE.languages,
    annualTurnover: profile.annualTurnover === null ? null : cleanNumber(profile.annualTurnover) ?? null,
    references: profile.references === null ? null : cleanNumber(profile.references) ?? null,
    minContractValue: profile.minContractValue === null ? null : cleanNumber(profile.minContractValue) ?? null,
    maxContractValue: profile.maxContractValue === null ? null : cleanNumber(profile.maxContractValue) ?? null,
  };
}

export async function POST(request: Request): Promise<Response> {
  let payload: Record<string, unknown>;
  try {
    const parsed: unknown = await request.json();
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      return Response.json(
        { error: "Search request must be a JSON object." },
        { status: 422, headers: { "cache-control": "no-store" } },
      );
    }
    payload = parsed as Record<string, unknown>;
  } catch {
    return Response.json({ error: "A JSON search request is required." }, { status: 400 });
  }
  const filters = filtersFromPayload(payload);
  const validationErrors = [...invalidPayload(payload), ...invalidFilters(filters)];
  if (validationErrors.length) return Response.json({ error: "Invalid tender search filters.", details: validationErrors }, { status: 422, headers: { "cache-control": "no-store" } });
  const paginationMode = filters.iterationNextToken ? "ITERATION" : "PAGE_NUMBER";
  const tedRequest: Record<string, unknown> = {
    query: buildTedQuery(filters), fields: TED_FIELDS, limit: filters.limit,
    scope: "ACTIVE", paginationMode, onlyLatestVersions: true,
  };
  if (paginationMode === "ITERATION") tedRequest.iterationNextToken = filters.iterationNextToken;
  else tedRequest.page = filters.page;
  const started = performance.now();
  try {
    const response = await fetch(TED_SEARCH_URL, {
      method: "POST",
      headers: { accept: "application/json", "content-type": "application/json", "user-agent": "AppliedAILab-EUTenderIntelligence/2.0" },
      body: JSON.stringify(tedRequest), signal: AbortSignal.timeout(15_000),
    });
    if (!response.ok) throw new Error(`TED Search API returned ${response.status}`);
    const raw = await response.json() as { notices?: unknown[]; totalNoticeCount?: number; iterationNextToken?: string; timedOut?: boolean };
    const normalized = (Array.isArray(raw.notices) ? raw.notices : [])
      .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
      .map((item) => normalizeTedNotice(item));
    const filtered = applyClientFilters(normalized, filters);
    const notices = filtered.map((notice) => ({ notice, assessment: assessTender(notice, profileFromPayload(payload.profile)) }));
    const hasPostFilters = filters.minValue !== undefined || filters.maxValue !== undefined || Boolean(filters.deadlineFrom);
    const hasMore = Boolean(raw.iterationNextToken) || (!raw.iterationNextToken && normalized.length === filters.limit && (raw.totalNoticeCount ?? 0) > (filters.page ?? 1) * (filters.limit ?? 12));
    return Response.json({
      retrievedAt: new Date().toISOString(), source: "TED Search API v3", endpoint: TED_SEARCH_URL,
      officialDocs: "https://docs.ted.europa.eu/api/latest/search.html", query: tedRequest.query,
      notices, tedTotalNoticeCount: raw.totalNoticeCount ?? normalized.length,
      filteredBatchCount: notices.length, filteredTotalKnown: !hasPostFilters,
      totalNoticeCount: hasPostFilters ? null : raw.totalNoticeCount ?? notices.length,
      iterationNextToken: raw.iterationNextToken ?? null, timedOut: raw.timedOut ?? false,
      hasMore, trace: { source: "TED", fetched: normalized.length, returned: notices.length, page: filters.page, paginationMode, latencyMs: Math.round(performance.now() - started) },
    }, { headers: { "cache-control": "private, no-store" } });
  } catch (error) {
    console.error("TED ingestion failed", error);
    const timedOut = error instanceof DOMException && error.name === "TimeoutError";
    return Response.json({ error: timedOut ? "The official TED Search API timed out." : "The official TED Search API is temporarily unavailable.", category: timedOut ? "TED_TIMEOUT" : "TED_UPSTREAM", source: "TED Search API v3" }, { status: timedOut ? 504 : 502, headers: { "cache-control": "no-store" } });
  }
}
