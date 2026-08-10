import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/live",
  testMatch: "*.spec.ts",
  timeout: 45_000,
  expect: {
    timeout: 12_000,
  },
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "line" : "list",
  use: {
    baseURL:
      process.env.PLAYWRIGHT_BASE_URL ??
      "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-chromium",
      use: { ...devices["Pixel 7"] },
    },
  ],
});
