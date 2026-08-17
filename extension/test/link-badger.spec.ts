import { expect, test } from "./fixtures.js";

const BROKER = "https://broker.example.com:8443";

// The content script runs on a REAL (non-extension) page — the harness listing served over the
// host-resolved HTTPS domain — so this drives the actual injected DOM markers (#69).
test("link-badging: enable the site, then only openOM links get honest markers", async ({ context, extensionId }) => {
  // 1. Opt this domain in via the popup per-site toggle (also exercises linkbadge:toggle).
  const popup = await context.newPage();
  await popup.goto(`chrome-extension://${extensionId}/popup.html?url=${encodeURIComponent(`${BROKER}/valid/deal.pdf`)}`);
  await popup.waitForSelector(".lb-toggle");
  await expect(popup.locator(".lb-toggle")).not.toBeChecked();
  await popup.locator(".lb-toggle").check();
  await expect(popup.locator(".lb-toggle")).toBeChecked();
  await popup.close();

  // 2. Visit the listing page; the content script verifies + badges the links.
  const page = await context.newPage();
  await page.goto(`${BROKER}/listing`);

  // valid → openOM (origin-verified or integrity-ok); tampered → altered; plain → no marker.
  const valid = page.locator('a[href="/valid/deal.pdf"] + [data-openom-marker]');
  await expect(valid).toBeVisible();
  await expect(valid).toHaveAttribute("data-state", /origin-verified|integrity-ok/);

  const tampered = page.locator('a[href="/tampered/deal.pdf"] + [data-openom-marker]');
  await expect(tampered).toHaveAttribute("data-state", "hash-mismatch");

  await expect(page.locator('a[href="/plain/deal.pdf"] + [data-openom-marker]')).toHaveCount(0);
});
