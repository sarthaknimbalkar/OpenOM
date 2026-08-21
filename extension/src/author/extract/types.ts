// The extraction seam. Inference (when present) lives ONLY behind this interface, in the on-device
// adapter - never in /core, /mcp, the consumer bundle, or any om_* verb. Three adapters implement it:
// on-device (Prompt API, a browser global), hosted-stub (a disabled seam for the paid path, §15 Q2),
// and a deterministic test-double. Whatever an extractor returns is a DRAFT for the human review gate
// - extraction confidence is never consent ([OM-EXTP-003]).
import type { PageText } from "openom-js";

export type { PageText };

export interface FieldExtraction {
  /** RFC 6901 JSON pointer into the payload, e.g. "/deal/capRate". */
  path: string;
  value: unknown;
  /** Where in the OM it came from - page + quoted text; absent when the model cited nothing. */
  evidence?: { page?: number; quote?: string };
}

export interface ExtractionResult {
  fields: FieldExtraction[];
}

export interface Extractor {
  readonly kind: "on-device" | "hosted-stub" | "test";
  available(): Promise<boolean>;
  extract(pages: PageText[]): Promise<ExtractionResult>;
}
