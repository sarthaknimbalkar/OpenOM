// Concrete Buildout client over MCP Streamable HTTP (decision memo §3.1/§3.3 Q1: HTTP/OAuth ->
// runs in the extension). This is a real MCP client - initialize -> notifications/initialized ->
// tools/call - the same transport openOM's own hosted server speaks. It is DETERMINISTIC (a
// data-fetch, no inference) and injected into `makeBuildoutConnector`, so it sits on the
// deterministic side of the cardinal rule.
//
// The one contract this ASSUMES (the memo's Q2 - another product's private API): the tool name
// (`get_listing`) and that it returns a JSON listing object matching `BuildoutListing`. Both are
// isolated here + in the mapper, so reconciling them with the real Buildout MCP is a one-line change
// and cannot leak into the rest of openOM.
import type { BuildoutClient, BuildoutListing } from "./buildout.js";

export interface BuildoutHttpConfig {
  /** The Buildout MCP Streamable-HTTP endpoint (e.g. https://mcp.buildout.example/mcp). */
  endpoint: string;
  /** The tool that returns a listing record by id. Assumed name; override to match the real MCP. */
  toolName?: string;
}

/** Fetch a listing id from a Buildout listing page URL, else null (connector then unavailable). */
export function buildoutRefFromUrl(url: string | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    if (!/(^|\.)buildout\.com$/i.test(u.hostname)) return null;
    // Buildout listing paths carry a numeric id, e.g. /listings/123456 or /.../123456. Take the last
    // numeric path segment. (Assumed shape - reconcile with the real URL scheme if it differs.)
    const nums = u.pathname.split("/").filter((s) => /^\d+$/.test(s));
    return nums.length ? nums[nums.length - 1] : null;
  } catch {
    return null;
  }
}

interface RpcResponse {
  result?: { content?: Array<{ type: string; text?: string }>; structuredContent?: unknown };
  error?: { code: number; message: string };
}

/** Parse an MCP HTTP response body that is either application/json or an SSE stream. */
function parseRpc(contentType: string, body: string): RpcResponse {
  if (contentType.includes("text/event-stream")) {
    // take the last `data:` line's JSON (the tool result)
    const data = body
      .split(/\r?\n/)
      .filter((l) => l.startsWith("data:"))
      .map((l) => l.slice(5).trim())
      .filter(Boolean);
    if (!data.length) throw new Error("empty SSE response");
    return JSON.parse(data[data.length - 1]) as RpcResponse;
  }
  return JSON.parse(body) as RpcResponse;
}

/** Pull the listing object out of a tools/call result (structuredContent, or JSON in a text block). */
function listingFromResult(r: RpcResponse): BuildoutListing {
  if (r.error) throw new Error(`Buildout MCP error ${r.error.code}: ${r.error.message}`);
  const sc = r.result?.structuredContent;
  if (sc && typeof sc === "object") return sc as BuildoutListing;
  const text = r.result?.content?.find((c) => c.type === "text")?.text;
  if (!text) throw new Error("Buildout MCP returned no listing content");
  return JSON.parse(text) as BuildoutListing;
}

/**
 * A `BuildoutClient` over MCP Streamable HTTP. `getToken` supplies the bearer/OAuth token (from the
 * extension secret-store); `fetchImpl` is injectable for tests. isConfigured() is true only when an
 * endpoint and a token are both present - so an unconfigured install is inert and the picker falls
 * back to the on-device extractor.
 */
export function httpMcpBuildoutClient(
  config: BuildoutHttpConfig,
  getToken: () => Promise<string | null>,
  fetchImpl: typeof fetch = fetch,
): BuildoutClient {
  const tool = config.toolName ?? "get_listing";

  async function rpc(sessionId: string | null, body: unknown): Promise<Response> {
    const token = await getToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
    };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (sessionId) headers["Mcp-Session-Id"] = sessionId;
    return fetchImpl(config.endpoint, { method: "POST", headers, body: JSON.stringify(body) });
  }

  return {
    isConfigured: async () => Boolean(config.endpoint) && Boolean(await getToken()),
    getListing: async (ref: string): Promise<BuildoutListing> => {
      // 1. initialize (captures the session id)
      const init = await rpc(null, {
        jsonrpc: "2.0",
        id: 1,
        method: "initialize",
        params: {
          protocolVersion: "2024-11-05",
          capabilities: {},
          clientInfo: { name: "openom-extension", version: "0.1" },
        },
      });
      if (!init.ok) throw new Error(`Buildout MCP initialize failed: ${init.status}`);
      const sessionId = init.headers.get("mcp-session-id");
      // 2. initialized notification
      await rpc(sessionId, { jsonrpc: "2.0", method: "notifications/initialized" });
      // 3. tools/call -> the listing
      const res = await rpc(sessionId, {
        jsonrpc: "2.0",
        id: 2,
        method: "tools/call",
        params: { name: tool, arguments: { ref } },
      });
      if (!res.ok) throw new Error(`Buildout MCP tools/call failed: ${res.status}`);
      const body = await res.text();
      return listingFromResult(parseRpc(res.headers.get("content-type") ?? "", body));
    },
  };
}
