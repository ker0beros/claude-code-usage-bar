## Conflict Detection Report

### BLOCKERS (0)

None. No LOCKED ADRs (no ADRs at all), so no LOCKED-vs-LOCKED contradictions. No cross-ref
cycles (the four plan→spec references form a DAG; all other refs point to external URLs or
code files outside the ingest set). No UNKNOWN / low-confidence classifications.

### WARNINGS (0)

None. No PRD-classified documents, so no competing acceptance-criteria variants. No
cross-precedence contradictions requiring user resolution.

### INFO (2)

[INFO] Overlapping rate-limit-prediction scope — resolved in-source by explicit coexistence
  Found: docs/superpowers/specs/2026-06-02-rate-limit-forecast-design.md defines the at-risk
    ⚠~ETA chip (time-to-limit, shown only when at-risk); docs/superpowers/specs/2026-06-02-
    rate-limit-projection-learning-design.md defines the always-on →NN% projection over the
    same 5h/7d windows.
  Note: Not a contradiction — the projection design's non-goals explicitly state "do NOT make
    the ⚠~ETA warning chip the projection model" and require explicit coexistence. Both are
    same-precedence SPECs and both extend predict.py; no auto-resolution applied. Flagged so
    the roadmapper sequences them as complementary features sharing one module.

[INFO] Context readout evolution across two same-precedence SPECs
  Found: docs/superpowers/specs/2026-03-25-rate-limit-focused-redesign.md de-emphasizes the
    context window ("context window % ... is noise") when introducing the rate-limit-focused
    bar; docs/superpowers/specs/2026-07-15-context-bar-quota-mode-design.md later re-introduces
    context as a dedicated bar segment in quota mode (behind a default-on show_context toggle).
  Note: Both are same-precedence SPECs (precedence engine does not auto-resolve by date), and
    they are not strictly contradictory — the later design adds an opt-out bar rather than the
    original always-on numeric noise. Flagged for roadmapper awareness so the newer context-bar
    behavior is treated as the current intent.
