// Stale-vs-tamper (§AA [OM-TRUST-009], OMW-W051) - single-sourced in openom-js (js/src/stale.ts) so
// the service worker, the embeddable badge, and the /verify tool decide staleness identically ([M2]).
export { classifyStale, type StaleResult } from "openom-js";
