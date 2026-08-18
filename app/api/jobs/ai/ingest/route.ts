import { localAiFetch, unavailableBody } from "../../../../../lib/job-ai-local";

export async function POST(request: Request): Promise<Response> {
  try {
    const payload = (await request.json()) as { jobs?: unknown };
    if (!Array.isArray(payload.jobs) || payload.jobs.length > 100) {
      return Response.json({ error: "jobs must be an array with at most 100 items" }, { status: 400, headers: { "cache-control": "no-store" } });
    }
    const response = await localAiFetch(
      "ingest",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ jobs: payload.jobs }),
      },
      120_000,
    );
    return new Response(response.body, {
      status: response.status,
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  } catch {
    return Response.json(unavailableBody, {
      status: 503,
      headers: { "cache-control": "no-store" },
    });
  }
}
