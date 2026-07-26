"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

export type ProjectId =
  | "home"
  | "olist"
  | "housing"
  | "credit"
  | "documents"
  | "vision";

type LabShellProps = {
  activeProject: ProjectId;
};

const projects = [
  {
    id: "olist" as const,
    href: "/olist-delivery-delay-predictor",
    title: "Olist Delivery Delay",
    status: "In development",
    icon: "OD",
  },
  {
    id: "housing" as const,
    href: "/housing-value-forecast",
    title: "Housing Value Forecast",
    status: "Planned",
    icon: "HV",
  },
  {
    id: "credit" as const,
    href: "/credit-risk-assessment",
    title: "Credit Risk Assessment",
    status: "Planned",
    icon: "CR",
  },
  {
    id: "documents" as const,
    href: "/document-processing",
    title: "Document Processing",
    status: "Planned",
    icon: "DP",
  },
  {
    id: "vision" as const,
    href: "/image-recognition",
    title: "Image Recognition",
    status: "Planned",
    icon: "IR",
  },
];

const plannedCopy: Record<
  Exclude<ProjectId, "home" | "olist">,
  { eyebrow: string; title: string; description: string; outcome: string }
> = {
  housing: {
    eyebrow: "Future project · Planned",
    title: "Housing Value Forecast",
    description:
      "A future tool for estimating a property value from clearly documented location and property features.",
    outcome: "An estimate with an honest uncertainty range and model limitations.",
  },
  credit: {
    eyebrow: "Future project · Planned",
    title: "Credit Risk Assessment",
    description:
      "A future decision-support project focused on transparent risk signals, validation and responsible use.",
    outcome: "A calibrated risk assessment with explainable contributing factors.",
  },
  documents: {
    eyebrow: "Future project · Planned",
    title: "Document Processing",
    description:
      "A future workspace for extracting structured fields from business documents and checking the result.",
    outcome: "Reviewable structured data, never an invisible or irreversible automation.",
  },
  vision: {
    eyebrow: "Future project · Planned",
    title: "Image Recognition",
    description:
      "A future computer-vision tool built around a defined dataset, evaluation protocol and practical task.",
    outcome: "A tested classification or detection result with visible confidence limits.",
  },
};

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span>AI</span>
    </span>
  );
}

function Navigation({
  activeProject,
  onNavigate,
}: LabShellProps & { onNavigate?: () => void }) {
  return (
    <>
      <Link
        href="/"
        className={`nav-link ${activeProject === "home" ? "is-active" : ""}`}
        onClick={onNavigate}
      >
        <span className="nav-icon">⌂</span>
        <span>
          <strong>Lab overview</strong>
          <small>Purpose & roadmap</small>
        </span>
      </Link>
      <div className="nav-label">Projects</div>
      {projects.map((project) => (
        <Link
          href={project.href}
          key={project.id}
          className={`nav-link ${
            activeProject === project.id ? "is-active" : ""
          }`}
          onClick={onNavigate}
        >
          <span className="nav-icon nav-initials">{project.icon}</span>
          <span>
            <strong>{project.title}</strong>
            <small
              className={project.status === "Planned" ? "is-planned" : ""}
            >
              {project.status}
            </small>
          </span>
        </Link>
      ))}
    </>
  );
}

