// The assertion step: turn a reviewed Draft into the payload the broker is asserting, then validate
// and embed. The pure core (`finalizePayload`, `assertAndEmbed`, `suggestedFilename`) lives in
// openom-js (js/src/author.ts) - single-sourced with the hosted authoring companion so the two author
// surfaces can never diverge. `finalize` here adapts the extension's Draft to that core; `handBack`
// hands the produced OM to the broker as a download. Zero inference. Called only after a human Assert.
import type { Draft } from "./draft.js";
import type { BrokerProfile } from "./profile.js";
import { finalizePayload } from "openom-js";

export { assertAndEmbed, suggestedFilename } from "openom-js";

/**
 * Produce the payload the broker asserts from the extension's Draft (delegates to the shared
 * `finalizePayload`). The panel validates THIS shape (not the raw draft) so the Assert gate reflects
 * what would actually be embedded.
 */
export function finalize(
  draft: Draft,
  profile: BrokerProfile,
  today: string,
  prior: { payloadHash: string } | null,
  sourceDocHash?: string,
): Record<string, unknown> {
  return finalizePayload(
    draft.payload,
    {
      broker: profile.broker ?? "",
      brokerage: profile.brokerage ?? "",
      license: profile.license ?? "",
    },
    today,
    prior,
    sourceDocHash,
  );
}

/** Hand the embedded OM to the broker as a download (panel document; no `downloads` permission). */
export function handBack(out: Uint8Array, filename: string): void {
  const url = URL.createObjectURL(new Blob([new Uint8Array(out)], { type: "application/pdf" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
