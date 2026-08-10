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
    page.getByRole("heading", { name: "Finland Rail Reliability Monitor" }),
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
    page.getByRole("heading", { name: "Finland Rail Reliability Monitor" }),
  ).toBeVisible();
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
