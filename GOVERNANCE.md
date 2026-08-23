# openOM governance

openOM is an open standard, not just a tool. This document says how the standard evolves, what is
guaranteed stable, and how to propose a change - so implementers can adopt it as *the* standard, not a
single vendor's product.

## Steward

openOM is stewarded by **[Vervelio Labs](https://verveliolabs.com)** as a neutral maintainer. The
toolchain is MIT-licensed and the specification is CC-BY-4.0 - anyone may implement, fork, embed, or
build on it without permission. Stewardship means maintaining the spec, the conformance suite, and the
reference implementations in the open; it does not mean gatekeeping who may use the standard.

## What is guaranteed stable

The **`/spec`** directory is the source of truth: the JSON Schema, the JSON-LD `@context`, the sample
payloads, the conformance vectors, and the changelog.

- **Published URLs are immutable.** Once a versioned namespace/schema URL is published
  (`https://openom.app/ns/0.1`, `.../spec/om-0.1.schema.json`), the bytes it serves never change in a
  breaking way. A JSON-LD processor or `$ref` resolver can pin it forever.
- **Within a version, changes are additive only** - new optional fields, new vocabulary terms, relaxed
  constraints. Nothing that would invalidate a previously-valid payload.
- **Breaking changes ship a new version** - a new namespace (`.../ns/0.2`) and schema `$id`. The old
  version keeps resolving.
- **Codes are stable.** Validation codes (`OMV-E###`, `OMW-W###`, `OMI-I###`) keep their meaning.

### Consumer-side compatibility (what a minor/patch may change under you)

The "additive only" rule above protects *producers* (an old payload stays valid). Consumers should
also know what a **minor** release may change in what they RECEIVE:

- **Emitted values.** A relaxed constraint (a widened numeric range, a loosened enum/pattern) means a
  minor openOM may emit or accept values an older consumer didn't expect. Validate defensively; do not
  hard-code the old bounds.
- **New finding codes.** New `OMW-W###`/`OMI-I###` codes (never blocking) may appear in a minor. Treat
  an unknown warning/info code as non-fatal; branch only on codes you recognize.
- **Deprecation signaling.** An optional field slated to move is marked `deprecated` in the schema and
  announced in `CHANGELOG.md` at least one minor before it changes; it never disappears within a `0.x`.
- **Namespace permanence.** A published versioned namespace/schema URI (`.../ns/0.x`,
  `.../spec/om-0.x.schema.json`) is immutable and **keeps resolving indefinitely** after its successor
  ships - it is never taken down (the norm for versioned web namespaces: W3C, schema.org, JSON-LD
  contexts). A pinned integration therefore does not break; upgrading to a new version is opt-in.

## The one invariant that never changes

**Deterministic core, inference at the edges.** The open engine, MCP server, and consumer tooling
contain zero inference - no model calls, no keys, no per-call cost. Any change that would put inference
into `/core`, `/mcp`, `/mcp-worker`, or consumer `/js` is out of scope by definition.

## Proposing a change (RFC)

1. **Open a spec-change RFC** using the [issue template](.github/ISSUE_TEMPLATE/spec-change.md):
   state the problem, the proposed change, backward-compatibility impact, and migration.
2. **Discussion** happens on the issue. Small, additive, backward-compatible changes are the easy path;
   anything breaking must justify a version bump.
3. **A maintainer decides** (see [CODEOWNERS](.github/CODEOWNERS)) and records the outcome. Accepted
   changes land as a PR that updates `/spec` (schema + `@context` + samples + vectors) **and** both
   reference cores (`/core` Python and `/js` TypeScript) so byte-parity is preserved, with a
   `spec/CHANGELOG.md` entry.
4. **Every accepted spec change** is reflected in the conformance vectors so implementers can verify.

## Conformance

The conformance suite in `/spec` defines what "openOM 0.1 conformant" means. An implementation is
conformant for a role when it passes the vectors for that role. The names/marks may be used to describe
conformance ("openOM 0.1 conformant") only by implementations that pass - not to imply endorsement of a
non-conformant product, and not to name a fork. Forking the spec is permitted (CC-BY-4.0); using the
marks for a fork is not.

## Scope: assertions, not facts

openOM records **who** asserted data, that it is **unaltered**, and **as of when** - never that the
figures are true. Tooling checks internal consistency (NOI ÷ price vs cap rate, schedule sums, date
math); it never adjudicates market truth, and proposals to make it do so are out of scope.

## Security

Report vulnerabilities per [SECURITY.md](SECURITY.md) - privately, not via a public issue.
