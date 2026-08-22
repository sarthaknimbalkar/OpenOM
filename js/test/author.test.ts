import { describe, expect, test } from "vitest";
import {
  finalizePayload,
  suggestedFilename,
  assertAndEmbed,
  looksLikePdf,
  captureFromBytes,
  OM_CONTEXT,
} from "../src/author.js";
import type { ValidationReport } from "../src/validate.js";
import type { ReadResult } from "../src/read.js";
import type { OMPayload } from "../src/payload-types.js";

const profile = { broker: "Jane Broker", brokerage: "Example Realty", license: "RE-1" };

describe("finalizePayload - shared assertion core", () => {
  test("stamps spec constants, assertedBy, and assertedDate", () => {
    const p = finalizePayload({ deal: { askingPrice: 1_000_000 } }, profile, "2026-08-22", null);
    expect(p["@context"]).toEqual(OM_CONTEXT);
    expect(p["@type"]).toBe("RealEstateListing");
    expect(p["specVersion"]).toBe("0.1");
    expect(p["assertedBy"]).toEqual(profile);
    expect(p["assertedDate"]).toBe("2026-08-22");
    expect((p["meta"] as Record<string, unknown>).supersedes).toBeNull();
  });

  test("sets meta.supersedes to the prior hash on a reprice", () => {
    const p = finalizePayload({}, profile, "2026-08-22", { payloadHash: "abc123" });
    expect((p["meta"] as Record<string, unknown>).supersedes).toBe("abc123");
  });

  test("promotes rentSchedule source extracted → asserted", () => {
    const p = finalizePayload(
      {
        lease: {
          rentSchedule: [
            { annualRent: 1, source: "extracted" },
            { annualRent: 2, source: "asserted" },
          ],
        },
      },
      profile,
      "2026-08-22",
      null,
    );
    const rs = (p["lease"] as { rentSchedule: { source: string }[] }).rentSchedule;
    expect(rs.map((r) => r.source)).toEqual(["asserted", "asserted"]);
  });

  test("does not mutate the input payload", () => {
    const input = { deal: { askingPrice: 1 } };
    finalizePayload(input, profile, "2026-08-22", null);
    expect(input).toEqual({ deal: { askingPrice: 1 } });
  });
});

describe("suggestedFilename", () => {
  test("slugs the street address", () => {
    expect(suggestedFilename({ property: { address: { streetAddress: "123 Main St." } } })).toBe(
      "123-main-st-openom.pdf",
    );
  });
  test("falls back to the source URL basename", () => {
    expect(suggestedFilename({}, "https://x.com/files/deal-book.pdf")).toBe("deal-book-openom.pdf");
  });
  test("final fallback", () => {
    expect(suggestedFilename({})).toBe("openom-embedded.pdf");
  });
});

describe("looksLikePdf", () => {
  test("accepts a %PDF- signature (even with a small BOM/prefix)", () => {
    expect(looksLikePdf(new TextEncoder().encode("%PDF-1.7\n..."))).toBe(true);
    expect(looksLikePdf(new TextEncoder().encode("﻿ junk %PDF-1.4"))).toBe(true);
  });
  test("rejects non-PDF bytes", () => {
    expect(looksLikePdf(new TextEncoder().encode("<html>"))).toBe(false);
  });
});

describe("captureFromBytes", () => {
  const mk = (over: Partial<ReadResult>): ReadResult =>
    ({
      state: "absent",
      payload: null,
      payloadHash: null,
      verification: { hashValid: false, signatureValid: false },
      ...over,
    }) as ReadResult;

  test("present payload becomes the reprice base", async () => {
    const cap = await captureFromBytes(new Uint8Array([1]), async () =>
      mk({ state: "present", payload: { a: 1 } as unknown as OMPayload, payloadHash: "h" }),
    );
    expect(cap.prior?.payloadHash).toBe("h");
    expect(cap.priorUnverified).toBe(false);
    expect(cap.encrypted).toBe(false);
  });

  test("hash-mismatch is flagged, not used as a base", async () => {
    const cap = await captureFromBytes(new Uint8Array([1]), async () =>
      mk({ state: "hash-mismatch", payload: { a: 1 } as unknown as OMPayload, payloadHash: "h" }),
    );
    expect(cap.prior).toBeNull();
    expect(cap.priorUnverified).toBe(true);
  });

  test("empty-password encryption is decrypted then re-read (wasDecrypted)", async () => {
    const decrypted = new Uint8Array([9, 9]);
    let call = 0;
    const cap = await captureFromBytes(
      new Uint8Array([1]),
      async () => (call++ === 0 ? mk({ state: "encrypted" }) : mk({ state: "absent" })),
      async () => decrypted,
    );
    expect(cap.wasDecrypted).toBe(true);
    expect(cap.encrypted).toBe(false);
    expect(Array.from(cap.bytes)).toEqual([9, 9]);
  });

  test("undecryptable encryption stays encrypted (CLI refuse)", async () => {
    const cap = await captureFromBytes(
      new Uint8Array([1]),
      async () => mk({ state: "encrypted" }),
      async () => null,
    );
    expect(cap.encrypted).toBe(true);
    expect(cap.wasDecrypted).toBe(false);
  });
});

describe("assertAndEmbed", () => {
  const clean: ValidationReport = {
    specVersion: "0.1",
    validatorVersion: "t",
    errors: [],
    warnings: [],
    info: [],
    summary: { errorCount: 0, warningCount: 0, infoCount: 0 },
    blocked: false,
  };
  test("embeds when there are no schema errors", async () => {
    const out = await assertAndEmbed(
      { a: 1 },
      new Uint8Array([1]),
      () => clean,
      async () => new Uint8Array([9]),
    );
    expect(Array.from(out)).toEqual([9]);
  });
  test("refuses to embed a schema-invalid payload", async () => {
    const bad: ValidationReport = {
      ...clean,
      errors: [{ code: "OMV-E001", severity: "error", path: "", message: "x" }],
      summary: { errorCount: 1, warningCount: 0, infoCount: 0 },
      blocked: true,
    };
    await expect(
      assertAndEmbed(
        {},
        new Uint8Array(),
        () => bad,
        async () => new Uint8Array(),
      ),
    ).rejects.toThrow(/cannot embed/);
  });
});
