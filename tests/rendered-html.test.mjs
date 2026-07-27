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

test("renders a minimal home page with direct planned-project links", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /Applied AI Lab/);
  assert.match(html, /Home Page/);
  assert.match(html, /Delivery Delay Predictor/);
  assert.match(html, /Planned projects/);
  assert.match(html, /href="\/housing-value-forecast"/);
  assert.match(html, /href="\/credit-risk-assessment"/);
  assert.doesNotMatch(
    html,
    /hero-card|Project status|Future prediction|Completed analytics|predictor-form/,
  );
  assert.match(html, /favicon\.svg\?v=20260727-10/);
  assert.match(html, /og-v20260727-4\.png/);
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
  assert.match(html, /all 14,280 orders in the final test period/);
  assert.match(html, /Logistic regression \(selected\)/);
  assert.match(html, /relative risk score from 0 to 100/);
  assert.match(html, /11\.9(?:<!-- -->)?%/);
  assert.match(html, /27\.4(?:<!-- -->)?%/);
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
  assert.doesNotMatch(css, /gradient|backdrop-filter/i);
});
