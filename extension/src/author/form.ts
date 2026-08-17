// The author review FORM — stable, typed controls built ONCE per capture (never rebuilt on keystroke,
// so input focus is never lost; #77). Each control is a schema-driven view of the draft that reports
// edits through callbacks; the draft stays the single source of truth. Renders the review-contract's
// per-field rows (value + evidence + flag), the #93 conditional NOI controls, the rent-schedule
// editor, a collapsible More-fields section, and the Advanced raw-JSON escape hatch (.draft-json).
import schema from "../../../spec/om-0.1.schema.json";
import { type Draft, fieldsWithoutEvidence, getField } from "./draft.js";
import { type FieldDescriptor, type FieldKind, schemaFieldDescriptors } from "./schema-fields.js";

export interface FormCallbacks {
  onField: (path: string, value: unknown) => void;
  onEvidence: (path: string, ev: { page?: number; quote?: string }) => void;
  onAddRentPeriod: () => void;
  onRemoveRentPeriod: (index: number) => void;
}

/** Common mapping-guide fields shown first (in order); the rest go under "More fields". */
export const CORE_PATHS: readonly string[] = [
  "/property/address/streetAddress",
  "/property/address/addressLocality",
  "/property/address/addressRegion",
  "/deal/askingPrice",
  "/deal/capRate",
  "/deal/noi",
  "/deal/noiType", // conditional (see below)
  "/deal/noiAsOfDate", // conditional
  "/deal/pricePerSF",
  "/lease/tenantEntity",
  "/lease/leaseTypeAsserted",
  "/lease/commencement",
  "/lease/expiration",
];

const el = (tag: string, cls?: string, text?: string): HTMLElement => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

export function buildForm(root: HTMLElement, draft: Draft, cb: FormCallbacks): void {
  const all = schemaFieldDescriptors(schema as { properties?: Record<string, unknown> });
  const byPath = new Map(all.map((d) => [d.path, d]));
  const flagged = new Set(fieldsWithoutEvidence(draft));
  const hasNoi = getField(draft, "/deal/noi") !== undefined;

  // Core section (in CORE_PATHS order; NOI enum/date only when noi is set — #93).
  const core = el("section", "form-core");
  for (const path of CORE_PATHS) {
    if ((path === "/deal/noiType" || path === "/deal/noiAsOfDate") && !hasNoi) continue;
    const desc = byPath.get(path);
    if (desc) core.appendChild(fieldRow(desc, draft, flagged, cb));
  }

  // Rent-schedule editor.
  const rent = rentEditor(draft, cb);

  // More fields (everything not in core, not an array): collapsed.
  const more = document.createElement("details");
  more.className = "more-fields";
  more.appendChild(el("summary", undefined, "More fields"));
  for (const desc of all) {
    if (CORE_PATHS.includes(desc.path)) continue;
    more.appendChild(fieldRow(desc, draft, flagged, cb));
  }

  // Advanced raw JSON escape hatch (kept for power users + gate compatibility).
  const advanced = document.createElement("details");
  advanced.className = "advanced";
  advanced.appendChild(el("summary", undefined, "Advanced (raw JSON)"));
  const ta = el("textarea", "draft-json") as HTMLTextAreaElement;
  ta.value = JSON.stringify(draft.payload, null, 2);
  advanced.appendChild(ta);

  root.replaceChildren(core, rent, more, advanced);
}

