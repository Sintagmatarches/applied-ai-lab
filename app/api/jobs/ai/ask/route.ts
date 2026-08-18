import { localAiFetch, unavailableBody } from "../../../../../lib/job-ai-local";

export async function POST(request: Request): Promise<Response> {
  try {
    const payload = (await request.json()) as { question?: unknown; profile?: unknown };
    if (typeof payload.question !== "string" || payload.question.trim().length < 2 || payload.question.length > 1_000) {
      return Response.json({ error: "question must contain 2–1000 characters" }, { status: 400, headers: { "cache-control": "no-store" } });
    }
    if (payload.profile !== undefined && (typeof payload.profile !== "object" || payload.profile === null || Array.isArray(payload.profile))) {
      return Response.json({ error: "profile must be an object" }, { status: 400, headers: { "cache-control": "no-store" } });
    }
    const response = await localAiFetch(
      "ask",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: payload.question.trim(), profile: payload.profile || {} }),
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
