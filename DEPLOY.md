# Deploying openOM (site + domain)

> **Chosen host: Cloudflare Pages** (decided 2026-08-21) - free, CI-driven, honors `site/_headers`.
> The `.htaccess`/GoDaddy path below is kept only as a portable fallback.

What this covers: making the **site live** - the docs, the verify tool, the grounding page, and the
**resolvable namespace** (`…/openom/ns/0.1` + the schemas, #139) - on **openom.app** (front-door) and
**verveliolabs.com** (canonical namespace host). This is account/DNS work; it is **operational**, not
code. It does **not** touch the Buildout MCP hookup (separate - needs the Buildout client/server).

The `site/` tree is already generated and drift-locked; `.github/workflows/deploy-site.yml` publishes
it to **Cloudflare Pages** (chosen because it honors `site/_headers`, which serves the extensionless
`ns/0.1` as `application/ld+json` with CORS - a plain host would break JSON-LD).

## Hosting options - you are NOT locked to Cloudflare

The only hard requirement is a host that can set **`Content-Type: application/ld+json`** + open
**CORS** on the extensionless `ns/0.1` path (and `application/schema+json` on the schemas). The tree
ships **both** header configs so it's host-portable:

| Host | Works? | Uses | Notes |
|------|:------:|------|-------|
| Cloudflare Pages | ✅ | `site/_headers` | free, CLI/Git deploy, auto-TLS - the wired default |
| Netlify | ✅ | `site/_headers` | same file; drag-and-drop or Git deploy, free |
| **GoDaddy** (Linux / cPanel hosting) | ✅ | `site/.htaccess` | upload the `site/` folder via cPanel File Manager / FTP; Apache reads `.htaccess`. Needs a paid hosting plan; no CI deploy |
| GoDaddy **Website Builder** | ❌ | - | locked builder - can't upload files or set headers |
| GitHub Pages | ⚠️ | - | can't set content-type for the extensionless `ns/0.1` |

You can also **keep the domain registered at GoDaddy** and point its DNS at any of the free hosts -
you don't have to move to Cloudflare to use openom.app. The GoDaddy-hosting path below is only if you
specifically want to host *on* GoDaddy.

### GoDaddy cPanel hosting (if you host on GoDaddy)
1. Buy a GoDaddy **Web Hosting** (Linux/cPanel) plan for the domain.
2. `python spec/scripts/gen_site.py` locally to (re)build `site/`.
3. In cPanel → File Manager (or FTP), upload the **contents of `site/`** into `public_html/`
   (including the hidden `.htaccess` - enable "show hidden files").
4. Confirm `mod_headers` is enabled (it is on GoDaddy Linux hosting); the `.htaccess` sets the
   content-types + CORS. Re-upload whenever `site/` changes - there's no CI path for this host.

The rest of this doc (Cloudflare) is the recommended, free, CI-driven path.

## Domain reality (updated 2026-08-21 - migrated to openom.app; supersedes memo §8)

The canonical namespace is now **`https://openom.app/...`** - the schema `$id`, the JSON-LD
`@context`, and the XMP marker namespace all resolve there. `openom.app` is a fresh, dedicated domain
(verveliolabs.com is the company domain - left untouched). So you attach **only `openom.app`** to the
Pages project; it serves the whole `site/` tree (namespace + docs + verify). `verveliolabs.com` is
**not** needed for openOM.

## One-time setup

### 1. Cloudflare account + Pages project
1. Create a free Cloudflare account.
2. Workers & Pages → Create → **Pages** → name the project **`openom`** (the workflow passes
   `--project-name=openom`).
3. Get credentials for CI:
   - **Account ID**: Workers & Pages overview → right sidebar.
   - **API token**: My Profile → API Tokens → Create Token → *Cloudflare Pages: Edit* permission.

### Cloudflare API token - full dev-phase permissions (make ONE, reuse it)

Create one Custom Token (My Profile → API Tokens → Create Custom Token) with everything openOM will
need through the dev phase, so you never have to recreate it. Store it in `.env` (gitignored) as
`CLOUDFLARE_API_TOKEN`; 30-day expiry + rotation is fine.

**Account permissions** - scope: Include → *Hello@vervelio.com's Account* (`REDACTED`):
- **Cloudflare Pages · Edit** - create + deploy the docs/namespace site *(in use)*
- **Cloudflare Tunnel · Edit** - the self-hosted MCP endpoint (gx10) + any future self-hosted service *(in use)*
- **Workers Scripts · Edit** - deploy the hosted deterministic MCP (`om-mcp-http`) as a Worker *(later)*
- **Workers R2 Storage · Edit** - the MCP blob store (R2 uploads, ≤24h TTL) *(later)*
- **Workers KV Storage · Edit** - distributed rate-limit/quota counters + API-key store (#51/#52) *(later)*
- **D1 · Edit** - optional alternative store for API keys *(later, if chosen)*
- **Account Settings · Read** - resolve account id / general

**Zone permissions** - scope: Include → *All zones from account* (covers openom.app + any future domain):
- **DNS · Edit** - custom-domain records, the MCP subdomain, tunnel CNAMEs, verification records *(in use)*
- **Zone · Read** - read zone info *(in use)*
- **Workers Routes · Edit** - bind the MCP Worker to a route/subdomain *(later)*
- **SSL and Certificates · Edit** - custom hostnames / origin certs *(later)*
- **Cache Purge · Purge** - purge the edge cache after a deploy *(later)*

This is the **complete** Cloudflare surface openOM will ever need - set it once (30-day dev-phase
expiry + rotation is fine) and never revisit. Strictly for the **static site deploy** you only need
Pages·Edit + DNS·Edit + Zone·Read; the **gx10 MCP endpoint** additionally needs Cloudflare Tunnel·Edit;
the rest future-proof the token for the hosted Worker + R2/KV/D1 without a remake.

### 2. GitHub secrets (activates the deploy workflow)
Repo → Settings → Secrets and variables → Actions → add:
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

(Until both exist the deploy step self-skips - that's why CI stays green pre-deploy.)

### 3. Point openom.app at Cloudflare
1. Cloudflare → Add a site → `openom.app`; Cloudflare gives you two nameservers. (openom.app is
   fresh - new Aug 2026 - so there are no existing records to migrate.)
2. **GoDaddy** (where openom.app is registered): Domain → Nameservers → Change → **Custom** → enter
   Cloudflare's two nameservers. Wait for propagation (minutes–hours).

### 4. Attach the custom domain to the Pages project
Pages project **openom** → Custom domains → add `openom.app` (and `www.openom.app` if you want it).
Cloudflare issues TLS automatically once DNS resolves to it. (No verveliolabs.com - the namespace is
openom.app now.)

### 5. Deploy
Manual (CI is `workflow_dispatch`-only):
```bash
gh workflow run deploy-site.yml
```
It verifies `site/` isn't stale, builds the badge widget into the tree, and runs
`wrangler pages deploy site --project-name=openom`.

## Verify it worked
```bash
# canonical namespace resolves with the right content-type:
curl -sI https://openom.app/ns/0.1 | grep -i content-type   # application/ld+json
curl -s  https://openom.app/spec/om-0.1.schema.json | head
# pages:
#   https://openom.app/docs/         (docs)
#   https://openom.app/verify/       (verify tool)
#   https://openom.app/docs/grounding-ai.html
```
Then run the opt-in live check: `OPENOM_SITE_BASE=https://openom.app pytest spec/tests/test_site.py -k live`.

> URLs are bare on the dedicated domain: `openom.app/ns/0.1`, `openom.app/spec/…`,
> `openom.app/docs/`, `openom.app/verify/` (the `/openom/` path prefix was dropped).

## What this does NOT solve (separate items)
- **Buildout MCP ingestion** - needs your Buildout client/server, not the domain.
- **Hosted deterministic MCP** (`om-mcp-http`) - a separate service deploy (Workers/Fly/Render), not
  the static site.
- **Package publish** - PyPI (Trusted Publishing) + npm (`--provenance`) via
  `.github/workflows/release.yml`, triggered by a version tag; needs the PyPI/npm project setup.
