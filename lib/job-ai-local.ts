const DEFAULT_LOCAL_AI_URL = "http://127.0.0.1:8099";

export function localAiProxyAvailable(): boolean {
  return process.env.NODE_ENV !== "production" || process.env.JOB_AI_ALLOW_LOCAL_PROXY === "true";
}

export function localAiUrl(path: string): URL {
  const configured = process.env.JOB_AI_LOCAL_URL || DEFAULT_LOCAL_AI_URL;
  const base = new URL(configured);
  if (base.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(base.hostname)) {
    throw new Error("Local AI proxy only permits an HTTP loopback address");
  }
  const target = new URL(path, `${base.toString().replace(/\/$/, "")}/`);
  if (target.origin !== base.origin) throw new Error("Local AI path cannot change the configured origin");
  return target;
}

export async function localAiFetch(
  path: string,
  init: RequestInit = {},
  timeoutMs = 5_000,
): Promise<Response> {
  if (!localAiProxyAvailable()) {
    throw new Error("Local AI is intentionally unavailable in the public deployment");
  }
  return fetch(localAiUrl(path), {
    ...init,
    signal: AbortSignal.timeout(timeoutMs),
  });
}

export const unavailableBody = {
  connected: false,
  boundary: "public-deterministic",
  error: "Local Ollama is not exposed by the public Cloudflare deployment.",
};
