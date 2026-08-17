// openOM MV3 service worker — consumer mode. Orchestration lands in Task 4.
import { badgeState } from "openom-js";

// Scaffold sanity: prove the /js alias bundles into the SW.
const _scaffold = badgeState({ present: false, hashValid: null, originVerified: false, signatureValid: null });
void _scaffold;
