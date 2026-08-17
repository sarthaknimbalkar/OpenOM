// Self-signed HTTPS fixture server for the M5a-B consumer gate. Serves the labeled §AA fixtures +
// their om.json mirrors, and a /hook receiver that recomputes the §Y HMAC to confirm publish. The
// cert covers broker.example.com + attacker.net (Playwright maps both to 127.0.0.1); the client
// runs with --ignore-certificate-errors.

import { createHmac } from "node:crypto";
import { readFileSync } from "node:fs";
import { createServer } from "node:https";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import selfsigned from "selfsigned";

const HERE = dirname(fileURLToPath(import.meta.url));
const FIX = join(HERE, "fixtures");
const SECRET = "test-secret";
const PORT = Number(process.env.OM_HARNESS_PORT ?? 8443);

const pems = selfsigned.generate([{ name: "commonName", value: "broker.example.com" }], {
  days: 2,
  keySize: 2048,
  extensions: [
    {
      name: "subjectAltName",
      altNames: [
        { type: 2, value: "broker.example.com" },
        { type: 2, value: "attacker.net" },
        { type: 2, value: "localhost" },
        { type: 7, ip: "127.0.0.1" },
      ],
    },
  ],
});

const files = {
  "/valid/deal.pdf": ["application/pdf", "valid/deal.pdf"],
  "/valid/om.json": ["application/json", "valid/om.json"],
  "/integrity/deal.pdf": ["application/pdf", "integrity/deal.pdf"],
  "/tampered/deal.pdf": ["application/pdf", "tampered/deal.pdf"],
  "/plain/deal.pdf": ["application/pdf", "plain/deal.pdf"],
  "/stale/deal.pdf": ["application/pdf", "stale/deal.pdf"],
  "/stale/om.json": ["application/json", "stale/om.json"],
  "/author/plain.pdf": ["application/pdf", "author/plain.pdf"],
  "/author/embedded.pdf": ["application/pdf", "author/embedded.pdf"],
  "/author/text.pdf": ["application/pdf", "author/text.pdf"],
};

let lastHook = null;

const server = createServer({ key: pems.private, cert: pems.cert }, (req, res) => {
  const url = new URL(req.url, "https://x");
  if (req.method === "POST" && url.pathname === "/hook") {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      const sig = String(req.headers["openom-signature"] ?? "");
      const t = /t=(\d+)/.exec(sig)?.[1];
      const v1 = /v1=([0-9a-f]+)/.exec(sig)?.[1];
      const expected = createHmac("sha256", SECRET).update(`${t}.${body}`).digest("hex");
      lastHook = { valid: v1 === expected, event: safeEvent(body) };
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify(lastHook));
    });
    return;
  }
  if (url.pathname === "/last-hook") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify(lastHook));
    return;
  }
  const entry = files[url.pathname];
  if (!entry) {
    res.writeHead(404);
    res.end("not found");
    return;
  }
  res.writeHead(200, { "content-type": entry[0], "access-control-allow-origin": "*" });
  res.end(readFileSync(join(FIX, entry[1])));
});

function safeEvent(body) {
  try {
    return JSON.parse(body).event;
  } catch {
    return null;
  }
}

server.listen(PORT, "127.0.0.1", () => console.log(`openOM harness https on 127.0.0.1:${PORT}`));
