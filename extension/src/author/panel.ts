// openOM author-mode side panel — capture → review → assert → embed → hand back. Deterministic;
// ZERO inference in B1 (on-device extraction arrives in M5b-2). This panel document is the ONLY place
// that reads the clock (assertedDate) and touches chrome.* / the DOM runtime; every transform it calls
// (capture / draft / finalize / repriceDiff / assertAndEmbed) is pure and unit-tested. The workflow
// validates the FINALIZED-shape payload (what would be embedded), so the Assert gate is honest.
import {
  extractPageText,
  integrityHashOfBytes,
  setPdfWorkerSrc,
  validatePayload,
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
  type Draft,
} from "./draft.js";
import { getProfile, setProfile, profileComplete, type BrokerProfile } from "./profile.js";
import { getDraft, setDraft, clearDraft } from "./draft-store.js";
import { finalize, assertAndEmbed, handBack, suggestedFilename } from "./assert.js";
import { renderDerived, repriceDiff } from "./review-panel.js";
import { buildForm, type FormCallbacks } from "./form.js";
import { applyExtraction } from "./extract/apply.js";
import { onDeviceExtractor } from "./extract/on-device.js";
import { pickExtractor } from "./extract/pick.js";
import { localDateISO } from "./clock.js";

const el = (tag: string, cls?: string, text?: string): HTMLElement => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

const todayISO = (): string => localDateISO(new Date());
const validate = (p: Record<string, unknown>): ValidationReport =>
  validatePayload(p, schema as Record<string, unknown>, { validate: precompiledValidate });

/** Entry screen: capture the current tab's PDF, or pick a local file. */
export function renderCaptureScreen(root: HTMLElement): void {
  root.replaceChildren();
  root.appendChild(el("h1", "title", "openOM — embed a payload"));
  root.appendChild(el("p", "hint", "Capture an offering memorandum, review its data, assert, and embed."));
  const useTab = el("button", "capture-tab", "Use current tab's PDF") as HTMLButtonElement;
  useTab.dataset.action = "capture-tab";
  const file = el("input", "capture-file") as HTMLInputElement;
  file.type = "file";
  file.accept = "application/pdf,.pdf";
  root.append(useTab, el("span", "sep", "or"), file);

  useTab.addEventListener("click", () => void captureFromTab(root));
  file.addEventListener("change", () => {
    const f = file.files?.[0];
    if (f) void f.arrayBuffer().then((b) => startReview(root, new Uint8Array(b)));
  });
}

async function captureFromTab(root: HTMLElement): Promise<void> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.url) await captureFromUrl(root, tab.url);
}

/** Fetch a URL's PDF bytes (SW-side, page-CSP-immune) and start review. Also the ?url= deep-link. */
async function captureFromUrl(root: HTMLElement, url: string): Promise<void> {
  const resp = (await chrome.runtime.sendMessage({ type: "author:fetch", url })) as
    | { b64: string | null }
    | { error: string };
  if ("error" in resp || !resp.b64) {
    root.replaceChildren(el("p", "err", "Could not fetch this page's PDF bytes."));
    return;
  }
  await startReview(root, fromB64(resp.b64));
}

