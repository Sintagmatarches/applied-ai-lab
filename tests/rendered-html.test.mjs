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
  assert.match(html, /favicon\.svg\?v=20260727-7/);
});

test("renders only the Olist project name and description", async () => {
  const response = await render("/olist-delivery-delay-predictor");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /Olist Delivery Delay Predictor/);
  assert.match(html, /estimate whether a new Olist order will arrive/);
  assert.match(html, /model has not been built or connected yet/);
  assert.doesNotMatch(
    html,
    /Project status|Future prediction|Completed analytics|fieldset|Model in development/,
  );
  assert.doesNotMatch(html, /\b\d{1,3}(?:\.\d+)?%\b/);
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

test("uses a flat minimal visual system without product-dashboard components", async () => {
  const css = await readFile(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );

  assert.match(css, /--page:\s*#12171d/);
  assert.match(css, /--navy:\s*#0c2547/);
  assert.match(css, /--cyan:\s*#19ccff/);
  assert.match(css, /\.project-tabs\s*\{/);
  assert.match(css, /\.minimal-page\s*\{/);
  assert.doesNotMatch(
    css,
    /hero-card|status-grid|workspace-card|predictor-form|resource-grid|planned-note|gradient|backdrop-filter/i,
  );
});
