// Device-local settings for consumer mode. `chrome.storage.local` ONLY - never `sync` (secrets
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

/** Buildout MCP connector config (author-mode deterministic ingestion). The token is a secret and
 * is wrapped at rest exactly like the webhook secret (#126); never persisted in plaintext. */
export interface BuildoutConfig {
  endpoint: string;
  token: string;
  toolName?: string;
}

interface StoredBuildout {
  endpoint: string;
  toolName?: string;
  enc?: WrappedSecret;
  token?: string; // legacy/no-crypto fallback only
}

const KEY_BUILDOUT = "openom.buildout";

export async function getBuildoutConfig(): Promise<BuildoutConfig | null> {
  const r = await chrome.storage.local.get(KEY_BUILDOUT);
  const s = r[KEY_BUILDOUT] as StoredBuildout | undefined;
  if (!s || !s.endpoint) return null;
  const token = s.enc && secretCryptoAvailable() ? await unwrapSecret(s.enc) : (s.token ?? "");
  return { endpoint: s.endpoint, token, toolName: s.toolName };
}

export async function setBuildoutConfig(c: BuildoutConfig | null): Promise<void> {
  if (!c || !c.endpoint) {
    await chrome.storage.local.remove(KEY_BUILDOUT);
    return;
  }
  const stored: StoredBuildout = secretCryptoAvailable()
    ? { endpoint: c.endpoint, toolName: c.toolName, enc: await wrapSecret(c.token) }
    : { endpoint: c.endpoint, toolName: c.toolName, token: c.token };
  await chrome.storage.local.set({ [KEY_BUILDOUT]: stored });
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
