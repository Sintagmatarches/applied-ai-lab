"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

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
    description: "Delivery delay risk for a new order.",
    status: "Model in development",
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
    result: "Estimated value with a validated uncertainty range.",
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

function BrandMark({ large = false }: { large?: boolean }) {
  return (
    <span className={`brand-mark ${large ? "is-large" : ""}`} aria-hidden="true">
      <span>AI</span>
      {large && <small>LAB</small>}
    </span>
  );
}

function NavGlyph({ id }: { id: ProjectId }) {
  if (id !== "home") {
    const project = projects.find((item) => item.id === id);
    return <span className="nav-letter">{project?.symbol}</span>;
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 11.3 12 4l8 7.3V20h-5v-5H9v5H4z" />
    </svg>
  );
}

function Navigation({
  activeProject,
  onNavigate,
  expanded = false,
}: LabShellProps & { onNavigate?: () => void; expanded?: boolean }) {
  const items = [
    { id: "home" as const, href: "/", title: "Overview" },
    ...projects,
  ];

  return (
    <>
      {items.map((item) => (
        <Link
          href={item.href}
          key={item.id}
          className={`rail-link ${activeProject === item.id ? "is-active" : ""}`}
          aria-current={activeProject === item.id ? "page" : undefined}
          aria-label={item.title}
          title={expanded ? undefined : item.title}
          onClick={onNavigate}
        >
          <span className="rail-icon">
            <NavGlyph id={item.id} />
          </span>
          {expanded && <span className="rail-label">{item.title}</span>}
        </Link>
      ))}
    </>
  );
}

function ProjectSearch() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const matches = useMemo(() => {
    const value = query.trim().toLowerCase();
    if (!value) return projects;
    return projects.filter((project) =>
      `${project.title} ${project.description}`.toLowerCase().includes(value),
    );
  }, [query]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (matches[0]) window.location.assign(matches[0].href);
  }

  return (
    <form className="project-search" onSubmit={submit}>
      <div className="search-field-wrap">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="11" cy="11" r="6.5" />
          <path d="m16 16 4 4" />
        </svg>
        <input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          placeholder="Find a project…"
          aria-label="Find a project"
        />
        {open && (
          <div className="search-results">
            {matches.length > 0 ? (
              matches.map((project) => (
                <Link href={project.href} key={project.id}>
                  <span>{project.symbol}</span>
                  <strong>{project.title}</strong>
                  <small>{project.status}</small>
                </Link>
              ))
            ) : (
              <p>No matching projects</p>
            )}
          </div>
        )}
      </div>
      <button type="submit" disabled={!matches.length}>
        Search
      </button>
    </form>
  );
}

function ContextLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link className="context-link" href={href}>
      <span>{children}</span>
      <svg viewBox="0 0 20 20" aria-hidden="true">
        <path d="m5 7 5 5 5-5" />
      </svg>
    </Link>
  );
}

function SectionTitle({
  children,
  note,
}: {
  children: React.ReactNode;
  note?: string;
}) {
  return (
    <div className="section-title">
      <h2>{children}</h2>
      {note && <p>{note}</p>}
    </div>
  );
}

function ProjectGrid() {
  return (
    <div className="project-grid">
      {projects.map((project) => (
        <Link href={project.href} className="project-tile" key={project.id}>
          <strong>{project.title}</strong>
          <span className="tile-symbol" aria-hidden="true">
            {project.symbol}
          </span>
          <small>{project.status}</small>
          <span className="tile-arrow" aria-hidden="true">→</span>
        </Link>
      ))}
    </div>
  );
}

function HomeContent() {
  return (
    <>
      <ContextLink href="/olist-delivery-delay-predictor">
        Applied AI Lab
      </ContextLink>

      <section className="hero-card home-hero">
        <BrandMark large />
        <div className="hero-copy">
          <span className="eyebrow">PRACTICAL MACHINE-LEARNING TOOLS</span>
          <h1>Applied AI Lab</h1>
          <p>
            A single workspace for useful AI projects. Tools appear here only
            after their models are built, tested and connected.
          </p>
        </div>
        <div className="hero-summary">
          <strong>1</strong>
          <span>PROJECT IN DEVELOPMENT</span>
          <Link href="/olist-delivery-delay-predictor" className="hero-action">
            <span className="action-icon">O</span>
            <span>
              <strong>Open Olist predictor</strong>
              <small>View the current project state</small>
            </span>
            <span className="action-arrow">→</span>
          </Link>
        </div>
      </section>

      <section className="content-section">
        <SectionTitle>Projects</SectionTitle>
        <ProjectGrid />
      </section>
    </>
  );
}

