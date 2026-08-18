import { localAiFetch, unavailableBody } from "../../../../../lib/job-ai-local";

export async function GET(): Promise<Response> {
  try {
    const response = await localAiFetch("health", {}, 2_000);
    if (!response.ok) throw new Error("Local AI health check failed");
    return Response.json(await response.json(), {
      headers: { "cache-control": "no-store" },
    });
  } catch {
    return Response.json(unavailableBody, {
      headers: { "cache-control": "no-store" },
    });
  }
}
