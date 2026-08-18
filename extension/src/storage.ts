// Device-local settings for consumer mode. `chrome.storage.local` ONLY — never `sync` (secrets
// must not leave the device; [OM-SEC-003]). The webhook signing secret is wrapped at rest (#126,
// secret-store.ts) so chrome.storage never holds it in plaintext.
import {
  secretCryptoAvailable,
  unwrapSecret,
  wrapSecret,
  type WrappedSecret,
} from "./secret-store.js";

export interface Webhook {
  url: string;
  secret: string;
}

/** On-disk shape: `enc` is the wrapped secret (#126); `secret` is a legacy plaintext field migrated
 *  forward on the next write. Exactly one of them is populated per record. */
interface StoredWebhook {
  url: string;
  enc?: WrappedSecret;
  secret?: string;
}
export interface Settings {
  /** §15 Q8: detect + badge on navigation (opt-in; default is check-on-panel-open). [#84] */
  proactiveDetection: boolean;
  /** §15 Q8: registrable domains (eTLD+1) where openOM links are badged (opt-in per domain). [#69] */
  linkBadgingDomains: string[];
}

const DEFAULT_SETTINGS: Settings = {
  proactiveDetection: false,
  linkBadgingDomains: [],
};

const KEY_WEBHOOK = "openom.webhook";
const KEY_SETTINGS = "openom.settings";

export async function getWebhook(): Promise<Webhook | null> {
  const r = await chrome.storage.local.get(KEY_WEBHOOK);
  const stored = r[KEY_WEBHOOK] as StoredWebhook | undefined;
  if (!stored) return null;
  if (stored.enc && secretCryptoAvailable()) {
    return { url: stored.url, secret: await unwrapSecret(stored.enc) };
  }
  return { url: stored.url, secret: stored.secret ?? "" }; // legacy plaintext / no-crypto fallback
}

export async function setWebhook(w: Webhook): Promise<void> {
  const stored: StoredWebhook = secretCryptoAvailable()
    ? { url: w.url, enc: await wrapSecret(w.secret) } // wrapped at rest (#126); no plaintext persisted
    : { url: w.url, secret: w.secret }; // no WebCrypto/IndexedDB (e.g. tests) → plaintext passthrough
  await chrome.storage.local.set({ [KEY_WEBHOOK]: stored });
}

export async function getSettings(): Promise<Settings> {
  const r = await chrome.storage.local.get(KEY_SETTINGS);
  return {
    ...DEFAULT_SETTINGS,
    ...((r[KEY_SETTINGS] as Partial<Settings> | undefined) ?? {}),
  };
}

export async function setSettings(s: Settings): Promise<void> {
  await chrome.storage.local.set({ [KEY_SETTINGS]: s });
}

/** Is this registrable domain in the link-badging allowlist? [#69] */
export async function isLinkBadgingDomain(domain: string): Promise<boolean> {
  return (await getSettings()).linkBadgingDomains.includes(domain);
}

/** Add or remove a registrable domain from the link-badging allowlist (deduped). [#69] */
export async function setLinkBadging(
  domain: string,
  on: boolean,
): Promise<void> {
  const s = await getSettings();
  const set = new Set(s.linkBadgingDomains);
  if (on) set.add(domain);
  else set.delete(domain);
  await setSettings({ ...s, linkBadgingDomains: [...set] });
}