/** One field row: label + typed control (data-path) + evidence (page/quote) + no-evidence flag. */
function fieldRow(desc: FieldDescriptor, draft: Draft, flagged: Set<string>, cb: FormCallbacks): HTMLElement {
  const row = el("div", "review-field");
  const control = makeControl(desc, getField(draft, desc.path));
  // `input` only (fires for text/number/date/select/checkbox in modern browsers). Deliberately NOT
  // `change`: a change on blur would re-render the derived panel mid-click and replace #assert,
  // making the Assert click miss its own target.
  control.addEventListener("input", () => cb.onField(desc.path, readControl(desc, control)));
  // Wrap the control in its label so the two are associated for assistive tech (#71).
  const label = el("label", "field-label");
  label.append(`${desc.label} `, control);
  row.appendChild(label);

  // evidence — placeholder alone is not an accessible name, so label each input explicitly.
  const ev = el("span", "field-evidence");
  const priorEv = draft.evidence[desc.path];
  const page = el("input", "ev-page") as HTMLInputElement;
  page.type = "number";
  page.placeholder = "pg";
  page.setAttribute("aria-label", `${desc.label} — evidence page`);
  if (priorEv?.page !== undefined) page.value = String(priorEv.page);
  const quote = el("input", "ev-quote") as HTMLInputElement;
  quote.placeholder = "quote";
  quote.setAttribute("aria-label", `${desc.label} — evidence quote`);
  if (priorEv?.quote) quote.value = priorEv.quote;
  const emitEv = (): void =>
    cb.onEvidence(desc.path, {
      page: page.value === "" ? undefined : Number(page.value),
      quote: quote.value === "" ? undefined : quote.value,
    });
  page.addEventListener("input", emitEv);
  quote.addEventListener("input", emitEv);
  ev.append(page, quote);
  row.appendChild(ev);

  if (flagged.has(desc.path)) row.appendChild(el("span", "field-flag", "no evidence — please cite"));
  return row;
}

function makeControl(desc: FieldDescriptor, value: unknown): HTMLElement {
  let c: HTMLInputElement | HTMLSelectElement;
  if (desc.kind === "enum") {
    const s = document.createElement("select");
    s.appendChild(new Option("—", ""));
    for (const opt of desc.enum ?? []) s.appendChild(new Option(opt, opt));
    if (typeof value === "string") s.value = value;
    c = s;
  } else {
    const i = document.createElement("input");
    i.type = desc.kind === "number" ? "number" : desc.kind === "date" ? "date" : desc.kind === "boolean" ? "checkbox" : "text";
    if (desc.kind === "boolean") i.checked = value === true;
    else if (value !== undefined && value !== null) i.value = String(value);
    c = i;
  }
  c.dataset.path = desc.path;
  return c;
}

/** Read a control's value back as the correctly-typed payload value (undefined when blank). */
function readControl(desc: FieldDescriptor, control: HTMLElement): unknown {
  if (desc.kind === "boolean") return (control as HTMLInputElement).checked;
  const raw = (control as HTMLInputElement | HTMLSelectElement).value;
  if (raw === "") return undefined;
  return desc.kind === "number" ? Number(raw) : raw;
}

const RENT_FIELDS: { key: string; kind: FieldKind; label: string }[] = [
  { key: "periodStart", kind: "date", label: "Start" },
  { key: "periodEnd", kind: "date", label: "End" },
  { key: "annualRent", kind: "number", label: "Annual rent" },
  { key: "rentPSF", kind: "number", label: "Rent PSF" },
];

function rentEditor(draft: Draft, cb: FormCallbacks): HTMLElement {
  const sec = el("section", "rent-schedule");
  sec.appendChild(el("h3", undefined, "Rent schedule"));
  const rows = (getField(draft, "/lease/rentSchedule") as Record<string, unknown>[] | undefined) ?? [];
  rows.forEach((period, i) => {
    const row = el("div", "rent-row");
    for (const f of RENT_FIELDS) {
      const desc: FieldDescriptor = { path: `/lease/rentSchedule/${i}/${f.key}`, kind: f.kind, label: f.label };
      const control = makeControl(desc, period[f.key]);
      control.setAttribute("aria-label", `Rent period ${i + 1} — ${f.label}`); // #71
      control.addEventListener("input", () => cb.onField(desc.path, readControl(desc, control)));
      row.appendChild(control);
    }
    const src = el("span", "rent-source", String(period.source ?? "extracted"));
    const rm = el("button", "rm-rent", "Remove") as HTMLButtonElement;
    rm.addEventListener("click", () => cb.onRemoveRentPeriod(i));
    row.append(src, rm);
    sec.appendChild(row);
  });
  const add = el("button", "add-rent", "Add period") as HTMLButtonElement;
  add.addEventListener("click", () => cb.onAddRentPeriod());
  sec.appendChild(add);
  return sec;
}
