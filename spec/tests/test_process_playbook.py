"""[Ma8/Ma1] Drift-lock the /process playbook against the real tool surface + safety controls,
so a future edit can't reintroduce the mis-calls (om_embed/om_validate) or drop the injection
fence the AI-builder audit found. The playbook is committed product an agent executes."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROCESS = ROOT / "process"
PLAYBOOK = ["SKILL.md", "agent-instructions.md", "mapping-guide.md"]
ALL_DOCS = PLAYBOOK + ["example/transcript.md"]


def _text(name: str) -> str:
    return (PROCESS / name).read_text(encoding="utf-8")


def test_no_om_embed_assertedDate_argument() -> None:
    # om_embed(pdf, payload[, outPath, badge, sourceDocHash]) - assertedDate is a PAYLOAD field.
    bad = re.compile(r"om_embed\([^)]*assertedDate")
    offenders = [d for d in ALL_DOCS if bad.search(_text(d))]
    assert not offenders, f"om_embed called with an assertedDate argument in: {offenders}"


def test_no_om_validate_schema_argument() -> None:
    # om_validate(payload[, tolerances]) - there is no schema parameter (schema is built in).
    bad = re.compile(r"om_validate\([^)]*schema")
    offenders = [d for d in ALL_DOCS if bad.search(_text(d))]
    assert not offenders, f"om_validate called with a schema argument in: {offenders}"


def test_injection_fence_present_in_every_playbook_file() -> None:
    # Each agent-facing playbook file MUST mark OM content as untrusted data, not commands.
    for name in PLAYBOOK:
        assert "untrusted" in _text(name).lower(), f"{name}: no untrusted-content fence"


def test_no_payloadPresent_misname() -> None:
    # [Mi18] om_inspect returns payload.present, not a top-level payloadPresent.
    offenders = [d for d in ALL_DOCS if "payloadPresent" in _text(d)]
    assert not offenders, f"stale om_inspect field name 'payloadPresent' in: {offenders}"
