import { describe, expect, test } from "vitest";
import { classifyStale } from "../../src/stale.js";

const EMB = { assertedDate: "2026-06-15", meta: { supersedes: null } };

describe("classifyStale — OMW-W051 [OM-TRUST-009]", () => {
  test("equal hashes → not stale", () => {
    expect(
      classifyStale({ embeddedHash: "sha256:a", mirrorHash: "sha256:a", embeddedPayload: EMB, mirrorPayload: EMB }),
    ).toEqual({ stale: false });
  });

  test("mirror asserts later → stale (OMW-W051), badge not downgraded", () => {
    const mirror = { assertedDate: "2026-09-01", meta: { supersedes: "sha256:emb" } };
    const r = classifyStale({
      embeddedHash: "sha256:emb",
      mirrorHash: "sha256:new",
      embeddedPayload: EMB,
      mirrorPayload: mirror,
    });
    expect(r).toEqual({ stale: true, code: "OMW-W051", mirrorAssertedDate: "2026-09-01" });
  });

  test("mirror supersedes our hash even without a newer date → stale", () => {
    const mirror = { assertedDate: "2026-06-15", meta: { supersedes: "sha256:emb" } };
    const r = classifyStale({
      embeddedHash: "sha256:emb",
      mirrorHash: "sha256:new",
      embeddedPayload: EMB,
      mirrorPayload: mirror,
    });
    expect(r.stale).toBe(true);
    expect(r.code).toBe("OMW-W051");
  });

  test("different hash but mirror is older/unrelated → NOT stale (real mismatch)", () => {
    const mirror = { assertedDate: "2026-01-01", meta: { supersedes: null } };
    expect(
      classifyStale({
        embeddedHash: "sha256:emb",
        mirrorHash: "sha256:other",
        embeddedPayload: EMB,
        mirrorPayload: mirror,
      }),
    ).toEqual({ stale: false });
  });

  test("mirror unreachable (null) with differing hash → not stale", () => {
    expect(
      classifyStale({ embeddedHash: "sha256:emb", mirrorHash: "sha256:x", embeddedPayload: EMB, mirrorPayload: null }),
    ).toEqual({ stale: false });
  });
});
