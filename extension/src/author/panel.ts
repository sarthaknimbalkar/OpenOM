// openOM author-mode side panel - capture → review → assert → embed → hand back. Deterministic;
// ZERO inference in B1 (on-device extraction arrives in M5b-2). This panel document is the ONLY place
// that reads the clock (assertedDate) and touches chrome.* / the DOM runtime; every transform it calls
// (capture / draft / finalize / repriceDiff / assertAndEmbed) is pure and unit-tested. The workflow
// validates the FINALIZED-shape payload (what would be embedded), so the Assert gate is honest.
import { wordmark } from "../wordmark.js";
import {
  extractPageText,
  integrityHashOfBytes,
  setPdfWorkerSrc,
  validatePayload,
  type PageText,
  type ValidationReport,
} from "openom-js";
import schema from "../../../spec/om-0.1.schema.json";
import { precompiledValidate } from "../validator.js";
import { captureFromBytes, looksLikePdf, type Capture } from "./capture.js";
import {
  newDraft,
  setField,
  setEvidence,
  appendArrayItem,
  removeArrayItem,
  getField,
  type Draft,
} from "./draft.js";
import {
  getProfile,
  setProfile,
  profileComplete,
  type BrokerProfile,
} from "./profile.js";
import { getDraft, setDraft, clearDraft } from "./draft-store.js";
import {
  finalize,
  assertAndEmbed,
  handBack,
  suggestedFilename,
} from "./assert.js";
import { renderDerived, repriceDiff } from "./review-panel.js";
import { buildForm, type FormCallbacks } from "./form.js";
import { applyExtraction } from "./extract/apply.js";
import { onDeviceExtractor } from "./extract/on-device.js";
import { extractorSource, pickDraftSource } from "./extract/source.js";
import { buildoutRefFromUrl } from "./extract/connectors/buildout-http.js";
import { loadBuildoutSource } from "./extract/connectors/load.js";
import { localDateISO } from "./clock.js";

const el = (tag: string, cls?: string, text?: string): HTMLElement => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

const todayISO = (): string => localDateISO(new Date());
const validate = (p: Record<string, unknown>): ValidationReport =>
  validatePayload(p, schema as Record<string, unknown>, {
    validate: precompiledValidate,
  });

const INTRO_SEEN_KEY = "openom.author.seenIntro";

/** One-time, dismissible orientation card so a first-time broker knows what this is + the 3 steps.
 * Never shows again after dismiss or after the first successful embed (see markIntroSeen). */
async function maybeShowIntro(root: HTMLElement, anchor: HTMLElement): Promise<void> {
  try {
    const seen = (await chrome.storage.local.get(INTRO_SEEN_KEY))[INTRO_SEEN_KEY];
    if (seen) return;
  } catch {
    return; // storage unavailable - just skip the card, never block capture
  }
  const card = el("section", "intro-card");
  card.appendChild(
    el("h2", "intro-title", "Turn an offering memorandum into a verified openOM PDF."),
  );
  card.appendChild(
    el(
      "p",
      "intro-body",
      "openOM embeds your listing's key data (price, cap rate, NOI, rent) inside the PDF itself, " +
        "signed as your assertion - so buyers and their tools can read it without re-keying. You " +
        "stay in control: you review and approve every field before anything is embedded.",
    ),
  );
  const steps = el("ol", "intro-steps");
  for (const s of [
    "Load the OM PDF (below).",
    "Review the data - fill or fix each field.",
    "Assert & embed - downloads your openOM PDF.",
  ])
    steps.appendChild(el("li", undefined, s));
  card.appendChild(steps);
  card.appendChild(
    el(
      "p",
      "intro-optional",
      "Optional: Chrome's on-device AI can pre-fill a draft you then review. Not required - you " +
        "can enter everything by hand.",
    ),
  );
  const gotIt = el("button", "intro-dismiss", "Got it") as HTMLButtonElement;
  gotIt.dataset.action = "dismiss-intro";
  gotIt.addEventListener("click", () => {
    card.remove();
    void chrome.storage.local.set({ [INTRO_SEEN_KEY]: true }).catch(() => {});
  });
  card.appendChild(gotIt);
  root.insertBefore(card, anchor);
}

