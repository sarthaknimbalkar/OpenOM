# Deploying openOM (site + domain)

What this covers: making the **site live** — the docs, the verify tool, the grounding page, and the
**resolvable namespace** (`…/openom/ns/0.1` + the schemas, #139) — on **openom.app** (front-door) and
**verveliolabs.com** (canonical namespace host). This is account/DNS work; it is **operational**, not
code. It does **not** touch the Buildout MCP hookup (separate — needs the Buildout client/server).

The `site/` tree is already generated and drift-locked; `.github/workflows/deploy-site.yml` publishes
it to **Cloudflare Pages** (chosen because it honors `site/_headers`, which serves the extensionless
`ns/0.1` as `application/ld+json` with CORS — a plain host would break JSON-LD).

## Domain reality (decision 2026-08-21, memo §8)

- **Canonical namespace stays `https://verveliolabs.com/openom/...`** — the schema `$id` + `@context`
  are pinned there and MUST resolve there. Attach `verveliolabs.com` to the Pages project.
- **openom.app is the human front-door** (docs / verify / marketing / eventual hosted MCP) — attach
  it to the *same* Pages project so both serve the one `site/` tree.

## One-time setup

### 1. Cloudflare account + Pages project
1. Create a free Cloudflare account.
2. Workers & Pages → Create → **Pages** → name the project **`openom`** (the workflow passes
   `--project-name=openom`).
3. Get credentials for CI:
   - **Account ID**: Workers & Pages overview → right sidebar.
   - **API token**: My Profile → API Tokens → Create Token → *Cloudflare Pages: Edit* permission.

### 2. GitHub secrets (activates the deploy workflow)
Repo → Settings → Secrets and variables → Actions → add:
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

(Until both exist the deploy step self-skips — that's why CI stays green pre-deploy.)

### 3. Point the domains at Cloudflare
Easiest is to let Cloudflare host DNS for both domains (free):
1. Cloudflare → Add a site → `openom.app`; Cloudflare gives you two nameservers.
2. **GoDaddy** (where openom.app is registered): Domain → Nameservers → Change → **Custom** → enter
   Cloudflare's two nameservers. Wait for propagation (minutes–hours).
3. Repeat for `verveliolabs.com` (or, if its DNS must stay elsewhere, add a CNAME for the
   `/openom` host to the Pages `*.pages.dev` target — nameserver delegation is simpler).

### 4. Attach custom domains to the Pages project
Pages project **openom** → Custom domains → add:
- `openom.app` (and `www.openom.app` if you want it)
- `verveliolabs.com` (so `verveliolabs.com/openom/*` resolves the canonical namespace)

Cloudflare issues TLS automatically once DNS resolves to it.

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
curl -sI https://verveliolabs.com/openom/ns/0.1 | grep -i content-type   # application/ld+json
curl -s  https://verveliolabs.com/openom/spec/om-0.1.schema.json | head
# front-door pages:
#   https://openom.app/openom/docs/         (docs)
#   https://openom.app/openom/verify/       (verify tool)
#   https://openom.app/openom/docs/grounding-ai.html
```
Then run the opt-in live check: `OPENOM_SITE_BASE=https://verveliolabs.com pytest spec/tests/test_site.py -k live`.

> Note the `/openom/` path prefix: the tree is built under it (canonical namespace is
> `verveliolabs.com/openom/*`), so openom.app serves `openom.app/openom/...`. If you want bare
> `openom.app/docs`, that's a namespace change (memo §8 keeps the prefix for now) — do it before wide
> adoption if ever.

## What this does NOT solve (separate items)
- **Buildout MCP ingestion** — needs your Buildout client/server, not the domain.
- **Hosted deterministic MCP** (`om-mcp-http`) — a separate service deploy (Workers/Fly/Render), not
  the static site.
- **Package publish** — PyPI (Trusted Publishing) + npm (`--provenance`) via
  `.github/workflows/release.yml`, triggered by a version tag; needs the PyPI/npm project setup.
