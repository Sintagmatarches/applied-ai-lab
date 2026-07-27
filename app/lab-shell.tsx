import Link from "next/link";
import type { ReactNode } from "react";

export type ProjectId =
  | "home"
  | "olist"
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
      project.id !== "olist",
  );

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
          href={projects[0].href}
          className={activeProject === "olist" ? "is-active" : ""}
          aria-current={activeProject === "olist" ? "page" : undefined}
        >
          {projects[0].tabTitle}
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
    <section className="minimal-page home-page">
      <h1>Planned projects</h1>
      <ul className="project-link-list">
        {projects.slice(1).map((project) => (
          <li key={project.id}>
            <Link href={project.href}>{project.title}</Link>
          </li>
        ))}
      </ul>
    </section>
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
            <small>Practical machine-learning tools</small>
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