/** After a successful embed, offer the next steps so the flow doesn't dead-end at a download:
 * verify the file, or embed another. (The distribution lever on the supply side.) */
function renderSuccessActions(anchor: HTMLElement, root: HTMLElement): void {
  const actions = el("section", "success-actions");
  const verify = el("button", "verify-embed", "Verify it") as HTMLButtonElement;
  verify.addEventListener("click", () => {
    try {
      void chrome.tabs?.create({ url: "https://openom.app/verify/" });
    } catch {
      /* no tabs API in a test harness - the link text still tells the user where to go */
    }
  });
  const again = el("button", "embed-another", "Embed another") as HTMLButtonElement;
  again.addEventListener("click", () => renderCaptureScreen(root));
  actions.append(verify, again);
  anchor.insertAdjacentElement("afterend", actions);
}

/** Mark the intro as seen so a returning broker (post-first-embed) never sees it again. */
async function markIntroSeen(): Promise<void> {
  try {
    await chrome.storage.local.set({ [INTRO_SEEN_KEY]: true });
  } catch {
    /* best-effort */
  }
}

/** Entry screen: capture the current tab's PDF, or pick a local file.
 * An optional `error` renders a banner ABOVE the still-present controls, so a failed capture never
 * strands the broker on a dead-end screen - the retry paths (tab button / file picker) stay visible. */
export function renderCaptureScreen(root: HTMLElement, opts?: { error?: string }): void {
  root.replaceChildren();
  root.appendChild(wordmark("embed a payload"));
  if (opts?.error) root.appendChild(el("p", "err", opts.error));
  root.appendChild(
    el(
      "p",
      "hint",
      "Capture an offering memorandum, review its data, assert, and embed.",
    ),
  );
  const useTab = el(
    "button",
    "capture-tab",
    "Use current tab's PDF",
  ) as HTMLButtonElement;
  useTab.dataset.action = "capture-tab";
  const file = el("input", "capture-file") as HTMLInputElement;
  file.type = "file";
  file.accept = "application/pdf,.pdf";
  file.setAttribute("aria-label", "Choose an OM PDF from your computer");
  const tabHint = el(
    "p",
    "capture-sub",
    "\"Use current tab's PDF\" grabs the OM open in the active tab; or choose a PDF from your "
      + "computer (any size).",
  );
  root.append(useTab, el("span", "sep", "or"), file, tabHint);

  if (!opts?.error) void maybeShowIntro(root, useTab);

  useTab.addEventListener("click", () => void captureFromTab(root));
  file.addEventListener("change", () => {
    const f = file.files?.[0];
    if (f)
      void f.arrayBuffer().then((b) => startReview(root, new Uint8Array(b)));
  });

  // [M6] Surface the highest-value path up front: if the active tab is a Buildout listing, tell the
  // broker their fields will be imported automatically once they pick the OM PDF (the connector needs
  // the PDF to embed into). Previously the connector was only discoverable deep inside the review flow.
  void chrome.tabs
    ?.query({ active: true, currentWindow: true })
    .then(([tab]) => {
      if (buildoutRefFromUrl(tab?.url)) {
        const hint = el(
          "p",
          "buildout-hint",
          "This looks like a Buildout listing - choose the OM PDF above and its fields will be imported from Buildout automatically.",
        );
        root.insertBefore(hint, useTab);
      }
    })
    .catch(() => {});
}

async function captureFromTab(root: HTMLElement): Promise<void> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.url) {
    await captureFromUrl(root, tab.url);
    return;
  }
  // [P4] no active-tab URL (e.g. a chrome:// page or a restricted tab) - say so, and KEEP the
  // capture controls so the broker can retry via the file picker instead of being stranded.
  renderCaptureScreen(root, {
    error:
      "Couldn't read the current tab's URL. Open the OM in a tab, or choose a PDF from your "
      + "computer below.",
  });
}

