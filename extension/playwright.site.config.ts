import { defineConfig, devices } from "@playwright/test";

// Local site gate: serve the committed site/ tree and drive the hosted authoring companion (/embed/)
// and the /verify URL tool in a real headless browser - no MV3, no deploy, so it runs in CI and is the
// committed regression proof for the zero-install broker surfaces (#B1/#B2). Plain Chromium: exactly
// what a visitor's browser gets.
export default defineConfig({
  testDir: "test",
  testMatch: /embed-companion\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  timeout: 45_000,
  webServer: {
    command: "node test/site-server.mjs",
    url: "http://127.0.0.1:8100/embed/",
    reuseExistingServer: true,
    timeout: 15_000,
  },
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:8100" },
});
