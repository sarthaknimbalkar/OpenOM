/**
 * The hosted authoring companion (#B1) - a fully client-side "drop an OM → fill the deal → assert →
 * download the embedded OM" flow for brokers with no toolchain. Bytes NEVER leave the browser: read,
 * validate, and embed all run locally via the exact deterministic openom-js path the extension and CLI
 * use (never re-implemented), so a web-embedded OM and a CLI-embedded OM can never disagree.
 *
 * Zero inference (consumer/authoring-deterministic surface): this companion does NO extraction - the
 * broker types the fields and asserts them. It is the human assertion gate in its simplest form.
 *
 * This file is the DOM shell; build it via widget/build.mjs and typecheck via tsconfig.widget.json
 * (it needs the DOM lib the deterministic core deliberately excludes).
 */
import { embedPayload } from "../src/embed.js";
import { validatePayload, type ValidationReport } from "../src/validate.js";
import { schemaFieldDescriptors, type FieldDescriptor, type FieldKind } from "../src/fields.js";
import {
  finalizePayload,
  assertAndEmbed,
  suggestedFilename,
  captureFromBytes,
} from "../src/author.js";
import schema from "../../spec/om-0.1.schema.json";

const SCHEMA = schema as Record<string, unknown>;

/** UTC calendar date (YYYY-MM-DD) - the assertedDate stamped at assert time (#64: UTC, never local). */
function todayUtc(): string {
  return new Date().toISOString().slice(0, 10);
}

// ---- JSON-pointer get/set (numeric token → array, per #86) ------------------------------------------
function getField(obj: Record<string, unknown>, pointer: string): unknown {
  const parts = pointer.split("/").filter(Boolean);
  let cur: unknown = obj;
  for (const raw of parts) {
    const key = raw.replace(/~1/g, "/").replace(/~0/g, "~");
    if (cur === null || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[key];
  }
  return cur;
}
function setField(obj: Record<string, unknown>, pointer: string, value: unknown): void {
  const parts = pointer
    .split("/")
    .filter(Boolean)
    .map((r) => r.replace(/~1/g, "/").replace(/~0/g, "~"));
  if (parts.length === 0) return;
  let cur: Record<string, unknown> | unknown[] = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    const key = parts[i] as string;
    const nextIsIndex = /^\d+$/.test(parts[i + 1] as string);
    const existing = Array.isArray(cur) ? cur[Number(key)] : cur[key];
    if (existing === undefined || existing === null || typeof existing !== "object") {
      const created: Record<string, unknown> | unknown[] = nextIsIndex ? [] : {};
      if (Array.isArray(cur)) cur[Number(key)] = created;
      else cur[key] = created;
      cur = created;
    } else {
      cur = existing as Record<string, unknown> | unknown[];
    }
  }
  const last = parts[parts.length - 1] as string;
  if (value === undefined) {
    if (Array.isArray(cur)) delete cur[Number(last)];
    else delete cur[last];
    return;
  }
  if (Array.isArray(cur)) cur[Number(last)] = value;
  else cur[last] = value;
}

// ---- small DOM helpers ------------------------------------------------------------------------------
function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  cls?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

function makeControl(desc: FieldDescriptor, value: unknown): HTMLInputElement | HTMLSelectElement {
  if (desc.kind === "enum") {
    const s = document.createElement("select");
    s.appendChild(new Option("-", ""));
    for (const opt of desc.enum ?? []) s.appendChild(new Option(opt, opt));
    if (typeof value === "string") s.value = value;
    return s;
  }
  const i = document.createElement("input");
  i.type =
    desc.kind === "number"
      ? "number"
      : desc.kind === "date"
        ? "date"
        : desc.kind === "boolean"
          ? "checkbox"
          : "text";
  if (desc.kind === "boolean") i.checked = value === true;
  else if (value !== undefined && value !== null) i.value = String(value);
  return i;
}
function readControl(desc: FieldDescriptor, c: HTMLInputElement | HTMLSelectElement): unknown {
  if (desc.kind === "boolean") return (c as HTMLInputElement).checked;
  const raw = c.value;
  if (raw === "") return undefined;
  return desc.kind === "number" ? Number(raw) : raw;
}

