// The author draft: a working payload plus per-field evidence annotations, all pure and immutable so
// the review panel and its tests stay deterministic. Evidence is broker-entered in B1 (M5b-2's
// on-device extractor pre-fills it). Fields carry source "extracted" until the assert step promotes
// them. No chrome, no clock, no /js — just data transforms over a JSON-pointer-addressed payload.

export interface FieldEvidence {
  page?: number;
  quote?: string;
}

export interface Draft {
  readonly payload: Record<string, unknown>;
  /** keyed by RFC 6901 JSON pointer, e.g. "/deal/capRate" */
  readonly evidence: Record<string, FieldEvidence>;
}

export function newDraft(seed?: Record<string, unknown>): Draft {
  return { payload: seed ? structuredClone(seed) : {}, evidence: {} };
}

/** Immutably set a JSON-pointer leaf, cloning objects along the path. */
export function setField(d: Draft, path: string, value: unknown): Draft {
  const tokens = tokensOf(path);
  const payload = structuredClone(d.payload);
  let node: Record<string, unknown> = payload;
  for (let i = 0; i < tokens.length - 1; i++) {
    const k = tokens[i];
    const next = node[k];
    node[k] = typeof next === "object" && next !== null ? next : {};
    node = node[k] as Record<string, unknown>;
  }
  node[tokens[tokens.length - 1]] = value;
  return { payload, evidence: d.evidence };
}

export function setEvidence(d: Draft, path: string, ev: FieldEvidence): Draft {
  return { payload: d.payload, evidence: { ...d.evidence, [path]: ev } };
}

/** Schema-known paths that the payload does not set (deliberate omissions to confirm, never invent). */
export function omissions(d: Draft, schemaPaths: string[]): string[] {
  return schemaPaths.filter((p) => resolve(d.payload, p) === undefined);
}

/** Leaf paths that carry a value but no citable evidence — flagged for the human, never blocked. */
export function fieldsWithoutEvidence(d: Draft): string[] {
  return leaves(d.payload).map(([p]) => p).filter((p) => {
    const ev = d.evidence[p];
    return !ev || (ev.page === undefined && !ev.quote);
  });
}

/** JSON-pointer path + value for every primitive/null leaf (recursing objects and arrays). */
export function leaves(obj: unknown): [string, unknown][] {
  return leafEntries(obj, "");
}

function tokensOf(pointer: string): string[] {
  return pointer.split("/").slice(1); // "/deal/capRate" -> ["deal","capRate"]
}

function resolve(obj: unknown, pointer: string): unknown {
  let node: unknown = obj;
  for (const k of tokensOf(pointer)) {
    if (typeof node !== "object" || node === null) return undefined;
    node = (node as Record<string, unknown>)[k];
  }
  return node;
}

function leafEntries(obj: unknown, prefix: string): [string, unknown][] {
  if (typeof obj !== "object" || obj === null) return prefix ? [[prefix, obj]] : [];
  const entries: [string, unknown][] = Array.isArray(obj)
    ? obj.map((v, i) => [String(i), v])
    : Object.entries(obj as Record<string, unknown>);
  return entries.flatMap(([k, v]) => leafEntries(v, `${prefix}/${k}`));
}
