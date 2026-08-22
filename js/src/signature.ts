// Detect whether PDF bytes carry a digital signature (or a DocMDP certification), so an author surface
// can WARN before embedding: openOM's embed rewrites the PDF (pdf-lib load->save, not an incremental
// update), which invalidates any existing signature's /ByteRange. Deterministic + pure (bytes in), so
// both the extension author mode and the hosted companion share one detector ([M1]).
//
// A signature dict is identified by its `/ByteRange` (the signed byte span) - present in every real
// PDF signature and absent from unsigned PDFs. We also match the signature `/SubFilter` handler names
// (adbe.pkcs7.* / ETSI.CAdES) and a certification `/DocMDP` transform, for robustness. A raw byte scan
// (not a full parse) keeps this cheap and unaffected by object-stream layout.

const NEEDLES: readonly Uint8Array[] = [
  strBytes("/ByteRange"),
  strBytes("adbe.pkcs7"),
  strBytes("ETSI.CAdES"),
  strBytes("/DocMDP"),
];

function strBytes(s: string): Uint8Array {
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

function indexOf(hay: Uint8Array, needle: Uint8Array): boolean {
  outer: for (let i = 0; i + needle.length <= hay.length; i++) {
    for (let j = 0; j < needle.length; j++) {
      if (hay[i + j] !== needle[j]) continue outer;
    }
    return true;
  }
  return false;
}

/** True when the PDF bytes carry a digital signature or a DocMDP certification. Pure; a byte scan. */
export function pdfHasSignature(bytes: Uint8Array): boolean {
  return NEEDLES.some((n) => indexOf(bytes, n));
}
