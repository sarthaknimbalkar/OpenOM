import { describe, expect, test } from "vitest";
import schema from "../../../spec/om-0.1.schema.json";
import { precompiledValidate } from "../../src/validator.js";
import { profileComplete } from "../../src/author/profile.js";
import { assertEmbeddable } from "../../src/author/embed-guard.js";
import { finalize } from "../../src/author/assert.js";
import { newDraft } from "../../src/author/draft.js";

const complete = { broker: "Jane", brokerage: "Acme", license: "CA-1" };

describe("profileComplete (#97)", () => {
  test("requires all three assertedBy members, non-blank", () => {
    expect(profileComplete(complete)).toBe(true);
    expect(profileComplete({ broker: "Jane", brokerage: "", license: "CA-1" })).toBe(false);
    expect(profileComplete({ broker: " ", brokerage: "Acme", license: "CA-1" })).toBe(false);
  });
});

describe("assertEmbeddable (#98) - defense-in-depth", () => {
  const S = schema as Record<string, unknown>;
  test("throws on a schema-invalid payload", () => {
    expect(() => assertEmbeddable({ currency: "usd" }, S, precompiledValidate)).toThrow(/refusing to embed/);
  });
  test("passes a valid finalized payload", () => {
    const ok = finalize(newDraft(), complete, "2026-08-18", null);
    expect(() => assertEmbeddable(ok, S, precompiledValidate)).not.toThrow();
  });
});

describe("finalize sourceDocHash (#96)", () => {
  test("records meta.sourceDocHash when provided", () => {
    const p = finalize(newDraft(), complete, "2026-08-18", null, "sha256:abc");
    expect((p.meta as Record<string, unknown>).sourceDocHash).toBe("sha256:abc");
  });
  test("omits sourceDocHash when not provided", () => {
    const p = finalize(newDraft(), complete, "2026-08-18", null);
    expect((p.meta as Record<string, unknown>).sourceDocHash).toBeUndefined();
  });
});
