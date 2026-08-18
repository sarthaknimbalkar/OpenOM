import { describe, expect, test } from "vitest";
import "fake-indexeddb/auto"; // provides indexedDB in the Node test runtime
import {
  secretCryptoAvailable,
  unwrapSecret,
  wrapSecret,
  type WrappedSecret,
} from "../../src/secret-store.js";

// #126: the webhook signing secret is wrapped at rest with a non-extractable AES-GCM key in IndexedDB.
// Node 20+ provides crypto.subtle + CryptoKey; fake-indexeddb provides indexedDB → the real wrap path
// runs off-browser here (the real-browser path is additionally proven by the live publish gate). The
// wrapping key is created once and reused across these tests (as in production).
describe("secret-store (webhook secret at rest, #126)", () => {
  test("crypto is available in this runtime", () => {
    expect(secretCryptoAvailable()).toBe(true);
  });

  test("wrap → unwrap round-trips the secret", async () => {
    const w = await wrapSecret("super-secret-hmac-key");
    expect(await unwrapSecret(w)).toBe("super-secret-hmac-key");
  });

  test("the wrapped form contains no plaintext of the secret", async () => {
    const secret = "PLAINTEXT_MARKER_9f3a";
    const w = await wrapSecret(secret);
    expect(w.v).toBe(1);
    expect(JSON.stringify(w)).not.toContain(secret);
    expect(atob(w.ct)).not.toContain(secret); // ciphertext, not the raw secret
  });

  test("distinct nonces → distinct ciphertext for the same secret", async () => {
    const a = await wrapSecret("k");
    const b = await wrapSecret("k");
    expect(a.iv).not.toBe(b.iv);
    expect(a.ct).not.toBe(b.ct);
    expect(await unwrapSecret(a)).toBe(await unwrapSecret(b));
  });

  test("the wrapping key is non-extractable (cannot be exported)", async () => {
    await wrapSecret("k"); // creates + persists the key
    const db = await new Promise<IDBDatabase>((res, rej) => {
      const req = indexedDB.open("openom", 1);
      req.onsuccess = () => res(req.result);
      req.onerror = () => rej(req.error);
    });
    const key = await new Promise<unknown>((res, rej) => {
      const req = db
        .transaction("keys", "readonly")
        .objectStore("keys")
        .get("webhook-wrap-key");
      req.onsuccess = () => res(req.result);
      req.onerror = () => rej(req.error);
    });
    expect(key).toBeInstanceOf(CryptoKey);
    expect((key as CryptoKey).extractable).toBe(false);
    await expect(
      crypto.subtle.exportKey("raw", key as CryptoKey),
    ).rejects.toThrow();
  });

  test("a tampered wrapped secret fails to unwrap (GCM auth)", async () => {
    const w = await wrapSecret("k");
    const bad: WrappedSecret = { ...w, ct: btoa("garbage-ciphertext") };
    await expect(unwrapSecret(bad)).rejects.toThrow();
  });
});
