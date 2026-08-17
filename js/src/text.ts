// Deterministic per-page text extraction via pdf.js — the ONLY input author-mode inference reads
// ([OM-DoD-007] M5b-2). Worker-AGNOSTIC: it never references `chrome` or configures a worker, so it
// is a clean /js module reused unchanged in Node (tests) and the browser panel (which owns worker
// setup). No inference here; pdf.js is already a /js dependency.

export interface PageText {
  readonly page: number;
  readonly text: string;
}

/**
 * Point pdf.js at its worker (a plain URL string — this stays worker-agnostic and never touches
 * `chrome`; the browser caller supplies the extension URL). Sets it on the SAME pdf.js module instance
 * `extractPageText` imports, so a browser page (which requires a real worker) can run extraction.
 */
export async function setPdfWorkerSrc(src: string): Promise<void> {
  const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
  pdfjs.GlobalWorkerOptions.workerSrc = src;
}

/**
 * Extract text for pages 1..min(numPages, maxPages). Over-cap pages are omitted; the caller compares
 * the returned length to the document length to surface truncation (never silently "complete").
 */
export async function extractPageText(bytes: Uint8Array, maxPages = 40): Promise<PageText[]> {
  const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
  const pdf = await pdfjs.getDocument({ data: bytes.slice(), verbosity: 0 }).promise;
  try {
    const last = Math.min(pdf.numPages, maxPages);
    const pages: PageText[] = [];
    for (let p = 1; p <= last; p++) {
      const content = await (await pdf.getPage(p)).getTextContent();
      const text = content.items.map((i) => ("str" in i ? i.str : "")).join(" ");
      pages.push({ page: p, text });
    }
    return pages;
  } finally {
    await pdf.destroy();
  }
}
