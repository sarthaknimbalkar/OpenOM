// The hosted extraction path as a SEAM ONLY (§15 Q2). Hosted inference is the separate, paid Vervelio
// service — never part of the open extension. This adapter is present so the boundary has a name, but
// it is permanently disabled: available() is false and extract() throws. It is NEVER a live network
// call, keeping the open bundle deterministic + egress-free.
import type { Extractor } from "./types.js";

export const hostedStub: Extractor = {
  kind: "hosted-stub",
  available: async () => false,
  extract: async () => {
    throw new Error("hosted extraction is a separate Vervelio service, not part of the open extension");
  },
};
