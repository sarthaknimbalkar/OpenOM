# openom-cli

The `om` command over [`openom-core`](../core) - no UI, no inference; also the server-side path.

```sh
# From a clone (not yet on PyPI): install core first, then cli.
pip install -e core && pip install -e cli   # add [dev] to either only to contribute
# Once published:  pip install openom-cli

om inspect  offering.pdf
om embed    offering.pdf --payload deal.json --out out.pdf --asserted-date 2026-08-16 --validate
om read     out.pdf
om validate deal.json
om check    out.pdf               # consistency only
om --version
```

## Conformance (CI integrity gate)

`om conformance` reproduces the pinned spec vectors + samples with your installed openOM - run it in
CI so an environment/version change can't silently drift from the standard. It reads the repo's
`spec/` tree (pass `--spec-dir <path>/spec` from outside a checkout):

```sh
om --quiet conformance                       # exit 0 = conformant, 1 = a check failed
om conformance --impl-dir ./my-output        # certify a THIRD-PARTY implementation's output
```

## Bulk / back-catalog embed

Embed openOM data into many OMs in one run - the adoption path (seed supply at the source):

```sh
# a folder of *.pdf, each paired with a sibling <name>.om.json payload:
om embed-batch --dir ./catalog --out-dir ./embedded --asserted-date 2026-08-22 \
   --schema ../spec/om-0.1.schema.json
#   --dry-run        preview (validate + report, write nothing)
#   --skip-existing  resume a large run;  --force  overwrite;  --jobs 4  parallel

# or a JSON manifest of {pdf, payload, out?, assertedDate?} items:
om embed-batch --manifest ./manifest.json --out-dir ./embedded --schema ../spec/om-0.1.schema.json
```

Deterministic, non-destructive, idempotent (re-embed replaces + records `supersedes`); schema errors
skip that item (never embedded); emits a JSON summary (per-status counts) and `--report FILE`.

### From Buildout (connector -> manifest)

Turn fetched Buildout listings into an `embed-batch` manifest. Save each `buildout_get_listing` JSON
as `<id>.json` and its OM PDF as `<id>.pdf`, then:

```sh
om buildout-manifest --listings-dir ./listings --pdf-dir ./oms --out-dir ./staged \
   --broker "Jane Broker" --brokerage "Acme NNN" --license "MI 000" \
   --asserted-date 2026-08-22 --noi-type in-place
om embed-batch --manifest ./staged/manifest.json --out-dir ./embedded --schema ../spec/om-0.1.schema.json
```

The map is deterministic (names/units normalized, absent fields omitted, `cap_rate_derived` used);
the assertion identity is yours (flags), never inferred. Review the staged payloads before embedding.

## Watch-folder (server-side automation)

Drop `<name>.pdf` + `<name>.json` pairs into a folder and get embedded OMs out - no UI:

```sh
om watch ./inbox --out ./outbox --asserted-date 2026-08-18 \
   --schema ../spec/om-0.1.schema.json      # a payload with schema errors is skipped, not embedded

om watch ./inbox --out ./outbox --asserted-date 2026-08-18 --once   # drain the backlog + exit (cron/CI)
```

Deterministic, zero inference. A pair is re-embedded when its pdf/json changes; `--once` processes
the current backlog and exits (otherwise it polls every `--interval` seconds until Ctrl-C).

Reads stdin / writes stdout with `--format`/`--quiet`; exit codes follow the §I contract.
Tests: `pytest cli -q`.
