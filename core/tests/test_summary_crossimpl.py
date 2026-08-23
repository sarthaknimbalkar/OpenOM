"""[Mi22] summarize_deal (Python) MUST be byte-identical to summarizeDeal (/js) — the cross-impl
parity vector. Runs the JS view via node against the SAME payloads and diffs the JSON. Skips when
node or the built js/dist is unavailable (it runs in the cross-impl CI job, which builds js)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from openom_core import summarize_deal

ROOT = Path(__file__).resolve().parents[2]
JS_SUMMARY = ROOT / "js" / "dist" / "src" / "summary.js"

pytestmark = pytest.mark.cross_impl

_CASES = [
    {"deal": {"askingPrice": 1850000, "capRate": 0.0625, "noi": 115625, "noiType": "in-place"}},
    {"currency": "EUR", "deal": {"askingPrice": 1000000, "pricePerSF": 12.7}},
    {"property": {"propertyType": "retail", "buildingSF": 9100}, "assertedDate": "2026-01-01"},
    {},  # null-safe
]


def _js_summary(payload: dict) -> dict:
    src = JS_SUMMARY.as_uri()  # file:// URL — required by the Node ESM loader on Windows
    code = (
        f"import {{ summarizeDeal }} from '{src}';"
        "let d='';process.stdin.on('data',c=>d+=c).on('end',()=>"
        "process.stdout.write(JSON.stringify(summarizeDeal(JSON.parse(d)))));"
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", code],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
@pytest.mark.skipif(not JS_SUMMARY.exists(), reason="js not built (run: npm --prefix js run build)")
def test_summary_is_byte_identical_across_impls() -> None:
    for payload in _CASES:
        assert summarize_deal(payload) == _js_summary(payload), payload
