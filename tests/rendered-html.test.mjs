import assert from "node:assert/strict";
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

test("server-renders the Applied AI Lab overview", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /Applied AI Lab/);
  assert.match(html, /Useful AI starts with an honest baseline/);
  assert.match(html, /No demos pretending to be models/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton/i);
  assert.match(html, /https:\/\/lab\.example\/og-v20260726\.png/);
});

test("renders the Olist model boundary without a fake prediction", async () => {
  const response = await render("/olist-delivery-delay-predictor");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /Olist Delivery/);
  assert.match(html, /No live model is connected/);
  assert.match(html, /Waiting for a validated model/);
  assert.match(html, /fieldset disabled/);
  assert.doesNotMatch(html, /\b\d{1,3}(?:\.\d+)?%\b/);
});

test("keeps every planned project available at a stable direct route", async () => {
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
    assert.match(html, /Planned/);
    assert.match(html, /No dataset, trained model or performance result/);
  }
});
