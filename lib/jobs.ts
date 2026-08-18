export type PublicJob = {
  id: string;
  source: "Arbeitnow" | "Jobicy";
  sourceUrl: string;
  url: string;
  company: string;
  title: string;
  location: string;
  remote: boolean;
  description: string;
  tags: string[];
  employmentType: string;
  seniority: string;
  salary: string | null;
  publishedAt: string | null;
};

export type JobSearchResponse = {
  retrievedAt: string;
  jobs: PublicJob[];
  sources: Array<{
    name: string;
    url: string;
    status: "ok" | "unavailable";
    count: number;
  }>;
  duplicateCount: number;
};

type ArbeitnowJob = {
  slug?: unknown;
  company_name?: unknown;
  title?: unknown;
  description?: unknown;
  remote?: unknown;
  url?: unknown;
  tags?: unknown;
  job_types?: unknown;
  location?: unknown;
  created_at?: unknown;
};

type JobicyJob = {
  id?: unknown;
  url?: unknown;
  jobTitle?: unknown;
  companyName?: unknown;
  jobIndustry?: unknown;
  jobType?: unknown;
  jobGeo?: unknown;
  jobLevel?: unknown;
  jobDescription?: unknown;
  pubDate?: unknown;
  salaryMin?: unknown;
  salaryMax?: unknown;
  salaryCurrency?: unknown;
  salaryPeriod?: unknown;
};

const SKILLS = [
  "Python",
  "SQL",
  "Power BI",
  "Tableau",
  "Excel",
  "JavaScript",
  "TypeScript",
  "React",
  "Node.js",
  "FastAPI",
  "Docker",
  "Kubernetes",
  "Azure",
  "AWS",
  "GCP",
  "Databricks",
  "Spark",
  "Machine Learning",
  "NLP",
  "LLM",
  "RAG",
  "Git",
  "REST",
  "PostgreSQL",
  "MySQL",
  "Snowflake",
] as const;

function asString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function safeUrl(value: unknown): string | null {
  try {
    const url = new URL(asString(value));
    return url.protocol === "https:" || url.protocol === "http:"
      ? url.toString()
      : null;
  } catch {
    return null;
  }
}

export function textFromHtml(value: unknown): string {
  return asString(value)
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&quot;/gi, '"')
    .replace(/&#(?:x27|39);/gi, "'")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 12_000);
}

export function inferSkills(text: string, explicit: string[] = []): string[] {
  const haystack = ` ${text.toLowerCase()} `;
  const inferred = SKILLS.filter((skill) => {
    const escaped = skill
      .toLowerCase()
      .replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
      .replace(/\\ /g, "[\\s/-]+");
    return new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`, "i").test(
      haystack,
    );
  });
  return [...new Set([...explicit.map((tag) => tag.trim()), ...inferred])]
    .filter(Boolean)
    .slice(0, 12);
}

function inferSeniority(title: string, description: string): string {
  const text = `${title} ${description}`.toLowerCase();
  if (/\b(intern|internship|trainee)\b/.test(text)) return "Internship";
  if (/\b(junior|entry[ -]level|graduate)\b/.test(text)) return "Entry level";
  if (/\b(principal|staff|lead|head|director)\b/.test(text)) return "Lead / principal";
  if (/\b(senior|sr\.)\b/.test(text)) return "Senior";
  return "Not stated";
}

function normalizeDate(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    const date = new Date(value * 1000);
    return Number.isNaN(date.valueOf()) ? null : date.toISOString();
  }
  const text = asString(value);
  if (!text) return null;
  const date = new Date(text);
  return Number.isNaN(date.valueOf()) ? null : date.toISOString();
}

function salaryLabel(job: JobicyJob): string | null {
  const minimum = typeof job.salaryMin === "number" ? job.salaryMin : null;
  const maximum = typeof job.salaryMax === "number" ? job.salaryMax : null;
  if (minimum === null && maximum === null) return null;
  const currency = asString(job.salaryCurrency) || "USD";
  const period = asString(job.salaryPeriod);
  const range = [minimum, maximum]
    .filter((value): value is number => value !== null)
    .map((value) => value.toLocaleString("en-US"))
    .join("–");
  return `${currency} ${range}${period ? ` / ${period}` : ""}`;
}

export function normalizeArbeitnow(job: ArbeitnowJob): PublicJob | null {
  const url = safeUrl(job.url);
  const title = asString(job.title);
  const company = asString(job.company_name);
  if (!url || !title || !company) return null;
  const description = textFromHtml(job.description);
  const explicitTags = Array.isArray(job.tags)
    ? job.tags.map(asString).filter(Boolean)
    : [];
  const jobTypes = Array.isArray(job.job_types)
    ? job.job_types.map(asString).filter(Boolean)
    : [];
  return {
    id: `arbeitnow:${asString(job.slug) || url}`,
    source: "Arbeitnow",
    sourceUrl: "https://www.arbeitnow.com/blog/job-board-api",
    url,
    company,
    title,
    location: asString(job.location) || "Not stated",
    remote: job.remote === true || /remote/i.test(asString(job.location)),
    description,
    tags: inferSkills(`${title} ${description}`, explicitTags),
    employmentType: jobTypes.join(" · ") || "Not stated",
    seniority: inferSeniority(title, description),
    salary: null,
    publishedAt: normalizeDate(job.created_at),
  };
}

export function normalizeJobicy(job: JobicyJob): PublicJob | null {
  const url = safeUrl(job.url);
  const title = asString(job.jobTitle);
  const company = asString(job.companyName);
  if (!url || !title || !company) return null;
  const description = textFromHtml(job.jobDescription);
  const industry = asString(job.jobIndustry);
  const statedLevel = asString(job.jobLevel);
  return {
    id: `jobicy:${asString(job.id) || url}`,
    source: "Jobicy",
    sourceUrl: "https://jobicy.com/jobs-rss-feed",
    url,
    company,
    title,
    location: asString(job.jobGeo) || "Remote",
    remote: true,
    description,
    tags: inferSkills(`${title} ${description}`, industry ? [industry] : []),
    employmentType: asString(job.jobType) || "Not stated",
    seniority: statedLevel || inferSeniority(title, description),
    salary: salaryLabel(job),
    publishedAt: normalizeDate(job.pubDate),
  };
}

export function deduplicateJobs(jobs: PublicJob[]): {
  jobs: PublicJob[];
  duplicateCount: number;
} {
  const seen = new Set<string>();
  const unique: PublicJob[] = [];
  for (const job of jobs) {
    const key = [job.company, job.title, job.location]
      .map((value) => value.toLowerCase().replace(/[^a-z0-9]+/g, ""))
      .join(":");
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(job);
  }
  return { jobs: unique, duplicateCount: jobs.length - unique.length };
}

export function matchesSearch(
  job: PublicJob,
  query: string,
  location: string,
  remoteOnly: boolean,
): boolean {
  const searchable = [
    job.title,
    job.company,
    job.description,
    job.tags.join(" "),
  ]
    .join(" ")
    .toLowerCase();
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .map((term) => term.trim())
    .filter((term) => term.length > 1);
  const queryMatches = terms.length === 0 || terms.some((term) => searchable.includes(term));
  const locationMatches =
    !location ||
    job.location.toLowerCase().includes(location.toLowerCase()) ||
    (job.remote && /remote|worldwide|europe|emea/i.test(location));
  return queryMatches && locationMatches && (!remoteOnly || job.remote);
}
