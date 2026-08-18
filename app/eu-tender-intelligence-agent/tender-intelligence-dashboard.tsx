"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { DEMO_SUPPLIER_PROFILE, type BidAssessment, type ProcurementNotice, type SupplierProfile } from "../../lib/tenders";

type Result = { notice: ProcurementNotice; assessment: BidAssessment };
type SearchResponse = {
  retrievedAt: string; query: string; source: string; totalNoticeCount: number;
  iterationNextToken: string | null; notices: Result[];
  trace: { fetched: number; returned: number; paginationMode: string; latencyMs: number; page: number };
};

const PROFILE_KEY = "eu-tender-demo-supplier-v1";
const WATCHLIST_KEY = "eu-tender-watchlist-v1";
const TODAY = new Date().toISOString().slice(0, 10);
const SEARCH_START = new Date(new Date().valueOf() - 120 * 86400000).toISOString().slice(0, 10);

function money(value: number | null, currency: string | null) {
  if (value === null) return "Value not stated";
  return new Intl.NumberFormat("en", { style: "currency", currency: currency || "EUR", maximumFractionDigits: 0 }).format(value);
}

function date(value: string | null) {
  if (!value) return "Not stated";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function TenderIntelligenceDashboard() {
  const [results, setResults] = useState<Result[]>([]);
  const [profile, setProfile] = useState<SupplierProfile>(DEMO_SUPPLIER_PROFILE);
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [meta, setMeta] = useState<SearchResponse | null>(null);
  const [selected, setSelected] = useState<Result | null>(null);
  const [filters, setFilters] = useState({
    keywords: "data analytics", cpv: "", buyerCountry: "FIN", placeCountry: "",
    publishedFrom: SEARCH_START,
    publishedTo: TODAY, minValue: "", maxValue: "", deadlineFrom: "", procedureType: "",
  });

  useEffect(() => {
    try {
      const storedProfile = localStorage.getItem(PROFILE_KEY);
      const storedWatchlist = localStorage.getItem(WATCHLIST_KEY);
      const parsedProfile = storedProfile ? JSON.parse(storedProfile) as SupplierProfile : null;
      const parsedWatchlist = storedWatchlist ? JSON.parse(storedWatchlist) as string[] : null;
      queueMicrotask(() => {
        if (parsedProfile) setProfile(parsedProfile);
        if (parsedWatchlist) setWatchlist(parsedWatchlist);
      });
    } catch { /* Invalid local state is ignored. */ }
  }, []);

  async function search(event?: FormEvent, token?: string, page = 1) {
    event?.preventDefault();
    setLoading(true); setError("");
    try {
      const response = await fetch("/api/tenders/search", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ ...filters, minValue: filters.minValue || undefined, maxValue: filters.maxValue || undefined, deadlineFrom: filters.deadlineFrom || undefined, iterationNextToken: token, page, profile }),
      });
      const body = await response.json() as SearchResponse & { error?: string };
      if (!response.ok) throw new Error(body.error || "TED search failed");
      setMeta(body); setResults((current) => token || page > 1 ? [...current, ...body.notices] : body.notices);
      if (!token && page === 1) setSelected(body.notices[0] ?? null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Search failed"); }
    finally { setLoading(false); }
  }

  function updateProfile(next: SupplierProfile) {
    const versioned = { ...next, version: profile.version + 1 };
    setProfile(versioned); localStorage.setItem(PROFILE_KEY, JSON.stringify(versioned));
  }

  function toggleWatchlist(id: string) {
    const next = watchlist.includes(id) ? watchlist.filter((item) => item !== id) : [...watchlist, id];
    setWatchlist(next); localStorage.setItem(WATCHLIST_KEY, JSON.stringify(next));
  }

  const changes = useMemo(() => results.filter(({ notice }) => notice.version > 1), [results]);

  return (
    <div className="tender-page">
      <header className="tender-hero">
        <div>
          <p className="eyebrow">Agentic procurement intelligence · Official TED data</p>
          <h1>EU Tender<br />Intelligence Agent</h1>
          <p>Discover opportunities, qualify mandatory eligibility, monitor amendments, and reassess bid decisions from cited procurement evidence.</p>
        </div>
        <aside className="tender-pipeline" aria-label="System pipeline">
          {['DISCOVER', 'QUALIFY', 'MONITOR CHANGES', 'REASSESS'].map((step, index) => <div key={step}><span>0{index + 1}</span><strong>{step}</strong></div>)}
        </aside>
      </header>

      <section className="tender-boundary">
        <strong>Honest runtime boundary</strong>
        <p>Public: live anonymous TED Search API v3, normalization, lots, structured extraction, and deterministic assessment. Local only: Ollama embeddings, hybrid RAG, tool-calling agent, and claim-level grounding.</p>
      </section>

      <section className="tender-workspace" aria-labelledby="discovery-title">
        <div className="section-heading"><div><p className="eyebrow">Search / discovery</p><h2 id="discovery-title">Official EU procurement notices</h2></div><a href="https://docs.ted.europa.eu/api/latest/search.html" target="_blank" rel="noreferrer">TED API documentation ↗</a></div>
        <form className="tender-filters" onSubmit={search}>
          <label>Keywords<input value={filters.keywords} onChange={(e) => setFilters({ ...filters, keywords: e.target.value })} placeholder="data, software, AI…" /></label>
          <label>CPV<input value={filters.cpv} onChange={(e) => setFilters({ ...filters, cpv: e.target.value })} placeholder="72000000 or 72*" /></label>
          <label>Buyer country<input value={filters.buyerCountry} onChange={(e) => setFilters({ ...filters, buyerCountry: e.target.value.toUpperCase() })} maxLength={3} /></label>
          <label>Place<input value={filters.placeCountry} onChange={(e) => setFilters({ ...filters, placeCountry: e.target.value.toUpperCase() })} placeholder="FIN" maxLength={3} /></label>
          <label>Published from<input type="date" value={filters.publishedFrom} onChange={(e) => setFilters({ ...filters, publishedFrom: e.target.value })} /></label>
          <label>Published to<input type="date" value={filters.publishedTo} onChange={(e) => setFilters({ ...filters, publishedTo: e.target.value })} /></label>
          <label>Minimum value<input type="number" value={filters.minValue} onChange={(e) => setFilters({ ...filters, minValue: e.target.value })} placeholder="EUR" /></label>
          <label>Maximum value<input type="number" value={filters.maxValue} onChange={(e) => setFilters({ ...filters, maxValue: e.target.value })} placeholder="EUR" /></label>
          <label>Deadline after<input type="date" value={filters.deadlineFrom} onChange={(e) => setFilters({ ...filters, deadlineFrom: e.target.value })} /></label>
          <label>Procedure<select value={filters.procedureType} onChange={(e) => setFilters({ ...filters, procedureType: e.target.value })}><option value="">Any</option><option value="open">Open</option><option value="restricted">Restricted</option><option value="neg-w-call">Negotiated</option></select></label>
          <button type="submit" disabled={loading}>{loading ? "Querying TED…" : "Search live TED"}</button>
        </form>
        {error && <p className="tender-error" role="alert">{error}</p>}
        {meta && <div className="ingestion-trace"><span>QUERY {meta.query}</span><span>{meta.trace.fetched} FETCHED</span><span>{meta.trace.latencyMs} MS</span><span>{meta.totalNoticeCount.toLocaleString()} MATCHES</span></div>}
      </section>

      <section className="tender-results" aria-labelledby="opportunities-title">
        <div className="section-heading"><div><p className="eyebrow">Opportunities</p><h2 id="opportunities-title">Eligibility before enthusiasm</h2></div><span>{results.length} loaded · {watchlist.length} watched</span></div>
        {!meta && <div className="tender-empty"><strong>Run a live TED search.</strong><p>The dashboard does not ship hardcoded opportunities.</p></div>}
        <div className="tender-results-grid">
          <div className="tender-card-list">
            {results.map((result) => {
              const { notice, assessment } = result;
              return <article className={`tender-card status-${assessment.status.toLowerCase()}`} key={`${notice.noticeId}:${notice.version}`}>
                <div className="tender-card-header"><div><p>{notice.buyer} · {notice.buyerCountry}</p><h3>{notice.title}</h3></div><div className="decision-badge"><strong>{assessment.status.replace("_", " ")}</strong><span>FIT {assessment.strategicFit}/100</span></div></div>
                <dl className="tender-facts"><div><dt>Deadline</dt><dd>{date(notice.submissionDeadline)}</dd></div><div><dt>Value</dt><dd>{money(notice.estimatedValue, notice.currency)}</dd></div><div><dt>Lots</dt><dd>{notice.lots.length}</dd></div><div><dt>Procedure</dt><dd>{notice.procedureType}</dd></div></dl>
                <p className="tender-description">{notice.description.slice(0, 360)}{notice.description.length > 360 ? "…" : ""}</p>
                {assessment.blockingRequirements.length > 0 && <p className="blocking"><strong>Blocking:</strong> {assessment.blockingRequirements.map((item) => item.reason).join(" ")}</p>}
                {assessment.status === "INSUFFICIENT_EVIDENCE" && <p className="uncertain">No explicit eligibility condition was available in the returned structured fields. Review linked documents before deciding.</p>}
                <div className="tender-card-actions"><a href={notice.noticeUrl} target="_blank" rel="noreferrer">Open TED notice ↗</a>{notice.xmlUrl && <a href={notice.xmlUrl} target="_blank" rel="noreferrer">Source XML ↗</a>}<button onClick={() => setSelected(result)}>Inspect evidence</button><button onClick={() => toggleWatchlist(notice.noticeId)} className={watchlist.includes(notice.noticeId) ? "is-saved" : ""}>{watchlist.includes(notice.noticeId) ? "Watching" : "Watch"}</button></div>
              </article>;
            })}
            {meta && results.length < meta.totalNoticeCount && <button className="load-more" disabled={loading} onClick={() => meta.iterationNextToken ? search(undefined, meta.iterationNextToken) : search(undefined, undefined, meta.trace.page + 1)}>Load next TED batch</button>}
          </div>
          <aside className="evidence-panel">
            <p className="eyebrow">Evidence inspector</p>
            <h3>{selected ? selected.notice.publicationId : "Select an opportunity"}</h3>
            {selected && <>
              <p><strong>Mandatory eligibility:</strong> {selected.assessment.status.replace("_", " ")}. Strategic fit stays separate at {selected.assessment.strategicFit}/100.</p>
              <h4>Requirements</h4>
              {selected.notice.requirements.length ? <ul>{selected.notice.requirements.map((requirement) => <li key={requirement.id}><strong>{requirement.category}</strong> · {requirement.text}<br /><a href={selected.notice.evidence.find((item) => item.id === requirement.evidenceId)?.url} target="_blank" rel="noreferrer">{requirement.evidenceId} ↗</a></li>)}</ul> : <p>No structured requirement extracted from the Search API fields; linked procurement documents remain authoritative.</p>}
              <h4>Award criteria</h4>
              {selected.notice.awardCriteria.length ? <ul>{selected.notice.awardCriteria.slice(0, 8).map((criterion) => <li key={criterion.id}>{criterion.type}: {criterion.name}</li>)}</ul> : <p>Not stated in returned fields.</p>}
              <h4>Lots</h4><ol>{selected.notice.lots.map((lot) => <li key={lot.id}><strong>{lot.id}</strong> {lot.title}</li>)}</ol>
            </>}
          </aside>
        </div>
      </section>

      <section className="tender-secondary-grid">
        <article><p className="eyebrow">Watchlist</p><h2>{watchlist.length} saved opportunities</h2><p>Stored in this browser. Repeated ingestion in the local runtime persists source hashes and versions.</p></article>
        <article><p className="eyebrow">Changes</p><h2>{changes.length} versioned notices in this batch</h2><p>{changes.length ? "Open the local change timeline for field-level diffs and automatic reassessment." : "No multi-version record was returned in this latest-only public batch."}</p></article>
        <article><p className="eyebrow">AI analysis · local</p><h2>Grounded tool execution</h2><p>Use the local runtime for questions such as “Which mandatory requirement blocks us?” Claims are published only after evidence-ID validation.</p></article>
      </section>

      <section className="supplier-profile">
        <div><p className="eyebrow">Editable demo supplier</p><h2>{profile.companyName}</h2><p>This is an explicitly fictional portfolio profile, never a claim about the visitor or owner.</p></div>
        <form onSubmit={(event) => { event.preventDefault(); updateProfile(profile); }}>
          <label>Company name<input value={profile.companyName} onChange={(e) => setProfile({ ...profile, companyName: e.target.value })} /></label>
          <label>Annual turnover EUR<input type="number" value={profile.annualTurnover ?? ""} onChange={(e) => setProfile({ ...profile, annualTurnover: e.target.value ? Number(e.target.value) : null })} /></label>
          <label>Reference projects<input type="number" value={profile.references ?? ""} onChange={(e) => setProfile({ ...profile, references: e.target.value ? Number(e.target.value) : null })} /></label>
          <label>Certifications<input value={profile.certifications.join(", ")} onChange={(e) => setProfile({ ...profile, certifications: e.target.value.split(",").map((item) => item.trim()).filter(Boolean) })} placeholder="ISO 27001, ISO 9001" /></label>
          <label>Capabilities<textarea value={profile.capabilities.join(", ")} onChange={(e) => setProfile({ ...profile, capabilities: e.target.value.split(",").map((item) => item.trim()).filter(Boolean) })} /></label>
          <label>Countries served<input value={profile.countriesServed.join(", ")} onChange={(e) => setProfile({ ...profile, countriesServed: e.target.value.split(",").map((item) => item.trim().toUpperCase()).filter(Boolean) })} /></label>
          <button type="submit">Save profile & increment version</button>
        </form>
      </section>

      <section className="tender-limitations"><h2>Decision support, not procurement advice</h2><p>TED fields can omit qualification detail that exists only in attachments. “Insufficient evidence” is intentional. Verify source documents, deadlines, language and legal eligibility before any bid action.</p></section>
    </div>
  );
}
