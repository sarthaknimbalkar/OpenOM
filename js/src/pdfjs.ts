// [Mi26] pdf.js is an OPTIONAL peer dependency: only the text-extraction (text.ts) and encrypted-read
// fallback (read-decrypt.ts) paths need it. Read / verify / validate / summarize consumers don't, and
// must not pay for it. This loader imports it on demand and fails with a clear, actionable message
// (not a raw ERR_MODULE_NOT_FOUND) when a consumer uses a text/decrypt path without installing it.

let _pdfjs: typeof import("pdfjs-dist/legacy/build/pdf.mjs") | null = null;

export async function loadPdfjs(): Promise<typeof import("pdfjs-dist/legacy/build/pdf.mjs")> {
  if (_pdfjs) return _pdfjs;
  try {
    _pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
    return _pdfjs;
  } catch (e) {
    throw new Error(
      "openom-js: this feature (text extraction / encrypted-PDF read) needs the optional peer " +
        "dependency 'pdfjs-dist'. Install it: `npm install pdfjs-dist`. " +
        `(underlying error: ${(e as Error)?.message ?? e})`,
    );
  }
}
