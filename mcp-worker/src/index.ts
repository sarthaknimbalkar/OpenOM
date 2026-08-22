// openOM public MCP server on Cloudflare Workers - serverless, deterministic, READ-ONLY.
//
// Serves the grounding tools om_read + om_validate over MCP Streamable HTTP (stateless JSON mode),
// backed by the byte-parity openom-js core. ZERO inference (cardinal rule). This is the durable
// public home for mcp.openom.app; the Python server (om_extract_images, om_embed, doc-classification)
// stays for the tools that need PyMuPDF. Input is PDF bytes (base64) or an https URL we fetch
// (size-capped; only https, no internal hosts - the CF edge has no LAN to SSRF into, but we still
// refuse obvious internal/metadata targets).
import {
  readPayloadFromBytes,
  validatePayload,
  verifyOrigin,
  classifyStale,
  payloadHash,
  canonicalMirrorUrl,
} from "openom-js";
import schema from "../../spec/om-0.1.schema.json";
import { precompiledValidate } from "./validator.js";

const MAX_BYTES = 25 * 1024 * 1024; // 25 MB - an OM PDF ceiling
const MAX_BATCH = 20; // [M5] max JSON-RPC requests per batch call (keeps fan-out bounded)
const SERVER_INFO = { name: "openom", version: "0.1" };
const PROTOCOL = "2024-11-05";

