// Typed field descriptors from the JSON Schema ([#77/#93]) — the SINGLE source of form-control typing.
// Walking the schema (vs a hand-curated list) keeps the form in sync with the spec and makes #93 fall
// out for free: noiType is an enum → <select>, noiAsOfDate has format:date → date input. Array nodes
// (rentSchedule, options) are excluded here; the form renders those with a dedicated editor. Pure.

export type FieldKind = "number" | "text" | "date" | "enum" | "boolean";

export interface FieldDescriptor {
  path: string;
  kind: FieldKind;
  enum?: string[];
  label: string;
}

interface SchemaNode {
  type?: string;
  format?: string;
  enum?: string[];
  properties?: Record<string, SchemaNode>;
}

const SECTIONS = ["assertedBy", "property", "deal", "lease"] as const;

export function schemaFieldDescriptors(schema: { properties?: Record<string, unknown> }): FieldDescriptor[] {
  const out: FieldDescriptor[] = [];
  const props = (schema.properties ?? {}) as Record<string, SchemaNode>;
  for (const sec of SECTIONS) walk(props[sec], `/${sec}`, out);
  return out;
}

function walk(node: SchemaNode | undefined, prefix: string, out: FieldDescriptor[]): void {
  if (!node) return;
  if (node.type === "array") return; // rentSchedule / options — dedicated editor, not a flat control
  if (node.properties) {
    for (const [k, child] of Object.entries(node.properties)) walk(child, `${prefix}/${k}`, out);
    return;
  }
  out.push({ path: prefix, kind: kindOf(node), enum: node.enum, label: humanize(prefix) });
}

function kindOf(node: SchemaNode): FieldKind {
  if (node.enum) return "enum";
  if (node.format === "date") return "date";
  if (node.type === "number" || node.type === "integer") return "number";
  if (node.type === "boolean") return "boolean";
  return "text";
}

/** Humanize the last pointer segment: "noiAsOfDate" → "Noi As Of Date", "capRate" → "Cap Rate". */
function humanize(pointer: string): string {
  const seg = pointer.split("/").pop() ?? pointer;
  return seg
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/^./, (c) => c.toUpperCase());
}
