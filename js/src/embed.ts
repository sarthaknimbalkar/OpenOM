import { PDFDocument, AFRelationship, PDFName, PDFDict, PDFArray, PDFRef } from "pdf-lib";
import { preimageBytes, payloadHash } from "./hash.js";

/**
 * Embed an OpenOM payload into a PDF as the associated file `om.json`, with the
 * `omspec:` XMP integrity marker (§D). Deterministic; zero inference.
 *
 * Assumption A (confirmed with Track A): the stored `om.json` stream is the
 * signature-stripped **preimage** (`preimageBytes`), and `omspec:payloadHash`
 * is `payloadHash(payload)` — so a Consumer's byte-recompute of the stored
 * stream equals the marker directly ([OM-CANON-005], [OM-CANON-008]).
 *
 * NOTE: this uses pdf-lib's load→save, which is fine for author-mode/fresh
 * embeds but is NOT the incremental, byte-preserving save real OMs need
 * ([OM-EMB-020]); non-destructive embed on real fixtures is a follow-up.
 */
export async function embedPayload(
  pdfBytes: Uint8Array,
  payload: Record<string, unknown>,
): Promise<Uint8Array> {
  const bytes = preimageBytes(payload);
  const hash = payloadHash(payload);

  const staged = await PDFDocument.load(pdfBytes);
  // Pass the exact JCS bytes; never let the library re-serialize ([OM-EMB-010/022]).
  await staged.attach(bytes, "om.json", {
    mimeType: "application/ld+json",
    afRelationship: AFRelationship.Data,
  });
  // pdf-lib materializes /AF + /EmbeddedFiles + the /Filespec only at save; a
  // save→reload gives us the real objects to satisfy the §D shared-stream
  // invariant and to inject the XMP marker.
  const doc = await PDFDocument.load(await staged.save());

  ensureEfUf(doc);
  injectOmspecXmp(doc, {
    specName: "OpenOM",
    specVersion: "0.1",
    payloadFilename: "om.json",
    payloadHash: hash,
    assertedDate: String(payload["assertedDate"] ?? ""),
    supersedes: readSupersedes(payload),
  });

  return doc.save();
}

/**
 * pdf-lib's `attach` writes `/EF << /F … >>` with no `/UF`. §D requires both,
 * referencing the SAME stream ([OM-EMB-007]); mint `/EF /UF` from `/EF /F`.
 */
function ensureEfUf(doc: PDFDocument): void {
  const af = doc.catalog.lookup(PDFName.of("AF"), PDFArray);
  const filespec = doc.context.lookup(af.get(0), PDFDict);
  const ef = filespec.lookup(PDFName.of("EF"), PDFDict);
  const fRef = ef.get(PDFName.of("F"));
  if (fRef instanceof PDFRef && !(ef.get(PDFName.of("UF")) instanceof PDFRef)) {
    ef.set(PDFName.of("UF"), fRef);
  }
}

interface OmspecProps {
  specName: string;
  specVersion: string;
  payloadFilename: string;
  payloadHash: string;
  assertedDate: string;
  supersedes: string | null;
}

/**
 * Write the catalog `/Metadata` XMP packet carrying the `omspec:*` marker
 * (§D.2.1). Content MUST be handed to pdf-lib as UTF-8 BYTES (a JS string is
 * re-encoded and mangled). `omspec:supersedes` is omitted when null
 * ([OM-XMP-011]).
 */
function injectOmspecXmp(doc: PDFDocument, props: OmspecProps): void {
  const rows: Array<[string, string]> = [
    ["specName", props.specName],
    ["specVersion", props.specVersion],
    ["payloadFilename", props.payloadFilename],
    ["payloadHash", props.payloadHash],
    ["assertedDate", props.assertedDate],
  ];
  if (props.supersedes !== null) rows.push(["supersedes", props.supersedes]);

  const body = rows
    .map(([k, v]) => `   <omspec:${k}>${xmlEscape(v)}</omspec:${k}>`)
    .join("\n");
  const xml = `<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="OpenOM 0.1">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:omspec="https://SPEC-DOMAIN-TBD/ns/0.1#">
${body}
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>`;

  const stream = doc.context.stream(new TextEncoder().encode(xml), {
    Type: "Metadata",
    Subtype: "XML",
  });
  doc.catalog.set(PDFName.of("Metadata"), doc.context.register(stream));
}

function readSupersedes(payload: Record<string, unknown>): string | null {
  const meta = payload["meta"];
  if (meta !== null && typeof meta === "object" && !Array.isArray(meta)) {
    const s = (meta as Record<string, unknown>)["supersedes"];
    if (typeof s === "string") return s;
  }
  return null;
}

function xmlEscape(v: string): string {
  return v.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
