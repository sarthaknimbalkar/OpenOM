import { describe, expect, test } from "vitest";
import type { ReadResult } from "openom-js";
import { captureFromBytes } from "../../src/author/capture.js";

const ABSENT: ReadResult = {
  state: "absent",
  payload: null,
  payloadHash: null,
  verification: { hashValid: null, originVerified: null, signatureValid: null },
};
const PRESENT: ReadResult = {
  state: "present",
  payload: { assertedBy: { broker: "A" } },
  payloadHash: "sha256:abc",
  verification: { hashValid: true, originVerified: null, signatureValid: null },
};
const MISMATCH: ReadResult = { ...PRESENT, state: "hash-mismatch" };

const bytes = new Uint8Array([1, 2, 3]);

describe("captureFromBytes - prior payload drives reprice", () => {
  test("plain PDF → prior is null", async () => {
    const c = await captureFromBytes(bytes, async () => ABSENT);
    expect(c.bytes).toBe(bytes);
    expect(c.prior).toBeNull();
  });

  test("embedded PDF → prior carries the present read", async () => {
    const c = await captureFromBytes(bytes, async () => PRESENT);
    expect(c.prior?.state).toBe("present");
    expect(c.prior?.payloadHash).toBe("sha256:abc");
  });

  test("tampered prior (hash-mismatch) is NOT a reprice base → prior null", async () => {
    const c = await captureFromBytes(bytes, async () => MISMATCH);
    expect(c.prior).toBeNull();
  });

  test("tampered prior is flagged priorUnverified so the panel can warn (#87)", async () => {
    expect(
      (await captureFromBytes(bytes, async () => MISMATCH)).priorUnverified,
    ).toBe(true);
    expect(
      (await captureFromBytes(bytes, async () => ABSENT)).priorUnverified,
    ).toBe(false);
    expect(
      (await captureFromBytes(bytes, async () => PRESENT)).priorUnverified,
    ).toBe(false);
  });

  test("an out-of-scope encrypted PDF (decrypt → null) is refused (#107)", async () => {
    const ENCRYPTED: ReadResult = { ...ABSENT, state: "encrypted" };
    const c = await captureFromBytes(
      bytes,
      async () => ENCRYPTED,
      async () => null,
    );
    expect(c.encrypted).toBe(true);
    expect(c.wasDecrypted).toBe(false);
    expect((await captureFromBytes(bytes, async () => ABSENT)).encrypted).toBe(
      false,
    );
  });

  test("an empty-password AES PDF is decrypted then read as embeddable (#4)", async () => {
    const ENCRYPTED: ReadResult = { ...ABSENT, state: "encrypted" };
    const decrypted = new Uint8Array([9, 9, 9]);
    let call = 0;
    const read = async (): Promise<ReadResult> =>
      call++ === 0 ? ENCRYPTED : ABSENT;
    const c = await captureFromBytes(bytes, read, async () => decrypted);
    expect(c.wasDecrypted).toBe(true);
    expect(c.encrypted).toBe(false);
    expect(c.bytes).toBe(decrypted); // authoring proceeds against the decrypted copy
    expect(c.prior).toBeNull();
  });

  test("a fresh (unencrypted) capture reports wasDecrypted false", async () => {
    expect(
      (await captureFromBytes(bytes, async () => ABSENT)).wasDecrypted,
    ).toBe(false);
  });
});
