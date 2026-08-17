import { type BrowserContext, type Page } from "@playwright/test";
import { expect, test } from "./fixtures.js";
import { readPayloadFromBytes } from "../../js/src/index.js";
import { readFileSync } from "node:fs";

const BROKER = "https://broker.example.com:8443";

// The panel document is a plain extension page; the live gate drives it via the ?url= deep-link
// (same pattern the consumer popup uses) rather than the OS side panel — a faithful, hermetic path.
async function openPanel(
  context: BrowserContext,
  extensionId: string,
  targetUrl: string,
): Promise<Page> {
  const page = await context.newPage();
  await page.goto(
    `chrome-extension://${extensionId}/sidepanel.html?url=${encodeURIComponent(targetUrl)}`,
  );
  await page.waitForSelector(".p-broker", { timeout: 20_000 }); // review workspace ready
  return page;
}

async function fillProfile(page: Page): Promise<void> {
  await page.fill(".p-broker", "Jane Broker");
  await page.fill(".p-brokerage", "Acme CRE");
  await page.fill(".p-license", "CA-01234567");
}

async function readDownloadedPayload(page: Page) {
  const dl = await page.waitForEvent("download");
  const path = await dl.path();
  return readPayloadFromBytes(new Uint8Array(readFileSync(path)));
}

test("fresh embed → produced OM carries the asserted payload", async ({
  context,
  extensionId,
}) => {
  const page = await openPanel(
    context,
    extensionId,
    `${BROKER}/author/plain.pdf`,
  );
  await fillProfile(page);
  await expect(page.locator("#assert")).toBeEnabled();
  await page.click("#assert");

  const read = await readDownloadedPayload(page);
  expect(read.state).toBe("present");
  expect(read.verification.hashValid).toBe(true);
  const p = read.payload as Record<string, Record<string, unknown>>;
  expect(p.assertedBy.broker).toBe("Jane Broker");
  const now = new Date(); // assertedDate is the broker's LOCAL calendar date (#64), not UTC
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  expect(p.assertedDate).toBe(today);
});

test("[#4] encrypted OM → decrypted in-browser, notice shown, embed produces a readable payload", async ({
  context,
  extensionId,
}) => {
  const page = await openPanel(
    context,
    extensionId,
    `${BROKER}/author/encrypted.pdf`,
  );
  // The panel decrypted the empty-password AES OM in-browser and built the form (not the #107 refuse).
  await expect(page.locator(".decrypted-notice")).toContainText(
    "permission-encrypted",
  );
  await fillProfile(page);
  await expect(page.locator("#assert")).toBeEnabled();
  await page.click("#assert");

  const read = await readDownloadedPayload(page);
  expect(read.state).toBe("present");
  expect(read.verification.hashValid).toBe(true);
  const p = read.payload as Record<string, Record<string, unknown>>;
  expect(p.assertedBy.broker).toBe("Jane Broker");
});

test("assert-gated → a schema-invalid draft disables Assert until fixed", async ({
  context,
  extensionId,
}) => {
  const page = await openPanel(
    context,
    extensionId,
    `${BROKER}/author/plain.pdf`,
  );
  await fillProfile(page);
  await expect(page.locator("#assert")).toBeEnabled();
  // currency must match ^[A-Z]{3}$; finalize does not overwrite it, so the schema error survives.
  await page.locator(".advanced summary").click(); // open the raw-JSON editor (now collapsed)
  await page.fill(".draft-json", JSON.stringify({ currency: "usd" }));
  await page.locator(".draft-json").blur(); // fire change → rebuild + revalidate
  await expect(page.locator("#assert")).toBeDisabled();
});

test("reprice → new payload supersedes the prior hash, one om.json remains", async ({
  context,
  extensionId,
}) => {
  const page = await openPanel(
    context,
    extensionId,
    `${BROKER}/author/embedded.pdf`,
  );
  await fillProfile(page);
  await page.locator(".advanced summary").click(); // open the raw-JSON editor
  const seed = JSON.parse(await page.inputValue(".draft-json"));
  const priorHash = (
    await readPayloadFromBytes(
      new Uint8Array(
        readFileSync(
          new URL("./harness/fixtures/author/embedded.pdf", import.meta.url),
        ),
      ),
    )
  ).payloadHash;
  seed.deal.askingPrice = Number(seed.deal.askingPrice) + 500;
  await page.fill(".draft-json", JSON.stringify(seed));
  await page.locator(".draft-json").blur();
  await expect(page.locator(".reprice-diff")).toBeVisible();
  await page.click("#assert");

  const read = await readDownloadedPayload(page);
  expect(read.state).toBe("present");
  const meta = (read.payload as Record<string, Record<string, unknown>>).meta;
  expect(meta.supersedes).toBe(priorHash);
});

