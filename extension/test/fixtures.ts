import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { type BrowserContext, chromium, test as base } from "@playwright/test";

// Playwright fixtures for MV3 extension testing: a persistent context with the unpacked extension
// loaded, plus the resolved extension id. Headed Chromium is required — MV3 extensions do not run
// under chrome-headless-shell (on Linux CI, run under xvfb).
const DIST = join(dirname(fileURLToPath(import.meta.url)), "..", "dist");

export const test = base.extend<{ context: BrowserContext; extensionId: string }>({
  context: async ({}, use) => {
    const context = await chromium.launchPersistentContext("", {
      headless: false,
      args: [
        `--disable-extensions-except=${DIST}`,
        `--load-extension=${DIST}`,
        "--host-resolver-rules=MAP broker.example.com 127.0.0.1, MAP attacker.net 127.0.0.1",
        "--ignore-certificate-errors",
        // CI stability: headed Chromium under xvfb crashes ("browser has been closed") when the
        // runner's tiny /dev/shm (64 MB) fills; route shared memory to /tmp and drop the sandbox
        // (the CI user can't use it). Harmless locally.
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-gpu",
      ],
    });
    await use(context);
    await context.close();
  },
  extensionId: async ({ context }, use) => {
    let [sw] = context.serviceWorkers();
    if (!sw) sw = await context.waitForEvent("serviceworker");
    await use(sw.url().split("/")[2]);
  },
});

export const expect = test.expect;
