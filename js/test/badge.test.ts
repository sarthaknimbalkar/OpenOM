import { describe, expect, test } from "vitest";
import { badgeState, FORBIDDEN, honestLabel } from "../src/badge.js";

describe("badgeState — §AA strict precedence [OM-TRUST-001/002]", () => {
  test("absent when no payload", () => {
    expect(
      badgeState({ present: false, hashValid: null, originVerified: false, signatureValid: null }),
    ).toBe("absent");
  });

  test("hash-mismatch is terminal (ignores origin)", () => {
    expect(
      badgeState({ present: true, hashValid: false, originVerified: true, signatureValid: null }),
    ).toBe("hash-mismatch");
  });

  test("integrity-ok: hash passes, origin not verified", () => {
    expect(
      badgeState({ present: true, hashValid: true, originVerified: false, signatureValid: null }),
    ).toBe("integrity-ok");
  });

  test("origin-verified: hash passes AND origin verified", () => {
    expect(
      badgeState({ present: true, hashValid: true, originVerified: true, signatureValid: null }),
    ).toBe("origin-verified");
  });

  test("signature-verified is never returned in 0.1", () => {
    for (const sig of [true, false, null] as const) {
      const s = badgeState({
        present: true,
        hashValid: true,
        originVerified: true,
        signatureValid: sig,
      });
      expect(s).not.toBe("signature-verified");
    }
  });
});

describe("honestLabel — UI-honesty [OM-TRUST-003]", () => {
  test("integrity-only copy uses no forbidden word", () => {
    const { label, caption } = honestLabel("integrity-ok");
    const text = `${label} ${caption}`.toLowerCase();
    for (const word of FORBIDDEN) {
      expect(new RegExp(`\\b${word}\\b`).test(text)).toBe(false);
    }
    expect(text).toContain("unaltered"); // permitted framing
  });

  test("every state has a label + caption", () => {
    for (const s of ["absent", "hash-mismatch", "integrity-ok", "origin-verified"] as const) {
      const { label, caption } = honestLabel(s);
      expect(label.length).toBeGreaterThan(0);
      expect(caption.length).toBeGreaterThan(0);
    }
  });
});
