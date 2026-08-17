// Persist an in-progress author draft so closing/reopening the side panel doesn't lose review work
// ([#94]). Device-local via chrome.storage.local ONLY (never sync); keyed by the source document hash
// so each captured OM restores its own draft, and cleared once the OM is embedded.
import type { Draft } from "./draft.js";

const KEY = (id: string): string => `openom.draft.${id}`;

export async function getDraft(id: string): Promise<Draft | null> {
  const r = await chrome.storage.local.get(KEY(id));
  return (r[KEY(id)] as Draft | undefined) ?? null;
}

export async function setDraft(id: string, draft: Draft): Promise<void> {
  await chrome.storage.local.set({ [KEY(id)]: draft });
}

export async function clearDraft(id: string): Promise<void> {
  await chrome.storage.local.remove(KEY(id));
}
