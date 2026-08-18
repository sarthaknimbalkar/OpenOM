# openOM extraction playbook (/process)

The authoring playbook that drives `om_inspect → extract → map → om_validate → review → om_embed`.
No code; inference lives ONLY in the agent's mapping step — every `om_*` tool stays deterministic.

- `SKILL.md` — Claude-invocable `openom-author` skill.
- `agent-instructions.md` — the same substance for any MCP client.
- `mapping-guide.md` — field map, vocabularies, consistency relationships, ambiguity rules
  (omit-and-flag, never guess). Drift-locked to the schema + validator.
- `review-contract.md` — the human review/assertion gate contract.
- `example/` — a worked synthetic run (OM → payload → transcript), gated in CI.
