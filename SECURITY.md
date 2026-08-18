# Security Policy

## Reporting a vulnerability

Email **hello@vervelio.com** with details and a reproduction. Please do not open a public issue
for security-sensitive reports. We aim to acknowledge within 3 business days.

## Threat model

openOM's core processes **untrusted PDF input** and produces deterministic output. The design
constraints below are security properties, not just style:

- **No inference, no network, no telemetry in the core.** `core/`, `cli`, and `mcp` make zero
  outbound calls and hold no credentials (the hosted `/mcp` transport adds one explicit fetch, §M).
  There is nothing to exfiltrate and no key to leak. CI's `boundary` job fails if a
  network/inference client enters the dependency tree.
- **Decompression bombs.** Embedded payloads are capped (`MAX_PAYLOAD_BYTES`, 5 MB) and rejected
  with `OM-IO-BOMB`; the read-path inflate is streamed with a running ceiling so a lying/absent
  content-length cannot buffer an unbounded body first.
- **Malformed / hostile Unicode.** Canonicalization rejects unpaired surrogates
  (`OM-IO-BADUTF8`), duplicate member names after NFC (`OM-IO-DUPKEY`), non-representable
  numbers (`OM-IO-NUMRANGE`), and non-object top levels (`OM-IO-TOPLEVEL`).
- **Non-destructive by construction.** Embedding appends an attachment + XMP marker without
  touching page content; the visual document is unchanged.
- **Integrity, not authenticity (0.1).** The integrity hash (SHA-256 over the canonical bytes)
  detects tampering/corruption of the payload. Cryptographic *signatures* (authenticity of the
  asserting party) are reserved: `meta.signature` is null OR the reserved `{alg,keyId,value}`
  shape, and a 0.1 consumer MUST ignore a populated value (no trust weight).

### Trust boundaries

| Boundary | Untrusted side | Guard |
|---|---|---|
| Web page → extension content script | The page's DOM/links (attacker-controlled) | Content script is thin; it only asks the service worker for read-only badge state, and only on user-opted-in domains. |
| Content script → service worker | Messages from the hostile-page world | SW validates `sender.id === chrome.runtime.id` and confines content-script senders to `linkbadge:enabled`/`linkbadge:verify` (never fetch/embed/settings). |
| Extension → network (PDF re-fetch, origin mirror, webhook) | URLs derived from page content | `assertSafeUrl` — https only + reject private/loopback/link-local/CGNAT/metadata IP literals in every inet_aton + IPv6 form. |
| Internet → hosted `/mcp` HTTP transport | The uploaded/fetched PDF | SSRF resolve-then-pin (`fetch.py`), untrusted parse isolated in a killable, memory-bounded subprocess (`guard.py`), per-principal rate limit, page ceiling. |
| Webhook receiver ← extension | The signed delivery | HMAC-SHA256 signature (constant-time verify) + the receiver MUST re-check `payloadHash` binds the payload (`verifyEnvelopePayloadHash`). |

### Assets

| Asset | Where | Protection |
|---|---|---|
| Webhook signing secret | Extension (`chrome.storage.local`) | AES-GCM wrapped under a non-extractable IndexedDB key (#126); ciphertext only at rest. |
| Payload integrity | The embedded om.json + XMP `payloadHash` | SHA-256 over canonical bytes; a mismatch is terminal for trust (badge `hash-mismatch`). |
| Hosted API key / quota (M3) | Hosted service | Out of scope for the open repo; issuance/rotation is a hosted-deploy concern (#52). |

### Residual risks (known and accepted for 0.1)

- **DNS-name SSRF (browser).** `assertSafeUrl` cannot resolve DNS in the browser, so a *hostname*
  that resolves to a private IP is not caught client-side. The hosted `/mcp` `fetch.py` guard
  resolves-then-pins server-side; the webhook receiver should also validate `sourceUrl`/origin.
- **Off-POSIX memory bound.** The untrusted-parse memory cap uses `RLIMIT_AS` (POSIX). Off-POSIX
  the in-process cap is impossible, so a hosted deployment MUST bound memory at the platform layer
  (container/cgroup memory limit or a Windows Job Object); a rejected cap fails loud (#123).
- **Secret at rest vs. in-origin code.** Wrapping the webhook secret defends passive
  storage/disk inspection, NOT code executing inside the extension's own origin (which could use
  the non-extractable key) (#126).
- **In-browser decryption scope.** Author-mode in-browser decryption covers empty-user-password
  AES only (permission encryption); RC4, real passwords, and out-of-scope files fall back to the
  CLI. The raw ObjStm scan skips stream bodies and clamps `/Length` to the `endstream` bound (#124);
  a decrypt that cannot be produced faithfully fails safe to `null`, never a corrupt OM.
- **Supply chain.** A `vuln-scan` CI job fails the build on a high/critical advisory in shipped
  deps (pip-audit + `npm audit --omit=dev`); dev-only tooling advisories are surfaced but
  non-blocking and tracked by Dependabot.

## What is explicitly out of scope

- **Market truth.** openOM never asserts a claim is *correct*, only internally consistent. A
  payload is an identified party's opinion as of a date.
- **Extraction correctness of third-party authoring tools.** The standard defines the payload
  and its verification, not the accuracy of any particular producer's mapping.

## Supported versions

Pre-1.0: only the latest `main` receives fixes. The `0.1` schema may change until 1.0.
