import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./fixtures.js";

const BROKER = "https://broker.example.com:8443";

// Real automated accessibility audit (#71) — WCAG 2.0/2.1 A + AA — against both surfaces. We gate on
// serious/critical violations (the ones that actually block assistive-tech users); the full report
// is attached to the failure message for triage.
async function audit(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

test("popup: no serious/critical a11y violations", async ({ context, extensionId }) => {
  const page = await context.newPage();
  await page.goto(`chrome-extension://${extensionId}/popup.html?url=${encodeURIComponent(`${BROKER}/valid/deal.pdf`)}`);
  await page.waitForSelector(".badge-label");
  const v = await audit(page);
  expect(v.map((x) => x.id).join(", ") || "none").toBe("none");
});

test("author panel: no serious/critical a11y violations", async ({ context, extensionId }) => {
  const page = await context.newPage();
  await page.goto(`chrome-extension://${extensionId}/sidepanel.html?url=${encodeURIComponent(`${BROKER}/author/plain.pdf`)}`);
  await page.waitForSelector(".p-broker");
  const v = await audit(page);
  expect(v.map((x) => x.id).join(", ") || "none").toBe("none");
});
