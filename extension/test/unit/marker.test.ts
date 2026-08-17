// @vitest-environment jsdom
import { describe, expect, test } from "vitest";
import { markerFor } from "../../src/content/marker.js";

describe("markerFor (#69) — honest link badge", () => {
  test("no marker for absent / signature-verified (never overclaim §AA)", () => {
    expect(markerFor("absent")).toBeNull();
    expect(markerFor("signature-verified")).toBeNull();
  });

  test("origin-verified → ✓✓ pill with state + accessible name", () => {
    const m = markerFor("origin-verified")!;
    expect(m.hasAttribute("data-openom-marker")).toBe(true);
    expect(m.getAttribute("data-state")).toBe("origin-verified");
    expect(m.getAttribute("role")).toBe("img");
    expect((m.getAttribute("aria-label") ?? "").toLowerCase()).toContain("origin");
    expect(m.textContent).toContain("✓✓");
  });

  test("integrity-ok → single ✓; hash-mismatch → warning with its state", () => {
    expect(markerFor("integrity-ok")!.textContent).toContain("✓");
    const bad = markerFor("hash-mismatch")!;
    expect(bad.getAttribute("data-state")).toBe("hash-mismatch");
    expect(bad.textContent).toContain("⚠");
  });
});
