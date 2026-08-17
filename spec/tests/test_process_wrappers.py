"""M4 #60: keep the two playbook wrappers (SKILL.md for Claude, agent-instructions.md for any MCP
client) from drifting apart. Both MUST delegate field detail to the shared mapping-guide, name the
same deterministic tools, and state the load-bearing rules (review gate, never-invent). SKILL.md
must carry valid name/description frontmatter so it is invocable.
"""

from __future__ import annotations

import re
from pathlib import Path

PROC = Path(__file__).resolve().parents[2] / "process"
SKILL = (PROC / "SKILL.md").read_text(encoding="utf-8")
AGENT = (PROC / "agent-instructions.md").read_text(encoding="utf-8")
GUIDE = (PROC / "mapping-guide.md").read_text(encoding="utf-8")

TOOLS = ["om_inspect", "om_extract_text", "om_extract_images", "om_validate", "om_embed"]


def test_both_wrappers_delegate_to_the_mapping_guide() -> None:
    for name, text in (("SKILL.md", SKILL), ("agent-instructions.md", AGENT)):
        assert "mapping-guide.md" in text, f"{name} must reference the shared mapping guide"


def test_both_wrappers_name_the_same_tools() -> None:
    for name, text in (("SKILL.md", SKILL), ("agent-instructions.md", AGENT)):
        missing = [t for t in TOOLS if t not in text]
        assert not missing, f"{name} omits tools: {missing}"


def test_both_wrappers_state_the_review_gate_and_never_invent() -> None:
    for name, text in (("SKILL.md", SKILL), ("agent-instructions.md", AGENT)):
        low = text.lower()
        assert "review" in low, f"{name} must state the review gate"
        assert "never invent" in low, f"{name} must state the never-invent rule"


def test_skill_has_invocable_frontmatter() -> None:
    m = re.match(r"^---\n(.*?)\n---\n", SKILL, re.DOTALL)
    assert m, "SKILL.md needs YAML frontmatter"
    fm = m.group(1)
    assert re.search(r"^name:\s*openom-author\s*$", fm, re.MULTILINE)
    assert re.search(r"^description:\s*\S", fm, re.MULTILINE)


def test_mapping_guide_link_targets_exist() -> None:
    # every ./file.md linked from a wrapper actually exists (no dangling playbook links)
    for text in (SKILL, AGENT):
        for target in re.findall(r"\]\(\./([\w.-]+\.md)\)", text):
            assert (PROC / target).exists(), f"dangling link: {target}"
