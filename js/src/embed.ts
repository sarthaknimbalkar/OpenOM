import {
  PDFDocument,
  AFRelationship,
  PDFName,
  PDFDict,
  PDFArray,
  PDFRef,
  PDFString,
  PDFHexString,
} from "pdf-lib";
import { preimageBytes, payloadHash } from "./hash.js";

/**
 * Embed an openOM payload into a PDF as the associated file `om.json`, with the
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
  // Idempotent re-embed ([OM-XMP-004]): strip any prior om.json + its /AF ref first, so a reprice
  // replaces (never stacks a second attachment) — parity with the Python core's _remove_existing.
  removeExistingOmJson(staged);
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
    specName: "openOM",
    specVersion: "0.1",
    payloadFilename: "om.json",
    payloadHash: hash,
    assertedDate: String(payload["assertedDate"] ?? ""),
    supersedes: readSupersedes(payload),
  });

  return doc.save();
}

/** Decoded filename of a `/Filespec` dict (`/UF` preferred, else `/F`), or null. */
function filespecName(fs: PDFDict): string | null {
  const n = fs.lookup(PDFName.of("UF")) ?? fs.lookup(PDFName.of("F"));
  return n instanceof PDFString || n instanceof PDFHexString ? n.decodeText() : null;
}

/**
 * Remove any existing `om.json` attachment — its `/AF` reference AND its `/EmbeddedFiles` name-tree
 * entry — so a re-embed replaces rather than stacks a second copy ([OM-XMP-004]). Mirrors the Python
 * core's `_remove_existing`; without it, a reprice leaves a stale stream that fails the hash check.
 */
function removeExistingOmJson(doc: PDFDocument): void {
  const context = doc.context;
  const catalog = doc.catalog;

  const af = catalog.lookup(PDFName.of("AF"));
  if (af instanceof PDFArray) {
    for (let i = af.size() - 1; i >= 0; i--) {
      const fs = context.lookup(af.get(i));
      if (fs instanceof PDFDict && filespecName(fs) === "om.json") af.remove(i);
    }
    if (af.size() === 0) catalog.delete(PDFName.of("AF"));
  }

  const names = catalog.lookup(PDFName.of("Names"));
  const ef = names instanceof PDFDict ? names.lookup(PDFName.of("EmbeddedFiles")) : undefined;
  const arr = ef instanceof PDFDict ? ef.lookup(PDFName.of("Names")) : undefined;
  if (arr instanceof PDFArray) {
    for (let i = arr.size() - 2; i >= 0; i -= 2) {
      const nm = arr.get(i);
      const decoded = nm instanceof PDFString || nm instanceof PDFHexString ? nm.decodeText() : null;
      if (decoded === "om.json") {
        arr.remove(i + 1); // value ref
        arr.remove(i); // key name
      }
    }
  }
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

// PDF/A requires every custom XMP namespace to be described by an embedded Extension Schema
// (PDF/A-3 §6.6.2.3, #2). Static — describes the fixed 0.1 marker properties. MUST match the
// Python writer (core/src/openom_core/xmp.py) so the PDF/A claim is producer-independent.
const PDFA_EXTENSION_SCHEMA = [
  ["specName", "name of the embedded data standard"],
  ["specVersion", "version of the embedded data standard"],
  ["payloadFilename", "filename of the embedded om.json attachment"],
  ["payloadHash", "sha256 integrity hash of the canonical payload"],
  ["assertedDate", "assertion date of the embedded payload"],
  ["supersedes", "prior payload hash this payload replaces"],
]
  .map(
    ([name, desc]) =>
      `        <rdf:li rdf:parseType="Resource">
         <pdfaProperty:name>${name}</pdfaProperty:name>
         <pdfaProperty:valueType>Text</pdfaProperty:valueType>
         <pdfaProperty:category>internal</pdfaProperty:category>
         <pdfaProperty:description>${desc}</pdfaProperty:description>
        </rdf:li>`,
  )
  .join("\n");

const _PDFA_BLOCK = `  <rdf:Description rdf:about=""
      xmlns:pdfaExtension="http://www.aiim.org/pdfa/ns/extension/"
      xmlns:pdfaSchema="http://www.aiim.org/pdfa/ns/schema#"
      xmlns:pdfaProperty="http://www.aiim.org/pdfa/ns/property#">
   <pdfaExtension:schemas>
    <rdf:Bag>
     <rdf:li rdf:parseType="Resource">
      <pdfaSchema:schema>openOM offering-memorandum payload marker</pdfaSchema:schema>
      <pdfaSchema:namespaceURI>https://verveliolabs.com/openom/ns/0.1#</pdfaSchema:namespaceURI>
      <pdfaSchema:prefix>omspec</pdfaSchema:prefix>
      <pdfaSchema:property>
       <rdf:Seq>
${PDFA_EXTENSION_SCHEMA}
       </rdf:Seq>
      </pdfaSchema:property>
     </rdf:li>
    </rdf:Bag>
   </pdfaExtension:schemas>
  </rdf:Description>`;

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

  const body = rows.map(([k, v]) => `   <omspec:${k}>${xmlEscape(v)}</omspec:${k}>`).join("\n");
  const xml = `<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="openOM 0.1">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
${_PDFA_BLOCK}
  <rdf:Description rdf:about="" xmlns:omspec="https://verveliolabs.com/openom/ns/0.1#">
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
