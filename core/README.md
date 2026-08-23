# openom-core

The deterministic Python core of the [openOM](../README.md) standard: the PDF/data verbs
(`embed`, `read`, `inspect`, `extract`, `validate`) and RFC 8785 canonicalization + SHA-256
integrity. **Zero inference, ever** (CI's `boundary` job enforces it). Byte-parity with `js/`.

```sh
# From a clone (openom-core is not yet on PyPI):
pip install -e core                 # add the [dev] extra only to contribute
# Once published:  pip install openom-core
```

```python
from openom_core.embed import embed, read
out = embed(pdf_bytes, payload, asserted_date="2026-08-16")   # non-destructive
r = read(out)                                                 # r.present / r.hash_valid / r.payload
```

Entrypoints: `openom_core.{canonical,embed,validate,inspect,images,text,schema,xmp}`.
Tests: `pytest core -q --cov=openom_core --cov-fail-under=90`. Schema + vectors live in [`/spec`](../spec).
