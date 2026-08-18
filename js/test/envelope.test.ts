import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { buildEnvelope, type Verification } from "../src/webhook.js";
import { validateEnvelope, verifyEnvelopePayloadHash, ENVELOPE_SCHEMA } from "../src/envelope.js";
import { payloadHash } from "../src/hash.js";

const VERIF: Verification = { hashValid: true, originVerified: true, signatureValid: null };
const good = buildEnvelope({
  event: "om.payload.published",
  sourceUrl: "https://broker.example.com/deal.pdf",
  payload: { "@type": "RealEstateListing", specVersion: "0.1" },
  payloadHash: "sha256:" + "a".repeat(64),
  verification: VERIF,
  now: new Date("2026-08-18T12:00:00.000Z"),
  id: "11111111-1111-4111-8111-111111111111",
});

describe("validateEnvelope (§Y receiver, #14)", () => {
  test("a buildEnvelope output validates against the schema", () => {
    expect(validateEnvelope(good)).toEqual({ valid: true, errors: [] });
  });
  test("rejects a missing required field", () => {
    const { payloadHash: _drop, ...bad } = good;
    const r = validateEnvelope(bad);
    expect(r.valid).toBe(false);
    expect(r.errors.join(" ")).toContain("payloadHash");
  });
  test("rejects a malformed payloadHash", () => {
    expect(validateEnvelope({ ...good, payloadHash: "deadbeef" }).valid).toBe(false);
  });
  test("rejects the wrong envelopeVersion / an extra property", () => {
    expect(validateEnvelope({ ...good, envelopeVersion: "9" }).valid).toBe(false);
    expect(validateEnvelope({ ...good, extra: 1 }).valid).toBe(false);
  });
});

describe("verifyEnvelopePayloadHash (§Y receiver hash-binding, #120)", () => {
  const payload = { "@type": "RealEstateListing", specVersion: "0.1", assertedBy: { broker: "A" } };
  const bound = buildEnvelope({
    event: "om.payload.published",
    sourceUrl: "https://broker.example.com/deal.pdf",
    payload,
    payloadHash: payloadHash(payload),
    verification: VERIF,
    now: new Date("2026-08-18T12:00:00.000Z"),
    id: "22222222-2222-4222-8222-222222222222",
  });

  test("true when payloadHash binds the inline payload", () => {
    expect(verifyEnvelopePayloadHash(bound)).toBe(true);
  });
  test("false when payloadHash does not match the payload", () => {
    expect(verifyEnvelopePayloadHash({ ...bound, payloadHash: "sha256:" + "a".repeat(64) })).toBe(
      false,
    );
  });
  test("false when the payload is tampered after signing", () => {
    expect(verifyEnvelopePayloadHash({ ...bound, payload: { ...payload, extra: 1 } })).toBe(false);
  });
  test("false on malformed input", () => {
    expect(verifyEnvelopePayloadHash(null)).toBe(false);
    expect(verifyEnvelopePayloadHash({ payload, payloadHash: 5 })).toBe(false);
  });
});

describe("envelope schema — no drift between /js and /spec", () => {
  test("ENVELOPE_SCHEMA equals the published spec/webhook-envelope-0.1.schema.json", () => {
    const specPath = join(
      dirname(fileURLToPath(import.meta.url)),
      "..",
      "..",
      "spec",
      "webhook-envelope-0.1.schema.json",
    );
    const published = JSON.parse(readFileSync(specPath, "utf8"));
    expect(published).toEqual(JSON.parse(JSON.stringify(ENVELOPE_SCHEMA)));
  });
});
