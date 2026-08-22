// The DRAFT-SOURCE seam (#166 groundwork) - a layer ABOVE the Extractor seam that unifies two ways
// to produce a draft payload for the human review gate:
//
//   1. inference EXTRACTORS (on-device Prompt API, hosted) - run a model over the PDF's text.
//      Non-deterministic; the existing `Extractor` adapters, wrapped by `extractorSource`.
//   2. structured CONNECTORS (Buildout MCP, DealGround, a CRM) - fetch the broker's OWN structured
//      record at the source and map it, with NO inference and NO PDF text. Deterministic.
//
// A connector is NOT a drop-in Extractor: it takes no `pages`. So it slots here, above the seam, and
// emits the same `ExtractionResult` shape via the pure deterministic mapper `partialPayloadToFields`.
// This is why a connector pull sits on the deterministic side of the cardinal rule and can demote the
// on-device model to a fallback (`pickDraftSource` prefers deterministic sources).
//
// SCOPE: the generic, reusable scaffold. The concrete Buildout connector (`connectors/buildout.ts` +
// the MCP-HTTP client `connectors/buildout-http.ts`) and the panel wiring are now built - author mode
// offers a Buildout pull when configured (options page) on a Buildout listing tab, with on-device as
// the fallback. `connectors/buildout.ts` maps the REAL nested Buildout get_listing shape (byte-parity
// with the reference Python mapper cli/src/openom_cli/buildout.py); `partialPayloadToFields` is
// dependency-free so it can move to /js for a CLI/hosted run.
import type {
  Extractor,
  ExtractionResult,
  ExtractorReadiness,
  FieldExtraction,
  PageText,
} from "./types.js";

/** What a draft source is given. Inference extractors use `pages`; connectors ignore it. */
export interface DraftContext {
  pages: PageText[];
  /** Surfaced to the UI while an on-device model downloads before first use ([M5]). */
  onDownloadProgress?: (fraction: number) => void;
}

/** A source of a DRAFT payload for the review gate. `deterministic` connectors carry no inference. */
export interface DraftSource {
  readonly id: string;
  readonly label: string;
  readonly deterministic: boolean;
  available(): Promise<boolean>;
  /** Finer than `available()`: "needs-download" lets the UI warn before a large model download ([M5]).
   * Deterministic connectors are always "ready". */
  readiness(): Promise<ExtractorReadiness>;
  draft(ctx: DraftContext): Promise<ExtractionResult>;
}

/** Adapt an existing inference `Extractor` into a `DraftSource` (no churn to the Extractor seam). */
export function extractorSource(
  extractor: Extractor,
  label: string,
): DraftSource {
  return {
    id: extractor.kind,
    label,
    deterministic: false,
    available: () => extractor.available(),
    readiness: () =>
      extractor.readiness
        ? extractor.readiness()
        : extractor.available().then((a) => (a ? "ready" : "unavailable")),
    draft: (ctx) => extractor.extract(ctx.pages, { onDownloadProgress: ctx.onDownloadProgress }),
  };
}

/**
 * A structured data source (e.g. a Buildout MCP OAuth connector). It returns a PARTIAL openOM
 * payload - the broker's own pre-flatten record - which the deterministic mapper turns into draft
 * fields. Concrete connectors normalize their API into a partial payload; that is the only adapter
 * work, keeping the openOM shape as the single intermediate (no third vocabulary).
 */
export interface StructuredConnector {
  readonly id: string;
  readonly label: string;
  available(): Promise<boolean>;
  /** Fetch a partial openOM payload for `ref` (a listing/deal id in the source system). */
  fetch(ref: string): Promise<Record<string, unknown>>;
}

/** Wrap a `StructuredConnector` + a target `ref` into a deterministic `DraftSource`. */
export function connectorSource(
  connector: StructuredConnector,
  ref: string,
): DraftSource {
  return {
    id: connector.id,
    label: connector.label,
    deterministic: true,
    available: () => connector.available(),
    readiness: async () => ((await connector.available()) ? "ready" : "unavailable"),
    draft: async () => partialPayloadToFields(await connector.fetch(ref)),
  };
}

// Top-level members a connector must NOT draft: structural (@context/@type/specVersion/meta) and the
// human-only assertion identity (assertedBy/assertedDate are stamped at the review gate, never
// imported). Everything else - property.*, deal.*, lease.* - is draftable. (Whether deal.noiType /
// noiAsOfDate should be connector-filled or stay gate-only is decision-memo Q4, deferred; the human
// gate confirms every field regardless.)
const NON_DRAFTABLE_TOP_LEVEL = new Set([
  "@context",
  "@type",
  "specVersion",
  "assertedBy",
  "assertedDate",
  "meta",
]);

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function walk(value: unknown, pointer: string, out: FieldExtraction[]): void {
  if (Array.isArray(value)) {
    value.forEach((item, i) => walk(item, `${pointer}/${i}`, out));
  } else if (isPlainObject(value)) {
    for (const [k, v] of Object.entries(value)) {
      // RFC 6901 escaping: "~" -> "~0", "/" -> "~1".
      const token = k.replace(/~/g, "~0").replace(/\//g, "~1");
      walk(v, `${pointer}/${token}`, out);
    }
  } else {
    out.push({ path: pointer, value }); // a leaf: scalar or null
  }
}

/**
 * Flatten a PARTIAL openOM payload into review-gate draft fields - DETERMINISTIC, no inference.
 * Each leaf becomes a `FieldExtraction` whose `path` is its RFC 6901 JSON pointer; structural and
 * human-only top-level members are skipped. Connector-sourced fields carry no page/quote evidence
 * (there is no PDF locus) - provenance labeling for imported data is decision-memo Q4, deferred.
 */
export function partialPayloadToFields(
  partial: Record<string, unknown>,
): ExtractionResult {
  const fields: FieldExtraction[] = [];
  for (const [key, value] of Object.entries(partial)) {
    if (NON_DRAFTABLE_TOP_LEVEL.has(key)) continue;
    const token = key.replace(/~/g, "~0").replace(/\//g, "~1");
    walk(value, `/${token}`, fields);
  }
  return { fields };
}

/**
 * Choose the draft source to offer: deterministic connectors first (a structured pull is
 * higher-fidelity and inference-free), then inference extractors as the fallback; null if none is
 * available (the panel then falls back to manual entry). Realizes the decision memo's "Buildout
 * primary, on-device fallback."
 */
export async function pickDraftSource(
  sources: DraftSource[],
): Promise<DraftSource | null> {
  const ordered = [...sources].sort(
    (a, b) => Number(b.deterministic) - Number(a.deterministic),
  );
  for (const s of ordered) {
    if (await s.available()) return s;
  }
  return null;
}
