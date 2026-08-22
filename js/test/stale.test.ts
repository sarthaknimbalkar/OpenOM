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

  test("[polish] compares dates, not strings (datetime mirror still detected as newer)", () => {
    // Lexicographically "2026-06-01T00:00:00Z" > "2026-01-01" too, but a datetime for OURS would break
    // a naive compare; verify real date parsing on both sides.
    const r = classifyStale({
      embeddedHash: "sha256:A",
      embeddedPayload: { assertedDate: "2026-01-01T09:00:00Z" },
      mirrorHash: "sha256:B",
      mirrorPayload: { assertedDate: "2026-06-01" },
    });
    expect(r).toMatchObject({ stale: true, code: "OMW-W051" });
  });

  test("[polish] a malformed mirror date falls back to the supersedes branch, not a false 'not stale'", () => {
    // Malformed date → date branch skipped; supersedes still catches it.
    const r = classifyStale({
      embeddedHash: "sha256:A",
      embeddedPayload: { assertedDate: "2026-01-01" },
      mirrorHash: "sha256:B",
      mirrorPayload: { assertedDate: "not-a-date", meta: { supersedes: "sha256:A" } },
    });
    expect(r.stale).toBe(true);
    // And with neither a valid newer date nor a supersede, it stays not-stale (no string-quirk downgrade).
    const r2 = classifyStale({
      embeddedHash: "sha256:A",
      embeddedPayload: { assertedDate: "2026-01-01" },
      mirrorHash: "sha256:B",
      mirrorPayload: { assertedDate: "not-a-date" },
    });
    expect(r2.stale).toBe(false);
  });
});
