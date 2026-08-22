---
name: Spec change (RFC)
about: Propose a change to the openOM specification (schema, @context, vocabulary, codes)
title: "[RFC] <short title>"
labels: ["spec", "rfc"]
---

<!-- See GOVERNANCE.md. The spec is the product; changes are versioned and byte-parity across cores. -->

## Problem
<!-- What can't be expressed / verified today? Who hits it? -->

## Proposed change
<!-- The concrete schema / @context / vocabulary / code change. -->

## Backward compatibility
<!-- Is this additive (new optional field/term, relaxed constraint) or breaking? A breaking change
     needs a version bump (ns/0.2). Would any previously-valid payload become invalid? -->

- [ ] Additive / backward-compatible (fits within the current version)
- [ ] Breaking (requires a new version)

## Impact
<!-- Which of these need updating: JSON Schema · @context · samples · conformance vectors ·
     /core (Python) · /js (TypeScript) · validation codes · changelog. Byte-parity must hold. -->

## Migration
<!-- How do existing producers/consumers move? Anything the immutability rule affects? -->