const TOOLS = [
  {
    name: "om_read",
    description:
      "Read the embedded, broker-asserted openOM payload from an offering-memorandum PDF and report " +
      "whether it is unaltered (hash-verified). Returns the payload as an ASSERTION (who/as-of-when), " +
      "never as verified market truth. Deterministic; no inference. For a back-catalog, send a JSON-RPC " +
      "batch array (up to 20 requests per call) instead of one HTTP round-trip each.",
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

/**
 * A tool failure with a STABLE machine code ([M4]) so a batch consumer can branch on WHY a read failed
 * (retry with own bytes, skip encrypted, drop oversize, alert) instead of string-matching English.
 */
class ToolError extends Error {
  constructor(
    readonly code:
      // [Ma9] Canonical numeric OM-IO-* codes — the SAME set the Python server (fetch.py) emits and
      // spec/requirements.json defines, so a client branching on `code` works against either server.
      | "OM-IO-001" // upstream fetch failed (non-2xx / DNS / connection)
      | "OM-IO-002" // SSRF: resolves to a blocked/internal address range
      | "OM-IO-005" // size cap exceeded / not a PDF
      | "OM-IO-008" // unsupported or absent PDF reference (non-https, or no pdfBase64/url)
      | "OM-IO-009" // redirect refused / limit exceeded / no Location
      | "OM-IO-010", // malformed PDF / read failure
    message: string,
  ) {
    super(message);
  }
}

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64.replace(/\s/g, ""));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/**
 * Refuse non-https and internal/metadata targets. The Worker has no raw socket, so this is a
 * hostname/IP-literal guard (not resolve-then-pin like the Python core); CF's edge also cannot route
 * to private networks, so DNS-rebinding to an internal IP is doubly mitigated. Covers IPv4 loopback/
 * private/link-local/CGNAT/this-host and IPv6 loopback/ULA/link-local/unspecified + IPv4-mapped IPv6.
 */
export function safeUrl(raw: string): URL {
  const u = new URL(raw);
  if (u.protocol !== "https:") throw new ToolError("OM-IO-008", "only https URLs are fetched");
  const h = u.hostname.toLowerCase().replace(/^\[|\]$/g, ""); // strip IPv6 brackets
  const blocked =
    h === "localhost" ||
    h.endsWith(".localhost") ||
    h.endsWith(".internal") ||
    h.endsWith(".local") ||
    // IPv4: loopback, this-host, private, link-local (metadata), CGNAT
    /^127\./.test(h) ||
    /^0\./.test(h) ||
    /^10\./.test(h) ||
    /^192\.168\./.test(h) ||
    /^169\.254\./.test(h) ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(h) ||
    /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\./.test(h) ||
    // IPv6: unspecified, loopback, ULA (fc00::/7), link-local (fe80::/10)
    h === "::" ||
    h === "::1" ||
    /^f[cd][0-9a-f]{0,2}:/.test(h) ||
    /^fe[89ab][0-9a-f]:/.test(h) ||
    // IPv4-mapped IPv6 (the URL parser normalizes ::ffff:169.254.169.254 -> ::ffff:a9fe:a9fe, so
    // block the whole mapped form - a legitimate public target never uses a mapped literal).
    /^::ffff:/.test(h);
  if (blocked) throw new ToolError("OM-IO-002", "refusing an internal/loopback host");
  return u;
}

const MAX_REDIRECTS = 3; // most real OM hosting is a presigned/CDN redirect; follow a bounded chain

/**
 * Fetch PDF bytes, following up to MAX_REDIRECTS hops and re-running the SSRF guard on EVERY hop's
 * Location (resolve-then-pin, parity with the Python core's mcp/fetch.py). Workers has no raw socket,
 * so the guard is hostname-based via safeUrl - re-validating each redirect target closes SSRF-via-
 * redirect while unblocking S3/GCS presigned links and CDN edge redirects (#36). `fetchImpl` is
 * injected for tests; `redirect:"manual"` so we see and re-check every Location ourselves.
 */
export async function fetchPdf(
  rawUrl: string,
  fetchImpl: typeof fetch = fetch,
): Promise<Uint8Array> {
  let url = safeUrl(rawUrl).toString();
  for (let hop = 0; hop <= MAX_REDIRECTS; hop++) {
    // [M5] cache immutable OM bytes at the CF edge (5 min) so re-reads of the same URL don't re-download
    // the whole PDF; still bounded + SSRF-guarded. A changed OM at the same URL is a new embed (new bytes).
    const res = await fetchImpl(url, { redirect: "manual", cf: { cacheTtl: 300, cacheEverything: true } });
    if (res.status >= 300 && res.status < 400) {
      const loc = res.headers.get("location");
      if (!loc) throw new ToolError("OM-IO-009", "redirect without a Location header");
      url = safeUrl(new URL(loc, url).toString()).toString(); // resolve relative + re-pin SSRF
      continue;
    }
    if (!res.ok) throw new ToolError("OM-IO-001", `fetch failed: ${res.status}`);
    const len = Number(res.headers.get("content-length") ?? "0");
    if (len > MAX_BYTES) throw new ToolError("OM-IO-005", "PDF exceeds the size limit");
    const buf = new Uint8Array(await res.arrayBuffer());
    if (buf.length > MAX_BYTES) throw new ToolError("OM-IO-005", "PDF exceeds the size limit");
    return buf;
  }
  throw new ToolError("OM-IO-009", `redirect limit (${MAX_REDIRECTS}) exceeded`);
}

async function omRead(args: Record<string, unknown>): Promise<unknown> {
  let bytes: Uint8Array;
  const sourceUrl = typeof args.url === "string" ? args.url : null;
  if (typeof args.pdfBase64 === "string") bytes = base64ToBytes(args.pdfBase64);
  else if (sourceUrl) bytes = await fetchPdf(sourceUrl);
  else throw new ToolError("OM-IO-008", "provide pdfBase64 or url");
  if (bytes.length > MAX_BYTES) throw new ToolError("OM-IO-005", "PDF exceeds the size limit");
  const r = await readPayloadFromBytes(bytes);

  // [M1/M8] When read from a URL and the payload declares a same-domain canonicalUrl mirror, verify
  // origin + staleness SERVER-SIDE (no CORS) so /verify + /v/ reach domain-origin (✓✓), superseded,
  // and diverged - the states unreachable client-side. Best-effort: any mirror error leaves them null.
  let originVerified: boolean | null = null;
  let stale: "OMW-W051" | null = null;
  let diverged: "OMW-W052" | null = null;
  const canonicalUrl = canonicalMirrorUrl(r.payload);
  if (sourceUrl && r.state === "present" && r.payloadHash && canonicalUrl) {
    try {
      // Fetch the mirror ONCE and reuse the bytes for both origin verification and the stale/diverged
      // classification (no redundant round-trip).
      let mirrorBytes: Uint8Array | null = null;
      const o = await verifyOrigin({
        sourceUrl,
        mirrorUrl: canonicalUrl,
        embeddedHash: r.payloadHash,
        fetchMirror: async (u) => {
          mirrorBytes = await fetchPdf(u); // safe fetch (SSRF-guarded, bounded redirects)
          return { https: safeUrl(u).protocol === "https:", body: mirrorBytes };
        },
      });
      originVerified = o.originVerified;
      if (o.reason === "hash-mismatch" && mirrorBytes) {
        // Distinguish a newer/superseding mirror (stale) from genuinely divergent content.
        try {
          const mp = JSON.parse(new TextDecoder().decode(mirrorBytes)) as Record<string, unknown>;
          const s = classifyStale({
            embeddedHash: r.payloadHash,
            mirrorHash: payloadHash(mp),
            embeddedPayload: r.payload ?? {},
            mirrorPayload: mp,
          });
          if (s.stale && s.code) stale = s.code;
          else diverged = "OMW-W052";
        } catch {
          /* mirror unparseable → no stale/diverged claim */
        }
      }
    } catch {
      /* mirror unreachable / cross-origin → leave origin null (degrade to integrity-only) */
    }
  }

  // [polish] Surface consistency warnings on a present payload so a naive consumer needn't make a
  // second om_validate round-trip to learn NOI/price-vs-cap-rate, rent-sum, or date-math notices.
  let warnings: { code: string; message: string }[] | undefined;
  if (r.state === "present" && r.payload) {
    const report = validatePayload(r.payload, schema as Record<string, unknown>, {
      validate: precompiledValidate,
    });
    if (report.warnings.length) {
      warnings = report.warnings.map((w) => ({ code: w.code, message: w.message }));
    }
  }

  const outPayload = r.state === "present" ? r.payload : null;
  return {
    state: r.state, // present | absent | hash-mismatch | encrypted
    payloadHash: r.payloadHash, // [M5] dedupe key - a caller skips re-processing an unchanged payload
    // [Ma9] specVersion + sourceDocHash mirror the Python om_read shape so a client written against
    // one server works against the other (the Worker response is a superset of the reference shape).
    specVersion:
      outPayload && typeof outPayload === "object"
        ? ((outPayload as Record<string, unknown>).specVersion ?? null)
        : null,
    sourceDocHash: r.sourceDocHash,
    verification: { ...(r.verification ?? {}), originVerified },
    ...(stale ? { stale } : {}),
    ...(diverged ? { diverged } : {}),
    ...(warnings ? { warnings } : {}),
    payload: outPayload,
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
  // [Ma9] Return the canonical Python om_validate contract ({ok, errors, warnings, info,
  // canonical:{hash}}) as a superset of the JS ValidationReport, so a client can branch on `ok`/
  // `canonical.hash` against either server. The raw report fields are kept for back-compat.
  return {
    ok: !report.blocked,
    errors: report.errors,
    warnings: report.warnings,
    info: report.info,
    canonical: { hash: payloadHash(args.payload as Record<string, unknown>) },
    specVersion: report.specVersion,
    validatorVersion: report.validatorVersion,
    summary: report.summary,
    blocked: report.blocked,
  };
}

async function callTool(name: string, args: Record<string, unknown>): Promise<unknown> {
  const data = name === "om_read" ? await omRead(args) : name === "om_validate" ? omValidate(args) : null;
  if (data === null && name !== "om_validate") throw new Error(`unknown tool: ${name}`);
  return { content: [{ type: "text", text: JSON.stringify(data) }], structuredContent: data };
}

interface RpcMsg {
  id?: unknown;
  method?: string;
  params?: Record<string, unknown>;
}

/** Handle one JSON-RPC message → a response object, or null for a notification (no reply). Shared by
 * the single-request and [M5] batch-array paths. */
async function handleRpc(msg: RpcMsg): Promise<Record<string, unknown> | null> {
  const { id, method, params } = msg;
  switch (method) {
    case "initialize":
      return {
        jsonrpc: "2.0",
        id,
        result: { protocolVersion: PROTOCOL, capabilities: { tools: {} }, serverInfo: SERVER_INFO },
      };
    case "notifications/initialized":
      return null; // a notification: no response
    case "ping":
      return { jsonrpc: "2.0", id, result: {} };
    case "tools/list":
      return { jsonrpc: "2.0", id, result: { tools: TOOLS } };
    case "tools/call": {
      const name = String(params?.name ?? "");
      const args = (params?.arguments as Record<string, unknown>) ?? {};
      try {
        return { jsonrpc: "2.0", id, result: await callTool(name, args) };
      } catch (e) {
        // tool errors are returned in-band (isError) per MCP. [M4] carry a stable machine code.
        const code = e instanceof ToolError ? e.code : "OM-IO-010";
        return {
          jsonrpc: "2.0",
          id,
          result: {
            content: [{ type: "text", text: `Error: ${(e as Error).message}` }],
            isError: true,
            code,
          },
        };
      }
    }
    default:
      return { jsonrpc: "2.0", id, error: { code: -32601, message: `method not found: ${method}` } };
  }
}

/** CF native Rate Limiting binding (wrangler.toml [[ratelimit]]); absent in local tests. */
interface Env {
  RATE_LIMITER?: { limit(o: { key: string }): Promise<{ success: boolean }> };
}

export default {
  async fetch(req: Request, env?: Env): Promise<Response> {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (req.method === "GET") {
      return json({ server: SERVER_INFO, transport: "streamable-http", tools: TOOLS.map((t) => t.name) });
    }
    if (req.method !== "POST") return json({ error: "method not allowed" }, 405);

    // Per-client rate limit for the open public endpoint (guarded: only when the binding is present).
    if (env?.RATE_LIMITER) {
      const ip = req.headers.get("cf-connecting-ip") ?? "anon";
      const { success } = await env.RATE_LIMITER.limit({ key: ip });
      if (!success) {
        return new Response(
          JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32029, message: "rate limit exceeded" } }),
          { status: 429, headers: { "Content-Type": "application/json", "Retry-After": "60", ...CORS } },
        );
      }
    }

    let parsed: unknown;
    try {
      parsed = await req.json();
    } catch {
      return rpcError(null, -32700, "parse error");
    }
    try {
      // [M5] JSON-RPC batch: an array of requests → an array of responses (notifications omitted), so a
      // portal onboarding a back-catalog reads many OMs in one HTTP round-trip instead of one call each.
      if (Array.isArray(parsed)) {
        if (parsed.length === 0) return rpcError(null, -32600, "empty batch");
        // [M5] bound the batch so one request can't fan out unbounded upstream fetches (abuse/DoS).
        if (parsed.length > MAX_BATCH) {
          return rpcError(null, -32600, `batch too large (max ${MAX_BATCH} requests per call)`);
        }
        const out = await Promise.all(parsed.map((m) => handleRpc(m as RpcMsg)));
        return json(out.filter((r) => r !== null));
      }
      const one = await handleRpc(parsed as RpcMsg);
      return one === null ? new Response(null, { status: 202, headers: CORS }) : json(one);
    } catch (e) {
      return rpcError(null, -32603, (e as Error).message);
    }
  },
};
