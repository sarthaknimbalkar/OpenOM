// Author-mode capture: turn PDF bytes into a Capture, reading any prior payload so the review panel
// can offer the reprice flow, and decrypting empty-password AES OMs in-browser ([#4]). The logic is
// single-sourced in openom-js (js/src/author.ts) so the extension author path and the hosted web
// authoring companion can never diverge. Deterministic; the byte source (re-fetch or file) is chosen
// by panel.ts.
export { looksLikePdf, captureFromBytes, type Capture } from "openom-js";
