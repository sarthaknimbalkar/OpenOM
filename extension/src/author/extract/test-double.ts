// A deterministic extractor for tests - returns a fixed ExtractionResult, no model, no I/O. It proves
// the seam and the apply/panel wiring without a real Prompt API model. (The live gate goes further and
// exercises the REAL on-device adapter against an injected fake LanguageModel global.)
import type { Extractor, ExtractionResult } from "./types.js";

export function makeTestDouble(result: ExtractionResult): Extractor {
  return {
    kind: "test",
    available: async () => true,
    extract: async () => result,
  };
}
