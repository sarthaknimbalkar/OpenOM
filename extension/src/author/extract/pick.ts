// Choose the extractor to offer: the first candidate whose model/capability is actually available,
// else null (the panel then falls back to manual entry — §15 Q6 graceful degradation). The hosted
// stub reports unavailable, so it is never selected in the open build.
import type { Extractor } from "./types.js";

export async function pickExtractor(candidates: Extractor[] = []): Promise<Extractor | null> {
  for (const c of candidates) {
    if (await c.available()) return c;
  }
  return null;
}
