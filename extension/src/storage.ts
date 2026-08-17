// Device-local settings for consumer mode. `chrome.storage.local` ONLY — never `sync` (secrets
// must not leave the device; [OM-SEC-003]).

export interface Webhook {
  url: string;
  secret: string;
}
export interface Settings {
  /** §15 Q8: detect + badge on navigation (opt-in; default is check-on-panel-open). [#84] */
  proactiveDetection: boolean;
  /** §15 Q8: registrable domains (eTLD+1) where openOM links are badged (opt-in per domain). [#69] */
  linkBadgingDomains: string[];
}

const DEFAULT_SETTINGS: Settings = { proactiveDetection: false, linkBadgingDomains: [] };

const KEY_WEBHOOK = "openom.webhook";
const KEY_SETTINGS = "openom.settings";

export async function getWebhook(): Promise<Webhook | null> {
  const r = await chrome.storage.local.get(KEY_WEBHOOK);
  return (r[KEY_WEBHOOK] as Webhook | undefined) ?? null;
}

export async function setWebhook(w: Webhook): Promise<void> {
  await chrome.storage.local.set({ [KEY_WEBHOOK]: w });
}

export async function getSettings(): Promise<Settings> {
  const r = await chrome.storage.local.get(KEY_SETTINGS);
  return { ...DEFAULT_SETTINGS, ...((r[KEY_SETTINGS] as Partial<Settings> | undefined) ?? {}) };
}

export async function setSettings(s: Settings): Promise<void> {
  await chrome.storage.local.set({ [KEY_SETTINGS]: s });
}

/** Is this registrable domain in the link-badging allowlist? [#69] */
export async function isLinkBadgingDomain(domain: string): Promise<boolean> {
  return (await getSettings()).linkBadgingDomains.includes(domain);
}

/** Add or remove a registrable domain from the link-badging allowlist (deduped). [#69] */
export async function setLinkBadging(domain: string, on: boolean): Promise<void> {
  const s = await getSettings();
  const set = new Set(s.linkBadgingDomains);
  if (on) set.add(domain);
  else set.delete(domain);
  await setSettings({ ...s, linkBadgingDomains: [...set] });
}
