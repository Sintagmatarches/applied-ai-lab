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
    title: "Olist Delivery Delay Predictor",
    description: "Delivery delay probability for a new order.",
    status: "In development",
    symbol: "O",
  },
  {
    id: "housing" as const,
    href: "/housing-value-forecast",
    title: "Housing Value Forecast",
    description: "Property value estimation.",
    status: "Planned",
    symbol: "H",
  },
  {
    id: "credit" as const,
    href: "/credit-risk-assessment",
    title: "Credit Risk Assessment",
    description: "Transparent credit risk support.",
    status: "Planned",
    symbol: "C",
  },
  {
    id: "documents" as const,
    href: "/document-processing",
    title: "Document Processing",
    description: "Structured data from documents.",
    status: "Planned",
    symbol: "D",
  },
  {
    id: "vision" as const,
    href: "/image-recognition",
    title: "Image Recognition",
    description: "A future computer-vision tool.",
    status: "Planned",
    symbol: "I",
  },
];

const plannedCopy: Record<
  Exclude<ProjectId, "home" | "olist">,
  { title: string; description: string; result: string }
> = {
  housing: {
    title: "Housing Value Forecast",
    description:
      "A future tool for estimating property value from documented location and property features.",
    result: "Estimated value with an uncertainty range.",
  },
  credit: {
    title: "Credit Risk Assessment",
    description:
      "A future decision-support tool focused on transparent and validated risk signals.",
    result: "A calibrated risk assessment with explanatory factors.",
  },
  documents: {
    title: "Document Processing",
    description:
      "A future workspace for extracting and reviewing structured fields from business documents.",
    result: "Reviewable structured data.",
  },
  vision: {
    title: "Image Recognition",
    description:
      "A future computer-vision tool built for a defined dataset and practical task.",
    result: "A tested classification or detection result.",
  },
};

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      AI
    </span>
  );
}

function StatusBadge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "success" | "warning";
}) {
  return <span className={`status-badge status-${tone}`}>{children}</span>;
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
        aria-current={activeProject === "home" ? "page" : undefined}
        onClick={onNavigate}
      >
        <span className="nav-icon" aria-hidden="true">⌂</span>
        <span className="nav-text">Overview</span>
      </Link>

      <div className="nav-section-label">Projects</div>

      {projects.map((project) => (
        <Link
          href={project.href}
          key={project.id}
          className={`nav-link ${
            activeProject === project.id ? "is-active" : ""
          }`}
          aria-current={activeProject === project.id ? "page" : undefined}
          onClick={onNavigate}
        >
          <span className="nav-icon nav-letter" aria-hidden="true">
            {project.symbol}
          </span>
          <span className="nav-text">{project.title}</span>
        </Link>
      ))}
    </>
  );
}

function SectionHeading({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="section-heading">
      <div>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
    </div>
  );
}