/** Fetch a URL's PDF bytes (SW-side, page-CSP-immune) and start review. Also the ?url= deep-link. */
async function captureFromUrl(root: HTMLElement, url: string): Promise<void> {
  // [P4] a large OM re-fetch can take a moment - show progress instead of a frozen panel.
  root.replaceChildren(el("p", "hint", "Fetching PDF…"));
  const resp = (await chrome.runtime.sendMessage({
    type: "author:fetch",
    url,
  })) as { b64: string | null; reason?: "oversize" | "fetch" } | { error: string };
  if ("error" in resp || !resp.b64) {
    // [M6] a too-big OM from the tab path gets a clear, actionable message (not a generic network
    // error) - and note the file picker has no such cap.
    const oversize = !("error" in resp) && resp.reason === "oversize";
    renderCaptureScreen(root, {
      error: oversize
        ? "This OM is larger than 25 MB, so it can't be re-fetched from the tab. Choose it from your computer below (no size limit), or use the openOM CLI."
        : "Could not fetch this page's PDF bytes. Choose the OM from your computer below instead.",
    });
    return;
  }
  await startReview(root, fromB64(resp.b64));
}

/** Build the review workspace: profile form + draft JSON + live-validated review render + Assert. */
async function startReview(
  root: HTMLElement,
  bytes: Uint8Array,
): Promise<void> {
  if (!looksLikePdf(bytes)) {
    // #65 - keep the capture controls so a wrong file is recoverable, not a dead end.
    renderCaptureScreen(root, {
      error:
        "That doesn't look like a PDF - choose an offering-memorandum PDF below and try again.",
    });
    return;
  }
  const capture: Capture = await captureFromBytes(bytes);
  // #107 - pd-lib can't load an encrypted PDF, so embedding would fail opaquely later. Say so now,
  // but keep the controls so the broker can load a different (unencrypted) PDF without being stranded.
  if (capture.encrypted) {
    renderCaptureScreen(root, {
      error:
        "This OM is encrypted, so the extension can't embed into it. Use the openOM CLI (which "
        + "handles encrypted OMs), ask the sender for an unencrypted copy, or load a different PDF below.",
    });
    return;
  }
  const profile0 = (await getProfile()) ?? {
    broker: "",
    brokerage: "",
    license: "",
  };
  root.replaceChildren();

  // #4 - this OM was empty-password permission-encrypted and we decrypted it in-browser to author.
  // pd-lib can't re-encrypt, so the embedded copy will be unencrypted; tell the broker plainly.
  if (capture.wasDecrypted) {
    root.appendChild(
      el(
        "p",
        "decrypted-notice",
        "This OM was permission-encrypted; the extension decrypted it to embed. The published copy will be unencrypted.",
      ),
    );
  }

  // A prior payload that FAILS integrity is not a reprice base - warn that this will be a fresh
  // assertion with no supersedes chain, so the broker is not surprised ([#87]).
  if (capture.priorUnverified) {
    root.appendChild(
      el(
        "p",
        "prior-unverified",
        "This PDF already contains openOM data that FAILS its integrity check. It will not be used as a reprice base - embedding will create a fresh assertion with no link to the prior payload.",
      ),
    );
  }

  // [M1] A digitally-signed OM: embedding rewrites the file and invalidates the signature. Warn and
  // require an explicit acknowledgement before Assert (the CLI is the path to preserve a signature).
  let signedAck = false;
  if (capture.signed) {
    const warn = el("section", "signed-warning");
    warn.appendChild(
      el(
        "p",
        undefined,
        "This PDF is digitally signed. Embedding rewrites the file and will invalidate that signature. To keep the signature, embed with the openOM CLI instead.",
      ),
    );
    const lbl = el("label", "signed-ack-field");
    const ck = el("input", "signed-ack") as HTMLInputElement;
    ck.type = "checkbox";
    ck.addEventListener("change", () => {
      signedAck = ck.checked;
      renderDerivedNow();
    });
    lbl.append(ck, " I understand embedding will invalidate the existing signature.");
    warn.appendChild(lbl);
    root.appendChild(warn);
  }

  // Broker profile (assertedBy), device-local.
  const prof = el("section", "profile");
  prof.appendChild(el("h2", undefined, "Reviewing broker"));
  const pin = (cls: string, ph: string, v: string): HTMLInputElement => {
    const label = el("label", "profile-field");
    const i = el("input", cls) as HTMLInputElement;
    i.placeholder = ph;
    i.value = v;
    i.setAttribute("aria-label", ph); // #71 - placeholder is not an accessible name
    label.append(`${ph} `, i);
    prof.appendChild(label);
    return i;
  };
  const broker = pin("p-broker", "broker", profile0.broker);
  const brokerage = pin("p-brokerage", "brokerage", profile0.brokerage ?? "");
  const license = pin("p-license", "license", profile0.license ?? "");
  root.appendChild(prof);

  // The draft (payload + evidence) is the source of truth so extracted evidence survives re-renders;
  // the textarea edits only the payload half. Seeded from a prior payload on reprice, OR restored from
  // a saved in-progress draft ([#94]). Extraction confidence is never consent - the human still clicks
  // Assert below on the SAME review the extraction pre-filled ([OM-EXTP-003]).
  const sourceDocHash = integrityHashOfBytes(capture.bytes); // #96 provenance + #94 draft key
  const restored = await getDraft(sourceDocHash);
  let draft: Draft = restored ?? newDraft(capture.prior?.payload ?? {});

  const profile = (): BrokerProfile => ({
    broker: broker.value,
    brokerage: brokerage.value,
    license: license.value,
  });
  const prior = capture.prior
    ? {
        payloadHash: capture.prior.payloadHash ?? "",
        payload: capture.prior.payload ?? {},
      }
    : null;

  // Draft source (M5b-2 / #166): prefer a deterministic structured connector (e.g. a Buildout MCP
  // pull), else the on-device Prompt API - else a manual-entry note. Connectors are prepended to this
  // list when configured (see extract/CONNECTORS.md); with none, this is the on-device path unchanged.
  // When Buildout is configured AND the active tab is a Buildout listing, offer that deterministic
  // pull first; any failure (no tab access, not configured, not a listing URL) is swallowed so the
  // on-device path is byte-identical to before.
  let buildoutSource = null;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const ref = buildoutRefFromUrl(tab?.url);
    if (ref) buildoutSource = await loadBuildoutSource(ref);
  } catch {
    buildoutSource = null;
  }
  // the on-device-model download progress renders in a dedicated line RIGHT UNDER the extract
  // button, not the bottom status line - so a broker watching the download sees it where they clicked.
  let extractProgress: HTMLElement | null = null;
  const source = await pickDraftSource([
    ...(buildoutSource ? [buildoutSource] : []),
    extractorSource(onDeviceExtractor, "on-device AI"),
  ]);
  if (source) {
    // [M5] Be honest when the on-device model isn't downloaded yet: a click would otherwise trigger a
    // silent multi-GB download. Label it so, and note manual entry is always available.
    const needsDownload = !source.deterministic && (await source.readiness()) === "needs-download";
    const label = source.deterministic
      ? `Import from ${source.label}`
      : needsDownload
        ? `Download on-device AI (~1-2 GB), then extract`
        : `Extract with ${source.label}`;
    const btn = el("button", "extract-btn", label) as HTMLButtonElement;
    btn.dataset.action = "extract";
    btn.addEventListener("click", () => void runExtract());
    root.appendChild(btn);
    extractProgress = el("p", "extract-progress"); // sits directly under the button
    extractProgress.setAttribute("aria-live", "polite");
    root.appendChild(extractProgress);
    if (needsDownload) {
      root.appendChild(
        el(
          "p",
          "extract-hint",
          "On-device AI isn't downloaded yet - the first extract downloads it (progress shown). You can also just enter the fields manually.",
        ),
      );
    }
  } else {
    root.appendChild(
      el(
        "p",
        "no-ai",
        "On-device AI isn't available in this browser (it needs Chrome 128+ with the built-in AI "
          + "model, and not all machines qualify). That's fine - entering the fields by hand is the "
          + "normal path, not a fallback. Fill in the review form below.",
      ),
    );
  }

  const formEl = el("section", "form"); // stable inputs, built once (focus-safe)
  const derivedEl = el("section", "derived"); // validation/preview/assert, re-rendered each edit
  const status = el("p", "status");
  status.setAttribute("aria-live", "polite"); // #71 - announce embed/extract/error outcomes
  root.append(formEl, derivedEl, status);

  // Re-render ONLY the derived panel (no inputs to lose focus). The Assert gate reflects the FINALIZED
  // payload - exactly what would be embedded - so the human approves the real assertion (#95).
  const renderDerivedNow = (): void => {
    const finalized = finalize(
      draft,
      profile(),
      todayISO(),
      prior && { payloadHash: prior.payloadHash },
      sourceDocHash,
    );
    const report = validate(finalized);
    const diff = prior
      ? repriceDiff(prior.payload, finalized, prior.payloadHash)
      : null;
    renderDerived(derivedEl, draft, { report, diff, finalized });
    if (!profileComplete(profile())) {
      derivedEl.appendChild(
        el(
          "p",
          "profile-incomplete",
          "Complete the broker profile (broker, brokerage, license) to assert.",
        ),
      ); // #97
    }
    const assertBtn = derivedEl.querySelector("#assert");
    // An incomplete broker profile must DISABLE Assert, not just show a note: the schema now rejects
    // a whitespace-only identity, but this also blocks the missing-profile case at the UI before the
    // human clicks - the assertion gate must never let an "asserted by nobody" record through.
    if (!profileComplete(profile()) && assertBtn instanceof HTMLButtonElement) {
      assertBtn.disabled = true;
    }
    // [M1] block Assert until a signed OM's invalidation is acknowledged.
    if (capture.signed && !signedAck && assertBtn instanceof HTMLButtonElement) {
      assertBtn.disabled = true;
    }
    assertBtn?.addEventListener("click", () => void doAssert());
  };

  // A field-level edit mutates the draft (source of truth), persists (#94), and refreshes the derived
  // panel only. Structural changes (rent rows, raw-JSON) additionally rebuild the form once.
  const edit = (mutate: (d: Draft) => Draft): void => {
    draft = mutate(draft);
    void setDraft(sourceDocHash, draft);
    renderDerivedNow();
  };
  const rebuild = (mutate: (d: Draft) => Draft): void => {
    draft = mutate(draft);
    void setDraft(sourceDocHash, draft);
    buildFormNow();
    renderDerivedNow();
  };

  const callbacks: FormCallbacks = {
    onField: (p, v) => {
      const wasNoi = getField(draft, "/deal/noi") !== undefined;
      draft = setField(draft, p, v);
      void setDraft(sourceDocHash, draft);
      // The #93 noiType/noiAsOfDate controls are conditional on deal.noi - rebuild the form only when
      // noi crosses the empty↔set boundary (so those controls appear/disappear), else just re-derive.
      if (
        p === "/deal/noi" &&
        wasNoi !== (getField(draft, "/deal/noi") !== undefined)
      )
        buildFormNow();
      renderDerivedNow();
    },
    onEvidence: (p, e) => edit((d) => setEvidence(d, p, e)),
    onAddRentPeriod: () =>
      rebuild((d) =>
        appendArrayItem(d, "/lease/rentSchedule", { source: "extracted" }),
      ),
    onRemoveRentPeriod: (i) =>
      rebuild((d) => removeArrayItem(d, "/lease/rentSchedule", i)),
    // [M7] open the SOURCE OM (the captured bytes) at the cited page in a new tab so the broker can
    // check the value against the document. Uses the PDF viewer's #page= fragment; a blob URL keeps
    // the bytes local (never uploaded).
    onViewPage: (n) => {
      const url = URL.createObjectURL(
        new Blob([new Uint8Array(capture.bytes)], { type: "application/pdf" }),
      );
      window.open(`${url}#page=${n}`, "_blank", "noopener");
      // Revoke after the viewer has had time to load the bytes.
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    },
  };

  const buildFormNow = (): void => {
    buildForm(formEl, draft, callbacks);
    // The Advanced raw-JSON textarea is rebuilt with the form; (re)wire it on `change` (not `input`)
    // so committing raw JSON rebuilds the form once, without a rebuild on every keystroke.
    const ta = formEl.querySelector(
      "textarea.draft-json",
    ) as HTMLTextAreaElement | null;
    ta?.addEventListener("change", () => {
      try {
        rebuild(() => ({
          payload: JSON.parse(ta.value) as Record<string, unknown>,
          evidence: draft.evidence,
        }));
      } catch {
        status.textContent = "Draft is not valid JSON.";
      }
    });
  };

  const doAssert = async (): Promise<void> => {
    if (capture.signed && !signedAck) {
      status.textContent = "Blocked: acknowledge the signature will be invalidated first.";
      return;
    }
    if (!profileComplete(profile())) {
      // Defense-in-depth: never embed an unidentified assertion even if the button were reached.
      status.textContent = "Blocked: complete the broker profile (broker, brokerage, license) first.";
      return;
    }
    try {
      await setProfile(profile());
      const final = finalize(
        draft,
        profile(),
        todayISO(),
        prior && { payloadHash: prior.payloadHash },
        sourceDocHash,
      );
      const out = await assertAndEmbed(
        final,
        capture.bytes,
        validate,
        embedViaSW,
      );
      handBack(out, suggestedFilename(final)); // #99 - meaningful name from the property address
      void clearDraft(sourceDocHash); // #94 - the OM is embedded; drop the saved draft
      void markIntroSeen(); // a broker who's shipped one OM no longer needs the first-run card
      status.textContent = "Embedded - your openOM PDF downloaded. What next:";
      renderSuccessActions(status, root);
    } catch (e) {
      status.textContent = `Blocked: ${(e as Error).message}`;
    }
  };

  const runExtract = async (): Promise<void> => {
    if (!source) return;
    try {
      // A deterministic connector (e.g. Buildout) needs NO PDF text - skip text extraction, the
      // scanned-no-text-layer block, and the truncation note, which are all PDF-inference-only.
      let pages: PageText[] = [];
      let totalPages = 0;
      if (!source.deterministic) {
        // [M4] read deeper than the old 40-page default - rent rolls / financial exhibits sit at the
        // back of long OMs; on-device extraction chunks the text, so more pages is safe.
        ({ pages, totalPages } = await extractPageText(capture.bytes, 80));
        // #91 - a scanned/flattened OM has no text layer; say so instead of pre-filling a blank draft.
        if (!pages.some((p) => p.text.trim().length > 0)) {
          status.textContent =
            "This OM appears to be scanned (no text layer) - extraction can't read it. Enter fields manually.";
          return;
        }
      }
      const result = await source.draft({
        pages,
        // [M5] surface on-device model download progress instead of a silent hang - directly under
        // the extract button (extractProgress) so it's visible where the broker clicked.
        onDownloadProgress: (f) =>
          ((extractProgress ?? status).textContent =
            `Downloading on-device AI… ${Math.round(f * 100)}%`),
      });
      if (extractProgress) extractProgress.textContent = ""; // clear once the model is ready
      rebuild((d) => applyExtraction(d, result)); // reflect drafted fields in the form + derived
      // #66 - surface when only a prefix of a long OM was read; never a silent "complete".
      const truncated =
        !source.deterministic && pages.length < totalPages
          ? ` (read pages 1–${pages.length} of ${totalPages} only)`
          : "";
      const verb = source.deterministic ? "Imported" : "Extracted";
      status.textContent = `${verb} a draft - review every field before asserting.${truncated}`;
    } catch (e) {
      status.textContent = `Extraction failed: ${(e as Error).message}`;
    }
  };

  for (const i of [broker, brokerage, license])
    i.addEventListener("input", renderDerivedNow);
  buildFormNow();
  renderDerivedNow();
}

async function embedViaSW(
  bytes: Uint8Array,
  payload: Record<string, unknown>,
): Promise<Uint8Array> {
  const resp = (await chrome.runtime.sendMessage({
    type: "author:embed",
    pdfB64: toB64(bytes),
    payload,
  })) as { okB64: string } | { error: string };
  if ("error" in resp) throw new Error(resp.error);
  return fromB64(resp.okB64);
}

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

// ---- runtime bootstrap (guarded so jsdom/unit imports don't require chrome) ----
if (typeof chrome !== "undefined" && chrome.runtime?.id) {
  const root = document.getElementById("author");
  if (root) {
    void (async () => {
      // pdf.js needs its worker as an extension URL before extractPageText runs (the panel is a full
      // page, so unlike the consumer service worker it CAN spawn the Worker). Set it once.
      await setPdfWorkerSrc(chrome.runtime.getURL("pdf.worker.mjs"));

      // ?url= deep-link auto-captures (used by the live gate and as a shareable "embed this" link);
      // otherwise show the capture screen (current tab / file picker).
      const override = new URLSearchParams(location.search).get("url");
      if (override) await captureFromUrl(root, override);
      else renderCaptureScreen(root);
    })();
  }
}
