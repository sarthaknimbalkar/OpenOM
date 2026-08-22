// @vitest-environment jsdom
import { describe, expect, test, vi, beforeEach } from "vitest";
// The embeddable badge element lives in /js/widget; tested here because the extension package already
// has a jsdom vitest environment. [B1] precomputed `state=` must render with zero network fetch.
import { defineOpenOmBadge, OpenOmBadgeElement } from "../../../js/widget/openom-badge.js";
import { clearBadgeCache } from "../../../js/widget/badge-core.js";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

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

  test("[polish] dispatches openom:state after render (host observability)", async () => {
    const badge = new OpenOmBadgeElement();
    const events: Array<{ state: string; present: boolean }> = [];
    badge.addEventListener("openom:state", (e) =>
      events.push((e as CustomEvent).detail as { state: string; present: boolean }),
    );
    badge.setAttribute("state", "integrity-ok");
    document.body.appendChild(badge);
    await Promise.resolve();
    expect(events).toContainEqual(expect.objectContaining({ state: "integrity-ok", present: true }));
  });

  test("[polish] the badge carries part=badge for ::part() theming", async () => {
    const badge = new OpenOmBadgeElement();
    badge.setAttribute("state", "integrity-ok");
    document.body.appendChild(badge);
    await Promise.resolve();
    expect(badge.shadowRoot?.querySelector('[part="badge"]')).not.toBeNull();
  });

  test("[polish] a details-only change repaints the cached view WITHOUT re-fetching", async () => {
    clearBadgeCache();
    const here = dirname(fileURLToPath(import.meta.url));
    const pdf = new Uint8Array(
      readFileSync(join(here, "..", "..", "..", "spec", "assets", "openom-sample.pdf")),
    );
    let fetches = 0;
    (globalThis as { fetch?: unknown }).fetch = async () => {
      fetches++;
      return new Response(pdf, { status: 200 });
    };
    const badge = new OpenOmBadgeElement();
    badge.setAttribute("src", "https://p.example.com/deal.pdf"); // no IntersectionObserver in jsdom → immediate
    document.body.appendChild(badge);
    await new Promise((r) => setTimeout(r, 0));
    expect(fetches).toBe(1);
    badge.setAttribute("details", "https://p.example.com/listing"); // details-only change
    await new Promise((r) => setTimeout(r, 0));
    expect(fetches).toBe(1); // repainted from cache, no second fetch
  });
});
