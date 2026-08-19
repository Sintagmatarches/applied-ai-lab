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
  const completedProjects = page.getByRole("region", { name: "Completed projects" });
  await expect(completedProjects).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Olist Delivery Delay Predictor" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Open predictor" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Finland Rail Monitoring System" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Open monitor" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Planned projects" })).toBeVisible();

  const completedTop = await completedProjects.boundingBox();
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
    page.getByRole("heading", { name: "Finland Rail Monitoring System" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Live rail health by region" })).toBeVisible();
  await expect(page.getByText("Live Digitraffic", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".region-shape")).toHaveCount(19);
  await page.getByRole("button", { name: /Åland: No rail service/ }).click();
  await expect(page.locator(".region-detail").getByText("No rail service", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "24 HOURS" }).click();
  await expect(page.getByText("Rolling window", { exact: true })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "HISTORICAL" }).click();
  await expect(page.getByText("2025-08-01 → 2026-07-31", { exact: true })).toBeVisible();
  await expect(page.getByText("Historical network view", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Key findings" })).toBeVisible();
  await expect(page.getByText("Weather association, not causation")).toBeVisible();
  const routeOrder = page.getByLabel("Order routes");
  const firstRoute = page
    .getByRole("region", { name: "Frequent end-to-end routes" })
    .locator("tbody tr")
    .first()
    .locator("th");

  await expect(routeOrder).toHaveValue("least-reliable");
  await expect(firstRoute).toContainText("Käpylä ↔ Lahti");
  await routeOrder.selectOption("most-reliable");
  await expect(firstRoute).toContainText("Helsinki ↔ Leppävaara");
  await routeOrder.selectOption("volume");
  await expect(firstRoute).toContainText("Helsinki ↔ Kerava");

  const fiveMinuteValue = await page
    .getByText("Arrived within 5 min", { exact: true })
    .locator("..")
    .locator("dd")
    .textContent();
  const fiveMinuteRouteValue = await page
    .getByRole("row", { name: /Helsinki ↔ Kerava/ })
    .locator("td")
    .nth(1)
    .textContent();
  const fiveMinuteProfileValue = await page.locator(".route-profile-kpi strong").textContent();
  await page.getByRole("button", { name: "≤ 15 min" }).click();
  const fifteenMinuteValue = await page
    .getByText("Arrived within 15 min", { exact: true })
    .locator("..")
    .locator("dd")
    .textContent();
  const fifteenMinuteRouteValue = await page
    .getByRole("row", { name: /Helsinki ↔ Kerava/ })
    .locator("td")
    .nth(1)
    .textContent();
  const fifteenMinuteProfileValue = await page.locator(".route-profile-kpi strong").textContent();
  expect(fifteenMinuteValue).not.toEqual(fiveMinuteValue);
  expect(fifteenMinuteRouteValue).not.toEqual(fiveMinuteRouteValue);
  expect(fifteenMinuteProfileValue).not.toEqual(fiveMinuteProfileValue);

  await routeOrder.selectOption("most-reliable");
  await expect(firstRoute).toContainText("Seinäjoki ↔ Ähtäri");

  if (testInfo.project.name === "desktop-chromium") {
    await page.setViewportSize({ width: 412, height: 915 });
  }
  const columns = await page.locator(".rail-kpi-grid").evaluate(
    (element) => getComputedStyle(element).gridTemplateColumns.split(" ").length,
  );
  expect(columns).toBe(1);

  const activeTabIsVisible = await page
    .locator(".project-tabs [aria-current='page']")
    .evaluate((element) => {
      const navigation = element.closest(".project-tabs");
      if (!navigation) return false;
      const tabRect = element.getBoundingClientRect();
      const navRect = navigation.getBoundingClientRect();
      return tabRect.left >= navRect.left && tabRect.right <= navRect.right;
    });
  expect(activeTabIsVisible).toBe(true);
  expect(browserErrors).toEqual([]);
});

test("published rail monitor preserves history when live data is unavailable", async ({
  page,
}) => {
  const browserErrors = failOnBrowserErrors(page);
  await page.route("**/api/rail/live", async (route) => {
    await route.fulfill({
      status: 502,
      contentType: "application/json",
      body: JSON.stringify({ error: "Digitraffic unavailable in test" }),
    });
  });

  const response = await page.goto(
    freshPath("/finland-rail-reliability-monitor"),
    { waitUntil: "networkidle" },
  );

  expect(response?.status()).toBe(200);
  await expect(page.getByText("Historical network view", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Recent service data is temporarily unavailable. Historical analysis remains available below."),
  ).toBeVisible();
  expect(browserErrors).toHaveLength(1);
  expect(browserErrors[0]).toContain("502");
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

test("published tender agent runs one live example and exposes lot evidence", async ({ page }, testInfo) => {
  const browserErrors = failOnBrowserErrors(page);
  const response = await page.goto(freshPath("/eu-tender-intelligence-agent"), { waitUntil: "networkidle" });
  expect(response?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "EU Tender Intelligence Agent" })).toBeVisible();
  await expect(page.getByText("PUBLIC LIVE", { exact: true })).toBeVisible();
  await expect(page.getByText("LOCAL AI", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /Architecture/ })).toBeVisible();
  await expect(page.getByLabel("Languages")).toBeVisible();
  await page.getByRole("button", { name: "Run live example search" }).click();
  await expect(page.getByText(/FETCHED THIS BATCH/)).toBeVisible({ timeout: 30_000 });
  const cards = page.locator(".tender-card");
  if (await cards.count()) {
    await cards.first().getByRole("button", { name: "Inspect evidence" }).click();
    await expect(page.getByRole("heading", { name: "Lot decisions" })).toBeVisible();
    await cards.first().getByRole("button", { name: "Watch" }).click();
    await expect(page.getByRole("button", { name: "Recheck watched notices" })).toBeEnabled();
  }
  if (testInfo.project.name === "mobile-chromium") {
    const columns = await page.locator(".tender-filters").evaluate((element) => getComputedStyle(element).gridTemplateColumns.split(" ").length);
    expect(columns).toBe(1);
  }
  expect(browserErrors).toEqual([]);
});

test("published tender agent renders a controlled search error", async ({ page }) => {
  const browserErrors = failOnBrowserErrors(page);
  await page.route("**/api/tenders/search", async (route) => route.fulfill({ status: 422, contentType: "application/json", body: JSON.stringify({ error: "Invalid tender search filters.", details: ["test validation error"] }) }));
  await page.goto(freshPath("/eu-tender-intelligence-agent"), { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Search live TED" }).click();
  await expect(page.getByRole("alert")).toContainText("test validation error");
  expect(browserErrors.some((message) => /422 \(Unprocessable Entity\)/.test(message))).toBe(true);
  expect(browserErrors.filter((message) => !/422 \(Unprocessable Entity\)/.test(message))).toEqual([]);
});
