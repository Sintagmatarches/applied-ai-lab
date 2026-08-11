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

test("renders both completed projects before clearly marked planned work", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /Applied AI Lab/);
  assert.match(html, /Home Page/);
  assert.match(html, /Delivery Delay Predictor/);
  assert.match(html, /Rail Reliability Monitor/);
  assert.match(html, /Completed project/);
  assert.match(html, /Open predictor/);
  assert.match(html, /Open monitor/);
  assert.match(html, /Planned projects/);
  assert.match(html, /href="\/housing-value-forecast"/);
  assert.match(html, /href="\/credit-risk-assessment"/);
  assert.ok(html.indexOf("Completed project") < html.indexOf("Planned projects"));
  assert.doesNotMatch(html, /predictor-form/);
  assert.match(html, /favicon\.svg\?v=20260811-olist-audit-1/);
  assert.match(html, /og\.png\?v=20260811-olist-audit-1/);
});

test("renders the evidence-backed Finland rail monitor and methodology", async () => {
  const response = await render("/finland-rail-reliability-monitor");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /Finland Rail Reliability Monitor/);
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

test("keeps every planned project as a minimal direct page and active tab", async () => {
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
  assert.match(css, /\.threshold-control\s*\{/);
  assert.match(css, /\.lahti-profile\s*\{/);
  assert.doesNotMatch(css, /gradient|backdrop-filter/i);
});
