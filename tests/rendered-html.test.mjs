import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render(pathname = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set(
    "test",
    `${process.pid}-${Date.now()}-${pathname.replaceAll("/", "-")}`,
  );
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`https://lab.example${pathname}`, {
      headers: {
        accept: "text/html",
        host: "lab.example",
        "x-forwarded-host": "lab.example",
        "x-forwarded-proto": "https",
      },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("renders only completed projects on the public home page", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /Applied AI Lab/);
  assert.match(html, /Home Page/);
  assert.match(html, /Delivery Delay Predictor/);
  assert.match(html, /Rail Monitoring System/);
  assert.match(html, /EU Tender Intelligence Agent/);
  assert.match(html, /Completed project/);
  assert.match(html, /Open predictor/);
  assert.match(html, /Open monitor/);
  assert.match(html, /Open tender agent/);
  assert.doesNotMatch(html, /Planned projects/);
  assert.doesNotMatch(html, /href="\/(?:housing-value-forecast|credit-risk-assessment|document-processing|image-recognition)"/);
  assert.doesNotMatch(html, /Housing Value Forecast|Credit Risk Assessment|Document Processing|Image Recognition/);
  assert.doesNotMatch(html, /predictor-form/);
  assert.match(html, /favicon\.svg\?v=20260905-input-validation-v1/);
  assert.doesNotMatch(html, /og\.png\?v=/);
});

test("keeps local Ollama unreachable from the public Worker", async () => {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("local-ai-boundary", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  const response = await worker.fetch(
    new Request("https://lab.example/api/tenders/ai/status"),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
  const body = await response.json();
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(body.connected, false);
  assert.equal(body.boundary, "public-deterministic");
  assert.equal(body.error, "Local Ollama is not exposed by the public Cloudflare deployment.");
  assert.match(body.localRuntime, /tender_ai\.server/);
});

test("redirects the migrated legacy route to tender intelligence", async () => {
  const response = await render("/job-search-ai-agent");
  assert.ok([301, 302, 303, 307, 308].includes(response.status));
  assert.equal(response.headers.get("location"), "/eu-tender-intelligence-agent");
});

test("renders the EU Tender Intelligence dashboard without hardcoded opportunities", async () => {
  const response = await render("/eu-tender-intelligence-agent");
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /EU Tender/);
  assert.match(html, /Intelligence Agent/);
  assert.match(html, /Official TED procurement data/);
  assert.match(html, /DISCOVER/);
  assert.match(html, /QUALIFY/);
  assert.match(html, /QUALIFY PER LOT/);
  assert.match(html, /WATCH \+ RECHECK/);
  assert.match(html, /GROUNDED AI/);
  assert.match(html, /Search live TED/);
  assert.match(html, /Editable fictional supplier/);
  assert.match(html, /Public Cloudflare never calls localhost Ollama/);
  assert.match(html, /RECORDED-REAL EVALUATION/);
  assert.match(html, /15<!-- --> notices/);
  assert.match(html, /14<!-- -->\/<!-- -->14<!-- --> curated holdout queries/);
  assert.match(html, /MODEL_UNAVAILABLE/);
  assert.match(html, /Source code/);
  assert.doesNotMatch(html, /Arbeitnow|Jobicy|Search public jobs/);

  const publishedFrom = html.match(/Published from<input type="date" value="(\d{4}-\d{2}-\d{2})"/)?.[1];
  const publishedTo = html.match(/Published to<input type="date" value="(\d{4}-\d{2}-\d{2})"/)?.[1];
  assert.ok(publishedFrom, "Published from must be rendered in the saved HTML");
  assert.ok(publishedTo, "Published to must be rendered in the saved HTML");
  assert.ok(Number(publishedFrom.slice(0, 4)) >= 2020, `Implausible Published from year: ${publishedFrom}`);
  assert.ok(Number(publishedTo.slice(0, 4)) >= 2020, `Implausible Published to year: ${publishedTo}`);
  assert.equal(publishedTo, new Date().toISOString().slice(0, 10));
  assert.equal(
    (Date.parse(publishedTo) - Date.parse(publishedFrom)) / 86_400_000,
    90,
    "The default TED search window must cover the previous 90 UTC calendar days",
  );
});

test("renders the evidence-backed Finland rail monitor and methodology", async () => {
  const response = await render("/finland-rail-reliability-monitor");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /Finland Rail Monitoring System/);
  assert.match(html, /National operating picture/);
  assert.match(html, /Current 3-hour operating window/);
  assert.match(html, /24 HOURS/);
  assert.match(html, /7 DAYS/);
  assert.match(html, /HISTORICAL/);
  assert.match(html, /Statistics Finland/);
  assert.match(html, /Historical network view/);
  assert.match(html, /Reliability depends on the threshold/);
  assert.match(html, /Key findings/);
  assert.match(html, /92\.4%/);
  assert.match(html, /Python/);
  assert.match(html, /Power BI \/ DAX/);
  assert.match(html, /Least reliable/);
  assert.match(html, /Most reliable/);
  assert.match(html, /Most services/);
  assert.match(html, /Lahti (?:↔|&harr;) Helsinki/);
  assert.match(html, /Weather association, not causation/);
  assert.match(html, /Reproducible from source to semantic model/);
  assert.match(html, /What this monitor does not claim/);
  assert.match(html, /Fintraffic \/ digitraffic\.fi/);
  assert.match(html, /CC BY 4\.0/);
  assert.match(html, /Passenger train journeys/);
  assert.doesNotMatch(html, /ChatGPT|chatgpt\.site/i);
  assert.doesNotMatch(html, /placeholder|fake live|coming soon/i);
});