const SECTION_LABEL: Record<string, string> = {
  property: "Property",
  deal: "Deal",
  lease: "Lease",
};
const RENT_FIELDS: { key: string; kind: FieldKind; label: string }[] = [
  { key: "periodStart", kind: "date", label: "Start" },
  { key: "periodEnd", kind: "date", label: "End" },
  { key: "annualRent", kind: "number", label: "Annual rent" },
  { key: "rentPSF", kind: "number", label: "Rent PSF" },
];

interface State {
  bytes: Uint8Array | null;
  filenameHint: string;
  draft: Record<string, unknown>;
  prior: { payloadHash: string } | null; // set on reprice (existing payload present)
  wasDecrypted: boolean; // an empty-password AES OM was decrypted in-browser ([#4])
  priorUnverified: boolean; // the prior payload failed its hash (tampered) - not a reprice base ([#87])
  signed: boolean; // source PDF is digitally signed; embedding invalidates the signature ([M1])
  signedAck: boolean; // the broker acknowledged the signature will be invalidated
}

/** Mount the whole companion into `root`. Idempotent-ish: clears and rebuilds `root`. */
export function mountAuthor(root: HTMLElement): void {
  const state: State = {
    bytes: null,
    filenameHint: "",
    draft: {},
    prior: null,
    wasDecrypted: false,
    priorUnverified: false,
    signed: false,
    signedAck: false,
  };
  root.replaceChildren();

  // ---- Step 1: pick the OM -------------------------------------------------------------------------
  const pick = el("div", "author-pick");
  const file = el("input") as HTMLInputElement;
  file.type = "file";
  file.accept = "application/pdf,.pdf";
  file.id = "om-file";
  const pickLabel = el("label");
  pickLabel.htmlFor = "om-file";
  pickLabel.append("Choose your offering-memorandum PDF: ", file);
  const pickNote = el("p", "author-note");
  pickNote.textContent =
    "It is read, filled, and embedded entirely in your browser - the bytes never leave your machine.";
  pick.append(pickLabel, pickNote);

  const stage = el("div", "author-stage"); // the editor appears here once a file is chosen
  root.append(pick, stage);

  file.addEventListener("change", () => {
    const f = file.files && file.files[0];
    if (!f) return;
    void loadFile(f);
  });

  async function loadFile(f: File): Promise<void> {
    stage.replaceChildren(el("p", "author-note", "Reading PDF…"));
    const raw = new Uint8Array(await f.arrayBuffer());
    state.filenameHint = f.name;
    state.draft = {};
    state.prior = null;
    state.wasDecrypted = false;
    state.priorUnverified = false;
    state.signed = false;
    state.signedAck = false;
    let cap;
    try {
      cap = await captureFromBytes(raw);
    } catch {
      // A non-PDF / unparseable file: treat as a fresh blank draft against the given bytes.
      state.bytes = raw;
      renderEditor();
      return;
    }
    if (cap.encrypted) {
      // Encrypted with a real password / RC4 / out of scope: embedPayload can't load it ([#107]).
      state.bytes = null;
      stage.replaceChildren(
        el(
          "div",
          "author-errors",
          "This PDF is password-protected or uses encryption we can't open in the browser. " +
            "Use the openOM CLI (om embed) to embed into it.",
        ),
      );
      return;
    }
    state.bytes = cap.bytes; // decrypted copy when wasDecrypted, else the original
    state.wasDecrypted = cap.wasDecrypted;
    state.priorUnverified = cap.priorUnverified;
    state.signed = cap.signed;
    if (cap.prior?.payload) {
      state.draft = structuredClone(cap.prior.payload);
      if (cap.prior.payloadHash) state.prior = { payloadHash: cap.prior.payloadHash };
    }
    renderEditor();
  }

  // ---- Step 2: the editor --------------------------------------------------------------------------
  function renderEditor(): void {
    stage.replaceChildren();

    if (state.prior) {
      stage.append(
        el(
          "div",
          "author-reprice",
          "This OM already carries an openOM payload - your assertion will replace it (a reprice).",
        ),
      );
    }
    if (state.priorUnverified) {
      stage.append(
        el(
          "div",
          "author-reprice",
          "This OM carried a payload that FAILED its integrity check (altered) - it is not used as a " +
            "base; you are making a fresh assertion.",
        ),
      );
    }
    if (state.wasDecrypted) {
      stage.append(
        el(
          "div",
          "author-reprice",
          "This OM was permission-encrypted; it was decrypted in your browser to embed. The downloaded " +
            "openOM PDF will be UNENCRYPTED (its print/copy restrictions are not carried over).",
        ),
      );
    }
    if (state.signed) {
      const box = el("div", "author-warnings");
      box.append(
        el(
          "strong",
          undefined,
          "This PDF is digitally signed. Embedding rewrites the file and will invalidate that " +
            "signature. To keep a signed OM's signature, embed with the openOM CLI instead.",
        ),
      );
      const lbl = el("label", "author-ack");
      const ck = el("input") as HTMLInputElement;
      ck.type = "checkbox";
      ck.id = "signed-ack";
      ck.checked = state.signedAck;
      ck.addEventListener("change", () => {
        state.signedAck = ck.checked;
        refresh();
      });
      lbl.append(ck, " I understand embedding will invalidate the existing signature.");
      box.append(lbl);
      stage.append(box);
    }

    // Your assertion (required) — broker/brokerage/license.
    const who = el("section", "author-who");
    who.append(el("h3", undefined, "Your assertion (required)"));
    for (const [path, label, ph] of [
      ["/assertedBy/broker", "Broker name", "Jane Broker"],
      ["/assertedBy/brokerage", "Brokerage", "Example Realty"],
      ["/assertedBy/license", "License #", "RE-000000"],
    ] as const) {
      const desc: FieldDescriptor = { path, kind: "text", label };
      const c = makeControl(desc, getField(state.draft, path)) as HTMLInputElement;
      c.placeholder = ph;
      c.addEventListener("input", () => {
        setField(state.draft, path, readControl(desc, c));
        refresh();
      });
      const l = el("label", "author-field");
      l.append(`${label} `, c);
      who.append(l);
    }
    stage.append(who);

    // Schema-derived fields, grouped by section (assertedBy handled above; assertedDate stamped at assert).
    const descs = schemaFieldDescriptors(SCHEMA as { properties?: Record<string, unknown> }).filter(
      (d) => !d.path.startsWith("/assertedBy/"),
    );
    for (const sec of ["property", "deal", "lease"] as const) {
      const secDescs = descs.filter((d) => d.path.startsWith(`/${sec}/`));
      if (secDescs.length === 0) continue;
      const s = el("section", "author-section");
      s.append(el("h3", undefined, SECTION_LABEL[sec]));
      for (const desc of secDescs) {
        const c = makeControl(desc, getField(state.draft, desc.path));
        c.addEventListener("input", () => {
          setField(state.draft, desc.path, readControl(desc, c));
          refresh();
        });
        const l = el("label", "author-field");
        l.append(`${desc.label} `, c);
        s.append(l);
      }
      stage.append(s);
    }

    // Rent schedule editor.
    stage.append(renderRent());

    // Status (errors/warnings/recap) + assert button.
    const status = el("div", "author-status");
    status.id = "author-status";
    stage.append(status);

    const assertBtn = el(
      "button",
      "author-assert",
      "Assert & embed → download OM",
    ) as HTMLButtonElement;
    assertBtn.id = "author-assert";
    assertBtn.addEventListener("click", () => void doAssert());
    stage.append(assertBtn);

    refresh();
  }

  function renderRent(): HTMLElement {
    const sec = el("section", "author-rent");
    sec.append(el("h3", undefined, "Rent schedule"));
    const rows =
      (getField(state.draft, "/lease/rentSchedule") as Record<string, unknown>[] | undefined) ?? [];
    rows.forEach((period, i) => {
      const row = el("div", "rent-row");
      for (const f of RENT_FIELDS) {
        const desc: FieldDescriptor = {
          path: `/lease/rentSchedule/${i}/${f.key}`,
          kind: f.kind,
          label: f.label,
        };
        const c = makeControl(desc, period[f.key]);
        c.setAttribute("aria-label", `Rent period ${i + 1} - ${f.label}`);
        c.addEventListener("input", () => {
          setField(state.draft, desc.path, readControl(desc, c));
          refresh();
        });
        const l = el("label", "rent-cell");
        l.append(`${f.label} `, c);
        row.append(l);
      }
      const rm = el("button", "rent-rm", "Remove") as HTMLButtonElement;
      rm.addEventListener("click", () => {
        rows.splice(i, 1);
        setField(state.draft, "/lease/rentSchedule", rows.length ? rows : undefined);
        renderEditor();
      });
      row.append(rm);
      sec.append(row);
    });
    const add = el("button", "rent-add", "Add rent period") as HTMLButtonElement;
    add.addEventListener("click", () => {
      const next = [...rows, { source: "asserted" }];
      setField(state.draft, "/lease/rentSchedule", next);
      renderEditor();
    });
    sec.append(add);
    return sec;
  }

  /** Build the payload the broker WOULD assert (constants stamped) for live validation + embed. */
  function finalShape(): Record<string, unknown> {
    const profile = {
      broker: String(getField(state.draft, "/assertedBy/broker") ?? ""),
      brokerage: String(getField(state.draft, "/assertedBy/brokerage") ?? ""),
      license: String(getField(state.draft, "/assertedBy/license") ?? ""),
    };
    return finalizePayload(state.draft, profile, todayUtc(), state.prior);
  }

  function refresh(): void {
    const status = document.getElementById("author-status");
    const assertBtn = document.getElementById("author-assert") as HTMLButtonElement | null;
    if (!status) return;
    const shape = finalShape();
    const report: ValidationReport = validatePayload(shape, SCHEMA);
    status.replaceChildren();

    // Human recap - what you are about to assert, in plain language (not JSON pointers).
    status.append(recap(shape, state.prior));

    if (report.errors.length > 0) {
      const box = el("div", "author-errors");
      box.append(
        el("strong", undefined, `${report.errors.length} thing(s) to fix before you can embed:`),
      );
      const ul = el("ul");
      for (const e of report.errors)
        ul.append(el("li", undefined, `${humanPath(e.path)}: ${e.message}`));
      box.append(ul);
      status.append(box);
    } else {
      status.append(el("div", "author-ok", "Ready to embed - no schema errors."));
    }
    if (report.warnings.length > 0) {
      const box = el("div", "author-warnings");
      box.append(
        el(
          "strong",
          undefined,
          `${report.warnings.length} consistency warning(s) (these do not block):`,
        ),
      );
      const ul = el("ul");
      for (const w of report.warnings)
        ul.append(el("li", undefined, `${humanPath(w.path)}: ${w.message}`));
      box.append(ul);
      status.append(box);
    }
    // Collapsible finalized-payload preview (the exact bytes-shaped object that will be embedded).
    const details = document.createElement("details");
    details.className = "author-preview";
    const sum = document.createElement("summary");
    sum.textContent = "Show the exact data that will be embedded (JSON)";
    const pre = el("pre");
    pre.textContent = JSON.stringify(shape, null, 2);
    details.append(sum, pre);
    status.append(details);

    if (assertBtn)
      assertBtn.disabled =
        report.errors.length > 0 || !state.bytes || (state.signed && !state.signedAck);
  }

  /** A plain-language recap of the assertion - price/cap/NOI/tenant + who + reprice note. */
  function recap(
    shape: Record<string, unknown>,
    prior: { payloadHash: string } | null,
  ): HTMLElement {
    const box = el("div", "author-recap");
    const deal = (shape.deal as Record<string, unknown> | undefined) ?? {};
    const lease = (shape.lease as Record<string, unknown> | undefined) ?? {};
    const by = (shape.assertedBy as Record<string, unknown> | undefined) ?? {};
    const prop = (shape.property as Record<string, unknown> | undefined) ?? {};
    const addr = (prop.address as Record<string, unknown> | undefined) ?? {};
    const money = (v: unknown): string =>
      typeof v === "number" ? "$" + v.toLocaleString("en-US") : "—";
    const pct = (v: unknown): string => (typeof v === "number" ? (v * 100).toFixed(2) + "%" : "—");
    const lines: [string, string][] = [
      ["Property", String(addr.streetAddress ?? "—")],
      ["Asking price", money(deal.askingPrice)],
      ["Cap rate", pct(deal.capRate)],
      ["NOI", `${money(deal.noi)}${deal.noiType ? ` (${String(deal.noiType)})` : ""}`],
      ["Tenant", String(lease.tenantEntity ?? "—")],
      ["Asserted by", String(by.broker ?? "—") + (by.brokerage ? `, ${String(by.brokerage)}` : "")],
      ["Asserted date", String(shape.assertedDate ?? "—")],
    ];
    box.append(el("strong", undefined, "You are asserting:"));
    const dl = el("dl", "recap-list");
    for (const [k, v] of lines) {
      dl.append(el("dt", undefined, k), el("dd", undefined, v));
    }
    box.append(dl);
    if (prior)
      box.append(
        el(
          "p",
          "recap-note",
          `This replaces a prior assertion (${prior.payloadHash.slice(0, 16)}…).`,
        ),
      );
    return box;
  }

  /** [M3] After embed, help the broker make a shareable verified-view link once they've hosted the OM:
   * paste the hosted URL → a copyable openom.app/v/?src=… link a buyer can open (badge + deal card). */
  function shareLink(): HTMLElement {
    const box = el("div", "author-share");
    box.append(el("strong", undefined, "Share a verified view"));
    box.append(
      el(
        "p",
        "author-note",
        "Once you've uploaded the OM, paste its public URL to get a link a buyer can open - it shows the trust badge and the deal card, no install.",
      ),
    );
    const input = el("input") as HTMLInputElement;
    input.type = "url";
    input.placeholder = "https://your-listing.example.com/deal.pdf";
    const out = el("p", "author-share-out");
    const snippet = el("pre", "author-badge-snippet") as HTMLPreElement;
    snippet.hidden = true;
    input.addEventListener("input", () => {
      const u = input.value.trim();
      out.replaceChildren();
      snippet.hidden = true;
      if (!u) return;
      const link = `https://openom.app/v/?src=${encodeURIComponent(u)}`;
      const a = el("a", undefined, link) as HTMLAnchorElement;
      a.href = link;
      a.target = "_blank";
      a.rel = "noopener";
      out.append("Verified link: ", a);
      // [P7] a copy-paste trust badge a portal drops next to the listing (one script tag + element).
      snippet.hidden = false;
      snippet.textContent =
        `<script src="https://openom.app/widget/openom-badge.js" defer></script>\n` +
        `<openom-badge src="${u}"></openom-badge>`;
    });
    box.append(
      input,
      out,
      el("p", "author-note", "Or drop this trust badge on your listing page:"),
      snippet,
    );
    return box;
  }

  async function doAssert(): Promise<void> {
    if (!state.bytes) return;
    const status = document.getElementById("author-status");
    try {
      const out = await assertAndEmbed(
        finalShape(),
        state.bytes,
        (p) => validatePayload(p, SCHEMA),
        (b, p) => embedPayload(b, p),
      );
      const filename = suggestedFilename(finalShape(), state.filenameHint);
      download(out, filename);
      if (status) {
        status.append(
          el(
            "div",
            "author-done",
            `Embedded - downloaded ${filename}. Upload THIS file (do not let a portal re-export it).`,
          ),
        );
        status.append(shareLink());
      }
    } catch (err) {
      if (status)
        status.append(el("div", "author-errors", `Could not embed: ${(err as Error).message}`));
    }
  }
}

function humanPath(pointer: string): string {
  if (!pointer) return "payload";
  return pointer
    .split("/")
    .filter(Boolean)
    .map((s) => s.replace(/([a-z0-9])([A-Z])/g, "$1 $2"))
    .join(" › ");
}

function download(bytes: Uint8Array, filename: string): void {
  const url = URL.createObjectURL(new Blob([new Uint8Array(bytes)], { type: "application/pdf" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// Expose the companion for the hosted /embed/ page (a plain page can't import an IIFE's exports).
declare global {
  interface Window {
    openOMAuthor?: { mountAuthor: typeof mountAuthor };
  }
}
if (typeof window !== "undefined") window.openOMAuthor = { mountAuthor };
