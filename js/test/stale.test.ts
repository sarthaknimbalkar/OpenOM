import { describe, expect, test } from "vitest";
import { classifyStale } from "../src/stale.js";

describe("classifyStale ([M2] OMW-W051) - single source for SW + badge + verify", () => {
  const base = { embeddedHash: "sha256:A", embeddedPayload: { assertedDate: "2026-01-01" } };

  test("equal hashes → not stale", () => {
    expect(classifyStale({ ...base, mirrorHash: "sha256:A", mirrorPayload: {} }).stale).toBe(false);
  });

  test("mirror explicitly supersedes the embedded hash → stale", () => {
    const r = classifyStale({
      ...base,
      mirrorHash: "sha256:B",
      mirrorPayload: { assertedDate: "2026-01-01", meta: { supersedes: "sha256:A" } },
    });
    expect(r).toMatchObject({ stale: true, code: "OMW-W051" });
  });

  test("mirror asserts strictly later → stale, carries the mirror date", () => {
    const r = classifyStale({
      ...base,
      mirrorHash: "sha256:B",
      mirrorPayload: { assertedDate: "2026-06-01" },
    });
    expect(r).toMatchObject({ stale: true, code: "OMW-W051", mirrorAssertedDate: "2026-06-01" });
  });

  test("different hash but neither newer nor superseding → NOT stale (a genuine mismatch)", () => {
    const r = classifyStale({
      ...base,
      mirrorHash: "sha256:B",
      mirrorPayload: { assertedDate: "2025-01-01" },
    });
    expect(r.stale).toBe(false);
  });
});
