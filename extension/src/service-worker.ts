// openOM MV3 service worker - consumer mode orchestration. Deterministic; zero inference. Runs the
// detect → read → validate → origin → stale → badge pipeline and sets the toolbar badge. The
// pipeline (`handleDetect`) is a pure function with injected deps so it is unit-testable off-browser.

import {
  type BadgeState,
  badgeState,
  embedPayload,
  honestLabel,
  readPayloadFromBytes,
  type ReadResult,
  validatePayload,
  verifyOrigin,
} from "openom-js";
import schema from "../../spec/om-0.1.schema.json";
import { refetchPdf, refetchPdfResult } from "./detect.js";
import { accepts } from "./message-gate.js";
import { guardedMirrorFetch, mirrorUrlFor } from "./mirror.js";
import { classifyStale } from "./stale.js";
import { precompiledValidate } from "./validator.js";
import { assertEmbeddable } from "./author/embed-guard.js";
import { getCachedDetect, setCachedDetect } from "./cache.js";
import { getSettings, isLinkBadgingDomain, setLinkBadging } from "./storage.js";
import { getDomain } from "tldts";

export interface DetectResult {
  state: BadgeState;
  label: string;
  caption: string;
  sourceUrl: string;
  payload: Record<string, unknown> | null;
  payloadHash: string | null;
  verification: {
    hashValid: boolean;
    originVerified: boolean;
    signatureValid: null;
  };
  findings: string[];
  /** [M3] full residual findings (code + human message + severity + path), not just bare codes, so a
   * consumer/portal shows "Cap rate vs NOI/price off (OMW-W020)" instead of an opaque token. */
  notices?: { code: string; message: string; severity: string; path: string }[];
  stale?: "OMW-W051";
  /** [M4] why state is "absent" when it's really an encrypted OM (the browser can't read it, but the
   * CLI/Python path can) - so programmatic ingest can route it deterministically instead of parsing a
   * caption. Absent on a genuinely payload-free PDF. */
  reason?: "encrypted";
}

export interface DetectDeps {
  refetch?: (url: string) => Promise<Uint8Array | null>;
  read?: (bytes: Uint8Array) => Promise<ReadResult>;
  mirrorFetch?: (
    url: string,
  ) => Promise<{ https: boolean; body: Uint8Array } | null>;
  setBadge?: (state: BadgeState) => void | Promise<void>;
}

const BADGE_TEXT: Record<BadgeState, string> = {
  absent: "",
  "hash-mismatch": "!",
  "integrity-ok": "✓",
  "origin-verified": "✓✓",
  "signature-verified": "✓✓",
};

