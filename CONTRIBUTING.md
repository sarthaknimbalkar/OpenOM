# Contributing to OpenOM

Thanks for helping build the standard. A few rules keep it trustworthy.

## The non-negotiables

1. **Deterministic core.** Never add an LLM, inference, or network client to `core/`, `mcp/`,
   or consumer-mode `js/`. CI's `boundary` job enforces this — a leaked dependency fails the
   build. Inference belongs only in the client-side authoring layer.
2. **The spec is the product.** Changes under `spec/` (schema, `@context`, vectors) are
   contract changes. Every payload-shape change bumps the version and updates the changelog.
   Regenerating vectors (`python core/scripts/gen_vectors.py`) MUST be a no-op — a diff means a
   canonical hash moved, which the `drift` job rejects.
3. **Cross-implementation fidelity.** `core` (Python) and `js` (TypeScript) must produce
   byte-identical JCS output. If you touch canonicalization, embedding, or the schema, run the
   cross-impl vectors on both sides.
4. **Assertions, not facts.** Tooling checks internal consistency only, never market truth.
   Schema errors block; consistency warnings never block.
5. **Never modify visual PDF content** without an explicit flag. Output PDFs are visually
   identical to their input.

## Setup

```bash
pip install -e "core[dev]" -e "cli[dev]"
pre-commit install
```

## The local gate (must pass before you push)

```bash
ruff check core/src core/tests core/scripts cli/src cli/tests
mypy core/src && mypy cli/src
pytest core -q --cov=openom_core --cov-fail-under=90
pytest cli  -q --cov=openom_cli  --cov-fail-under=90
python core/scripts/gen_vectors.py            # then: git diff --exit-code spec/vectors
```

## Testing philosophy

OpenOM is a deterministic library, so **tests run against real OM PDFs, not mocks.** Prefer
adding a fixture and a real round-trip over a mocked unit. Attack the messy cases: CMYK/SMask
images, flattened scans, empty payloads, hash mismatches, hostile rent schedules.

## Commits

- Small, [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`,
  `chore:`, `refactor:`, `spec:`.
- The message explains **why**, not just what.

## Code style

- **Python:** fully type-hinted, `mypy --strict`-clean, `ruff`-clean, deterministic pure
  functions where possible.
- **TypeScript:** strict mode, avoid `any`.
- Every source file carries an `SPDX-License-Identifier: MIT` header.
