import type { Metadata } from "next";
import Link from "next/link";
import summary from "../../artifacts/rail-summary.json";
import { LabShell } from "../lab-shell";
import { RailMonitor } from "./rail-monitor";

export const metadata: Metadata = {
  title: "Finland Rail Reliability Monitor",
  description:
    "Evidence-backed analysis of Finnish passenger-train, route and station reliability using official Fintraffic data.",
};

export default function FinlandRailReliabilityMonitor() {
  return (
    <LabShell activeProject="rail">
      <div className="rail-page">
        <header className="rail-hero">
          <div>
            <p className="eyebrow">Applied AI Lab · Project 02</p>
            <h1>Finland Rail Reliability Monitor</h1>
            <p className="intro-copy">
              How reliably do Finnish passenger trains reach their destination — and which routes, stations and operating periods carry the most delay risk?
            </p>
            <nav className="project-resources" aria-label="Rail project resources">
              <a href="https://github.com/Sintagmatarches/applied-ai-lab/tree/main/rail" target="_blank" rel="noreferrer">Pipeline</a>
              <a href="https://github.com/Sintagmatarches/applied-ai-lab/tree/main/docs/rail" target="_blank" rel="noreferrer">Technical documentation</a>
              <a href="https://www.digitraffic.fi/en/railway-traffic/" target="_blank" rel="noreferrer">Digitraffic source</a>
              <a href="https://en.ilmatieteenlaitos.fi/open-data" target="_blank" rel="noreferrer">FMI source</a>
            </nav>
          </div>
          <dl className="rail-hero-facts">
            <div>
              <dt>Coverage</dt>
              <dd>{summary.meta.coverage_start}<br />→ {summary.meta.coverage_end}</dd>
            </div>
            <div>
              <dt>Passenger journeys</dt>
              <dd>{summary.overall.scheduled.toLocaleString("en-FI")}</dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>Fintraffic / Digitraffic<br />CC BY 4.0</dd>
            </div>
            <div>
              <dt>Snapshot retrieved</dt>
              <dd>{summary.meta.retrieved_at.slice(0, 10)}</dd>
            </div>
          </dl>
        </header>

        <aside className="rail-definition-note">
          <strong>Default definition</strong>
          <span>
            “On time” means the final commercial arrival was no more than five whole minutes late. Cancelled trains and missing actual times are reported separately and never treated as on-time arrivals.
          </span>
        </aside>

        <RailMonitor summary={summary} />

        <section className="rail-method" aria-labelledby="method-title">
          <div>
            <p className="eyebrow">Engineering and governance</p>
            <h2 id="method-title">Reproducible from source to semantic model</h2>
          </div>
          <div className="method-card-grid">
            <article>
              <span>01</span>
              <h3>Incremental ingestion</h3>
              <p>One immutable Digitraffic departure-date partition is cached at a time. Re-runs download only missing days and preserve source fields.</p>
            </article>
            <article>
              <span>02</span>
              <h3>Quality gates</h3>
              <p>Unique train keys, route endpoints, missing actuals, station codes, cancellations, extreme values and reported-versus-calculated delay are audited.</p>
            </article>
            <article>
              <span>03</span>
              <h3>Analytical model</h3>
              <p>Train journeys, commercial station arrivals, dates, routes and stations form explicit grains for Fabric Lakehouse and Power BI measures.</p>
            </article>
            <article>
              <span>04</span>
              <h3>Honest delivery</h3>
              <p>The public site uses a versioned aggregate snapshot. Fabric workspace deployment and Power BI publishing remain documented external steps, not simulated claims.</p>
            </article>
          </div>
          <div className="rail-method-links">
            <Link href="/olist-delivery-delay-predictor">Compare with the Olist ML project</Link>
            <a href="https://github.com/Sintagmatarches/applied-ai-lab/blob/main/docs/rail/methodology.md" target="_blank" rel="noreferrer">Read definitions and limitations</a>
            <a href="https://github.com/Sintagmatarches/applied-ai-lab/tree/main/power-bi" target="_blank" rel="noreferrer">Review the Power BI semantic model</a>
          </div>
        </section>

        <aside className="rail-limitations">
          <h2>What this monitor does not claim</h2>
          <p>
            It measures trains, not passenger-weighted journeys; a lightly used service and a crowded service each count once. Missing actual times are excluded rather than inferred. Route metrics combine directions unless shown separately. Weather comparisons are descriptive and cannot isolate a causal effect from season, disruptions or infrastructure conditions. Deleted trains cancelled more than ten days before departure are not returned by the default historical endpoint and therefore are outside this snapshot.
          </p>
        </aside>

        <footer className="rail-attribution">
          <p>
            Railway source: <a href="https://www.digitraffic.fi/en/railway-traffic/" target="_blank" rel="noreferrer">Fintraffic / digitraffic.fi</a>, licensed under <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0</a>. Data was transformed into analytical aggregates; changes are documented in the repository.
          </p>
          <p>
            Weather source: <a href="https://en.ilmatieteenlaitos.fi/open-data" target="_blank" rel="noreferrer">Finnish Meteorological Institute open data</a>, licensed under CC BY 4.0.
          </p>
        </footer>
      </div>
    </LabShell>
  );
}

