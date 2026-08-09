import { expect, test, type Page } from "@playwright/test";

function failOnBrowserErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

function freshPath(pathname: string): string {
  const separator = pathname.includes("?") ? "&" : "?";
  return `${pathname}${separator}verify=${Date.now()}`;
}

test("published homepage leads with the completed projects", async ({ page }) => {
  const browserErrors = failOnBrowserErrors(page);
  const response = await page.goto(freshPath("/"), {
    waitUntil: "networkidle",
  });

  expect(response?.status()).toBe(200);
  await expect(page.getByText("Completed project", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Olist Delivery Delay Predictor" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Open predictor" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Finland Rail Reliability Monitor" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Open monitor" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Planned projects" })).toBeVisible();

  const completedTop = await page
    .getByText("Completed project", { exact: true })
    .boundingBox();
  const plannedTop = await page
    .getByRole("heading", { name: "Planned projects" })
    .boundingBox();
  expect(completedTop).not.toBeNull();
  expect(plannedTop).not.toBeNull();
  expect(completedTop!.y).toBeLessThan(plannedTop!.y);
  expect(browserErrors).toEqual([]);
});

test("published rail monitor changes thresholds and stays readable", async ({
  page,
}, testInfo) => {
  const browserErrors = failOnBrowserErrors(page);
  const response = await page.goto(
    freshPath("/finland-rail-reliability-monitor"),
    { waitUntil: "networkidle" },
  );

  expect(response?.status()).toBe(200);
  await expect(
    page.getByRole("heading", { name: "Finland Rail Reliability Monitor" }),
  ).toBeVisible();
  await expect(page.getByText("Historical network view", { exact: true })).toBeVisible();
  await expect(page.getByText("Weather association, not causation")).toBeVisible();
  const fiveMinuteValue = await page
    .getByText("Arrived within 5 min", { exact: true })
    .locator("..")
    .locator("dd")
    .textContent();
  await page.getByRole("button", { name: "≤ 15 min" }).click();
  const fifteenMinuteValue = await page
    .getByText("Arrived within 15 min", { exact: true })
    .locator("..")
    .locator("dd")
    .textContent();
  expect(fifteenMinuteValue).not.toEqual(fiveMinuteValue);

  if (testInfo.project.name === "mobile-chromium") {
    const columns = await page.locator(".rail-kpi-grid").evaluate(
      (element) => getComputedStyle(element).gridTemplateColumns.split(" ").length,
    );
    expect(columns).toBe(1);
  }
  expect(browserErrors).toEqual([]);
});

test("published predictor works and keeps its responsive layout", async ({
  page,
}, testInfo) => {
  const browserErrors = failOnBrowserErrors(page);
  const response = await page.goto(
    freshPath("/olist-delivery-delay-predictor"),
    { waitUntil: "networkidle" },
  );

  expect(response?.status()).toBe(200);
  await expect(
    page.getByRole("heading", { name: "Olist Delivery Delay Predictor" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "View source" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Model card" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Dataset" })).toBeVisible();
  await expect(page.getByText(/Olist.*CC BY-NC-SA 4\.0/)).toBeVisible();

  const columnCount = await page.locator(".form-grid").evaluate((element) =>
    getComputedStyle(element).gridTemplateColumns.split(" ").length,
  );
  if (testInfo.project.name === "mobile-chromium") {
    expect(columnCount).toBe(1);
  } else {
    expect(columnCount).toBe(3);
  }

  await page.getByRole("button", { name: "Estimate delay risk" }).click();
  await expect(page.locator(".prediction-result")).toBeVisible();
  await expect(page.getByText("Relative risk score", { exact: true })).toBeVisible();
  expect(browserErrors).toEqual([]);
});
