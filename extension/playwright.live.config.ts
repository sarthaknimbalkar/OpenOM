import { defineConfig, devices } from "@playwright/test";

// Post-deploy live smoke against the DEPLOYED origin (default https://openom.app; override with
// OPENOM_LIVE_BASE). Plain headless Chromium - no MV3, no local harness webServer - so it exercises
// exactly what a real visitor's browser gets. Run: `npm run test:live` (after a deploy). This is the
// guard for the "passes locally, broken live" class (e.g. the un-deployed /verify/ widget bundle).
export default defineConfig({
  testDir: "test",
  testMatch: /live-site\.spec\.ts/,
  fullyParallel: true,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  timeout: 45_000,
  use: { ...devices["Desktop Chrome"] },
});
