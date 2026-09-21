import model from "../../../../artifacts/olist-model.json";
import { olistModelMetadata } from "../../../../lib/olist-model";

// Hash the exact runtime object, not a separately maintained version declaration.
let digest: Promise<string> | undefined;

export async function GET(): Promise<Response> {
  digest ??= crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(model)))
    .then((bytes) => Array.from(new Uint8Array(bytes), (byte) => byte.toString(16).padStart(2, "0")).join(""));
  return Response.json({
    ...olistModelMetadata,
    artifactSha256: await digest,
    hashEncoding: "SHA-256 of UTF-8 JSON.stringify(runtime artifact)",
  }, { headers: { "cache-control": "no-store" } });
}
