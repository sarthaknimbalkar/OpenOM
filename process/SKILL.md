---
name: openom-author
description: Drive an offering-memorandum (OM) PDF to a reviewed, embedded openOM payload using the deterministic openOM MCP tools — inspect, extract, map, validate, human-review, embed. Use when a broker wants to author/attach an openOM data payload to an OM, or reprice an already-embedded one.
---

# openOM author

Announce: "I'm using the openom-author skill to author an openOM payload."

Turn an OM PDF into a reviewed, embedded openOM 0.1 payload. You supply the reading and mapping
(inference); every `om_*` tool you call is deterministic and holds no model. Field detail —
paths, enums, units, provenance, the consistency relationships — is in
[`./mapping-guide.md`](./mapping-guide.md); read it before mapping. This skill is the Claude wrapper
of the client-agnostic [`./agent-instructions.md`](./agent-instructions.md); the steps are the same.

## The loop

1. **Classify** — `om_inspect(pdf)`: note `class`, `pages`, `textCoverage`, `payloadPresent`
   (present ⇒ this is a reprice re-embed; capture the prior hash for `meta.supersedes`). If
   `class` is `scanned`, read the pages with your own vision.
2. **Gather** — `om_extract_text(pdf, pageRange, cursor)`, paging via `nextCursor` until complete;
   `om_extract_images(pdf)` for context. Capture the rent schedule, deal terms, lease abstract,
   property details.
3. **Map** — build the payload per `mapping-guide.md`: correct paths/enums/units, `capRate` as a
   decimal fraction, money in major units, ISO dates, each rent period `source: "extracted"`.
   **Omit any field the OM does not state — never invent.**
4. **Validate & iterate** — `om_validate(payload, schema)`: fix every `OMV-E###`; treat every
   `OMW-W###` as evidence your extraction is wrong and re-read the source — never silence a warning.
   Loop until schema-clean and warning-clean (or the residual is explained at review).
5. **Human review gate** — the assertion moment. **Do not self-assert.** Present exactly what
   [`./review-contract.md`](./review-contract.md) requires (per-field value + source evidence +
   `source` tag, omissions, residual warnings, and a reprice diff when re-embedding), and wait for
   the human's approval.
6. **Assert & embed** — on approval: set `assertedBy` to the reviewing broker, set `assertedDate`
   (today), confirm `noiType`/`noiAsOfDate`, promote each rent period `source` `"extracted"` →
   `"asserted"`, then `om_embed(pdf, payload, assertedDate)` (reprice ⇒ set `meta.supersedes`).

## Rules

- Assertions, not facts: transcribe what the OM states; never appraise, compute market truth, or
  guess. Never invent; omit the unknown.
- Unreviewed extraction is at most `source: "extracted"`, never `"verified"` ([OM-SCOPE-007]).
- No valuation/investment/legal advice. No chat-UI puppeteering — MCP connector / on-device /
  manual paths only.
- The review gate is the assertion moment (§7a, [OM-EXTP-003]); extraction output is a draft until
  a human approves it.
