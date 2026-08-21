import { type BrowserContext, type Page } from "@playwright/test";
import { expect, test } from "./fixtures.js";

const BROKER = "https://broker.example.com:8443";
const ATTACKER = "https://attacker.net:8443";

// Open the popup as a deep-link to a target URL - the full pipeline (SW re-fetch → read →
// verifyOrigin over the real HTTPS server → badge → card) runs identically to the active-tab path.
async function openPopup(context: BrowserContext, extensionId: string, targetUrl: string): Promise<Page> {
  const page = await context.newPage();
  const popup = `chrome-extension://${extensionId}/popup.html?url=${encodeURIComponent(targetUrl)}`;
  await page.goto(popup);
  await page.waitForSelector(".badge-label", { timeout: 20_000 });
  return page;
}

test("valid PDF at its origin → origin-verified", async ({ context, extensionId }) => {
  const page = await openPopup(context, extensionId, `${BROKER}/valid/deal.pdf`);
  await expect(page.locator(".badge")).toHaveClass(/badge-origin-verified/);
  await expect(page.locator(".card")).toBeVisible();
  await expect(page.locator(".badge-caption")).toContainText("vouches");
});

test("embedded but no mirror → integrity-ok, honest copy", async ({ context, extensionId }) => {
  const page = await openPopup(context, extensionId, `${BROKER}/integrity/deal.pdf`);
  await expect(page.locator(".badge")).toHaveClass(/badge-integrity-ok/);
  const text = (await page.locator("#app").innerText()).toLowerCase();
  for (const w of ["authentic", "genuine", "official"]) expect(text).not.toContain(w);
});

test("tampered payload → hash-mismatch, no card", async ({ context, extensionId }) => {
  const page = await openPopup(context, extensionId, `${BROKER}/tampered/deal.pdf`);
  await expect(page.locator(".badge")).toHaveClass(/badge-hash-mismatch/);
  await expect(page.locator(".card")).toHaveCount(0);
});

test("plain PDF → absent", async ({ context, extensionId }) => {
  const page = await openPopup(context, extensionId, `${BROKER}/plain/deal.pdf`);
  await expect(page.locator(".badge")).toHaveClass(/badge-absent/);
});

test("stale mirror → integrity/origin held + OMW-W051 notice", async ({ context, extensionId }) => {
  const page = await openPopup(context, extensionId, `${BROKER}/stale/deal.pdf`);
  await expect(page.locator(".badge")).toHaveClass(/badge-integrity-ok/);
  await expect(page.locator(".stale")).toBeVisible();
});

test("rehosted to another domain (no mirror) degrades gracefully to integrity-ok", async ({
  context,
  extensionId,
}) => {
  const page = await openPopup(context, extensionId, `${ATTACKER}/integrity/deal.pdf`);
  await expect(page.locator(".badge")).toHaveClass(/badge-integrity-ok/);
});

test("publish test-fire → receiver validates the HMAC signature", async ({ context, extensionId }) => {
  const page = await openPopup(context, extensionId, `${BROKER}/valid/deal.pdf`);
  await page.fill("input.wh-target", `${BROKER}/hook`);
  await page.fill("input.wh-secret", "test-secret");
  await page.click('[data-action="test-fire"]');
  await expect(page.locator(".status")).toContainText("200");

  // The browser-side POST hit broker.example.com (host-resolver-mapped to 127.0.0.1); read the
  // receiver's record over loopback directly - Playwright's Node request context does NOT honor the
  // browser's --host-resolver-rules, so the hostname wouldn't resolve here.
  const check = await page.request.get("https://127.0.0.1:8443/last-hook", {
    ignoreHTTPSErrors: true,
  });
  expect((await check.json()).valid).toBe(true);
});
