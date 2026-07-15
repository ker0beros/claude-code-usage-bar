# Ingest Synthesis Summary

Mode: new (bootstrap). Only `.planning/codebase/` existed prior; no existing PROJECT.md /
REQUIREMENTS.md / ROADMAP.md / CONTEXT.md to reconcile against.

This is the entry point for `gsd-roadmapper`.

## Doc counts by type

- Total classified: 16
- ADR: 0
- SPEC: 8
- PRD: 0
- DOC: 8
- UNKNOWN: 0

## Decisions locked

- 0 (no ADR documents in the ingest set → `decisions.md` records none)

## Requirements extracted

- 0 (no PRD documents → `requirements.md` records none; no REQ-* IDs; no competing variants)

## Constraints (8, all from SPECs)

- nfr (5): Rate-Limit Focused Status Bar Redesign; Per-segment color management + classic
  theme adoption; Project + branch identity segment; Rate-limit forecast chip (⚠~ETA);
  Context window as a bar in quota mode
- schema (3): Rate-limit projection model (→NN% design); Rate-limit Projection Model
  implementation contract; Burn-Rate Regime Detection
- Sources: docs/superpowers/specs/*.md + one .html (burn-regime) + one plan file classified
  SPEC (projection-model)

## Context topics (8, from DOCs)

- 4 implementation plans (each paired to a SPEC): rate-limit redesign, per-segment color,
  project+branch segment, rate-limit forecast
- 4 marketing / distribution / upstream materials: launch kit, HN prepared answers, Anthropic
  marketplace submission, upstream focused-subagent FR

## Cross-reference graph

- Cycle detection: run (DFS three-color), max depth well under the 50 cap.
- Result: acyclic. The four plan→spec edges are one-directional; all remaining cross_refs
  point to external URLs or source/test files outside the ingest set.

## Conflicts

- Blockers: 0
- Competing variants: 0
- Auto-resolved: 0
- Info: 2 (rate-limit forecast/projection scope overlap resolved by in-source coexistence;
  context readout evolution across two same-precedence SPECs)
- Detail: see .planning/INGEST-CONFLICTS.md

## Per-type intel files

- .planning/intel/decisions.md    (ADRs — none)
- .planning/intel/requirements.md (PRDs — none)
- .planning/intel/constraints.md  (8 SPEC constraints)
- .planning/intel/context.md      (8 DOC topics)

## Status

READY — no blockers, no competing variants. Safe to route to gsd-roadmapper. The two INFO
notes are transparency flags, not gates: the roadmapper should treat forecast (⚠~ETA) and
projection (→NN%) as complementary features on a shared predict.py, and treat the July
context-bar design as the current intent for the context readout.
