import { defineConfig } from "@playwright/test";

// One-off: screenshot the extension's UI surfaces (popup / author panel / options) for a visual
// review before Web-Store submission. Reuses the HTTPS fixture harness. Headed Chromium (MV3).
export default defineConfig({
  testDir: "test",
  testMatch: /showcase\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  webServer: {
    command: "node test/harness/server.mjs",
    url: "https://127.0.0.1:8443/last-hook",
    ignoreHTTPSErrors: true,
    reuseExistingServer: true,
    timeout: 15_000,
  },
  use: { ignoreHTTPSErrors: true },
});
