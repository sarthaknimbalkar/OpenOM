// @vitest-environment jsdom
import { describe, expect, test, vi, beforeEach } from "vitest";
// The embeddable badge element lives in /js/widget; tested here because the extension package already
// has a jsdom vitest environment. [B1] precomputed `state=` must render with zero network fetch.
import { defineOpenOmBadge, OpenOmBadgeElement } from "../../../js/widget/openom-badge.js";

defineOpenOmBadge();

describe("<openom-badge> precomputed state ([B1] zero-fetch for list pages)", () => {
  beforeEach(() => {
    document.body.replaceChildren();
    vi.restoreAllMocks();
  });

  test("state=integrity-ok renders the pill WITHOUT any network fetch", async () => {
    const fetchSpy = vi.fn();
    (globalThis as { fetch?: unknown }).fetch = fetchSpy;
    const badge = new OpenOmBadgeElement();
    badge.setAttribute("state", "integrity-ok");
    document.body.appendChild(badge);
    await Promise.resolve();
    expect(badge.shadowRoot?.textContent ?? "").toContain("Unaltered since embed");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  test("origin-verified precomputed state shows the strong verified label", async () => {
    const badge = new OpenOmBadgeElement();
    badge.setAttribute("state", "origin-verified");
    document.body.appendChild(badge);
    await Promise.resolve();
    expect(badge.shadowRoot?.textContent ?? "").toMatch(/verified/i);
  });

  test("unknown/absent state renders nothing (no false reassurance)", async () => {
    const badge = new OpenOmBadgeElement();
    badge.setAttribute("state", "garbage");
    document.body.appendChild(badge);
    await Promise.resolve();
    expect((badge.shadowRoot?.textContent ?? "").trim()).toBe("");
  });
});
