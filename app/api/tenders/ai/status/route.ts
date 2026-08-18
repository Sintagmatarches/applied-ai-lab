export async function GET(): Promise<Response> {
  return Response.json({
    connected: false,
    boundary: "public-deterministic",
    error: "Local Ollama is not exposed by the public Cloudflare deployment.",
    localRuntime: "python -m uvicorn tender_ai.server:app --host 127.0.0.1 --port 8099",
  }, { headers: { "cache-control": "no-store" } });
}
