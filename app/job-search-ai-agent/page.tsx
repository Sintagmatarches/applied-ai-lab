import type { Metadata } from "next";
import { LabShell } from "../lab-shell";
import { JobSearchAgent } from "./job-search-agent";

export const metadata: Metadata = {
  title: "Job Search AI Agent",
  description:
    "Search public job feeds and inspect source-grounded, deterministic match explanations without an account or paid API.",
  openGraph: {
    title: "Job Search AI Agent · Applied AI Lab",
    description:
      "Public job discovery and explainable matching without a personal account or paid API.",
    type: "website",
    images: [],
  },
  twitter: {
    card: "summary",
    title: "Job Search AI Agent · Applied AI Lab",
    description:
      "Public job discovery and explainable matching without a personal account or paid API.",
    images: [],
  },
};

export default function JobSearchAiAgentPage() {
  return (
    <LabShell activeProject="jobs">
      <div className="jobs-page">
        <header className="jobs-hero">
          <div>
            <p className="eyebrow">Applied AI Lab · Project 03</p>
            <h1>Job Search AI Agent</h1>
            <p className="intro-copy">
              Discover public vacancies, normalize them into one structure and
              see exactly why each role matches your profile—without connecting
              LinkedIn, sharing account cookies or paying for an AI API.
            </p>
          </div>
          <aside className="jobs-boundary" aria-label="Access boundary">
            <strong>Public-data boundary</strong>
            <ul>
              <li>No personal job-board account</li>
              <li>No CAPTCHA, paywall or login bypass</li>
              <li>No paid LLM or search API</li>
            </ul>
          </aside>
        </header>

        <JobSearchAgent />

        <section className="jobs-method" aria-labelledby="jobs-method-title">
          <div>
            <p className="eyebrow">System design</p>
            <h2 id="jobs-method-title">Agentic workflow, inspectable decisions</h2>
          </div>
          <div className="jobs-method-grid">
            <article>
              <span>01</span>
              <h3>Public acquisition</h3>
              <p>
                Provider adapters call documented, keyless feeds. Each source
                has a timeout and independent failure boundary, so one outage
                does not invent or erase another source&apos;s results.
              </p>
            </article>
            <article>
              <span>02</span>
              <h3>Normalize + deduplicate</h3>
              <p>
                HTML becomes inert text, URLs are validated, skills and
                seniority use deterministic rules, and matching company, title
                and location fingerprints collapse duplicates.
              </p>
            </article>
            <article>
              <span>03</span>
              <h3>Explainable matching</h3>
              <p>
                Role overlap, skill coverage and work-location preferences have
                declared weights. The score is derived from those features,
                never guessed by a model.
              </p>
            </article>
            <article>
              <span>04</span>
              <h3>Grounded agent tools</h3>
              <p>
                The evidence agent can rank, compare and summarize requirements
                only from the current result set, returning direct vacancy
                citations with every answer.
              </p>
            </article>
          </div>
        </section>

        <aside className="jobs-limitations">
          <h2>Honest operating limits</h2>
          <p>
            This hosted demonstration searches Arbeitnow and Jobicy because
            they publish documented, keyless feeds. It does not scrape LinkedIn
            or other login-gated pages. Saved jobs and the demo profile stay in
            this browser. Matching is deterministic; optional local-language
            reasoning is designed for an Ollama adapter and is not represented
            as running in this public Cloudflare deployment.
          </p>
          <nav aria-label="Job data sources">
            <a href="https://www.arbeitnow.com/blog/job-board-api" target="_blank" rel="noreferrer">
              Arbeitnow API documentation
            </a>
            <a href="https://jobicy.com/jobs-rss-feed" target="_blank" rel="noreferrer">
              Jobicy API documentation
            </a>
            <a href="https://github.com/Sintagmatarches/applied-ai-lab" target="_blank" rel="noreferrer">
              Source code
            </a>
          </nav>
        </aside>
      </div>
    </LabShell>
  );
}
