import assert from "node:assert/strict";
import test from "node:test";
import { assessTender, buildTedQuery, DEMO_SUPPLIER_PROFILE, normalizeTedNotice } from "../lib/tenders";

const raw = {
  "notice-identifier": "fixture-notice", "publication-number": "123456-2026", "notice-version": 2,
  "notice-title": { eng: "Finland – AI and data engineering services" }, "buyer-name": { eng: ["Test City"] },
  "buyer-country": ["FIN"], "publication-date": "2026-08-01+03:00", "deadline-date-lot": ["2026-09-30Z"],
  "estimated-value-proc": "700000", "estimated-value-cur-proc": "EUR", "classification-cpv": ["72000000"],
  "place-of-performance-country-lot": ["FIN"], "procedure-type": "open", "notice-type": "cn-standard", "form-type": "competition",
  "identifier-lot": ["LOT-0001"], "title-lot": { eng: ["Data platform"] },
  "description-lot": { eng: ["Minimum annual turnover 1000000 EUR. At least 3 references. ISO 27001 required. English required. Python SQL Azure analytics."] },
  "award-criterion-name-lot": { eng: ["Price", "Quality"] }, "award-criterion-type-lot": ["price", "quality"],
  links: { html: { ENG: "https://ted.europa.eu/en/notice/-/detail/123456-2026" }, xml: { MUL: "https://ted.europa.eu/en/notice/123456-2026/xml" } },
};

test("builds current TED expert-search syntax from independent filters", () => {
  const query = buildTedQuery({ keywords: "machine learning", cpv: "72*", buyerCountry: "FIN", placeCountry: "FIN", publishedFrom: "2026-01-01", publishedTo: "2026-08-18", procedureType: "open" });
  for (const fragment of ['FT ~ "machine learning"', "classification-cpv = 72*", "buyer-country = FIN", "place-of-performance-country-lot = FIN", "PD = (20260101 <> 20260818)", "procedure-type = open"]) assert.match(query, new RegExp(fragment.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
});

test("normalizes TED lots, values, CPV, deadline, criteria and evidence", () => {
  const notice = normalizeTedNotice(raw);
  assert.equal(notice.noticeId, "fixture-notice"); assert.equal(notice.lots.length, 1); assert.equal(notice.estimatedValue, 700000);
  assert.deepEqual(notice.cpvCodes, ["72000000"]); assert.equal(notice.submissionDeadline, "2026-09-30Z"); assert.equal(notice.awardCriteria.length, 2);
  assert.ok(notice.requirements.every((item) => notice.evidence.some((evidence) => evidence.id === item.evidenceId)));
});

test("mandatory failure overrides high opportunity fit", () => {
  const assessment = assessTender(normalizeTedNotice(raw), DEMO_SUPPLIER_PROFILE);
  assert.equal(assessment.status, "NO_BID"); assert.ok(assessment.strategicFit >= 50); assert.ok(assessment.blockingRequirements.length >= 1);
});

test("public TED API sends an anonymous official request and returns normalized assessments", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    assert.equal(String(input), "https://api.ted.europa.eu/v3/notices/search"); assert.equal(init?.method, "POST");
    const body = JSON.parse(String(init?.body)); assert.equal(body.paginationMode, "PAGE_NUMBER"); assert.equal(body.onlyLatestVersions, true);
    return Response.json({ notices: [raw], totalNoticeCount: 1, timedOut: false });
  };
  try {
    const { POST } = await import("../app/api/tenders/search/route");
    const response = await POST(new Request("https://lab.test/api/tenders/search", { method: "POST", body: JSON.stringify({ keywords: "AI", buyerCountry: "FIN" }) }));
    const result = await response.json() as { notices: unknown[]; source: string; endpoint: string };
    assert.equal(response.status, 200); assert.equal(result.source, "TED Search API v3"); assert.equal(result.notices.length, 1); assert.match(result.endpoint, /api\.ted\.europa\.eu/);
  } finally { globalThis.fetch = original; }
});
