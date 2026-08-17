// openOM MV3 service worker — consumer mode orchestration. Deterministic; zero inference. Runs the
// detect → read → validate → origin → stale → badge pipeline and sets the toolbar badge. The
// pipeline (`handleDetect`) is a pure function with injected deps so it is unit-testable off-browser.

import {
  type BadgeState,
  badgeState,
  honestLabel,
  readPayloadFromBytes,
  type ReadResult,
  validatePayload,
  verifyOrigin,
} from "openom-js";
import schema from "../../spec/om-0.1.schema.json";
import { refetchPdf } from "./detect.js";
import { guardedMirrorFetch, mirrorUrlFor } from "./mirror.js";
import { classifyStale } from "./stale.js";
import { precompiledValidate } from "./validator.js";

export interface DetectResult {
  state: BadgeState;
  label: string;
  caption: string;
  sourceUrl: string;
  payload: Record<string, unknown> | null;
  payloadHash: string | null;
  verification: { hashValid: boolean; originVerified: boolean; signatureValid: null };
  findings: string[];
  stale?: "OMW-W051";
}

export interface DetectDeps {
  refetch?: (url: string) => Promise<Uint8Array | null>;
  read?: (bytes: Uint8Array) => Promise<ReadResult>;
  mirrorFetch?: (url: string) => Promise<{ https: boolean; body: Uint8Array } | null>;
  setBadge?: (state: BadgeState) => void | Promise<void>;
}

const BADGE_TEXT: Record<BadgeState, string> = {
  absent: "",
  "hash-mismatch": "!",
  "integrity-ok": "✓",
  "origin-verified": "✓✓",
  "signature-verified": "✓✓",
};

export async function handleDetect(url: string, deps: DetectDeps = {}): Promise<DetectResult> {
  const refetch = deps.refetch ?? ((u: string) => refetchPdf(u));
  const readFn = deps.read ?? readPayloadFromBytes;
  const mirrorFetch = deps.mirrorFetch ?? ((u: string) => guardedMirrorFetch(u));

  const bytes = await refetch(url);
  const read = bytes ? await readFn(bytes) : null;

  let state: BadgeState;
  const findings: string[] = [];
  let stale: "OMW-W051" | undefined;
  let payload: Record<string, unknown> | null = null;

  if (!read || read.state === "absent") {
    state = "absent";
  } else if (read.state === "hash-mismatch" || read.verification.hashValid !== true) {
    state = "hash-mismatch"; // terminal — no L3/L4
  } else {
    payload = read.payload;
    // Eval-free validator (ajv standalone) — the MV3 CSP forbids ajv's runtime compile.
    const report = validatePayload(payload, schema as Record<string, unknown>, {
      validate: precompiledValidate,
    });
    findings.push(...report.warnings.map((w) => w.code));

    const mirrorUrl = mirrorUrlFor(url);
    const mirrorRes = await mirrorFetch(mirrorUrl);
    const origin = await verifyOrigin({
      sourceUrl: url,
      mirrorUrl,
      embeddedHash: read.payloadHash ?? "",
      fetchMirror: async () => mirrorRes,
    });

    if (!origin.originVerified && origin.reason === "hash-mismatch" && mirrorRes) {
      try {
        const mirrorPayload = JSON.parse(new TextDecoder().decode(mirrorRes.body)) as Record<
          string,
          unknown
        >;
        const s = classifyStale({
          embeddedHash: read.payloadHash ?? "",
          mirrorHash: origin.mirrorHash ?? "",
          embeddedPayload: payload ?? {},
          mirrorPayload,
        });
        if (s.stale && s.code) {
          stale = s.code;
          findings.push(s.code); // surfaced; badge NOT downgraded below integrity-ok
        }
      } catch {
        /* malformed mirror → treat as a plain origin miss, no stale claim */
      }
    }

    state = badgeState({
      present: true,
      hashValid: true,
      originVerified: origin.originVerified,
      signatureValid: null,
    });
  }

  if (deps.setBadge) await deps.setBadge(state);
  const { label, caption } = honestLabel(state);
  return {
    state,
    label,
    caption,
    sourceUrl: url,
    payload,
    payloadHash: read?.payloadHash ?? null,
    verification: {
      hashValid: state !== "absent" && state !== "hash-mismatch",
      originVerified: state === "origin-verified",
      signatureValid: null,
    },
    findings,
    ...(stale ? { stale } : {}),
  };
}

function _chromeSetBadge(state: BadgeState): void {
  chrome.action.setBadgeText({ text: BADGE_TEXT[state] });
  chrome.action.setBadgeBackgroundColor({
    color: state === "hash-mismatch" ? "#b60205" : state === "origin-verified" ? "#0e8a16" : "#888",
  });
}

// Wire messages only in the extension runtime (guarded so unit tests can import handleDetect).
if (typeof chrome !== "undefined" && chrome.runtime?.onMessage) {
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === "detect" && typeof msg.url === "string") {
      handleDetect(msg.url, { setBadge: _chromeSetBadge })
        .then(sendResponse)
        .catch((e) => sendResponse({ error: String(e?.stack ?? e) }));
      return true; // async response
    }
    return false;
  });
}
