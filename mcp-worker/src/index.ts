// openOM public MCP server on Cloudflare Workers - serverless, deterministic, READ-ONLY.
//
// Serves the grounding tools om_read + om_validate over MCP Streamable HTTP (stateless JSON mode),
// backed by the byte-parity openom-js core. ZERO inference (cardinal rule). This is the durable
// public home for mcp.openom.app; the Python server (om_extract_images, om_embed, doc-classification)
// stays for the tools that need PyMuPDF. Input is PDF bytes (base64) or an https URL we fetch
// (size-capped; only https, no internal hosts - the CF edge has no LAN to SSRF into, but we still
// refuse obvious internal/metadata targets).
import { readPayloadFromBytes, validatePayload } from "openom-js";
import schema from "../../spec/om-0.1.schema.json";
import { precompiledValidate } from "./validator.js";

const MAX_BYTES = 25 * 1024 * 1024; // 25 MB - an OM PDF ceiling
const SERVER_INFO = { name: "openom", version: "0.1" };
const PROTOCOL = "2024-11-05";

const TOOLS = [
  {
    name: "om_read",
    description:
      "Read the embedded, broker-asserted openOM payload from an offering-memorandum PDF and report " +
      "whether it is unaltered (hash-verified). Returns the payload as an ASSERTION (who/as-of-when), " +
      "never as verified market truth. Deterministic; no inference.",
    inputSchema: {
      type: "object",
      properties: {
        pdfBase64: { type: "string", description: "The PDF bytes, base64-encoded." },
        url: { type: "string", description: "https URL of a PDF to fetch and read instead." },
      },
    },
  },
  {
    name: "om_validate",
    description:
      "Validate an openOM payload: JSON-Schema errors (block) plus internal-consistency warnings " +
      "(NOI/price vs cap rate, rent-schedule sums, date math - never market truth). Deterministic.",
    inputSchema: {
      type: "object",
      properties: { payload: { type: "object", description: "An openOM payload object." } },
      required: ["payload"],
    },
  },
];

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Mcp-Session-Id, Authorization",
};

function json(body: unknown, status = 200, extra: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...CORS, ...extra },
  });
}
function rpcResult(id: unknown, result: unknown): Response {
  return json({ jsonrpc: "2.0", id, result });
}
function rpcError(id: unknown, code: number, message: string): Response {
  return json({ jsonrpc: "2.0", id, error: { code, message } });
}

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64.replace(/\s/g, ""));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/** Refuse non-https and obvious internal/metadata targets. */
function safeUrl(raw: string): URL {
  const u = new URL(raw);
  if (u.protocol !== "https:") throw new Error("only https URLs are allowed");
  const h = u.hostname.toLowerCase();
  if (
    h === "localhost" ||
    h.endsWith(".internal") ||
    h.endsWith(".local") ||
    /^(127\.|10\.|192\.168\.|169\.254\.|::1$)/.test(h) ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(h)
  ) {
    throw new Error("refusing an internal/loopback host");
  }
  return u;
}

async function fetchPdf(rawUrl: string): Promise<Uint8Array> {
  const u = safeUrl(rawUrl);
  // redirect:"manual" (Workers has no "error") + reject 3xx ourselves - also blocks SSRF-via-redirect.
  const res = await fetch(u.toString(), { redirect: "manual", cf: { cacheTtl: 0 } });
  if (res.status >= 300 && res.status < 400) throw new Error("refusing to follow a redirect");
  if (!res.ok) throw new Error(`fetch failed: ${res.status}`);
  const len = Number(res.headers.get("content-length") ?? "0");
  if (len > MAX_BYTES) throw new Error("PDF exceeds the size limit");
  const buf = new Uint8Array(await res.arrayBuffer());
  if (buf.length > MAX_BYTES) throw new Error("PDF exceeds the size limit");
  return buf;
}

async function omRead(args: Record<string, unknown>): Promise<unknown> {
  let bytes: Uint8Array;
  if (typeof args.pdfBase64 === "string") bytes = base64ToBytes(args.pdfBase64);
  else if (typeof args.url === "string") bytes = await fetchPdf(args.url);
  else throw new Error("provide pdfBase64 or url");
  if (bytes.length > MAX_BYTES) throw new Error("PDF exceeds the size limit");
  const r = await readPayloadFromBytes(bytes);
  return {
    state: r.state, // present | absent | hash-mismatch | encrypted
    verification: r.verification ?? null,
    payload: r.state === "present" ? r.payload : null,
    note:
      r.state === "hash-mismatch"
        ? "Payload present but altered (hash mismatch) - do not trust it."
        : "openOM records who asserted the data, unaltered, as of when - not that it is true.",
  };
}

function omValidate(args: Record<string, unknown>): unknown {
  if (typeof args.payload !== "object" || args.payload === null) throw new Error("provide payload");
  const report = validatePayload(args.payload, schema as Record<string, unknown>, {
    validate: precompiledValidate,
  });
  return report;
}

async function callTool(name: string, args: Record<string, unknown>): Promise<unknown> {
  const data = name === "om_read" ? await omRead(args) : name === "om_validate" ? omValidate(args) : null;
  if (data === null && name !== "om_validate") throw new Error(`unknown tool: ${name}`);
  return { content: [{ type: "text", text: JSON.stringify(data) }], structuredContent: data };
}

export default {
  async fetch(req: Request): Promise<Response> {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (req.method === "GET") {
      return json({ server: SERVER_INFO, transport: "streamable-http", tools: TOOLS.map((t) => t.name) });
    }
    if (req.method !== "POST") return json({ error: "method not allowed" }, 405);

    let msg: { id?: unknown; method?: string; params?: Record<string, unknown> };
    try {
      msg = await req.json();
    } catch {
      return rpcError(null, -32700, "parse error");
    }
    const { id, method, params } = msg;
    try {
      switch (method) {
        case "initialize":
          return rpcResult(
            id,
            { protocolVersion: PROTOCOL, capabilities: { tools: {} }, serverInfo: SERVER_INFO },
          );
        case "notifications/initialized":
          return new Response(null, { status: 202, headers: CORS });
        case "ping":
          return rpcResult(id, {});
        case "tools/list":
          return rpcResult(id, { tools: TOOLS });
        case "tools/call": {
          const name = String(params?.name ?? "");
          const args = (params?.arguments as Record<string, unknown>) ?? {};
          try {
            return rpcResult(id, await callTool(name, args));
          } catch (e) {
            // tool errors are returned in-band (isError) per MCP, not as protocol errors
            return rpcResult(id, {
              content: [{ type: "text", text: `Error: ${(e as Error).message}` }],
              isError: true,
            });
          }
        }
        default:
          return rpcError(id, -32601, `method not found: ${method}`);
      }
    } catch (e) {
      return rpcError(id, -32603, (e as Error).message);
    }
  },
};
