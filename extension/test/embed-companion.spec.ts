import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// The committed regression gate for the zero-install broker surfaces (#B1/#B2): the hosted authoring
// companion at /embed/ and the /verify URL tool, driven in a real headless browser against the
// committed site/ tree. This is the proof that "drop OM -> fill -> assert -> download a valid openOM"
// works end to end (round-trip, reprice, encrypted-OM decrypt) - and stays working.
const here = dirname(fileURLToPath(import.meta.url));
const fx = (p: string): string => resolve(here, "harness/fixtures", p);
const SAMPLE = resolve(here, "..", "..", "spec", "assets", "openom-sample.pdf");

/** In-page: capture the embedded blob instead of downloading, and load the read/verify bundle. */
async function armCaptureAndReader(page: import("@playwright/test").Page): Promise<void> {
  await page.evaluate(async () => {
    const w = window as unknown as { __blob?: Blob };
    const origCreate = URL.createObjectURL.bind(URL);
    URL.createObjectURL = (b: Blob) => {
      w.__blob = b;
      return origCreate(b);
    };
    HTMLAnchorElement.prototype.click = function () {};
    await new Promise<void>((res, rej) => {
      const s = document.createElement("script");
      s.src = "/widget/openom-badge.js";
      s.onload = () => res();
      s.onerror = () => rej(new Error("badge load"));
      document.head.appendChild(s);
    });
  });
}

async function readBack(page: import("@playwright/test").Page): Promise<Record<string, unknown>> {
  return page.evaluate(async () => {
    const w = window as unknown as {
      __blob?: Blob;
      openOM: { readPayloadFromBytes: (b: Uint8Array) => Promise<Record<string, unknown>> };
    };
    for (let i = 0; i < 80 && !w.__blob; i++) await new Promise((r) => setTimeout(r, 50));
    const out = new Uint8Array(await (w.__blob as Blob).arrayBuffer());
    const r = (await w.openOM.readPayloadFromBytes(out)) as {
      state: string;
      verification: { hashValid: boolean };
      payload: Record<string, unknown> | null;
    };
    const deal = (r.payload?.deal ?? {}) as Record<string, unknown>;
    const meta = (r.payload?.meta ?? {}) as Record<string, unknown>;
    return {
      state: r.state,
      hashValid: r.verification.hashValid,
      askingPrice: deal.askingPrice ?? null,
      assertedDate: r.payload?.assertedDate ?? null,
      supersedes: meta.supersedes ?? null,
    };
  });
}

test.describe("hosted authoring companion (/embed/)", () => {
  test("round-trip + reprice: sample OM -> edit -> assert -> valid embedded OM", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto("/embed/");
    await page.waitForFunction(() => Boolean((window as { openOMAuthor?: unknown }).openOMAuthor));
    await armCaptureAndReader(page);

    await page.setInputFiles("#om-file", SAMPLE);
    await expect(page.locator(".author-reprice")).toContainText(/reprice/i);
    await expect(page.locator("#author-status")).toContainText(/Ready to embed/i);
    // A human recap is shown (legibility), not just JSON pointers.
    await expect(page.locator(".author-recap")).toContainText(/You are asserting/i);

    // Edit the asking price via its labeled control, then assert.
    const price = page.locator("label", { hasText: /Asking Price/i }).locator("input");
    await price.fill("1234567");
    await page.locator("#author-assert").click();

    const r = await readBack(page);
    expect(r.state).toBe("present");
    expect(r.hashValid).toBe(true);
    expect(r.askingPrice).toBe(1234567);
    expect(String(r.assertedDate)).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(String(r.supersedes)).toContain("sha256:"); // reprice recorded
    expect(errors, errors.join(" | ")).toEqual([]);
  });

  test("encrypted OM: empty-password AES is decrypted in-browser, then embeds", async ({ page }) => {
    await page.goto("/embed/");
    await page.waitForFunction(() => Boolean((window as { openOMAuthor?: unknown }).openOMAuthor));
    await armCaptureAndReader(page);

    await page.setInputFiles("#om-file", fx("author/encrypted.pdf"));
    await expect(page.locator(".author-reprice")).toContainText(/decrypted in your browser/i);
    // Fill the required assertion identity (a fresh, unencrypted-source assertion).
    await page.locator("label", { hasText: "Broker name" }).locator("input").fill("Jane Broker");
    await page.locator("label", { hasText: "Brokerage" }).locator("input").fill("Example Realty");
    await page.locator("label", { hasText: "License #" }).locator("input").fill("RE-1");
    // noiType/noiAsOfDate for a consistent, schema-valid assertion.
    await page.locator("label", { hasText: /Noi Type/i }).locator("select").selectOption("pro-forma");
    await page.locator("label", { hasText: /Noi As Of Date/i }).locator("input").fill("2026-08-22");
    await expect(page.locator("#author-status")).toContainText(/Ready to embed/i);
    await page.locator("#author-assert").click();

    const r = await readBack(page);
    expect(r.state).toBe("present");
    expect(r.hashValid).toBe(true);
  });

  test("[M1] signed OM: Assert is blocked until the invalidation is acknowledged", async ({
    page,
  }) => {
    await page.goto("/embed/");
    await page.waitForFunction(() => Boolean((window as { openOMAuthor?: unknown }).openOMAuthor));
    await armCaptureAndReader(page);

    await page.setInputFiles("#om-file", fx("author/signed.pdf"));
    await expect(page.locator(".author-warnings")).toContainText(/digitally signed/i);
    await page.locator("label", { hasText: "Broker name" }).locator("input").fill("Jane Broker");
    await page.locator("label", { hasText: "Brokerage" }).locator("input").fill("Example Realty");
    await page.locator("label", { hasText: "License #" }).locator("input").fill("RE-1");
    await page.locator("label", { hasText: /Noi Type/i }).locator("select").selectOption("pro-forma");
    await page.locator("label", { hasText: /Noi As Of Date/i }).locator("input").fill("2026-08-22");
    // No schema errors, but Assert stays disabled until the signature ack.
    await expect(page.locator("#author-assert")).toBeDisabled();
    await page.locator("#signed-ack").check();
    await expect(page.locator("#author-assert")).toBeEnabled();
    await page.locator("#author-assert").click();
    const r = await readBack(page);
    expect(r.state).toBe("present");
    expect(r.hashValid).toBe(true);
  });

  test("no accessibility violations (WCAG 2 A/AA) with the editor open", async ({ page }) => {
    await page.goto("/embed/");
    await page.waitForFunction(() => Boolean((window as { openOMAuthor?: unknown }).openOMAuthor));
    await page.setInputFiles("#om-file", SAMPLE);
    await expect(page.locator("#author-assert")).toBeVisible();
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
  });
});

