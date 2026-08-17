import { defineConfig } from "@playwright/test";

// Real-browser consumer gate. Headed Chromium (MV3 extensions need it); one worker (persistent
// context). The harness HTTPS server is started + reused. [OM-DoD-006].
export default defineConfig({
  testDir: "test",
  testMatch: /(consumer|author|a11y|link-badger)\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  webServer: {
    command: "node test/harness/server.mjs",
    url: "https://127.0.0.1:8443/last-hook",
    ignoreHTTPSErrors: true,
    reuseExistingServer: true,
    timeout: 15_000,
  },
  use: { ignoreHTTPSErrors: true },
});
