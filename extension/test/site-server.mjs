// Static HTTP server for the committed site/ deploy tree - the local webServer for the site gate
// (embed-companion.spec.ts). Serves exactly the bytes gen_site.py produced (drift-locked), so the
// gate exercises the real /embed authoring companion + /verify tool + widget bundles a visitor gets.
import { readFileSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { dirname, extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SITE = join(HERE, "..", "..", "site");
const PORT = Number(process.env.OM_SITE_PORT ?? 8100);

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json",
  ".pdf": "application/pdf",
  ".css": "text/css",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
};

function resolve(pathname) {
  // Map "/embed/" -> site/embed/index.html; prevent path escape.
  let rel = decodeURIComponent(pathname.split("?")[0]);
  if (rel.endsWith("/")) rel += "index.html";
  const abs = normalize(join(SITE, rel));
  if (!abs.startsWith(SITE)) return null;
  try {
    if (statSync(abs).isDirectory()) return join(abs, "index.html");
    return abs;
  } catch {
    return null;
  }
}

const server = createServer((req, res) => {
  const abs = resolve(new URL(req.url, "http://x").pathname);
  if (!abs) {
    res.writeHead(404).end("not found");
    return;
  }
  try {
    const body = readFileSync(abs);
    res.writeHead(200, { "content-type": TYPES[extname(abs)] ?? "application/octet-stream" });
    res.end(body);
  } catch {
    res.writeHead(404).end("not found");
  }
});

server.listen(PORT, "127.0.0.1", () => console.log(`openOM site server on 127.0.0.1:${PORT}`));
