import { mkdirSync } from "node:fs";
import { expect, test } from "./fixtures.js";

const BROKER = "https://broker.example.com:8443";
const OUT = "showcase-out";
mkdirSync(`${OUT}`, { recursive: true });

test("capture the extension UI surfaces", async ({ context, extensionId }) => {
  const page = await context.newPage();

  // 1. Consumer popup - a valid OM at its origin → origin-verified badge card
  await page.setViewportSize({ width: 400, height: 620 });
  await page.goto(
    `chrome-extension://${extensionId}/popup.html?url=${encodeURIComponent(`${BROKER}/valid/deal.pdf`)}`,
  );
  await expect(page.locator("body")).toContainText(/verified|unaltered|openOM/i, { timeout: 20_000 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/1-popup-verified.png` });

  // 2. Consumer popup - a tampered payload → hash-mismatch (honest red state)
  await page.goto(
    `chrome-extension://${extensionId}/popup.html?url=${encodeURIComponent(`${BROKER}/tampered/deal.pdf`)}`,
  );
  await expect(page.locator("body")).toContainText(/altered|mismatch|do not trust/i, { timeout: 20_000 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/2-popup-tampered.png` });

  // 3. Author side panel - a plain OM → the review/assert form (fresh embed)
  await page.setViewportSize({ width: 460, height: 900 });
  await page.goto(
    `chrome-extension://${extensionId}/sidepanel.html?url=${encodeURIComponent(`${BROKER}/author/plain.pdf`)}`,
  );
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}/3-author-fresh.png`, fullPage: true });

  // 4. Author side panel - an already-embedded OM → reprice review
  await page.goto(
    `chrome-extension://${extensionId}/sidepanel.html?url=${encodeURIComponent(`${BROKER}/author/embedded.pdf`)}`,
  );
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}/4-author-reprice.png`, fullPage: true });

  // 5. Options page - settings (profile, webhook, detection, Buildout ingestion)
  await page.setViewportSize({ width: 720, height: 900 });
  await page.goto(`chrome-extension://${extensionId}/options.html`);
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/5-options.png`, fullPage: true });
});
