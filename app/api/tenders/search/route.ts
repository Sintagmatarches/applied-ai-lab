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

function filtersFromPayload(payload: Record<string, unknown>): TenderSearchFilters {
  return {
    keywords: cleanText(payload.keywords), cpv: cleanText(payload.cpv, 9),
    buyerCountry: cleanText(payload.buyerCountry, 3), placeCountry: cleanText(payload.placeCountry, 3),
    publishedFrom: cleanText(payload.publishedFrom, 10), publishedTo: cleanText(payload.publishedTo, 10),
    minValue: cleanNumber(payload.minValue), maxValue: cleanNumber(payload.maxValue),
    deadlineFrom: cleanText(payload.deadlineFrom, 10), procedureType: cleanText(payload.procedureType, 40),
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
    payload = await request.json() as Record<string, unknown>;
  } catch {
    return Response.json({ error: "A JSON search request is required." }, { status: 400 });
  }
  const filters = filtersFromPayload(payload);
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
    const notices = applyClientFilters(normalized, filters).map((notice) => ({ notice, assessment: assessTender(notice, profileFromPayload(payload.profile)) }));
    return Response.json({
      retrievedAt: new Date().toISOString(), source: "TED Search API v3", endpoint: TED_SEARCH_URL,
      officialDocs: "https://docs.ted.europa.eu/api/latest/search.html", query: tedRequest.query,
      notices, totalNoticeCount: raw.totalNoticeCount ?? notices.length,
      iterationNextToken: raw.iterationNextToken ?? null, timedOut: raw.timedOut ?? false,
      trace: { source: "TED", fetched: normalized.length, returned: notices.length, page: filters.page, paginationMode, latencyMs: Math.round(performance.now() - started) },
    }, { headers: { "cache-control": "public, max-age=120, s-maxage=600, stale-while-revalidate=3600" } });
  } catch (error) {
    console.error("TED ingestion failed", error);
    return Response.json({ error: "The official TED Search API is temporarily unavailable.", source: "TED Search API v3" }, { status: 502, headers: { "cache-control": "no-store" } });
  }
}
