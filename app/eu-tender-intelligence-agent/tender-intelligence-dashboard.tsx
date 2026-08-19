"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import type { TenderDateRange } from "../../lib/tender-date-range";
import { DEMO_SUPPLIER_PROFILE, type BidAssessment, type ProcurementNotice, type SupplierProfile } from "../../lib/tenders";

type Result = { notice: ProcurementNotice; assessment: BidAssessment };
type SearchResponse = {
  retrievedAt: string; query: string; source: string; tedTotalNoticeCount: number; totalNoticeCount: number | null;
  filteredBatchCount: number; filteredTotalKnown: boolean; hasMore: boolean;
  iterationNextToken: string | null; notices: Result[];
  trace: { fetched: number; returned: number; paginationMode: string; latencyMs: number; page: number };
};
export type PublicTenderEvidence = {
  verifiedAt: string; source: string; uniqueNotices: number; model: string;
  retrieval: { hits: number; candidateCount: number; latencyMs: number };
  agent: { answerStatus: string; toolCalls: number; fallbackUsed: boolean; citationValidity: number; claimSupportRate: number };
  evaluation: { cases: number; scope: string; securityTests: number };
};

const PROFILE_KEY = "eu-tender-demo-supplier-v2";
const WATCHLIST_KEY = "eu-tender-watchlist-v2";

function money(value: number | null, currency: string | null) {
  if (value === null) return "Value not stated";
  return new Intl.NumberFormat("en", { style: "currency", currency: currency || "EUR", maximumFractionDigits: 0 }).format(value);
}
function displayDate(value: string | null) {
  if (!value) return "Not stated";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}
function csv(value: string) { return value.split(",").map((item) => item.trim()).filter(Boolean); }

