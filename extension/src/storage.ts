// Device-local settings for consumer mode. `chrome.storage.local` ONLY — never `sync` (secrets
// must not leave the device; [OM-SEC-003]).

export interface Webhook {
  url: string;
  secret: string;
}
export interface Settings {
  linkBadging: boolean;
}

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
  return (r[KEY_SETTINGS] as Settings | undefined) ?? { linkBadging: false };
}

export async function setSettings(s: Settings): Promise<void> {
  await chrome.storage.local.set({ [KEY_SETTINGS]: s });
}
