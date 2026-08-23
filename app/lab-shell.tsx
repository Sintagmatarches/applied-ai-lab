import Link from "next/link";
import type { ReactNode } from "react";
import { ActiveTabScroller } from "./active-tab-scroller";

export type ProjectId =
  | "home"
  | "olist"
  | "rail"
  | "tenders"
  | "housing"
  | "credit"
  | "documents"
  | "vision";

type LabShellProps = {
  activeProject: ProjectId;
  children?: ReactNode;
};

const projects = [
  {
    id: "olist" as const,
    href: "/olist-delivery-delay-predictor",
    title: "Olist Delivery Delay Predictor",
    tabTitle: "Delivery Delay Predictor",
    description:
      "A working model that estimates whether a new Olist order will arrive at least one full day late.",
  },
  {
    id: "rail" as const,
    href: "/finland-rail-reliability-monitor",
    title: "Finland Rail Monitoring System",
    tabTitle: "Rail Monitoring System",
    description:
      "Official Fintraffic data transformed into a reproducible view of passenger-train, route and station reliability.",
  },
  {
    id: "tenders" as const,
    href: "/eu-tender-intelligence-agent",
    title: "EU Tender Intelligence Agent",
    tabTitle: "Tender Intelligence",
    description:
      "Official TED notices transformed into evidence-backed supplier qualification, bid decisions and change intelligence.",
  },
  {
    id: "housing" as const,
    href: "/housing-value-forecast",
    title: "Housing Value Forecast",
    description:
      "A future tool for estimating property value from documented location and property features.",
  },
  {
    id: "credit" as const,
    href: "/credit-risk-assessment",
    title: "Credit Risk Assessment",
    description:
      "A future decision-support tool focused on transparent and validated risk signals.",
  },
  {
    id: "documents" as const,
    href: "/document-processing",
    title: "Document Processing",
    description:
      "A future workspace for extracting and reviewing structured fields from business documents.",
  },
  {
    id: "vision" as const,
    href: "/image-recognition",
    title: "Image Recognition",
    description:
      "A future computer-vision tool built for a defined dataset and practical task.",
  },
];

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      AI
    </span>
  );
}

function ProjectTabs({ activeProject }: LabShellProps) {
  const currentPlanned = projects.find(
    (project) =>
      project.id === activeProject &&
      project.id !== "olist" && project.id !== "rail" && project.id !== "tenders",
  );

  return (
    <nav className="project-tabs" aria-label="Project navigation">
      <ActiveTabScroller />
      <div className="project-tabs-inner">
        <Link
          href="/"
          className={activeProject === "home" ? "is-active" : ""}
          aria-current={activeProject === "home" ? "page" : undefined}
        >
          Home Page
        </Link>
        <Link
          href={projects[0].href}
          className={activeProject === "olist" ? "is-active" : ""}
          aria-current={activeProject === "olist" ? "page" : undefined}
        >
          {projects[0].tabTitle}
        </Link>
        <Link
          href={projects[1].href}
          className={activeProject === "rail" ? "is-active" : ""}
          aria-current={activeProject === "rail" ? "page" : undefined}
        >
          {projects[1].tabTitle}
        </Link>
        <Link
          href={projects[2].href}
          className={activeProject === "tenders" ? "is-active" : ""}
          aria-current={activeProject === "tenders" ? "page" : undefined}
        >
          {projects[2].tabTitle}
        </Link>
        {currentPlanned && (
          <Link
            href={currentPlanned.href}
            className="is-active"
            aria-current="page"
          >
            {currentPlanned.title}
          </Link>
        )}
      </div>
    </nav>
  );
}

function HomeContent() {
  return (
    <div className="home-page">
      <header className="home-intro">
        <p className="eyebrow">Applied analytics portfolio</p>
        <h1>Data products built to be inspected.</h1>
        <p>
          Reproducible pipelines, analytical models and deployed tools with
          evidence, definitions and limitations shown alongside the result.
        </p>
      </header>

      <section className="completed-projects" aria-label="Completed projects">
        <article className="featured-project">
          <div className="featured-project-copy">
            <p className="project-status">Completed project · 01</p>
            <h2>{projects[0].title}</h2>
            <p>{projects[0].description}</p>
            <ul className="featured-project-facts" aria-label="Olist project summary">
              <li>Python model training</li>
              <li>96,470 historical orders</li>
              <li>Live server-side inference</li>
            </ul>
          </div>
          <div className="featured-project-actions">
            <Link className="primary-link" href={projects[0].href}>
              Open predictor
            </Link>
          </div>
        </article>

        <article className="featured-project featured-project-rail">
          <div className="featured-project-copy">
            <p className="project-status">Completed project · 02</p>
            <h2>{projects[1].title}</h2>
            <p>{projects[1].description}</p>
            <ul className="featured-project-facts" aria-label="Rail project summary">
              <li>Official Finnish railway data</li>
              <li>12 complete operating months</li>
              <li>PySpark / Delta Lakehouse</li>
            </ul>
          </div>
          <div className="featured-project-actions">
            <Link className="primary-link" href={projects[1].href}>
              Open monitor
            </Link>
          </div>
        </article>

        <article className="featured-project featured-project-tenders">
          <div className="featured-project-copy">
            <p className="project-status">Completed project · 03</p>
            <h2>{projects[2].title}</h2>
            <p>{projects[2].description}</p>
            <ul className="featured-project-facts" aria-label="Tender intelligence project summary">
              <li>Official TED Search API v3</li>
              <li>Deterministic bid / no-bid</li>
              <li>Version diff and grounded local RAG</li>
            </ul>
          </div>
          <div className="featured-project-actions">
            <Link className="primary-link" href={projects[2].href}>Open tender agent</Link>
          </div>
        </article>

      </section>

    </div>
  );
}

function ProjectContent({ projectId }: { projectId: Exclude<ProjectId, "home"> }) {
  const project = projects.find((item) => item.id === projectId);

  if (!project) return null;

  return (
    <section className="minimal-page project-page">
      <h1>{project.title}</h1>
      <p>{project.description}</p>
    </section>
  );
}

export function LabShell({ activeProject, children }: LabShellProps) {
  return (
    <div className="lab-app">
      <header className="topbar">
        <Link href="/" className="brand-link">
          <BrandMark />
          <span className="brand-text">
            <strong>Applied AI Lab</strong>
            <small>Analytics and machine-learning systems</small>
          </span>
        </Link>
      </header>

      <ProjectTabs activeProject={activeProject} />

      <main className="main-content">
        {children ? (
          children
        ) : activeProject === "home" ? (
          <HomeContent />
        ) : (
          <ProjectContent projectId={activeProject} />
        )}
      </main>
    </div>
  );
}
