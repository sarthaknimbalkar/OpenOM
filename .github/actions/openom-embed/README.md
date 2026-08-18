# openOM GitHub Action

Embed or validate openOM payloads in a broker's CI pipeline — no browser, no inference. Wraps the
deterministic `om` CLI.

## Validate a payload on every push (the gate)

```yaml
- uses: sarthaknimbalkar/OpenOM/.github/actions/openom-embed@main
  with:
    command: check
    payload: deals/123.json
    schema: spec/om-0.1.schema.json   # enables the blocking schema-error tier
    strict: "true"                    # also fail on consistency warnings
```

`check` accepts a payload JSON **or** a PDF with an embedded `om.json` (via `input:`). Schema errors
always fail the job; consistency warnings fail only under `strict`.

## Embed a payload at publish time

```yaml
- uses: sarthaknimbalkar/OpenOM/.github/actions/openom-embed@main
  with:
    command: embed
    pdf: offering.pdf
    payload: deals/123.json
    out: offering.openom.pdf
    asserted-date: "2026-08-18"       # defaults to today (UTC)
- uses: actions/upload-artifact@v4
  with: { name: openom-pdf, path: offering.openom.pdf }
```

The output PDF is visually identical; re-embedding replaces (never stacks) and records
`meta.supersedes`.

## Inputs

| Input | For | Default | Notes |
|-------|-----|---------|-------|
| `command` | both | `check` | `embed` or `check` |
| `pdf` | embed | — | input OM PDF |
| `payload` | both | — | payload JSON |
| `input` | check | `payload` | payload JSON **or** an embedded PDF |
| `out` | embed | `out.openom.pdf` | output path |
| `asserted-date` | embed | today (UTC) | ISO-8601 |
| `schema` | check | — | JSON Schema → error tier |
| `strict` | check | `false` | fail on warnings too |
| `version` | both | latest | pip spec, e.g. `==0.1.0` |
| `install` | both | `true` | set `false` if `om` is already on PATH |

Pin `@v0.1.0` (a release tag) rather than `@main` for reproducible builds once tags are published.
