// @vitest-environment jsdom
import { describe, expect, test } from "vitest";
import { FORBIDDEN } from "openom-js";
import { renderPopup } from "../../src/popup/popup.js";
import type { DetectResult } from "../../src/service-worker.js";

const PAYLOAD = {
  assertedBy: { broker: "Dana Sample" },
  property: { address: { streetAddress: "500 Example Blvd", addressLocality: "Testville", addressRegion: "TX" } },
  deal: { askingPrice: 2500000, capRate: 0.0575, noiType: "in-place" },
  lease: {
    tenantEntity: "Placeholder Quick Service, LLC",
    leaseTypeAsserted: "NNN",
    rentSchedule: [{ periodStart: "2021-06-01", periodEnd: "2026-05-31", annualRent: 143750, source: "asserted" }],
  },
};

const base = {
  sourceUrl: "https://broker.example.com/deal.pdf",
  payloadHash: "sha256:" + "a".repeat(64),
  verification: { hashValid: true, originVerified: false, signatureValid: null as null },
};

function render(result: Omit<DetectResult, keyof typeof base> & Partial<DetectResult>): HTMLElement {
  const root = document.createElement("div");
  renderPopup(root, { ...base, ...result } as DetectResult, null);
  return root;
}

describe("renderPopup", () => {
  test("integrity-ok: shows the card, no forbidden word, publish controls present", () => {
    const root = render({
      state: "integrity-ok",
      label: "Unaltered since embed",
      caption: "Integrity checks out; origin not yet confirmed. Not proof of authorship.",
      payload: PAYLOAD,
      findings: [],
    });
    const text = root.textContent!.toLowerCase();
    for (const w of FORBIDDEN) expect(new RegExp(`\\b${w}\\b`).test(text)).toBe(false);
    expect(text).toContain("500 example blvd");
    expect(text).toContain("[asserted]"); // rent period source tag
    expect(root.querySelectorAll("button[data-action]").length).toBe(4); // test-fire, send, copy, download
    expect(root.querySelector("input.wh-target")).not.toBeNull();
    // [M3] the webhook is framed as an advanced developer integration, not buyer "Publish".
    const publish = root.querySelector("details.publish");
    expect(publish).not.toBeNull();
    expect(publish!.querySelector("summary")!.textContent!.toLowerCase()).toContain("webhook");
    const labels = [...root.querySelectorAll("button[data-action]")].map((b) => b.textContent);
    expect(labels).toContain("Send"); // relabeled from the misleading "Publish"
    expect(labels).not.toContain("Publish");
  });

  test("[M3] card shows assertion metadata + formatted numbers; notices show messages", () => {
    const root = render({
      state: "integrity-ok",
      label: "Unaltered since embed",
      caption: "Integrity checks out; origin not yet confirmed.",
      payload: { ...PAYLOAD, assertedDate: "2026-05-31", deal: { ...PAYLOAD.deal, noi: 143750, noiAsOfDate: "2026-03-31" } },
      findings: ["OMW-W020"],
      notices: [{ code: "OMW-W020", message: "cap rate vs NOI/price is off", severity: "warning", path: "/deal" }],
    });
    const text = root.textContent!;
    expect(text).toContain("$2,500,000"); // formatted, not 2500000
    expect(text).toContain("5.75%"); // cap rate as %, not 0.0575
    expect(text).toMatch(/in-place/); // noiType surfaced
    expect(text).toContain("as of 2026-03-31"); // noiAsOfDate surfaced
    expect(text).toContain("2026-05-31"); // assertedDate surfaced
    expect(text).toContain("cap rate vs NOI/price is off (OMW-W020)"); // message, not bare code
  });

  test("origin-verified: shows the domain-vouch caption + card", () => {
    const root = render({
      state: "origin-verified",
      label: "Origin-verified",
      caption: "This domain vouches for this exact payload (HTTPS + matching mirror).",
      payload: PAYLOAD,
      findings: [],
    });
    expect(root.textContent).toContain("domain vouches");
    expect(root.querySelector(".card")).not.toBeNull();
  });

  test("hash-mismatch: warning shown, no card", () => {
    const root = render({
      state: "hash-mismatch",
      label: "Altered payload",
      caption: "The embedded data does not match its hash - do not trust it.",
      payload: null,
      findings: [],
    });
    expect(root.textContent).toContain("does not match");
    expect(root.querySelector(".card")).toBeNull();
  });

  test("stale: shows the OMW-W051 notice while keeping the card", () => {
    const root = render({
      state: "integrity-ok",
      label: "Unaltered since embed",
      caption: "…",
      payload: PAYLOAD,
      findings: ["OMW-W051"],
      stale: "OMW-W051",
    });
    expect(root.querySelector(".stale")).not.toBeNull();
    expect(root.querySelector(".card")).not.toBeNull();
  });
});

describe("profile discoverability (a reviewer: 'settable profile')", () => {
  test("the popup shows a Settings link to the broker profile", () => {
    const root = render({ state: "integrity-ok", label: "openOM", caption: "unaltered", findings: [], payload: PAYLOAD } as never);
    const s = root.querySelector(".open-settings");
    expect(s).not.toBeNull();
    expect(s?.textContent).toContain("broker profile");
  });
});