function OlistContent() {
  return (
    <>
      <ContextLink href="/">Olist Delivery Delay Predictor</ContextLink>

      <section className="hero-card project-hero">
        <span className="project-hero-mark" aria-hidden="true">O</span>
        <div className="hero-copy">
          <span className="eyebrow">PROJECT 01 · OLIST</span>
          <h1>Delivery Delay Predictor</h1>
          <p>
            The future model will estimate whether a new order will arrive at
            least one day late.
          </p>
        </div>
        <div className="hero-summary project-summary">
          <span>CURRENT STATE</span>
          <h2>Model in development</h2>
          <p>No live model is connected. This page does not generate predictions.</p>
        </div>
      </section>

      <section className="content-section">
        <SectionTitle>Project status</SectionTitle>
        <div className="status-grid">
          <article>
            <span>01</span>
            <strong>Data processing and SQL</strong>
            <small>Completed</small>
          </article>
          <article>
            <span>02</span>
            <strong>Power BI and final report</strong>
            <small>Completed</small>
          </article>
          <article className="is-current">
            <span>03</span>
            <strong>Model training and validation</strong>
            <small>In development</small>
          </article>
          <article>
            <span>04</span>
            <strong>Prediction API</strong>
            <small>Not connected</small>
          </article>
        </div>
      </section>

      <section className="content-section">
        <SectionTitle
          note="This area will be activated only after a validated model API is connected."
        >
          Future prediction
        </SectionTitle>

        <div className="workspace-card">
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
              <button type="button">Calculate probability</button>
            </fieldset>
          </form>
          <div className="empty-result">
            <span aria-hidden="true">—</span>
            <strong>Result unavailable</strong>
            <p>Waiting for a validated model and a real inference response.</p>
          </div>
        </div>
      </section>

      <section className="content-section analytics-section">
        <SectionTitle note="The analysis is complete; public URLs have not been supplied yet.">
          Completed analytics
        </SectionTitle>
        <div className="resource-grid">
          <button type="button" disabled>
            <span>Final report</span>
            <small>Link pending</small>
          </button>
          <button type="button" disabled>
            <span>Analytics project</span>
            <small>Link pending</small>
          </button>
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
  const symbol = projects.find((project) => project.id === activeProject)?.symbol;

  return (
    <>
      <ContextLink href="/">{copy.title}</ContextLink>
      <section className="hero-card project-hero planned-hero">
        <span className="project-hero-mark" aria-hidden="true">{symbol}</span>
        <div className="hero-copy">
          <span className="eyebrow">PLANNED PROJECT</span>
          <h1>{copy.title}</h1>
          <p>{copy.description}</p>
        </div>
        <div className="hero-summary project-summary">
          <span>INTENDED RESULT</span>
          <h2>{copy.result}</h2>
          <p>No dataset, trained model or performance result is claimed here.</p>
        </div>
      </section>
      <section className="content-section">
        <SectionTitle>Project availability</SectionTitle>
        <div className="planned-note">
          <strong>Coming later</strong>
          <p>This section is reserved for a future working tool.</p>
          <Link href="/">Return to all projects →</Link>
        </div>
      </section>
    </>
  );
}

export function LabShell({ activeProject }: LabShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);

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
            <span />
            <span />
            <span />
          </button>
          <Link href="/" className="brand-link">
            <BrandMark />
            <span className="brand-text">
              <strong>Applied AI Lab</strong>
              <small>Practical machine-learning tools</small>
            </span>
          </Link>
        </div>

        <ProjectSearch />

        <div className="top-actions">
          <Link href="/">Projects</Link>
          <Link href="/olist-delivery-delay-predictor">Olist</Link>
        </div>
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
          expanded
        />
      </aside>

      <main className="main-content">
        {activeProject === "home" && <HomeContent />}
        {activeProject === "olist" && <OlistContent />}
        {activeProject !== "home" && activeProject !== "olist" && (
          <PlannedContent activeProject={activeProject} />
        )}
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
