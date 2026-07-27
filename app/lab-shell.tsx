"use client";

import Link from "next/link";

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

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span>AI</span>
    </span>
  );
}

function ProjectTabs({ activeProject }: LabShellProps) {
  return (
    <nav className="project-tabs" aria-label="Project navigation">
      <div className="project-tabs-inner">
        <Link
          href="/"
          className={activeProject === "home" ? "is-active" : ""}
          aria-current={activeProject === "home" ? "page" : undefined}
        >
          Home Page
        </Link>
        <Link
          href="/olist-delivery-delay-predictor"
          className={activeProject === "olist" ? "is-active" : ""}
          aria-current={activeProject === "olist" ? "page" : undefined}
        >
          Delivery Delay Predictor
        </Link>
      </div>
    </nav>
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

function HomeContent() {
  return (
    <>
      <section className="home-heading">
        <span className="eyebrow">PRACTICAL MACHINE-LEARNING TOOLS</span>
        <h1>Applied AI Lab</h1>
        <p>
          Working projects receive their own page and appear as a tab above.
        </p>
      </section>

      <section className="content-section">
        <SectionTitle>Planned projects</SectionTitle>
        <ul className="planned-project-list">
          {projects.slice(1).map((project) => (
            <li key={project.id}>
              <Link href={project.href}>{project.title}</Link>
              <span>{project.status}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

function OlistContent() {
  return (
    <>
      <section className="hero-card project-hero">
        <span className="project-hero-mark" aria-hidden="true">O</span>
        <div className="hero-copy">
          <span className="eyebrow">OLIST PROJECT</span>
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
            <strong>Data processing and SQL</strong>
            <small>Completed</small>
          </article>
          <article>
            <strong>Power BI and final report</strong>
            <small>Completed</small>
          </article>
          <article className="is-current">
            <strong>Model training and validation</strong>
            <small>In development</small>
          </article>
          <article>
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
  return (
    <div className="lab-app">
      <header className="topbar">
        <div className="brand">
          <Link href="/" className="brand-link">
            <BrandMark />
            <span className="brand-text">
              <strong>Applied AI Lab</strong>
              <small>Practical machine-learning tools</small>
            </span>
          </Link>
        </div>
      </header>

      <ProjectTabs activeProject={activeProject} />

      <main className="main-content">
        {activeProject === "home" && <HomeContent />}
        {activeProject === "olist" && <OlistContent />}
        {activeProject !== "home" && activeProject !== "olist" && (
          <PlannedContent activeProject={activeProject} />
        )}
      </main>

    </div>
  );
}
