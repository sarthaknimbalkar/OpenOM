// §15 Q8: cache a per-URL detection result for 24h so re-opening the popup on the same PDF doesn't
// re-fetch + re-read every time ([#68]). Device-local; the clock is passed in so it stays testable.
import type { DetectResult } from "./service-worker.js";

interface CachedDetect {
  result: DetectResult;
  expiresAt: number;
}

const TTL_MS = 24 * 60 * 60 * 1000;
const KEY = (url: string): string => `openom.detect.${url}`;

export async function getCachedDetect(url: string, nowMs: number): Promise<DetectResult | null> {
  const r = await chrome.storage.local.get(KEY(url));
  const c = r[KEY(url)] as CachedDetect | undefined;
  return c && c.expiresAt > nowMs ? c.result : null;
}

export async function setCachedDetect(
  url: string,
  result: DetectResult,
  nowMs: number,
  ttlMs = TTL_MS,
): Promise<void> {
  await chrome.storage.local.set({ [KEY(url)]: { result, expiresAt: nowMs + ttlMs } });
}