export function TenderIntelligenceDashboard({ defaultDateRange, publicEvidence }: { defaultDateRange: TenderDateRange; publicEvidence: PublicTenderEvidence }) {
  const [results, setResults] = useState<Result[]>([]);
  const [profile, setProfile] = useState<SupplierProfile>(DEMO_SUPPLIER_PROFILE);
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [meta, setMeta] = useState<SearchResponse | null>(null);
  const [selected, setSelected] = useState<Result | null>(null);
  const [sort, setSort] = useState("eligibility");
  const [filters, setFilters] = useState({
    keywords: "", cpv: "", buyerCountry: "FIN", placeCountry: "",
    publishedFrom: defaultDateRange.publishedFrom, publishedTo: defaultDateRange.publishedTo,
    minValue: "", maxValue: "", deadlineFrom: "", procedureType: "",
  });

  useEffect(() => {
    try {
      const storedProfile = localStorage.getItem(PROFILE_KEY);
      const storedWatchlist = localStorage.getItem(WATCHLIST_KEY);
      const parsedProfile = storedProfile ? JSON.parse(storedProfile) as SupplierProfile : null;
      const parsedWatchlist = storedWatchlist ? JSON.parse(storedWatchlist) as string[] : null;
      queueMicrotask(() => { if (parsedProfile) setProfile(parsedProfile); if (parsedWatchlist) setWatchlist(parsedWatchlist); });
    } catch { /* Corrupt device-local preferences are ignored. */ }
  }, []);

  async function search(event?: FormEvent, token?: string, page = 1, override?: Partial<typeof filters>) {
    event?.preventDefault();
    setLoading(true); setError("");
    const active = { ...filters, ...override };
    if (override) setFilters(active);
    try {
      const response = await fetch("/api/tenders/search", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ ...active, minValue: active.minValue || undefined, maxValue: active.maxValue || undefined, deadlineFrom: active.deadlineFrom || undefined, iterationNextToken: token, page, profile }),
      });
      const body = await response.json() as SearchResponse & { error?: string; details?: string[] };
      if (!response.ok) throw new Error([body.error, ...(body.details ?? [])].filter(Boolean).join(" "));
      setMeta(body);
      setResults((current) => {
        const incoming = token || page > 1 ? [...current, ...body.notices] : body.notices;
        return [...new Map(incoming.map((item) => [item.notice.noticeId, item])).values()];
      });
      if (!token && page === 1) setSelected(body.notices[0] ?? null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Search failed"); }
    finally { setLoading(false); }
  }
  function runExample() { void search(undefined, undefined, 1, { keywords: "", cpv: "72*", buyerCountry: "FIN", placeCountry: "" }); }
  function updateProfile(next: SupplierProfile) {
    const versioned = { ...next, version: profile.version + 1 };
    setProfile(versioned); localStorage.setItem(PROFILE_KEY, JSON.stringify(versioned));
  }
  function toggleWatchlist(id: string) {
    const next = watchlist.includes(id) ? watchlist.filter((item) => item !== id) : [...watchlist, id];
    setWatchlist(next); localStorage.setItem(WATCHLIST_KEY, JSON.stringify(next));
  }
  const sorted = useMemo(() => [...results].sort((left, right) => {
    if (sort === "fit") return right.assessment.strategicFit - left.assessment.strategicFit;
    if (sort === "deadline") return (left.notice.submissionDeadline ?? "9999").localeCompare(right.notice.submissionDeadline ?? "9999");
    const rank = { BID: 0, REVIEW: 1, INSUFFICIENT_EVIDENCE: 2, NO_BID: 3 };
    return rank[left.assessment.status] - rank[right.assessment.status];
  }), [results, sort]);

  return <div className="tender-page">
    <header className="tender-hero">
      <div><p className="eyebrow">Applied AI · Official TED procurement data</p><h1>EU Tender<br />Intelligence Agent</h1><p>Discover notices, qualify each lot deterministically, recheck saved opportunities, and inspect grounded local-AI evidence.</p></div>
      <aside className="tender-pipeline" aria-label="System pipeline">{["DISCOVER", "QUALIFY PER LOT", "WATCH + RECHECK", "GROUNDED AI"].map((step, index) => <div key={step}><span>0{index + 1}</span><strong>{step}</strong></div>)}</aside>
    </header>

    <section className="tender-boundary" aria-label="Runtime boundaries"><strong>PUBLIC LIVE</strong><p>Anonymous TED Search API, cautious field normalization, lot-level deterministic assessment and manual watchlist recheck.</p><strong>LOCAL AI</strong><p>Persistent history, bounded Qwen tool loop, Nomic retrieval and deterministic grounding gate. Public Cloudflare never calls localhost Ollama.</p></section>

    <nav className="tender-project-links" aria-label="Project evidence">
      <a href="https://github.com/Sintagmatarches/applied-ai-lab/tree/main/tender_ai">Source code ↗</a>
      <a href="https://github.com/Sintagmatarches/applied-ai-lab/blob/main/docs/tender-ai-architecture.md">Architecture ↗</a>
      <a href="https://github.com/Sintagmatarches/applied-ai-lab/blob/main/docs/tender-ai-evaluation.md">Evaluation ↗</a>
      <a href="https://github.com/Sintagmatarches/applied-ai-lab/blob/main/docs/tender-ai-live-verification.md">Live verification ↗</a>
      <a href="https://github.com/Sintagmatarches/applied-ai-lab/blob/main/docs/tender-ai-threat-model.md">Security ↗</a>
    </nav>

    <section className="tender-workspace" aria-labelledby="discovery-title">
      <div className="section-heading"><div><p className="eyebrow">Search / discovery</p><h2 id="discovery-title">Official procurement notices</h2></div><button type="button" onClick={runExample} disabled={loading}>Run live example search</button></div>
      <form className="tender-filters" onSubmit={search}>
        <label>Procurement keywords<input value={filters.keywords} onChange={(e) => setFilters({ ...filters, keywords: e.target.value })} placeholder="software platform, cyber security…" /></label>
        <label>CPV classification<input value={filters.cpv} onChange={(e) => setFilters({ ...filters, cpv: e.target.value })} placeholder="72000000 or 72*" /></label>
        <label>Buyer country (TED code)<input value={filters.buyerCountry} onChange={(e) => setFilters({ ...filters, buyerCountry: e.target.value.toUpperCase() })} maxLength={3} /></label>
        <label>Place of performance<input value={filters.placeCountry} onChange={(e) => setFilters({ ...filters, placeCountry: e.target.value.toUpperCase() })} placeholder="FIN" maxLength={3} /></label>
        <label>Published from<input type="date" value={filters.publishedFrom} onChange={(e) => setFilters({ ...filters, publishedFrom: e.target.value })} /></label>
        <label>Published to<input type="date" value={filters.publishedTo} onChange={(e) => setFilters({ ...filters, publishedTo: e.target.value })} /></label>
        <label>Minimum lot value (EUR)<input type="number" value={filters.minValue} onChange={(e) => setFilters({ ...filters, minValue: e.target.value })} /></label>
        <label>Maximum lot value (EUR)<input type="number" value={filters.maxValue} onChange={(e) => setFilters({ ...filters, maxValue: e.target.value })} /></label>
        <label>Lot deadline on/after<input type="date" value={filters.deadlineFrom} onChange={(e) => setFilters({ ...filters, deadlineFrom: e.target.value })} /></label>
        <label>Procedure<select value={filters.procedureType} onChange={(e) => setFilters({ ...filters, procedureType: e.target.value })}><option value="">Any</option><option value="open">Open</option><option value="restricted">Restricted</option><option value="neg-w-call">Negotiated with call</option></select></label>
        <button type="submit" disabled={loading}>{loading ? "Querying official TED…" : "Search live TED"}</button>
      </form>
      {error && <p className="tender-error" role="alert">{error}</p>}
      {loading && <div className="tender-loading" role="status">Loading and qualifying TED lots…</div>}
      {meta && <div className="ingestion-trace"><span>{meta.trace.fetched} FETCHED THIS BATCH</span><span>{meta.filteredBatchCount} AFTER LOT FILTERS</span><span>{meta.trace.latencyMs} MS</span><span>{meta.tedTotalNoticeCount.toLocaleString()} TED SOURCE MATCHES</span></div>}
    </section>

    <section className="tender-results" aria-labelledby="opportunities-title">
      <div className="section-heading"><div><p className="eyebrow">Opportunities</p><h2 id="opportunities-title">Eligibility before enthusiasm</h2></div><label>Sort<select value={sort} onChange={(event) => setSort(event.target.value)}><option value="eligibility">Eligible first</option><option value="fit">Heuristic fit</option><option value="deadline">Deadline</option></select></label></div>
      {!meta && !loading && <div className="tender-empty"><strong>No fake opportunities are preloaded.</strong><p>Run the live CPV 72* Finland example or define a procurement query.</p></div>}
      {meta && !loading && !results.length && <div className="tender-empty"><strong>No notices survived this batch and its lot filters.</strong><p>TED source matches and client-side lot filters are reported separately above.</p></div>}
      <div className="tender-results-grid"><div className="tender-card-list">
        {sorted.map(({ notice, assessment }) => <article className={`tender-card status-${assessment.status.toLowerCase()}`} key={notice.noticeId}>
          <div className="tender-card-header"><div><p>{notice.buyer} · {notice.buyerCountry}</p><h3>{notice.title}</h3></div><div className="decision-badge"><strong>{assessment.status.replaceAll("_", " ")}</strong><span>{assessment.heuristicFitLabel} HEURISTIC FIT · {assessment.strategicFit}/100</span></div></div>
          <dl className="tender-facts"><div><dt>Eligible lots</dt><dd>{assessment.summary.eligibleLots.length}</dd></div><div><dt>Blocked lots</dt><dd>{assessment.summary.blockedLots.length}</dd></div><div><dt>Review lots</dt><dd>{assessment.summary.reviewLots.length}</dd></div><div><dt>Procedure</dt><dd>{notice.procedureType}</dd></div></dl>
          <div className="tender-lot-summary">{assessment.lotAssessments.map((lot) => {
            const sourceLot = notice.lots.find((item) => item.id === lot.lotId);
            return <div key={lot.lotId}><strong>{lot.lotId} · {lot.status.replaceAll("_", " ")}</strong><span>{sourceLot?.title} · {money(sourceLot?.value ?? null, sourceLot?.currency ?? null)} · {displayDate(sourceLot?.deadline ?? null)}</span>{lot.blockingRequirements.map((item) => <small key={item.requirementId}>Blocking: {item.reason}</small>)}</div>;
          })}</div>
          <div className="tender-card-actions"><a href={notice.noticeUrl} target="_blank" rel="noreferrer">Open TED notice ↗</a><button onClick={() => setSelected({ notice, assessment })}>Inspect evidence</button><button onClick={() => toggleWatchlist(notice.noticeId)} className={watchlist.includes(notice.noticeId) ? "is-saved" : ""}>{watchlist.includes(notice.noticeId) ? "Watching" : "Watch"}</button></div>
        </article>)}
        {meta?.hasMore && <button className="load-more" disabled={loading} onClick={() => meta.iterationNextToken ? search(undefined, meta.iterationNextToken) : search(undefined, undefined, meta.trace.page + 1)}>Load next TED batch</button>}
      </div><aside className="evidence-panel"><p className="eyebrow">Evidence inspector</p><h3>{selected ? selected.notice.publicationId : "Select an opportunity"}</h3>{selected && <>
        <p><strong>Notice summary:</strong> {selected.assessment.status.replaceAll("_", " ")}. The score is an uncalibrated, explainable heuristic—not a probability.</p>
        <h4>Lot decisions</h4>{selected.assessment.lotAssessments.map((lot) => <div key={lot.lotId}><strong>{lot.lotId}: {lot.status}</strong><ul>{lot.checks.map((check) => <li key={check.requirementId}>{check.mandatory ? "Mandatory" : "Optional"} · {check.outcome} · {check.reason}</li>)}</ul></div>)}
        <h4>Structured award criteria</h4>{selected.notice.awardCriteria.length ? <ul>{selected.notice.awardCriteria.map((criterion) => <li key={criterion.id}>{criterion.lotId ?? "Unassigned lot"} · {criterion.type}: {criterion.name}{criterion.weight === null ? "" : ` · ${criterion.weight} (${criterion.weightType ?? "number"})`}</li>)}</ul> : <p>Not present in the selected TED fields.</p>}
        <h4>Security findings</h4>{selected.notice.securityFindings.length ? <ul>{selected.notice.securityFindings.map((finding) => <li key={finding.id}>{finding.type} quarantined for {finding.lotId}; it does not alter eligibility.</li>)}</ul> : <p>No source-text instruction pattern was detected.</p>}
      </>}</aside></div>
    </section>

    <section className="tender-secondary-grid">
      <article><p className="eyebrow">PUBLIC WATCHLIST</p><h2>{watchlist.length} saved notices</h2><p>Device-local list. Recheck explicitly reruns the current official query and refreshes watched notices present in the returned batch.</p><button type="button" disabled={!watchlist.length || loading} onClick={() => void search()}>Recheck watched notices</button></article>
      <article><p className="eyebrow">RECORDED VERIFIED EVIDENCE</p><h2>{publicEvidence.uniqueNotices} live notices · {publicEvidence.retrieval.hits} retrieval hits</h2><p>Verified {publicEvidence.verifiedAt.slice(0, 10)} against {publicEvidence.source}. Model: {publicEvidence.model}. Last answer status: {publicEvidence.agent.answerStatus}; fallback {publicEvidence.agent.fallbackUsed ? "used and disclosed" : "not used"}.</p></article>
      <article><p className="eyebrow">GROUNDING</p><h2>{Math.round(publicEvidence.agent.citationValidity * 100)}% valid citations</h2><p>Claim support {Math.round(publicEvidence.agent.claimSupportRate * 100)}% in the recorded run. Security suite: {publicEvidence.evaluation.securityTests} adversarial regression checks. Scope: {publicEvidence.evaluation.scope}.</p></article>
    </section>

    <section className="supplier-profile"><div><p className="eyebrow">Editable fictional supplier</p><h2>{profile.companyName}</h2><p>Used only by deterministic code. The LLM cannot send or replace these values in tool arguments.</p></div><form onSubmit={(event) => { event.preventDefault(); updateProfile(profile); }}>
      <label>Company name<input value={profile.companyName} onChange={(e) => setProfile({ ...profile, companyName: e.target.value })} /></label>
      <label>Annual turnover EUR<input type="number" value={profile.annualTurnover ?? ""} onChange={(e) => setProfile({ ...profile, annualTurnover: e.target.value ? Number(e.target.value) : null })} /></label>
      <label>Reference projects<input type="number" value={profile.references ?? ""} onChange={(e) => setProfile({ ...profile, references: e.target.value ? Number(e.target.value) : null })} /></label>
      <label>Minimum contract value<input type="number" value={profile.minContractValue ?? ""} onChange={(e) => setProfile({ ...profile, minContractValue: e.target.value ? Number(e.target.value) : null })} /></label>
      <label>Maximum contract value<input type="number" value={profile.maxContractValue ?? ""} onChange={(e) => setProfile({ ...profile, maxContractValue: e.target.value ? Number(e.target.value) : null })} /></label>
      <label>Languages<input value={profile.languages.join(", ")} onChange={(e) => setProfile({ ...profile, languages: csv(e.target.value) })} /></label>
      <label>Certifications<input value={profile.certifications.join(", ")} onChange={(e) => setProfile({ ...profile, certifications: csv(e.target.value) })} /></label>
      <label>Capabilities<textarea value={profile.capabilities.join(", ")} onChange={(e) => setProfile({ ...profile, capabilities: csv(e.target.value) })} /></label>
      <label>Countries served<input value={profile.countriesServed.join(", ")} onChange={(e) => setProfile({ ...profile, countriesServed: csv(e.target.value).map((item) => item.toUpperCase()) })} /></label>
      <button type="submit">Save profile version {profile.version + 1}</button>
    </form></section>
    <section className="tender-limitations"><h2>Decision support, not procurement advice</h2><p>Structured TED fields can omit conditions held in procurement documents. Unassigned multi-lot criteria stay uncertain rather than being attached to the wrong lot. Always verify the official notice and documents before bidding.</p></section>
  </div>;
}
