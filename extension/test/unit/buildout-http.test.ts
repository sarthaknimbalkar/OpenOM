import { describe, expect, test, vi } from "vitest";
import {
  buildoutRefFromUrl,
  httpMcpBuildoutClient,
} from "../../src/author/extract/connectors/buildout-http.js";

// The real MCP Streamable-HTTP client, exercised with an injected fake fetch (same pattern as the
// on-device extractor's fake): proves the initialize -> notifications/initialized -> tools/call
// sequence and that a listing is coerced from both a JSON and an SSE tool result. No network.

describe("buildoutRefFromUrl", () => {
  test("extracts the trailing numeric id from a Buildout listing URL", () => {
    expect(buildoutRefFromUrl("https://buildout.com/listings/123456")).toBe("123456");
    expect(buildoutRefFromUrl("https://team.buildout.com/website/987/x")).toBe("987");
  });
  test("null for non-Buildout / id-less / bad URLs", () => {
    expect(buildoutRefFromUrl("https://example.com/listings/1")).toBeNull();
    expect(buildoutRefFromUrl("https://buildout.com/about")).toBeNull();
    expect(buildoutRefFromUrl(undefined)).toBeNull();
    expect(buildoutRefFromUrl("not a url")).toBeNull();
  });
});

const LISTING = { addressLine1: "1 A St", city: "Townville", state: "TX", capRatePct: 6.25 };

function fakeFetch(toolBody: { ct: string; body: string }): typeof fetch {
  const calls: Array<Record<string, unknown>> = [];
  const impl = vi.fn(async (_url: string, init: RequestInit) => {
    const msg = JSON.parse(init.body as string);
    calls.push(msg);
    if (msg.method === "initialize") {
      return new Response(JSON.stringify({ jsonrpc: "2.0", id: 1, result: {} }), {
        status: 200,
        headers: { "content-type": "application/json", "mcp-session-id": "sess-1" },
      });
    }
    if (msg.method === "notifications/initialized") return new Response(null, { status: 202 });
    // tools/call
    return new Response(toolBody.body, {
      status: 200,
      headers: { "content-type": toolBody.ct },
    });
  });
  (impl as unknown as { calls: typeof calls }).calls = calls;
  return impl as unknown as typeof fetch;
}

describe("httpMcpBuildoutClient", () => {
  const cfg = { endpoint: "https://mcp.buildout.example/mcp" };
  const token = async () => "tok-123";

  test("isConfigured requires endpoint + token", async () => {
    expect(await httpMcpBuildoutClient(cfg, async () => null).isConfigured()).toBe(false);
    expect(await httpMcpBuildoutClient({ endpoint: "" }, token).isConfigured()).toBe(false);
    expect(await httpMcpBuildoutClient(cfg, token).isConfigured()).toBe(true);
  });

  test("getListing runs the MCP handshake and coerces a JSON tool result", async () => {
    const f = fakeFetch({
      ct: "application/json",
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 2,
        result: { content: [{ type: "text", text: JSON.stringify(LISTING) }] },
      }),
    });
    const listing = await httpMcpBuildoutClient(cfg, token, f).getListing("123");
    expect(listing.capRatePct).toBe(6.25);
    const calls = (f as unknown as { calls: Array<{ method: string }> }).calls;
    expect(calls.map((c) => c.method)).toEqual([
      "initialize",
      "notifications/initialized",
      "tools/call",
    ]);
  });

  test("coerces an SSE tool result (structuredContent)", async () => {
    const sse = `event: message\ndata: ${JSON.stringify({
      jsonrpc: "2.0",
      id: 2,
      result: { structuredContent: LISTING },
    })}\n\n`;
    const listing = await httpMcpBuildoutClient(cfg, token, fakeFetch({ ct: "text/event-stream", body: sse })).getListing("123");
    expect(listing.state).toBe("TX");
  });

  test("surfaces an MCP error instead of returning garbage", async () => {
    const f = fakeFetch({
      ct: "application/json",
      body: JSON.stringify({ jsonrpc: "2.0", id: 2, error: { code: -32001, message: "not found" } }),
    });
    await expect(httpMcpBuildoutClient(cfg, token, f).getListing("nope")).rejects.toThrow(/not found/);
  });
});
