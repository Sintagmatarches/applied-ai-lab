import type { Metadata } from "next";
import Link from "next/link";
import summary from "../../artifacts/rail-summary.json";
import { LabShell } from "../lab-shell";
import { RailMonitor } from "./rail-monitor";
import { RegionalRailMonitor } from "./regional-monitor";

export const metadata: Metadata = {
  title: "Finland Rail Monitoring System",
  description:
    "Live regional monitoring and historical reliability analysis for Finland's passenger-rail network using official Fintraffic and Statistics Finland data.",
};

function rate(value: number | null | undefined): string {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

export default function FinlandRailReliabilityMonitor() {
  const june2026 = summary.monthly.find((month) => month.month === "2026-06");
  const lahtiToHelsinki = summary.lahti_helsinki.directions.find(
    (direction) => direction.direction === "Lahti → Helsinki",
  );
  const helsinkiToLahti = summary.lahti_helsinki.directions.find(
    (direction) => direction.direction === "Helsinki → Lahti",
  );
  const helsinkiRovaniemi = summary.routes.find(
    (route) => route.route_key === "HKI--ROI",
  );

  return (
    <LabShell activeProject="rail">
      <div className="rail-page">
        <header className="rail-hero">
          <div>
            <p className="eyebrow">Applied AI Lab · Project 02</p>
            <h1>Finland Rail Monitoring System</h1>
            <p className="intro-copy">
              See where Finland’s passenger-rail network is operating normally right now — and which regions, stations and routes are under pressure.
            </p>
            <ul className="rail-tech-summary" aria-label="Technology and engineering stack">
              <li>Python</li>
              <li>PySpark / Delta Lake</li>
              <li>Bronze / Silver / Gold</li>
              <li>Fintraffic / Digitraffic API</li>
              <li>FMI Open Data</li>
              <li>Analytics engineering</li>
              <li>Incremental Lakehouse</li>
              <li>Power BI / DAX</li>
            </ul>
            <nav className="project-resources" aria-label="Rail project resources">
              <a href="https://github.com/Sintagmatarches/applied-ai-lab/tree/main/rail" target="_blank" rel="noreferrer">Pipeline</a>
              <a href="https://github.com/Sintagmatarches/applied-ai-lab/tree/main/docs/rail" target="_blank" rel="noreferrer">Technical documentation</a>
              <a href="https://www.digitraffic.fi/en/railway-traffic/" target="_blank" rel="noreferrer">Digitraffic source</a>
              <a href="https://stat.fi/en/services/statistical-data-services/geographic-data/statistical-areas/municipality-based-statistical-units" target="_blank" rel="noreferrer">Regional boundaries</a>
              <a href="https://en.ilmatieteenlaitos.fi/open-data" target="_blank" rel="noreferrer">FMI source</a>
            </nav>
          </div>
          <dl className="rail-hero-facts">
            <div>
              <dt>Coverage</dt>
              <dd>{summary.meta.coverage_start}<br />→ {summary.meta.coverage_end}</dd>
            </div>
            <div>
              <dt>Passenger train journeys</dt>
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

        <RegionalRailMonitor />

        <aside className="rail-definition-note">
          <strong>Default definition</strong>
          <span>
            “On time” means the final commercial arrival was no more than five whole minutes late. Cancelled trains and missing actual times are reported separately and never treated as on-time arrivals.
          </span>
        </aside>

        <section className="rail-key-findings" aria-labelledby="key-findings-title">
          <div className="rail-key-findings-heading">
            <p className="eyebrow">Committed analytical snapshot</p>
            <h2 id="key-findings-title">Key findings</h2>
          </div>
          <ol>
            <li>
              <strong>{rate(summary.overall.on_time["5"].rate)}</strong>
              <span>of completed passenger-train journeys arrived within five minutes across the current twelve-month network snapshot.</span>
            </li>
            <li>
              <strong>{rate(june2026?.on_time["5"].rate)}</strong>
              <span>within five minutes in June 2026, materially below the full-period network rate.</span>
            </li>
            <li>
              <strong>{rate(lahtiToHelsinki?.on_time["5"].rate)} vs {rate(helsinkiToLahti?.on_time["5"].rate)}</strong>
              <span>for direct Lahti → Helsinki and Helsinki → Lahti services respectively.</span>
            </li>
            <li>
              <strong>{rate(helsinkiRovaniemi?.on_time["5"].rate)}</strong>
              <span>for Helsinki–Rovaniemi, the lowest five-minute rate among routes with at least 1,000 completed train journeys.</span>
            </li>
          </ol>
          <p>These are descriptive comparisons from the committed snapshot; they do not establish causes for delay.</p>
        </section>

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
              <p>Immutable Bronze payloads use SHA-256 identity. Delta watermarks skip unchanged dates and replace only revised or backfilled partitions.</p>
            </article>
            <article>
              <span>02</span>
              <h3>Quality gates</h3>
              <p>Executable contracts block duplicate keys, empty/anomalous partitions, missing critical fields and impossible values before Gold publication.</p>
            </article>
            <article>
              <span>03</span>
              <h3>Analytical model</h3>
              <p>PySpark builds Delta journey facts plus network, route, station and maakunta marts with the monitor&apos;s existing KPI thresholds.</p>
            </article>
            <article>
              <span>04</span>
              <h3>Honest delivery</h3>
              <p>Local and CI Delta runs are evidenced. Fabric, Databricks and Power BI are clearly separated credentialed deployment targets, not simulated claims.</p>
            </article>
          </div>
          <div className="rail-method-links">
            <Link href="/olist-delivery-delay-predictor">Compare with the Olist ML project</Link>
            <a href="https://github.com/Sintagmatarches/applied-ai-lab/blob/main/docs/rail/methodology.md" target="_blank" rel="noreferrer">Read definitions and limitations</a>
            <a href="https://github.com/Sintagmatarches/applied-ai-lab/blob/main/docs/rail/data-platform.md" target="_blank" rel="noreferrer">Review the Lakehouse implementation</a>
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
          <p>
            Regional boundaries: <a href="https://stat.fi/en/services/statistical-data-services/geographic-data/statistical-areas/municipality-based-statistical-units" target="_blank" rel="noreferrer">Statistics Finland municipality-based statistical units</a>, licensed under CC BY 4.0. Station coordinates are spatially joined to official maakunta polygons.
          </p>
        </footer>
      </div>
    </LabShell>
  );
}
