# openom-mcp

A thin, **deterministic** [FastMCP](https://github.com/jlowin/fastmcp) server over
[`openom-core`](../core) — six tools, zero inference:
`om_inspect · om_extract_text · om_extract_images · om_read · om_validate · om_embed`.
Two transports: **stdio** (`om-mcp`) and **hosted Streamable HTTP** (`om-mcp-http`, SSRF-guarded,
rate-limited, untrusted-parse-isolated).

```sh
pip install openom-mcp           # or, from a clone:  pip install -e "mcp[dev]"
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

`om-mcp-http` serves Streamable HTTP on `:8080`. Vervelio runs a free public deterministic
instance; point your client's HTTP-MCP connector at its URL (published once live). Two-tier
validation: schema errors block, consistency warnings never do; market truth is out of scope.

## Grounding an AI agent

Treat an openOM payload as the broker's **asserted opinion**, not fact: attribute every figure to
`assertedBy` as of `assertedDate`, don't use a payload whose `verification.hashValid` isn't true,
and never present an OM figure as verified truth (an OM is an advertisement / opinion of value). The
full guide — MCP config, tool usage, and a system-prompt snippet — is
**[Grounding AI agents in openOM](../site/openom/docs/grounding-ai.html)** (served at
`…/openom/docs/grounding-ai.html`).

Tests: `pytest mcp -q`.
