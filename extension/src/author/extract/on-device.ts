// The ONLY inference site in openOM. Wraps the browser's on-device Prompt API (Gemini Nano via the
// `LanguageModel` global, or the older `window.ai.languageModel`) to draft a payload from OM text. It
// is a browser global, NOT an npm dependency, so assert-no-inference stays green. It touches the model
// ONLY — never fetch/XHR/WebSocket, so extraction never leaves the device ([OM-PRIV-001]). Its output
// is a DRAFT for the human review gate; nothing here asserts or embeds.
import type { Extractor, ExtractionResult, PageText } from "./types.js";

interface PromptSession {
  prompt(input: string): Promise<string>;
}
interface PromptFactory {
  create(): Promise<PromptSession>;
}

function promptFactory(): PromptFactory | null {
  const g = globalThis as Record<string, unknown>;
  const lm = g.LanguageModel as PromptFactory | undefined;
  if (lm && typeof lm.create === "function") return lm;
  const ai = (g.window as { ai?: { languageModel?: PromptFactory } } | undefined)?.ai?.languageModel;
  if (ai && typeof ai.create === "function") return ai;
  return null;
}

// Key instructions only — the payload paths the model may fill (mirrors process/mapping-guide.md).
// Full mapping nuance lives in that guide; here we ground the model and demand strict, citable JSON.
const FIELD_MAP_HINT = [
  "Fill only these payload paths when the OM states them (omit anything unstated, never guess):",
  "property.address.{streetAddress,addressLocality,addressRegion,postalCode}, property.buildingSF,",
  "deal.askingPrice, deal.capRate (DECIMAL fraction: 6.25% -> 0.0625), deal.noi, deal.pricePerSF,",
  "lease.tenantEntity, lease.leaseTypeAsserted, lease.commencement, lease.expiration,",
  'lease.rentSchedule[] = {periodStart,periodEnd,annualRent,rentPSF?,source:"extracted"}.',
  "Do NOT fill assertedBy/assertedDate/noiType/noiAsOfDate — those are set by the human at review.",
].join(" ");

const SYSTEM = [
  "You extract structured data from a commercial-real-estate offering memorandum.",
  FIELD_MAP_HINT,
  'Return STRICT JSON only: {"fields":[{"path":"/deal/capRate","value":0.0625,"evidence":{"page":1,"quote":"Cap Rate: 6.25%"}}]}.',
  "Each field MUST cite evidence (page number + the exact quoted text). Omit fields you cannot cite.",
].join("\n");

export const onDeviceExtractor: Extractor = {
  kind: "on-device",
  available: async () => promptFactory() !== null,
  extract: async (pages: PageText[]): Promise<ExtractionResult> => {
    const lm = promptFactory();
    if (!lm) throw new Error("on-device Prompt API is unavailable");
    const body = pages.map((p) => `[p${p.page}]\n${p.text}`).join("\n\n");
    const session = await lm.create();
    const raw = await session.prompt(`${SYSTEM}\n\n--- OM TEXT ---\n${body}`);
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      throw new Error("on-device extraction returned non-JSON output");
    }
    const fields = (parsed as { fields?: unknown }).fields;
    if (!Array.isArray(fields)) throw new Error("on-device extraction output missing a fields array");
    return { fields: fields as ExtractionResult["fields"] };
  },
};
