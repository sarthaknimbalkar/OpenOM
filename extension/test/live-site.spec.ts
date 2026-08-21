import { expect, test } from "@playwright/test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// Live post-deploy smoke: drive the DEPLOYED /verify/ tool in a real browser and confirm the three
// openOM states read correctly with ZERO console errors. Catches what local unit/gate tests can't:
// an un-deployed widget bundle (404), or a browser-only runtime error like the node:zlib import.
const BASE = (process.env.OPENOM_LIVE_BASE ?? "https://openom.app").replace(/\/$/, "");
const here = dirname(fileURLToPath(import.meta.url));
const fx = (p: string): string => resolve(here, "harness/fixtures", p);

test.describe("live: deployed origin", () => {
  test("/verify/ reads valid / plain / tampered with no console errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    page.on("pageerror", (e) => errors.push(String(e)));

    await page.goto(`${BASE}/verify/`);
    await page.waitForFunction(() => Boolean((window as unknown as { openOM?: unknown }).openOM), {
      timeout: 15_000,
    });

    const cases: Array<[string, RegExp]> = [
      ["valid/deal.pdf", /Unaltered since embed/i],
      ["plain/deal.pdf", /No openOM data/i],
      ["tampered/deal.pdf", /Altered payload|does not match its hash/i],
    ];
    for (const [rel, expected] of cases) {
      await page.setInputFiles("#f", fx(rel));
      await expect(page.locator("#badge")).toContainText(expected, { timeout: 10_000 });
    }
    expect(errors, `unexpected console errors: ${errors.join(" | ")}`).toEqual([]);
  });

  test("core pages + assets resolve 200 on the live origin", async ({ page }) => {
    const paths = [
      "/",
      "/docs/",
      "/verify/",
      "/docs/what-is-an-offering-memorandum",
      "/widget/openom-badge.js",
      "/favicon.ico",
      "/og.png",
      "/robots.txt",
      "/sitemap.xml",
      "/llms.txt",
      "/ns/0.1",
      "/spec/om-0.1.schema.json",
    ];
    for (const p of paths) {
      const r = await page.request.get(`${BASE}${p}`);
      expect(r.status(), `${p} status`).toBe(200);
    }
  });
});