// ---- M5b-2: on-device extraction. A FAKE LanguageModel global (injected before load) exercises the
// REAL on-device.ts adapter — the actual Gemini Nano model cannot run in CI Chromium, so the gate
// proves the ARCHITECTURE (egress-zero + pre-fill), never a real model. Surfaced, not faked. ----
const FAKE_MODEL = () => {
  (globalThis as unknown as { LanguageModel: unknown }).LanguageModel = {
    create: async () => ({
      prompt: async () =>
        JSON.stringify({
          fields: [
            {
              path: "/deal/capRate",
              value: 0.0575,
              evidence: { page: 1, quote: "Cap Rate: 5.75%" },
            },
          ],
        }),
    }),
  };
};

test("[OM-PRIV-001] extraction makes ZERO network requests leave the device", async ({
  context,
  extensionId,
}) => {
  await context.addInitScript(FAKE_MODEL);
  let offDevice = 0;
  await context.route("**", (route) => {
    if (!route.request().url().startsWith("chrome-extension://")) offDevice++;
    return route.continue();
  });
  const page = await openPanel(
    context,
    extensionId,
    `${BROKER}/author/text.pdf`,
  );
  offDevice = 0; // count only during extraction, not the panel/fixture load
  await page.click(".extract-btn");
  await expect(page.locator('input[data-path="/deal/capRate"]')).toHaveValue(
    "0.0575",
  ); // extraction ran
  expect(offDevice).toBe(0);
});

test("on-device extraction pre-fills the review, then the human asserts", async ({
  context,
  extensionId,
}) => {
  await context.addInitScript(FAKE_MODEL);
  const page = await openPanel(
    context,
    extensionId,
    `${BROKER}/author/text.pdf`,
  );
  await page.click(".extract-btn");
  await expect(page.locator('input[data-path="/deal/capRate"]')).toHaveValue(
    "0.0575",
  ); // form pre-filled
  await expect(page.locator(".field-evidence").first()).toBeVisible(); // evidence controls present
  await fillProfile(page);
  await expect(page.locator("#assert")).toBeEnabled();
  await page.click("#assert");
  const read = await readDownloadedPayload(page);
  const p = read.payload as Record<string, Record<string, unknown>>;
  expect(read.state).toBe("present");
  expect(p.deal.capRate).toBe(0.0575);
  expect(p.assertedBy.broker).toBe("Jane Broker");
});

// ---- form-driven coverage (#77 #93 #95) ----
test("#93 noiType/noiAsOfDate controls appear once deal.noi is entered", async ({
  context,
  extensionId,
}) => {
  const page = await openPanel(
    context,
    extensionId,
    `${BROKER}/author/plain.pdf`,
  );
  await expect(page.locator('[data-path="/deal/noiType"]')).toHaveCount(0);
  await page.fill('input[data-path="/deal/noi"]', "431250");
  await expect(page.locator('select[data-path="/deal/noiType"]')).toBeVisible();
});

test("editing core fields via the form → assert → read-back", async ({
  context,
  extensionId,
}) => {
  const page = await openPanel(
    context,
    extensionId,
    `${BROKER}/author/plain.pdf`,
  );
  await fillProfile(page);
  await page.fill('input[data-path="/deal/capRate"]', "0.06");
  await page.fill(
    'input[data-path="/property/address/streetAddress"]',
    "1000 Example Rd",
  );
  await expect(page.locator("#assert")).toBeEnabled();
  await page.click("#assert");
  const read = await readDownloadedPayload(page);
  const p = read.payload as Record<string, Record<string, unknown>>;
  expect(p.deal.capRate).toBe(0.06);
  expect((p.property.address as Record<string, unknown>).streetAddress).toBe(
    "1000 Example Rd",
  );
});

test("#95 adding a rent-schedule row shows it in the finalized preview", async ({
  context,
  extensionId,
}) => {
  const page = await openPanel(
    context,
    extensionId,
    `${BROKER}/author/plain.pdf`,
  );
  await page.click(".add-rent");
  await page.fill(
    'input[data-path="/lease/rentSchedule/0/annualRent"]',
    "123456",
  );
  await expect(page.locator(".finalized-preview")).toContainText("123456");
});
