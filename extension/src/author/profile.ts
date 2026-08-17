// The reviewing broker's identity, used as `assertedBy` at the assert step. Device-local via
// `chrome.storage.local` ONLY — never `chrome.storage.sync` ([OM-SEC-003]); the broker's license
// and identity must not sync off the device. Mirrors the consumer storage.ts pattern.

export interface BrokerProfile {
  broker: string;
  brokerage?: string;
  license?: string;
}

const KEY_PROFILE = "openom.profile";

export async function getProfile(): Promise<BrokerProfile | null> {
  const r = await chrome.storage.local.get(KEY_PROFILE);
  return (r[KEY_PROFILE] as BrokerProfile | undefined) ?? null;
}

export async function setProfile(p: BrokerProfile): Promise<void> {
  await chrome.storage.local.set({ [KEY_PROFILE]: p });
}