export async function handleDetect(
  url: string,
  deps: DetectDeps = {},
): Promise<DetectResult> {
  const refetch = deps.refetch ?? ((u: string) => refetchPdf(u));
  const readFn = deps.read ?? readPayloadFromBytes;
  const mirrorFetch =
    deps.mirrorFetch ?? ((u: string) => guardedMirrorFetch(u));

  const bytes = await refetch(url);
  const read = bytes ? await readFn(bytes) : null;

  let state: BadgeState;
  // [debt#3] `notices` is the single source of truth for validation findings; `findings` (the bare
  // code list) is DERIVED from it at return, so the two can't drift.
  const notices: DetectResult["notices"] = [];
  let stale: "OMW-W051" | undefined;
  let payload: Record<string, unknown> | null = null;
  const encrypted = read?.state === "encrypted"; // #72 - distinct from a plain "no payload" PDF

  if (!read || read.state === "absent" || read.state === "encrypted") {
    state = "absent";
  } else if (
    read.state === "hash-mismatch" ||
    read.verification.hashValid !== true
  ) {
    state = "hash-mismatch"; // terminal - no L3/L4
  } else {
    payload = read.payload;
    // Eval-free validator (ajv standalone) - the MV3 CSP forbids ajv's runtime compile.
    const report = validatePayload(payload, schema as Record<string, unknown>, {
      validate: precompiledValidate,
    });
    // [M3] carry the full finding (message/severity/path), not only the code.
    for (const w of [...report.warnings, ...report.info]) {
      notices.push({ code: w.code, message: w.message, severity: w.severity, path: w.path });
    }

    const mirrorUrl = mirrorUrlFor(url);
    const mirrorRes = await mirrorFetch(mirrorUrl);
    const origin = await verifyOrigin({
      sourceUrl: url,
      mirrorUrl,
      embeddedHash: read.payloadHash ?? "",
      fetchMirror: async () => mirrorRes,
    });

    if (
      !origin.originVerified &&
      origin.reason === "hash-mismatch" &&
      mirrorRes
    ) {
      try {
        const mirrorPayload = JSON.parse(
          new TextDecoder().decode(mirrorRes.body),
        ) as Record<string, unknown>;
        const s = classifyStale({
          embeddedHash: read.payloadHash ?? "",
          mirrorHash: origin.mirrorHash ?? "",
          embeddedPayload: payload ?? {},
          mirrorPayload,
        });
        if (s.stale && s.code) {
          stale = s.code; // surfaced (also in derived findings); badge NOT downgraded below integrity-ok
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
  const honest = honestLabel(state);
  // #72 - an encrypted PDF is "absent" for the badge, but say WHY rather than "no data / vision fallback".
  const label = encrypted ? "Encrypted PDF" : honest.label;
  const caption = encrypted
    ? "This PDF is encrypted - openOM can't read it."
    : honest.caption;
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
    // [debt#3] derived from `notices` (+ the encrypted/stale signals) - one source, no drift.
    findings: [
      ...(encrypted ? ["encrypted"] : []),
      ...notices.filter((n) => n.severity !== "info").map((n) => n.code),
      ...(stale ? [stale] : []),
    ],
    notices,
    ...(encrypted ? { reason: "encrypted" as const } : {}),
    ...(stale ? { stale } : {}),
  };
}

// Badge is PER-TAB ([#83]): a detection on one tab must not paint every tab's toolbar. When a tabId
// is known (the popup reports the tab it inspected), scope the badge to it; without one, no-op rather
// than set a misleading global badge.
function _chromeSetBadge(state: BadgeState, tabId?: number): void {
  if (typeof tabId !== "number") return;
  chrome.action.setBadgeText({ text: BADGE_TEXT[state], tabId });
  chrome.action.setBadgeBackgroundColor({
    color:
      state === "hash-mismatch"
        ? "#b60205"
        : state === "origin-verified"
          ? "#0e8a16"
          : "#888",
    tabId,
  });
}

/** base64 <-> bytes for structured-clone-safe panel<->SW message payloads (PDF bytes). */
function toB64(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}
function fromB64(b64: string): Uint8Array {
  const s = atob(b64);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

/** Detect for a URL, serving a fresh 24h cache when present (#68) and painting the per-tab badge. */
async function detectCached(
  url: string,
  tabId?: number,
): Promise<DetectResult> {
  const now = Date.now();
  const cached = await getCachedDetect(url, now);
  if (cached) {
    _chromeSetBadge(cached.state, tabId);
    return cached;
  }
  const result = await handleDetect(url, {
    setBadge: (s) => _chromeSetBadge(s, tabId),
  });
  await setCachedDetect(url, result, now);
  return result;
}

// Wire messages only in the extension runtime (guarded so unit tests can import handleDetect).
if (typeof chrome !== "undefined" && chrome.runtime?.onMessage) {
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    // #127 (fixed): only trust messages from THIS extension's own contexts, and confine content
    // scripts to the read-only badge verbs. The content-script test is by sender URL, not merely by
    // the presence of a tab - our own extension pages hosted in a tab (deep-link popup, side panel)
    // also have sender.tab set and must NOT be treated as content scripts. See message-gate.ts.
    if (!accepts(sender, msg?.type, chrome.runtime.id)) return false;
    if (msg?.type === "detect" && typeof msg.url === "string") {
      const tabId = typeof msg.tabId === "number" ? msg.tabId : undefined;
      detectCached(msg.url, tabId)
        .then(sendResponse)
        .catch((e) => sendResponse({ error: String(e?.stack ?? e) }));
      return true; // async response
    }
    // Author mode (M5b) - capture re-fetches PDF bytes SW-side (page CSP can't block it); embed runs
    // the deterministic /js embedPayload. Zero inference; the human assertion happens in the panel.
    if (msg?.type === "author:fetch" && typeof msg.url === "string") {
      // [M6] return a typed reason so the panel can say "too big - use the file picker/CLI" instead
      // of a generic network error (image-heavy OMs routinely exceed the 25MB re-fetch ceiling).
      refetchPdfResult(msg.url)
        .then((r) =>
          sendResponse(r.ok ? { b64: toB64(r.bytes) } : { b64: null, reason: r.reason }),
        )
        .catch((e) => sendResponse({ error: String(e?.stack ?? e) }));
      return true;
    }
    // Link-badging (#69) - the content script is thin; the SW gates by eTLD+1 and verifies via the
    // deterministic detect pipeline (24h cache), returning only the badge state (never a tab badge).
    if (msg?.type === "linkbadge:enabled" && typeof msg.hostname === "string") {
      const d = getDomain(msg.hostname);
      (d ? isLinkBadgingDomain(d) : Promise.resolve(false)).then((enabled) =>
        sendResponse({ enabled }),
      );
      return true;
    }
    if (msg?.type === "linkbadge:verify" && typeof msg.url === "string") {
      detectCached(msg.url)
        .then((r) => sendResponse({ state: r.state }))
        .catch(() => sendResponse({ state: "absent" as BadgeState }));
      return true;
    }
    if (msg?.type === "linkbadge:toggle" && typeof msg.hostname === "string") {
      const d = getDomain(msg.hostname);
      if (!d) {
        sendResponse({ enabled: false });
        return true;
      }
      isLinkBadgingDomain(d)
        .then(async (was) => {
          await setLinkBadging(d, !was);
          sendResponse({ enabled: !was });
        })
        .catch((e) => sendResponse({ error: String(e?.stack ?? e) }));
      return true;
    }
    if (
      msg?.type === "author:embed" &&
      typeof msg.pdfB64 === "string" &&
      msg.payload
    ) {
      const payload = msg.payload as Record<string, unknown>;
      Promise.resolve()
        .then(() => {
          assertEmbeddable(
            payload,
            schema as Record<string, unknown>,
            precompiledValidate,
          ); // #98
          return embedPayload(fromB64(msg.pdfB64), payload);
        })
        .then((out) => sendResponse({ okB64: toB64(out) }))
        .catch((e) => sendResponse({ error: String(e?.stack ?? e) }));
      return true;
    }
    return false;
  });
}

// §15 Q8 proactive detection (#84): OFF by default (privacy-conservative - the popup is the default
// check). When the broker opts in, detect + badge a freshly-loaded HTTPS PDF on navigation, reusing
// the 24h cache so it's cheap. Never fires unless the setting is on.
if (typeof chrome !== "undefined" && chrome.tabs?.onUpdated) {
  chrome.tabs.onUpdated.addListener((tabId, info, tab) => {
    if (info.status !== "complete") return;
    const url = tab.url;
    if (!url || !url.startsWith("https://") || !/\.pdf($|\?|#)/i.test(url))
      return;
    void getSettings().then((s) => {
      if (s.proactiveDetection) void detectCached(url, tabId).catch(() => {});
    });
  });
}
