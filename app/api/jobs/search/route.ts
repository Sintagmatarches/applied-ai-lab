import {
  deduplicateJobs,
  matchesSearch,
  normalizeArbeitnow,
  normalizeJobicy,
  type JobSearchResponse,
  type PublicJob,
} from "../../../../lib/jobs";

const REQUEST_TIMEOUT_MS = 8_000;
const MAX_RESULTS = 60;

type SourceResult = {
  name: string;
  url: string;
  jobs: PublicJob[];
};

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url, {
    headers: {
      accept: "application/json",
      "user-agent": "AppliedAILab-JobSearch/1.0 (+https://github.com/Sintagmatarches/applied-ai-lab)",
    },
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!response.ok) throw new Error(`Source returned ${response.status}`);
  return response.json();
}

async function searchArbeitnow(query: string): Promise<SourceResult> {
  const payload = (await fetchJson(
    "https://www.arbeitnow.com/api/job-board-api",
  )) as { data?: unknown };
  const rows = Array.isArray(payload.data) ? payload.data : [];
  const jobs = rows
    .map((row) => normalizeArbeitnow(row as Record<string, unknown>))
    .filter((job): job is PublicJob => job !== null)
    .filter((job) => matchesSearch(job, query, "", false));
  return {
    name: "Arbeitnow",
    url: "https://www.arbeitnow.com/blog/job-board-api",
    jobs,
  };
}

async function searchJobicy(query: string, location: string): Promise<SourceResult> {
  const params = new URLSearchParams({ count: "50" });
  if (query) params.set("tag", query);
  if (location) params.set("geo", location);
  const payload = (await fetchJson(
    `https://jobicy.com/api/v2/remote-jobs?${params.toString()}`,
  )) as { jobs?: unknown };
  const rows = Array.isArray(payload.jobs) ? payload.jobs : [];
  const jobs = rows
    .map((row) => normalizeJobicy(row as Record<string, unknown>))
    .filter((job): job is PublicJob => job !== null);
  return {
    name: "Jobicy",
    url: "https://jobicy.com/jobs-rss-feed",
    jobs,
  };
}

function validatedParam(url: URL, name: string): string {
  return (url.searchParams.get(name) ?? "").trim().slice(0, 80);
}

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const query = validatedParam(url, "q");
  const location = validatedParam(url, "location");
  const remoteOnly = url.searchParams.get("remote") === "true";

  const settled = await Promise.allSettled([
    searchArbeitnow(query),
    searchJobicy(query, location),
  ]);

  const successful = settled
    .filter((result): result is PromiseFulfilledResult<SourceResult> => result.status === "fulfilled")
    .map((result) => result.value);

  if (successful.length === 0) {
    console.error("All public job sources failed", settled);
    return Response.json(
      { error: "Public job sources are temporarily unavailable. Try again later." },
      { status: 502, headers: { "cache-control": "no-store" } },
    );
  }

  const filtered = successful
    .flatMap((source) => source.jobs)
    .filter((job) => matchesSearch(job, query, location, remoteOnly))
    .sort((left, right) =>
      (right.publishedAt ?? "").localeCompare(left.publishedAt ?? ""),
    );
  const deduplicated = deduplicateJobs(filtered);

  const body: JobSearchResponse = {
    retrievedAt: new Date().toISOString(),
    jobs: deduplicated.jobs.slice(0, MAX_RESULTS),
    duplicateCount: deduplicated.duplicateCount,
    sources: settled.map((result, index) => {
      const fallback = index === 0
        ? { name: "Arbeitnow", url: "https://www.arbeitnow.com/blog/job-board-api" }
        : { name: "Jobicy", url: "https://jobicy.com/jobs-rss-feed" };
      return result.status === "fulfilled"
        ? {
            name: result.value.name,
            url: result.value.url,
            status: "ok" as const,
            count: result.value.jobs.length,
          }
        : { ...fallback, status: "unavailable" as const, count: 0 };
    }),
  };

  return Response.json(body, {
    headers: {
      "cache-control": "public, max-age=300, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}