function HomeContent() {
  return (
    <>
      <section className="hero">
        <div>
          <div className="eyebrow">Applied machine learning · Built in public</div>
          <h1>Useful AI starts with an honest baseline.</h1>
          <p className="hero-copy">
            Applied AI Lab is a home for working machine-learning tools. Each
            project moves from analysis to a validated model and only then to a
            live prediction interface.
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" href="/olist-delivery-delay-predictor">
              View the first project
            </Link>
            <a className="button button-ghost" href="#principles">
              How the lab works
            </a>
          </div>
        </div>
        <div className="lab-console" aria-label="Applied AI Lab project status">
          <div className="console-top">
            <span>LAB STATUS</span>
            <span className="console-live">FOUNDATION ONLINE</span>
          </div>
          <div className="console-grid" aria-hidden="true">
            {Array.from({ length: 24 }, (_, index) => (
              <i key={index} className={index < 7 ? "is-lit" : ""} />
            ))}
          </div>
          <div className="console-row">
            <span>01</span>
            <strong>Completed analytics</strong>
            <b>Ready</b>
          </div>
          <div className="console-row">
            <span>02</span>
            <strong>Delivery model</strong>
            <b className="status-building">Building</b>
          </div>
          <div className="console-row">
            <span>03</span>
            <strong>Live prediction API</strong>
            <b className="status-queued">Not connected</b>
          </div>
        </div>
      </section>

      <section className="section" id="principles">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Lab principles</div>
            <h2>No demos pretending to be models.</h2>
          </div>
          <p>
            Every active tool will expose what it knows, what it does not know,
            and which version produced the result.
          </p>
        </div>
        <div className="principle-grid">
          <article className="principle-card">
            <span>01</span>
            <h3>Analysis first</h3>
            <p>Understand the data, leakage risks and useful target before training.</p>
          </article>
          <article className="principle-card">
            <span>02</span>
            <h3>Measured before live</h3>
            <p>Evaluate on unseen data and publish the metrics that matter.</p>
          </article>
          <article className="principle-card">
            <span>03</span>
            <h3>Real endpoint only</h3>
            <p>The prediction form unlocks only when a tested model API exists.</p>
          </article>
        </div>
      </section>

      <section className="section">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Project shelf</div>
            <h2>One lab, independent tools.</h2>
          </div>
          <p>
            Each project has a permanent direct link and its own interface while
            sharing the same navigation and visual system.
          </p>
        </div>
        <div className="project-shelf">
          {projects.map((project, index) => (
            <Link href={project.href} className="shelf-row" key={project.id}>
              <span className="shelf-number">0{index + 1}</span>
              <span className="shelf-title">{project.title}</span>
              <span
                className={`status-pill ${
                  project.status === "Planned" ? "status-planned" : ""
                }`}
              >
                {project.status}
              </span>
              <span className="shelf-arrow" aria-hidden="true">→</span>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}

function OlistContent() {
  return (
    <>
      <section className="project-hero">
        <div className="project-hero-copy">
          <div className="eyebrow">Project 01 · Model in development</div>
          <h1>Olist Delivery<br />Delay Predictor</h1>
          <p>
            A planned prediction tool for estimating whether a newly placed
            order will arrive at least one day after its promised delivery date.
          </p>
          <div className="status-line">
            <span className="signal-dot" />
            No live model is connected. No prediction is generated.
          </div>
        </div>
        <div className="project-spec">
          <div className="spec-row">
            <span>Current stage</span>
            <strong>Model development</strong>
          </div>
          <div className="spec-row">
            <span>Target</span>
            <strong>Delay ≥ 1 day</strong>
          </div>
          <div className="spec-row">
            <span>Input</span>
            <strong>New order details</strong>
          </div>
          <div className="spec-row">
            <span>Output</span>
            <strong>Calibrated probability</strong>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section-heading">
          <div>
            <div className="eyebrow">What exists today</div>
            <h2>Analysis complete. Prediction next.</h2>
          </div>
          <p>
            The finished Olist work explains historical delivery delays and
            their relationship with customer reviews. It does not predict new
            orders yet.
          </p>
        </div>
        <div className="timeline">
          <article className="timeline-step is-complete">
            <div className="step-marker">✓</div>
            <div>
              <span>Completed</span>
              <h3>Data processing & SQL</h3>
              <p>Historical order, delivery and review data prepared for analysis.</p>
            </div>
          </article>
          <article className="timeline-step is-complete">
            <div className="step-marker">✓</div>
            <div>
              <span>Completed</span>
              <h3>Power BI & final report</h3>
              <p>Analytical findings and delivery-delay patterns documented.</p>
            </div>
          </article>
          <article className="timeline-step is-current">
            <div className="step-marker">03</div>
            <div>
              <span>In development</span>
              <h3>Training & validation</h3>
              <p>Feature design, leakage checks, model comparison and calibration.</p>
            </div>
          </article>
          <article className="timeline-step">
            <div className="step-marker">04</div>
            <div>
              <span>Not started</span>
              <h3>Prediction API</h3>
              <p>A versioned endpoint will connect only after model acceptance.</p>
            </div>
          </article>
        </div>
        <div className="resource-note">
          <span className="resource-icon">↗</span>
          <div>
            <strong>Report and analytics links</strong>
            <p>
              Link slots are ready. They will be activated when the final public
              URLs are provided, without using placeholder destinations.
            </p>
          </div>
          <button type="button" disabled>Links pending</button>
        </div>
      </section>

      <section className="section">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Future prediction interface</div>
            <h2>Ready for the real model, not a mock result.</h2>
          </div>
          <p>
            This contract separates presentation from inference. A future API
            can be connected without rebuilding the project navigation.
          </p>
        </div>
        <div className="predictor-grid">
          <form className="predictor-form" aria-label="Future prediction form">
            <fieldset disabled>
              <div className="field">
                <label htmlFor="seller-state">Seller state</label>
                <select id="seller-state" defaultValue="">
                  <option value="">Available after feature validation</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="customer-state">Customer state</label>
                <select id="customer-state" defaultValue="">
                  <option value="">Available after feature validation</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="order-items">Number of order items</label>
                <input id="order-items" placeholder="Feature not connected" />
              </div>
              <div className="field">
                <label htmlFor="freight">Freight value</label>
                <input id="freight" placeholder="Feature not connected" />
              </div>
              <button type="button" className="button button-primary predict-button">
                Calculate probability
              </button>
            </fieldset>
          </form>
          <div className="prediction-result">
            <div className="result-lock" aria-hidden="true">×</div>
            <div className="eyebrow">Result unavailable</div>
            <h3>Waiting for a validated model</h3>
            <p>
              This panel will show a probability, a risk band, the model version
              and a concise explanation after a real inference response.
            </p>
            <div className="result-contract">
              <span><i /> probability</span>
              <span><i /> risk band</span>
              <span><i /> model version</span>
              <span><i /> main factors</span>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

function PlannedContent({
  activeProject,
}: {
  activeProject: Exclude<ProjectId, "home" | "olist">;
}) {
  const copy = plannedCopy[activeProject];
  return (
    <section className="planned-project">
      <div className="planned-code" aria-hidden="true">
        {projects.find((project) => project.id === activeProject)?.icon}
      </div>
      <div className="eyebrow">{copy.eyebrow}</div>
      <h1>{copy.title}</h1>
      <p>{copy.description}</p>
      <div className="planned-outcome">
        <span>Intended outcome</span>
        <strong>{copy.outcome}</strong>
      </div>
      <div className="planned-boundary">
        No dataset, trained model or performance result is being claimed on this
        page. The section is reserved so the future project already has a stable
        direct link.
      </div>
      <Link className="button button-ghost" href="/">
        Back to lab overview
      </Link>
    </section>
  );
}

export function LabShell({ activeProject }: LabShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    setDrawerOpen(false);
  }, [activeProject]);

  return (
    <div className="lab-app">
      <header className="topbar">
        <div className="brand">
          <button
            className="menu-button"
            type="button"
            onClick={() => setDrawerOpen(true)}
            aria-expanded={drawerOpen}
            aria-controls="mobile-drawer"
            aria-label="Open project menu"
          >
            ☰
          </button>
          <Link href="/" className="brand-link">
            <BrandMark />
            <span>
              <strong>Applied AI Lab</strong>
              <small>Practical models, honestly presented</small>
            </span>
          </Link>
        </div>
        <div className="topbar-status">
          <span className="signal-dot" />
          Lab foundation online
        </div>
      </header>

      <aside className="project-rail" aria-label="Project navigation">
        <Navigation activeProject={activeProject} />
        <div className="rail-footer">
          <span>Build policy</span>
          <strong>Evidence before interface</strong>
        </div>
      </aside>

      <div
        className={`drawer-backdrop ${drawerOpen ? "is-open" : ""}`}
        onClick={() => setDrawerOpen(false)}
      />
      <aside
        className={`mobile-drawer ${drawerOpen ? "is-open" : ""}`}
        id="mobile-drawer"
        aria-hidden={!drawerOpen}
      >
        <div className="drawer-header">
          <div>
            <span>Project navigator</span>
            <strong>Applied AI Lab</strong>
          </div>
          <button
            type="button"
            onClick={() => setDrawerOpen(false)}
            aria-label="Close project menu"
          >
            ×
          </button>
        </div>
        <Navigation
          activeProject={activeProject}
          onNavigate={() => setDrawerOpen(false)}
        />
      </aside>

      <main className="main-content">
        {activeProject === "home" && <HomeContent />}
        {activeProject === "olist" && <OlistContent />}
        {activeProject !== "home" && activeProject !== "olist" && (
          <PlannedContent activeProject={activeProject} />
        )}
        <footer>
          <span>Applied AI Lab</span>
          <p>Models become interactive only after validation and deployment.</p>
        </footer>
      </main>

      <nav className="mobile-nav" aria-label="Quick project navigation">
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          aria-label="Open all projects"
        >
          <span>☰</span>
          Menu
        </button>
        <Link href="/" className={activeProject === "home" ? "is-active" : ""}>
          <span>⌂</span>
          Overview
        </Link>
        <Link
          href="/olist-delivery-delay-predictor"
          className={activeProject === "olist" ? "is-active" : ""}
        >
          <span>OD</span>
          Olist
        </Link>
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          className={
            activeProject !== "home" && activeProject !== "olist"
              ? "is-active"
              : ""
          }
        >
          <span>•••</span>
          Planned
        </button>
      </nav>
    </div>
  );
}
