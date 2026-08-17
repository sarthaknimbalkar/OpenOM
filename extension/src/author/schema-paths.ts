// Derive the broker-fillable leaf paths from the JSON Schema ([#92]) so the review panel's "omitted
// (confirm or supply)" section reflects the WHOLE field map, not a hardcoded handful. Walks the
// human-relevant sections (property / deal / lease + assertedBy), excluding the gate-set noi fields.
// Pure; the schema is passed in.

interface SchemaNode {
  type?: string;
  properties?: Record<string, SchemaNode>;
}

const SECTIONS = ["assertedBy", "property", "deal", "lease"] as const;
const GATE_SET = new Set(["/deal/noiType", "/deal/noiAsOfDate"]); // confirmed by the human, not "omitted"

export function schemaExpectedPaths(schema: { properties?: Record<string, unknown> }): string[] {
  const out: string[] = [];
  const props = (schema.properties ?? {}) as Record<string, SchemaNode>;
  for (const sec of SECTIONS) walk(props[sec], `/${sec}`, out);
  return out.filter((p) => !GATE_SET.has(p));
}

function walk(node: SchemaNode | undefined, prefix: string, out: string[]): void {
  if (!node) return;
  if (node.properties) {
    for (const [k, child] of Object.entries(node.properties)) walk(child, `${prefix}/${k}`, out);
  } else {
    out.push(prefix); // a leaf (scalar or array) the broker may supply
  }
}
