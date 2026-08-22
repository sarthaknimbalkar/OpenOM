# openom-mcp

A thin, **deterministic** [FastMCP](https://github.com/jlowin/fastmcp) server over
[`openom-core`](../core) - six tools, zero inference:
`om_inspect · om_extract_text · om_extract_images · om_read · om_validate · om_embed`.
Two transports: **stdio** (`om-mcp`) and **hosted Streamable HTTP** (`om-mcp-http`, SSRF-guarded,
rate-limited, untrusted-parse-isolated).

```sh
pip install openom-mcp           # depends on openom-core (also from PyPI)
# from a clone (openom-core is not yet on PyPI): install core first, then mcp:
pip install -e ./core && pip install -e "./mcp[dev]"
```

## Connect it to an MCP client (stdio)

Add to your client's MCP config (e.g. Claude Desktop `claude_desktop_config.json`, or any
`mcp.json`):

```json
{
  "mcpServers": {
    "openom": { "command": "om-mcp" }
  }
}
```

## Hosted HTTP

`om-mcp-http` serves Streamable HTTP. By default it binds **loopback** (`127.0.0.1:8080`) — safe out
of the box, not a world-open server. The free **public grounding endpoint** at
`https://mcp.openom.app/mcp` is a serverless Cloudflare Worker (`/mcp-worker`) exposing the read-side
`om_read` + `om_validate` via the byte-parity `/js` core; run `om-mcp-http` yourself for the full
six-tool surface (extract/embed/inspect). Two-tier validation: schema errors block, consistency
warnings never do; market truth is out of scope.

### Configuration (env)

Every knob is an environment variable; defaults are safe for local use:

| Variable | Default | Meaning |
| --- | --- | --- |
| `OPENOM_MCP_HOST` | `127.0.0.1` | Bind address. Set `0.0.0.0` to expose publicly. |
| `OPENOM_MCP_PORT` | `8080` | Bind port. |
| `OPENOM_MCP_DNS_REBINDING` | auto | Host/Origin DNS-rebinding defense. **Auto-ON when bound to a non-loopback host.** |
| `OPENOM_MCP_ALLOWED_HOSTS` | *(empty)* | Comma-separated Host allowlist (set this when binding publicly). |
| `OPENOM_MCP_ALLOWED_ORIGINS` | *(empty)* | Comma-separated Origin allowlist. |
| `OPENOM_MCP_RATE_LIMIT` / `_WINDOW` | `120` / `60` | Per-principal request cap per window (seconds). |
| `OPENOM_MCP_MAX_FETCH_BYTES` | `209715200` | Cap on fetched PDF size (SSRF/DoS guard). |
| `OPENOM_MCP_MAX_PAGES` | *(unset)* | Per-call page ceiling for extraction. |
| `OPENOM_MCP_LOG` | — | Log level. |

When you bind publicly (`0.0.0.0`) always set `OPENOM_MCP_ALLOWED_HOSTS`/`_ORIGINS` — the server logs
a warning if you don't.

**Production backends (env-selectable):**

| Variable | Default | Meaning |
| --- | --- | --- |
| `OPENOM_MCP_BLOB_BACKEND` | `local` | `r2` uses Cloudflare R2/S3 (needs `OPENOM_R2_BUCKET`, `OPENOM_R2_ENDPOINT`, `OPENOM_R2_ACCESS_KEY`, `OPENOM_R2_SECRET_KEY`; `boto3` extra). |
| `OPENOM_MCP_LIMITER` | `memory` | `redis` uses a shared Redis so multiple replicas enforce one global limit (needs `OPENOM_REDIS_URL`; a `redis`-py-compatible client). |

(Both `boto3` and `redis` are imported lazily — neither is a hard dependency.) For anything further,
`build_http_app(...)` accepts `blob_store` / `rate_limiter` injections directly.

## Grounding an AI agent

Treat an openOM payload as the broker's **asserted opinion**, not fact: attribute every figure to
`assertedBy` as of `assertedDate`, don't use a payload whose `verification.hashValid` isn't true,
and never present an OM figure as verified truth (an OM is an advertisement / opinion of value). The
full guide - MCP config, tool usage, and a system-prompt snippet - is
**[Grounding AI agents in openOM](../site/openom/docs/grounding-ai.html)** (served at
`…/openom/docs/grounding-ai.html`).

Tests: `pytest mcp -q`.
