# openom-cli

The `om` command over [`openom-core`](../core) - no UI, no inference; also the server-side path.

```sh
pip install openom-cli            # or, from a clone:  pip install -e "cli[dev]"

om inspect  offering.pdf
om embed    offering.pdf --payload deal.json --out out.pdf --asserted-date 2026-08-16
om read     out.pdf
om validate deal.json
om check    out.pdf               # consistency only
```

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
