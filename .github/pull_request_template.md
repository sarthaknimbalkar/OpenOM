## What & why

<!-- What does this change do, and why? Link any issue. -->

## Checklist

- [ ] `ruff` + `mypy` clean (core & cli)
- [ ] `pytest` green with the coverage gate (`--cov-fail-under=90`)
- [ ] If canonicalization / schema / embedding changed: cross-impl vectors regenerated
      (`python core/scripts/gen_vectors.py`) and the diff is intentional
- [ ] No inference/network client added to `core/`, `mcp/`, or consumer-mode `js/`
- [ ] No visual PDF content modified without an explicit flag
- [ ] Spec changes bump the version + changelog
