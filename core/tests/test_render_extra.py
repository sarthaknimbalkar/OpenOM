"""[B1] openom-core is MIT-clean: embed / read / validate / canonical work with PyMuPDF (AGPL)
ABSENT - only extract / inspect / render + the signed-OM incremental path need the optional
[render] extra. Proven in a subprocess so blocking the import can't leak into the rest of the suite.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap


def test_core_embed_read_validate_without_pymupdf() -> None:
    code = textwrap.dedent(
        """
        import builtins
        _real = builtins.__import__
        def _guard(name, *a, **k):
            if name == "pymupdf" or name.startswith("pymupdf"):
                raise ImportError("pymupdf blocked for this test")
            return _real(name, *a, **k)
        builtins.__import__ = _guard

        import io, pikepdf, openom_core
        from openom_core.validate import validate

        p = pikepdf.new(); p.add_blank_page()
        buf = io.BytesIO(); p.save(buf)
        payload = {
            "@context": ["https://schema.org", "https://openom.app/ns/0.1"],
            "@type": "RealEstateListing", "assertedBy": {"broker": "X"},
            "assertedDate": "2026-08-24", "deal": {"status": "active"},
        }
        out = openom_core.embed(buf.getvalue(), payload, asserted_date="2026-08-24")
        r = openom_core.read(out)
        assert r.present and r.hash_valid, "embed/read failed without pymupdf"
        rep = validate(payload)  # runs the full schema+consistency validator with no pymupdf
        assert isinstance(rep.errors, list) and isinstance(rep.warnings, list)

        # extract/inspect must raise a CLEAR hint pointing at the [render] extra
        try:
            openom_core.extract_images(out)
            raise SystemExit("extract_images did not raise without pymupdf")
        except ImportError as e:
            assert "render" in str(e), f"unhelpful error: {e}"
        print("OK")
        """
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0 and "OK" in r.stdout, r.stderr or r.stdout