test.describe("[M3] shareable verified view (/v/)", () => {
  test("renders the badge + deal card for a same-origin OM", async ({ page }) => {
    await page.goto("/v/?src=/sample/openom-sample.pdf");
    await page.waitForFunction(() => Boolean((window as { openOM?: unknown }).openOM));
    await expect(page.locator("#vv-badge")).toContainText(/Unaltered since embed/i, {
      timeout: 10_000,
    });
    await expect(page.locator(".vv-deal")).toContainText(/Asking price|Cap rate|Property/i);
    await expect(page.locator(".vv-actions a")).toContainText(/Download the OM/i);
  });

  test("no src → explains it's a shareable link (no scary state)", async ({ page }) => {
    await page.goto("/v/");
    await page.waitForFunction(() => Boolean((window as { openOM?: unknown }).openOM));
    await expect(page.locator("#vv-status")).toContainText(/shareable verified-view link/i);
  });
});

test.describe("[M3] companion share-link helper", () => {
  test("after embed, pasting the hosted URL yields a copyable /v/ link", async ({ page }) => {
    await page.goto("/embed/");
    await page.waitForFunction(() => Boolean((window as { openOMAuthor?: unknown }).openOMAuthor));
    await armCaptureAndReader(page);
    await page.setInputFiles("#om-file", SAMPLE);
    await expect(page.locator("#author-assert")).toBeEnabled();
    await page.locator("#author-assert").click();
    await expect(page.locator(".author-share")).toBeVisible();
    await page.locator(".author-share input").fill("https://listings.example.com/deal.pdf");
    await expect(page.locator(".author-share-out a")).toHaveAttribute(
      "href",
      /\/v\/\?src=https%3A%2F%2Flistings\.example\.com%2Fdeal\.pdf/,
    );
  });
});

test.describe("verify URL tool (/verify/)", () => {
  test("checks a same-origin PDF URL and reports its state", async ({ page }) => {
    await page.goto("/verify/");
    await page.waitForFunction(() => Boolean((window as { openOM?: unknown }).openOM));
    await page.locator("#u").fill("/sample/openom-sample.pdf");
    await page.locator("#ub").click();
    await expect(page.locator("#badge")).toContainText(/Unaltered since embed/i, { timeout: 10_000 });
  });

  test("a bad URL fails honestly (never a scary verdict)", async ({ page }) => {
    await page.goto("/verify/");
    await page.waitForFunction(() => Boolean((window as { openOM?: unknown }).openOM));
    await page.locator("#u").fill("/no/such/file.pdf");
    await page.locator("#ub").click();
    await expect(page.locator("#badge")).toContainText(/Couldn't fetch that URL/i, { timeout: 10_000 });
  });
});
