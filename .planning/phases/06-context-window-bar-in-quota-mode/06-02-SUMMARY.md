---
phase: 06-context-window-bar-in-quota-mode
plan: 02
subsystem: ui
tags: [rendering, ansi, status-line, context-window]

# Dependency graph
requires:
  - phase: 06-context-window-bar-in-quota-mode (plan 01)
    provides: show_context config field (StatusbarConfig, config show)
provides:
  - "show_context kwarg on format_status_line (progress.py) and render_classic/render_capsule/render_hairline (styles.py)"
  - "quota-mode ctx[…]/CTX pill/ctx mini-bar segment inserted between 7d and model in each style, gated by show_context"
  - "model-neutralization when the ctx segment is drawn (classic/hairline neutral ink, capsule drops redundant context dot)"
  - "_context_dimension() (progress.py) and ctx_pill()/ctx_segment() (styles.py) as the single source of truth shared by quota and no-quota rendering"
affects: [06-context-window-bar-in-quota-mode plan 03 (core.py/preview.py wiring)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Renderer-level segment factored into a shared helper so quota-mode and no-quota-mode draw byte-identical output for the same input"

key-files:
  created:
    - tests/test_context_bar_render.py
  modified:
    - src/claude_statusbar/progress.py
    - src/claude_statusbar/styles.py

key-decisions:
  - "Factored the classic ctx[…] segment into module-level _context_dimension(), and the capsule/hairline segments into function-local ctx_pill()/ctx_segment() helpers, so no-quota mode and the new quota-mode insertion call the exact same code path — guarantees byte-identical output by construction rather than by parallel-maintained copies."
  - "Left the classic quota_stale sub-branch untouched (optional per 06-CONTEXT.md 'Claude's Discretion') — kept scope tight."

requirements-completed: [CTX-01, CTX-02]

coverage:
  - id: D1
    description: "Classic quota-mode line renders a ctx[…NN%…] bar between the 7d bar and the model when show_context is on; model goes neutral ink; severity uses the 70/85 context band, not the 5h/7d comfort band."
    requirement: "CTX-01, CTX-02"
    verification:
      - kind: unit
        ref: "tests/test_context_bar_render.py#test_classic_quota_ctx_bar_between_7d_and_model"
        status: pass
      - kind: unit
        ref: "tests/test_context_bar_render.py#test_classic_quota_ctx_severity_band"
        status: pass
      - kind: unit
        ref: "tests/test_context_bar_render.py#test_classic_quota_ctx_none_no_bar_model_neutral"
        status: pass
    human_judgment: false
  - id: D2
    description: "show_context off (renderer default False) leaves classic output byte-for-byte unchanged: no ctx segment, 5h/7d bars intact."
    requirement: "CTX-01"
    verification:
      - kind: unit
        ref: "tests/test_context_bar_render.py#test_classic_quota_ctx_off_unchanged"
        status: pass
    human_judgment: false
  - id: D3
    description: "Capsule renders a ⛁ CTX NN% ● pill after the 7D pill when show_context is on, and drops the model pill's redundant context dot; off is unchanged."
    requirement: "CTX-01"
    verification:
      - kind: unit
        ref: "tests/test_context_bar_render.py#test_capsule_quota_ctx_pill_after_7d"
        status: pass
      - kind: unit
        ref: "tests/test_context_bar_render.py#test_capsule_quota_ctx_off_unchanged"
        status: pass
    human_judgment: false
  - id: D4
    description: "Hairline renders a › ctx <mini3> NN% segment after the 7d segment when show_context is on, and neutralizes the model; off is unchanged."
    requirement: "CTX-01"
    verification:
      - kind: unit
        ref: "tests/test_context_bar_render.py#test_hairline_quota_ctx_segment_after_7d"
        status: pass
      - kind: unit
        ref: "tests/test_context_bar_render.py#test_hairline_quota_ctx_off_unchanged"
        status: pass
    human_judgment: false
  - id: D5
    description: "The quota-mode ctx segment is ANSI-stripped byte-identical to the no-quota ctx segment for the same ctx_pct, in all three styles."
    verification:
      - kind: unit
        ref: "tests/test_context_bar_render.py#test_quota_ctx_matches_no_quota_per_style"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-15
status: complete
---

# Phase 6 Plan 2: Quota-mode ctx bar renderers Summary

**`show_context` kwarg threaded through format_status_line/render_classic/render_capsule/render_hairline draws the existing no-quota ctx segment between the 7d segment and the model in quota mode, with the model going neutral once the bar carries severity.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-15T04:40:00Z (approx)
- **Completed:** 2026-07-15T05:05:01Z
- **Tasks:** 2
- **Files modified:** 2 (+1 test file created)

## Accomplishments
- Classic style: `show_context: bool = False` kwarg on `format_status_line`; the ctx[…] battery bar is inserted between `7d[…]` and the model when `show_context and ctx_pct is not None`, colored on `CONTEXT_WARNING_THRESHOLD`/`CONTEXT_CRITICAL_THRESHOLD` (70/85), with the model forced to neutral ink.
- Extracted `_context_dimension()` in `progress.py` as the single source of truth for the ctx[…] segment — used by both the existing no-quota branch and the new quota-mode insertion, so the two are byte-identical by construction (no parallel-maintained copies to drift).
- Capsule style: `⛁ CTX NN% ●` pill inserted after the 7D pill (or 5H when `show_weekly` is off); model pill's redundant context dot dropped once the CTX pill is shown. Factored into a local `ctx_pill()` helper shared with the no-quota branch.
- Hairline style: `› ctx <mini3> NN%` segment inserted after the 7d segment (or 5h); model goes neutral ink once the ctx segment is shown. Factored into a local `ctx_segment()` helper shared with the no-quota branch.
- `render_classic` threads `show_context` through to `format_status_line`.
- All three styles verified byte-identical (ANSI-stripped) between quota-mode (`show_context=True`) and no-quota-mode (`no_quota=True`) for the same `ctx_pct=52`.
- `show_context` off (the default) leaves all existing output unchanged — verified for classic, capsule, and hairline.

## Task Commits

Each task followed RED → GREEN (TDD):

1. **Test file (RED gate, both tasks' tests):** `55a63e8` (test) — added 9 failing/mixed render tests in `tests/test_context_bar_render.py`
2. **Task 1: Classic — ctx bar in format_status_line quota branch** — `88fa7fa` (feat)
3. **Task 2: Capsule + hairline + classic wrapper — thread show_context** — `7fd3cf4` (feat)

**Plan metadata:** (this commit) `docs(06-02): complete quota-mode ctx bar renderers plan`

_Note: both tasks' tests were authored together in one RED commit, then implemented as two separate GREEN commits (Task 1, Task 2) — the RED→GREEN gate sequence per task is: test file commit precedes both feat commits, and each feat commit's tests were verified red beforehand (`pytest -k classic` for Task 1; full file for Task 2) before implementing._

## Files Created/Modified
- `tests/test_context_bar_render.py` - new render-test suite: classic/capsule/hairline quota-mode ctx segment placement, severity band, off-unchanged, and quota/no-quota parity across all three styles
- `src/claude_statusbar/progress.py` - `show_context` kwarg on `format_status_line`; `_context_dimension()` helper; ctx segment insertion + model neutralization in the main quota branch
- `src/claude_statusbar/styles.py` - `show_context` kwarg on `render_capsule`/`render_hairline`/`render_classic`; `ctx_pill()`/`ctx_segment()` local helpers; ctx segment insertion + model-dot/color neutralization in each style's quota branch

## Decisions Made
- Reused the plan's suggested "extract a tiny local helper" discretion point: `_context_dimension()` (module-level, progress.py) and `ctx_pill()`/`ctx_segment()` (function-local closures, styles.py) so quota-mode and no-quota-mode call the identical code path rather than two copies that could drift — this is what makes the byte-identical parity test (`test_quota_ctx_matches_no_quota_per_style`) hold by construction.
- Did not touch the classic `quota_stale` sub-branch — explicitly optional per 06-CONTEXT.md "Claude's Discretion", and out of scope for this plan's tight objective.

## Deviations from Plan

None - plan executed exactly as written. The test names in the delivered `tests/test_context_bar_render.py` match the plan's `<artifacts>` list exactly (`test_classic_quota_ctx_bar_between_7d_and_model`, `test_classic_quota_ctx_off_unchanged`, `test_classic_quota_ctx_severity_band`, `test_capsule_quota_ctx_pill_after_7d`, `test_hairline_quota_ctx_segment_after_7d`, `test_quota_ctx_matches_no_quota_per_style`), plus two extra edge-case tests (`test_classic_quota_ctx_none_no_bar_model_neutral`, `test_capsule_quota_ctx_off_unchanged`, `test_hairline_quota_ctx_off_unchanged`) covering the plan's explicitly-described edge cases and off-path regressions.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Renderers are ready for plan 06-03 (core.py official-quota + waiting branches must stop appending the `(used/size)` suffix when `cfg.show_context` is on, and pass `show_context=cfg.show_context` into `_render_style`; `preview.py` must thread `show_context` similarly).
- No blockers. `tests/test_context_bar_render.py`, `tests/test_styles.py`, `tests/test_no_quota_render.py`, `tests/test_progress.py`, `tests/test_quota_stale.py`, and the full suite (929 tests) all pass.

---
*Phase: 06-context-window-bar-in-quota-mode*
*Completed: 2026-07-15*

## Self-Check: PASSED

All created/modified files and all task commit hashes verified present on disk / in git log.