function HomeContent() {
  return (
    <div className="page-stack">
      <section className="card intro-card">
        <div className="intro-main">
          <span className="page-label">Applied AI Lab</span>
          <h1>Practical machine-learning tools</h1>
          <p>
            One place for working ML projects. A tool becomes active only after
            its model is tested and connected.
          </p>
          <Link className="btn" href="/olist-delivery-delay-predictor">
            Open Olist project
          </Link>
        </div>

        <div className="summary-panel" aria-label="Current lab status">
          <div className="summary-row">
            <span>Completed analytics</span>
            <StatusBadge tone="success">Ready</StatusBadge>
          </div>
          <div className="summary-row">
            <span>Prediction models</span>
            <StatusBadge tone="warning">In development</StatusBadge>
          </div>
          <div className="summary-row">
            <span>Live model APIs</span>
            <StatusBadge>Not connected</StatusBadge>
          </div>
        </div>
      </section>

      <section className="card">
        <SectionHeading
          title="Projects"
          description="Choose a project. Every section has its own direct link."
        />

        <div className="project-list">
          {projects.map((project) => (
            <Link className="project-row" href={project.href} key={project.id}>
              <span className="project-symbol" aria-hidden="true">
                {project.symbol}
              </span>
              <span className="project-copy">
                <strong>{project.title}</strong>
                <small>{project.description}</small>
              </span>
              <StatusBadge
                tone={project.status === "In development" ? "warning" : "neutral"}
              >
                {project.status}
              </StatusBadge>
              <span className="project-arrow" aria-hidden="true">›</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="card">
        <SectionHeading title="Release rule" />
        <div className="rule-list">
          <div>
            <span>1</span>
            <p>Analyze the data.</p>
          </div>
          <div>
            <span>2</span>
            <p>Train and validate the model.</p>
          </div>
          <div>
            <span>3</span>
            <p>Connect the real API.</p>
          </div>
        </div>
      </section>
    </div>
  );
}

function OlistContent() {
  return (
    <div className="page-stack">
      <section className="card project-header-card">
        <div className="project-title-row">
          <div>
            <span className="page-label">Olist project</span>
            <h1>Delivery Delay Predictor</h1>
          </div>
          <StatusBadge tone="warning">Model in development</StatusBadge>
        </div>
        <p className="project-lead">
          The future model will estimate whether a new order will arrive at
          least one day late.
        </p>
        <div className="notice warning-notice">
          No live model is connected. This page does not generate a prediction.
        </div>
      </section>

      <section className="card">
        <SectionHeading title="Current status" />
        <div className="status-steps">
          <div className="status-step is-complete">
            <span className="step-icon">✓</span>
            <div>
              <strong>Data processing and SQL</strong>
              <small>Completed</small>
            </div>
          </div>
          <div className="status-step is-complete">
            <span className="step-icon">✓</span>
            <div>
              <strong>Power BI and final report</strong>
              <small>Completed</small>
            </div>
          </div>
          <div className="status-step is-current">
            <span className="step-icon">3</span>
            <div>
              <strong>Model training and validation</strong>
              <small>In development</small>
            </div>
          </div>
          <div className="status-step">
            <span className="step-icon">4</span>
            <div>
              <strong>Prediction API</strong>
              <small>Not connected</small>
            </div>
          </div>
        </div>
      </section>

      <section className="card">
        <SectionHeading title="What the model will return" />
        <div className="meta-grid">
          <div className="meta-item">
            <span>Target</span>
            <strong>Delay of at least 1 day</strong>
          </div>
          <div className="meta-item">
            <span>Input</span>
            <strong>New order details</strong>
          </div>
          <div className="meta-item">
            <span>Output</span>
            <strong>Validated probability</strong>
          </div>
          <div className="meta-item">
            <span>Result details</span>
            <strong>Risk band and model version</strong>
          </div>
        </div>
      </section>

      <section className="card">
        <SectionHeading
          title="Analytics"
          description="The analytical work is complete. Public links have not been supplied yet."
        />
        <div className="resource-actions">
          <button className="btn" type="button" disabled>
            Final report — link pending
          </button>
          <button className="btn" type="button" disabled>
            Analytics project — link pending
          </button>
        </div>
      </section>

      <section className="card">
        <SectionHeading
          title="Prediction form"
          description="The fields will be activated after the real model API is ready."
        />

        <div className="predictor-layout">
          <form className="predictor-form" aria-label="Future prediction form">
            <fieldset disabled>
              <div className="field">
                <label htmlFor="seller-state">Seller state</label>
                <select id="seller-state" defaultValue="">
                  <option value="">Not available yet</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="customer-state">Customer state</label>
                <select id="customer-state" defaultValue="">
                  <option value="">Not available yet</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="order-items">Order items</label>
                <input id="order-items" placeholder="Not available yet" />
              </div>
              <div className="field">
                <label htmlFor="freight">Freight value</label>
                <input id="freight" placeholder="Not available yet" />
              </div>
              <button className="btn form-submit" type="button">
                Calculate probability
              </button>
            </fieldset>
          </form>

          <div className="empty-result">
            <span className="empty-result-icon" aria-hidden="true">—</span>
            <strong>Result unavailable</strong>
            <p>Waiting for a validated model and a real inference response.</p>
          </div>
        </div>
      </section>
    </div>
  );
}

function PlannedContent({
  activeProject,
}: {
  activeProject: Exclude<ProjectId, "home" | "olist">;
}) {
  const copy = plannedCopy[activeProject];
  return (
    <div className="page-stack">
      <section className="card planned-card">
        <span className="planned-symbol" aria-hidden="true">
          {projects.find((project) => project.id === activeProject)?.symbol}
        </span>
        <StatusBadge>Planned</StatusBadge>
        <h1>{copy.title}</h1>
        <p>{copy.description}</p>
        <div className="meta-item planned-result">
          <span>Intended result</span>
          <strong>{copy.result}</strong>
        </div>
        <div className="notice">
          No dataset, trained model or performance result is claimed here.
        </div>
        <Link className="btn" href="/">
          Back to overview
        </Link>
      </section>
    </div>
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
            className="menu-trigger"
            type="button"
            onClick={() => setDrawerOpen(true)}
            aria-expanded={drawerOpen}
            aria-controls="project-drawer"
            aria-label="Open project menu"
          >
            ☰
          </button>
          <Link href="/" className="brand-link">
            <BrandMark />
            <span className="brand-text">
              <strong>Applied AI Lab</strong>
              <small>Practical machine-learning tools</small>
            </span>
          </Link>
        </div>
        <Link className="topbar-button" href="/olist-delivery-delay-predictor">
          Olist · In development
        </Link>
      </header>

      <nav className="project-rail" aria-label="Project navigation">
        <Navigation activeProject={activeProject} />
      </nav>

      <div
        className={`drawer-backdrop ${drawerOpen ? "is-open" : ""}`}
        onClick={() => setDrawerOpen(false)}
      />
      <aside
        className={`project-drawer ${drawerOpen ? "is-open" : ""}`}
        id="project-drawer"
        aria-hidden={!drawerOpen}
      >
        <div className="drawer-header">
          <strong>Projects</strong>
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
        <div className="app-shell">
          {activeProject === "home" && <HomeContent />}
          {activeProject === "olist" && <OlistContent />}
          {activeProject !== "home" && activeProject !== "olist" && (
            <PlannedContent activeProject={activeProject} />
          )}
        </div>
      </main>

      <nav className="mobile-nav" aria-label="Mobile navigation">
        <button type="button" onClick={() => setDrawerOpen(true)}>
          <span aria-hidden="true">☰</span>
          Menu
        </button>
        <Link href="/" className={activeProject === "home" ? "is-active" : ""}>
          <span aria-hidden="true">⌂</span>
          Overview
        </Link>
        <Link
          href="/olist-delivery-delay-predictor"
          className={activeProject === "olist" ? "is-active" : ""}
        >
          <span aria-hidden="true">O</span>
          Olist
        </Link>
      </nav>
    </div>
  );
}
