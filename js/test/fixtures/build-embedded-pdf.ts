import { PDFDocument, AFRelationship, PDFName } from "pdf-lib";
import { canonicalize } from "../../src/canonicalize.js";
import { payloadHash } from "../../src/hash.js";

/**
 * TEST-ONLY fixture builder. Synthesizes a PDF with an embedded `om.json` and
 * an injected `omspec:` XMP marker, so the production reader (`src/read.ts`) has
 * realistic input BEFORE Track A's `/spec/vectors/pdfs/` land and BEFORE the
 * conformant embed module is built (held until the contract freeze). This is
 * deliberately minimal — it is NOT §D-conformant embed (e.g. it does not fix
 * `/EF /UF`, is not non-destructive, is not idempotent).
 */

export interface BuildOptions {
  /** Force a specific `omspec:payloadHash` (to simulate tampering). */
  readonly overridePayloadHash?: string;
  /** Omit `omspec:payloadHash` entirely (degraded producer, OM-XMP-008). */
  readonly omitXmpHash?: boolean;
}

function xmpPacket(props: Record<string, string>): Uint8Array {
  const lines = Object.entries(props)
    .map(([k, v]) => `   <omspec:${k}>${v}</omspec:${k}>`)
    .join("\n");
  const xml = `<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="openOM 0.1">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:omspec="https://openom.app/ns/0.1#">
${lines}
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>`;
  return new TextEncoder().encode(xml);
}

export async function buildEmbeddedPdf(
  payload: Record<string, unknown>,
  options: BuildOptions = {},
): Promise<Uint8Array> {
  const jcs = canonicalize(payload);
  const doc = await PDFDocument.create();
  doc.addPage([200, 200]);
  await doc.attach(jcs, "om.json", {
    mimeType: "application/ld+json",
    afRelationship: AFRelationship.Data,
  });

  const props: Record<string, string> = {
    specName: "openOM",
    specVersion: "0.1",
    payloadFilename: "om.json",
    assertedDate: String((payload as { assertedDate?: unknown }).assertedDate ?? ""),
  };
  if (!options.omitXmpHash) {
    props["payloadHash"] = options.overridePayloadHash ?? payloadHash(payload);
  }
  const supersedes = (payload as { meta?: { supersedes?: unknown } }).meta?.supersedes;
  if (typeof supersedes === "string") {
    props["supersedes"] = supersedes;
  }

  const stream = doc.context.stream(xmpPacket(props), { Type: "Metadata", Subtype: "XML" });
  doc.catalog.set(PDFName.of("Metadata"), doc.context.register(stream));

  return doc.save();
}

/** A PDF with no embedded payload and no `omspec:` marker (the `absent` case). */
export async function buildPlainPdf(): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  doc.addPage([200, 200]);
  return doc.save();
}
