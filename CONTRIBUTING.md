# Contributing to openOM

Thanks for helping build the standard. A few rules keep it trustworthy.

## The non-negotiables

1. **Deterministic core.** Never add an LLM, inference, or network client to `core/`, `mcp/`,
   or consumer-mode `js/`. CI's `boundary` job enforces this - a leaked dependency fails the
   build. Inference belongs only in the client-side authoring layer.
2. **The spec is the product.** Changes under `spec/` (schema, `@context`, vectors) are
   contract changes. Every payload-shape change bumps the version and updates the changelog.
   Regenerating vectors (`python core/scripts/gen_vectors.py`) MUST be a no-op - a diff means a
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

## Verification gates

CI (`.github/workflows/ci.yml`) is **manual** - it runs only when dispatched (`gh workflow run
ci.yml` or the Actions tab), not on push. Gates are verified **locally before pushing**; the
workflow reproduces them on demand.

### Deterministic gate (must pass before you push)

```bash
ruff check core/src core/tests core/scripts cli/src cli/tests mcp/src mcp/tests spec/tests spec/scripts
mypy core/src && mypy cli/src
pytest core -q --cov=openom_core --cov-fail-under=90
pytest cli  -q --cov=openom_cli  --cov-fail-under=90
pytest spec/tests -q                          # context/matrix/process/site drift + resolve-check
python core/scripts/gen_vectors.py            # then: git diff --exit-code spec/vectors
python core/scripts/gen_fuzz_corpus.py        # then: git diff --exit-code spec/vectors/fuzz
python spec/scripts/gen_site.py               # then: git diff --exit-code site
npm --prefix js ci && npm --prefix js run typecheck && npm --prefix js run lint && npm --prefix js run coverage
npm --prefix js run build:widget              # builds the badge + asserts inference-free
```

### Live extension gate (local/manual - #163)

Headed MV3 Chromium crashes deterministically under the GitHub-hosted xvfb runner, so this runs
**locally**, where it passes fully. It is the real proof of the extension (repo Rule 5 - no mocks):

```bash
npm --prefix extension run test:consumer      # headed Chromium: consumer + author + a11y + link-badger
npm --prefix extension run assert-no-inference
```

### Mutation testing (local/manual - #164)

Assertion-strength beyond coverage. Slow; run before a release. A surviving mutant (a flipped
comparison / wrong rounding no test catches) is real coverage debt - the class of bug that forks a
standard silently.

```bash
cd core && mutmut run && mutmut results        # Python core (Linux/macOS)
```

## Testing philosophy

openOM is a deterministic library, so **tests run against real OM PDFs, not mocks.** Prefer
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
