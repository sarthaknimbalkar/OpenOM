# openom-cli

The `om` command over [`openom-core`](../core) — no UI, no inference; also the server-side path.

```sh
pip install openom-cli            # or, from a clone:  pip install -e "cli[dev]"

om inspect  offering.pdf
om embed    offering.pdf --payload deal.json --out out.pdf --asserted-date 2026-08-16
om read     out.pdf
om validate deal.json
om check    out.pdf               # consistency only
```

Reads stdin / writes stdout with `--format`/`--quiet`; exit codes follow the §I contract.
Tests: `pytest cli -q`.