/** Build the review workspace: profile form + draft JSON + live-validated review render + Assert. */
async function startReview(root: HTMLElement, bytes: Uint8Array): Promise<void> {
  if (!looksLikePdf(bytes)) {
    root.replaceChildren(el("p", "err", "That doesn't look like a PDF — capture an offering-memorandum PDF.")); // #65
    return;
  }
  const capture: Capture = await captureFromBytes(bytes);
  const profile0 = (await getProfile()) ?? { broker: "", brokerage: "", license: "" };
  root.replaceChildren();

  // A prior payload that FAILS integrity is not a reprice base — warn that this will be a fresh
  // assertion with no supersedes chain, so the broker is not surprised ([#87]).
  if (capture.priorUnverified) {
    root.appendChild(
      el(
        "p",
        "prior-unverified",
        "This PDF already contains openOM data that FAILS its integrity check. It will not be used as a reprice base — embedding will create a fresh assertion with no link to the prior payload.",
      ),
    );
  }

  // Broker profile (assertedBy), device-local.
  const prof = el("section", "profile");
  prof.appendChild(el("h2", undefined, "Reviewing broker"));
  const pin = (cls: string, ph: string, v: string): HTMLInputElement => {
    const i = el("input", cls) as HTMLInputElement;
    i.placeholder = ph;
    i.value = v;
    prof.appendChild(i);
    return i;
  };
  const broker = pin("p-broker", "broker", profile0.broker);
  const brokerage = pin("p-brokerage", "brokerage", profile0.brokerage ?? "");
  const license = pin("p-license", "license", profile0.license ?? "");
  root.appendChild(prof);

  // The draft (payload + evidence) is the source of truth so extracted evidence survives re-renders;
  // the textarea edits only the payload half. Seeded from a prior payload on reprice, OR restored from
  // a saved in-progress draft ([#94]). Extraction confidence is never consent — the human still clicks
  // Assert below on the SAME review the extraction pre-filled ([OM-EXTP-003]).
  const sourceDocHash = integrityHashOfBytes(capture.bytes); // #96 provenance + #94 draft key
  const restored = await getDraft(sourceDocHash);
  let draft: Draft = restored ?? newDraft(capture.prior?.payload ?? {});

  const profile = (): BrokerProfile => ({ broker: broker.value, brokerage: brokerage.value, license: license.value });
  const prior = capture.prior ? { payloadHash: capture.prior.payloadHash ?? "", payload: capture.prior.payload ?? {} } : null;

  // On-device extraction (M5b-2): offer it only when a Prompt API is present; else a manual-entry note.
  const extractor = await pickExtractor([onDeviceExtractor]);
  if (extractor) {
    const btn = el("button", "extract-btn", "Extract with on-device AI") as HTMLButtonElement;
    btn.dataset.action = "extract";
    btn.addEventListener("click", () => void runExtract());
    root.appendChild(btn);
  } else {
    root.appendChild(el("p", "no-ai", "On-device AI unavailable — enter fields manually."));
  }

  const formEl = el("section", "form"); // stable inputs, built once (focus-safe)
  const derivedEl = el("section", "derived"); // validation/preview/assert, re-rendered each edit
  const status = el("p", "status");
  root.append(formEl, derivedEl, status);

  // Re-render ONLY the derived panel (no inputs to lose focus). The Assert gate reflects the FINALIZED
  // payload — exactly what would be embedded — so the human approves the real assertion (#95).
  const renderDerivedNow = (): void => {
    const finalized = finalize(draft, profile(), todayISO(), prior && { payloadHash: prior.payloadHash }, sourceDocHash);
    const report = validate(finalized);
    const diff = prior ? repriceDiff(prior.payload, finalized, prior.payloadHash) : null;
    renderDerived(derivedEl, draft, { report, diff, finalized });
    if (!profileComplete(profile())) {
      derivedEl.appendChild(el("p", "profile-incomplete", "Complete the broker profile (broker, brokerage, license) to assert.")); // #97
    }
    derivedEl.querySelector("#assert")?.addEventListener("click", () => void doAssert());
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
    onField: (p, v) => edit((d) => setField(d, p, v)),
    onEvidence: (p, e) => edit((d) => setEvidence(d, p, e)),
    onAddRentPeriod: () => rebuild((d) => appendArrayItem(d, "/lease/rentSchedule", { source: "extracted" })),
    onRemoveRentPeriod: (i) => rebuild((d) => removeArrayItem(d, "/lease/rentSchedule", i)),
  };

  const buildFormNow = (): void => {
    buildForm(formEl, draft, callbacks);
    // The Advanced raw-JSON textarea is rebuilt with the form; (re)wire it on `change` (not `input`)
    // so committing raw JSON rebuilds the form once, without a rebuild on every keystroke.
    const ta = formEl.querySelector("textarea.draft-json") as HTMLTextAreaElement | null;
    ta?.addEventListener("change", () => {
      try {
        rebuild(() => ({ payload: JSON.parse(ta.value) as Record<string, unknown>, evidence: draft.evidence }));
      } catch {
        status.textContent = "Draft is not valid JSON.";
      }
    });
  };

  const doAssert = async (): Promise<void> => {
    try {
      await setProfile(profile());
      const final = finalize(draft, profile(), todayISO(), prior && { payloadHash: prior.payloadHash }, sourceDocHash);
      const out = await assertAndEmbed(final, capture.bytes, validate, embedViaSW);
      handBack(out, suggestedFilename(final)); // #99 — meaningful name from the property address
      void clearDraft(sourceDocHash); // #94 — the OM is embedded; drop the saved draft
      status.textContent = "Embedded — downloaded the OM.";
    } catch (e) {
      status.textContent = `Blocked: ${(e as Error).message}`;
    }
  };

  const runExtract = async (): Promise<void> => {
    if (!extractor) return;
    try {
      const { pages, totalPages } = await extractPageText(capture.bytes);
      // #91 — a scanned/flattened OM has no text layer; say so instead of pre-filling a blank draft.
      if (!pages.some((p) => p.text.trim().length > 0)) {
        status.textContent =
          "This OM appears to be scanned (no text layer) — extraction can't read it. Enter fields manually.";
        return;
      }
      const result = await extractor.extract(pages);
      rebuild((d) => applyExtraction(d, result)); // reflect extracted fields in the form + derived
      // #66 — surface when only a prefix of a long OM was read; never a silent "complete".
      const truncated = pages.length < totalPages ? ` (read pages 1–${pages.length} of ${totalPages} only)` : "";
      status.textContent = `Extracted a draft — review every field before asserting.${truncated}`;
    } catch (e) {
      status.textContent = `Extraction failed: ${(e as Error).message}`;
    }
  };

  for (const i of [broker, brokerage, license]) i.addEventListener("input", renderDerivedNow);
  buildFormNow();
  renderDerivedNow();
}

async function embedViaSW(bytes: Uint8Array, payload: Record<string, unknown>): Promise<Uint8Array> {
  const resp = (await chrome.runtime.sendMessage({ type: "author:embed", pdfB64: toB64(bytes), payload })) as
    | { okB64: string }
    | { error: string };
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
