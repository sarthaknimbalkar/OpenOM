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

/** Readiness of an on-device model ([M5]): usable now, present but needs a (large) download, or absent. */
export type ExtractorReadiness = "ready" | "needs-download" | "unavailable";

/** Optional per-run hooks - e.g. surfacing model-download progress to the review panel ([M5]). */
export interface ExtractOptions {
  /** Called with a 0..1 fraction while an on-device model downloads before first use. */
  onDownloadProgress?: (fraction: number) => void;
}

export interface Extractor {
  readonly kind: "on-device" | "hosted-stub" | "test";
  available(): Promise<boolean>;
  /** Finer-grained than `available()`: distinguishes ready from a pending model download ([M5]). */
  readiness?(): Promise<ExtractorReadiness>;
  extract(pages: PageText[], opts?: ExtractOptions): Promise<ExtractionResult>;
}
