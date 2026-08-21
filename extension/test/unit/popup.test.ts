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
    expect(root.querySelectorAll("button[data-action]").length).toBe(4); // test-fire, publish, copy, download
    expect(root.querySelector("input.wh-target")).not.toBeNull();
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
