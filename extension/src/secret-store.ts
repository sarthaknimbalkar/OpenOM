// At-rest protection for the webhook signing secret (#126). chrome.storage.local is plaintext on
// disk, so the raw HMAC secret was recoverable by a storage dump / disk forensics. We wrap it with
// AES-GCM under a NON-EXTRACTABLE CryptoKey kept in IndexedDB: the wrapped form in chrome.storage
// carries no usable secret, and the wrapping key cannot be exported via the API. This defends the
// stated threat (passive storage/disk inspection); it does NOT defend against code execution inside
// the extension origin (which could use the key) — see SECURITY.md's threat model.
//
// Degrades to a passthrough where WebCrypto/IndexedDB are unavailable (e.g. a Node unit-test runtime);
// the real browser path (popup/options) always wraps and is proven end-to-end by the live publish gate.

export interface WrappedSecret {
  readonly v: 1;
  readonly iv: string; // base64 (12-byte GCM nonce)
  readonly ct: string; // base64 ciphertext+tag
}

const DB_NAME = "openom";
const STORE = "keys";
const KEY_ID = "webhook-wrap-key";

export function secretCryptoAvailable(): boolean {
  return (
    typeof indexedDB !== "undefined" &&
    typeof crypto !== "undefined" &&
    !!crypto.subtle
  );
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE))
        req.result.createObjectStore(STORE);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error("indexedDB open failed"));
  });
}

function idbGet(db: IDBDatabase, key: string): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, "readonly").objectStore(STORE).get(key);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function idbPut(db: IDBDatabase, key: string, value: unknown): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put(value, key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

/** Get (or create + persist) the non-extractable AES-GCM wrapping key. */
async function wrappingKey(): Promise<CryptoKey> {
  const db = await openDb();
  const existing = await idbGet(db, KEY_ID);
  if (existing instanceof CryptoKey) return existing;
  const key = await crypto.subtle.generateKey(
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
  await idbPut(db, KEY_ID, key); // stored non-extractable: the raw bytes never leave the API
  return key;
}

const b64 = (b: Uint8Array): string => btoa(String.fromCharCode(...b));
// Cast to BufferSource works around the TS DOM-lib Uint8Array<ArrayBufferLike> vs BufferSource mismatch.
const unb64 = (s: string): BufferSource =>
  Uint8Array.from(atob(s), (c) => c.charCodeAt(0)) as unknown as BufferSource;

/** Encrypt a secret for at-rest storage. */
export async function wrapSecret(plain: string): Promise<WrappedSecret> {
  const key = await wrappingKey();
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    new TextEncoder().encode(plain) as unknown as BufferSource,
  );
  return { v: 1, iv: b64(iv), ct: b64(new Uint8Array(ct)) };
}

/** Decrypt a wrapped secret back to plaintext (for signing / display in the owner's own UI). */
export async function unwrapSecret(w: WrappedSecret): Promise<string> {
  const key = await wrappingKey();
  const pt = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: unb64(w.iv) },
    key,
    unb64(w.ct),
  );
  return new TextDecoder().decode(pt);
}