test("renders the working Olist model, evidence and honest limitation", async () => {
  const response = await render("/olist-delivery-delay-predictor");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /Olist Delivery Delay Predictor/);
  assert.match(html, /Check one order/);
  assert.match(html, /Estimate delay risk/);
  assert.match(html, /What the final time test showed/);
  assert.match(html, /Selection used rolling time validation/);
  assert.match(
    html,
    /Precision, Delay capture, False \/ found, and the confusion matrix/,
  );
  assert.match(html, /14,471(?:<!-- -->)? orders/);
  assert.match(html, /complete final benchmark/);
  assert.match(html, /Logistic regression \(selected\)/);
  assert.match(html, /relative risk score from 0 to 100/);
  assert.match(html, /7\.4(?:<!-- -->)?%/);
  assert.match(html, /17\.3(?:<!-- -->)?%/);
  assert.match(html, /PR-AUC lift/);
  assert.match(html, /pending order cannot leak its future label/);
  assert.match(html, /View source/);
  assert.match(html, /Model card/);
  assert.match(html, /Dataset/);
  assert.match(html, /CC BY-NC-SA 4\.0/);
  assert.doesNotMatch(html, /model has not been built or connected yet/i);
});

test("keeps legacy placeholder routes compatible without listing them on home", async () => {
  const routes = [
    ["/housing-value-forecast", "Housing Value Forecast"],
    ["/credit-risk-assessment", "Credit Risk Assessment"],
    ["/document-processing", "Document Processing"],
    ["/image-recognition", "Image Recognition"],
  ];

  for (const [route, title] of routes) {
    const response = await render(route);
    assert.equal(response.status, 200, route);
    const html = await response.text();
    assert.match(html, new RegExp(title));
    assert.match(html, new RegExp(`aria-current="page"[^>]*>${title}`));
    assert.match(html, /<meta name="robots" content="noindex, nofollow"/);
    assert.doesNotMatch(
      html,
      /INTENDED RESULT|Project availability|Coming later|hero-card/,
    );
  }
});

test("preserves the dark lab visual system and adds scoped predictor styles", async () => {
  const css = await readFile(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );

  assert.match(css, /--page:\s*#12171d/);
  assert.match(css, /--navy:\s*#0c2547/);
  assert.match(css, /--cyan:\s*#19ccff/);
  assert.match(css, /\.project-tabs\s*\{/);
  assert.match(css, /\.minimal-page\s*\{/);
  assert.match(css, /\.predictor-form\s*\{/);
  assert.match(css, /\.prediction-result\s*\{/);
  assert.match(css, /\.featured-project\s*\{/);
  assert.match(css, /\.rail-page\s*\{/);
  assert.match(css, /\.regional-monitor\s*\{/);
  assert.match(css, /\.finland-region-map\s*\{/);
  assert.match(css, /\.threshold-control\s*\{/);
  assert.match(css, /\.lahti-profile\s*\{/);
  assert.match(css, /\.tender-page\s*\{/);
  assert.match(css, /\.evidence-panel\s*\{/);
  assert.doesNotMatch(css, /gradient|backdrop-filter/i);
});

test("packages the tracked Sites hosting contract into the production build", async () => {
  const source = JSON.parse(await readFile(new URL("../.openai/hosting.json", import.meta.url), "utf8"));
  const packaged = JSON.parse(await readFile(new URL("../dist/.openai/hosting.json", import.meta.url), "utf8"));
  assert.equal(source.project_id, "appgprj_6a6627e396388191b7aa5d08cc2dba27");
  assert.deepEqual(packaged, source);
});
