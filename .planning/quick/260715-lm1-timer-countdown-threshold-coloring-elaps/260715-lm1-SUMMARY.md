---
phase: 260715-lm1-timer-countdown-threshold-coloring-elaps
plan: 01
subsystem: ui
tags: [status-line, coloring, ansi, timer, thresholds]

requires:
  - phase: 260715-jbf-projection-off-and-standardize-threshold
    provides: The 65/85 unified color band + severity-helper pattern this task mirrors for the timer's own fixed band.
provides:
  - "⏰ 5h/7d countdown text colors by elapsed% of its own window on a fixed 65/85 band, independent of the bar's severity color"
  - "One shared helper (timer_severity_rgb) reused by classic, capsule, hairline, and cs preview"
affects: [status-line, preview, config-thresholds]

tech-stack:
  added: []
  patterns:
    - "timer_severity_rgb(elapsed_pct, *, flip, theme) — fixed-cutoff severity helper mirroring window_severity_rgb's shape but reading module-level TIMER_* constants instead of the caller-configurable warning/critical_threshold, guaranteeing the timer band can never be retuned by bar config."

key-files:
  created:
    - tests/test_timer_coloring.py
  modified:
    - src/claude_statusbar/progress.py
    - src/claude_statusbar/styles.py
    - src/claude_statusbar/core.py
    - src/claude_statusbar/preview.py
    - CHANGELOG.md

key-decisions:
  - "Timer band constants (TIMER_WARNING_THRESHOLD/TIMER_CRITICAL_THRESHOLD = 65.0/85.0) are fresh module-level values, NOT aliases of DEFAULT_WARNING_THRESHOLD/DEFAULT_CRITICAL_THRESHOLD — verified via inspect.signature that timer_severity_rgb takes no threshold parameters at all, so bar retuning can never leak into the timer band."
  - "core.py only threads timer_elapsed_5h/7d into the has_official quota branch's _render_style call; the waiting/stale/exception branches keep the renderer default of None so undefined windows fall back to the prior bar-inherited color rather than crash."
  - "hairline's reset-text color-wrap is NOT byte-identical to the prior string when elapsed is undefined (MUTE is re-applied via an extra RESET+MUTE pair rather than the original single wrap) — visually identical, verified by a dedicated equality test against the omitted-kwargs case."

patterns-established:
  - "Fixed-cutoff severity helper pattern: a helper that hardcodes its own threshold constants (never accepting them as parameters) is the correct shape when a signal must stay decoupled from a caller-configurable band, even when the numeric values happen to coincide today."

requirements-completed: [D-01, D-02, D-03]

coverage:
  - id: D1
    description: "5h ⏰ countdown text colors by elapsed% on a FLIPPED fixed 65/85 band (short countdown = green), decoupled from the 5h bar's severity color"
    requirement: "D-01"
    verification:
      - kind: unit
        ref: "tests/test_timer_coloring.py#test_timer_severity_rgb_5h_flipped_boundaries"
        status: pass
      - kind: unit
        ref: "tests/test_timer_coloring.py#test_timer_color_differs_from_bar_color_when_signals_disagree"
        status: pass
    human_judgment: false
  - id: D2
    description: "7d ⏰ countdown text colors by elapsed% on a NORMAL fixed 65/85 band (short countdown = red), decoupled from the 7d bar's severity color"
    requirement: "D-02"
    verification:
      - kind: unit
        ref: "tests/test_timer_coloring.py#test_timer_severity_rgb_7d_normal_boundaries"
        status: pass
      - kind: unit
        ref: "tests/test_timer_coloring.py#test_timer_color_differs_from_bar_color_7d"
        status: pass
    human_judgment: false
  - id: D3
    description: "classic, capsule, hairline, and cs preview render the countdown color identically for the same elapsed% via one shared helper"
    requirement: "D-02"
    verification:
      - kind: unit
        ref: "tests/test_timer_coloring.py#test_render_no_elapsed_never_crashes"
        status: pass
      - kind: manual_procedural
        ref: "uv run cs preview --style classic (manual spot-check during execution)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Timer band stays fixed at 65/85 even when the bar's configurable thresholds are customized; timer_severity_rgb exposes no threshold parameter"
    requirement: "D-03"
    verification:
      - kind: unit
        ref: "tests/test_timer_coloring.py#test_timer_color_ignores_customized_bar_thresholds"
        status: pass
      - kind: unit
        ref: "tests/test_timer_coloring.py#test_timer_severity_rgb_signature_has_no_threshold_params"
        status: pass
    human_judgment: false
  - id: D5
    description: "Edge cases (absent resets_at, undefined windows, negative/stale remaining) never crash and clamp/fall back correctly"
    verification:
      - kind: unit
        ref: "tests/test_timer_coloring.py#test_timer_elapsed_pct_negative_remaining_clamps_to_100"
        status: pass
      - kind: unit
        ref: "tests/test_timer_coloring.py#test_render_absent_reset_never_crashes"
        status: pass
    human_judgment: false
  - id: D6
    description: "Full existing suite stays green with no regressions and no tests removed"
    verification:
      - kind: unit
        ref: "uv run --with pytest -m pytest -q (969/970 passed; 1 pre-existing unrelated failure, see Deviations)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-07-15
status: complete
---

# Quick Task 260715-lm1: Timer Countdown Threshold Coloring Summary

**Reset-timer countdowns (`⏰`) now color by elapsed% of their own window on a fixed 65/85 band via one shared `timer_severity_rgb` helper — 5h flipped green-when-fresh, 7d normal red-when-late — fully decoupled from the bar's configurable severity thresholds.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 3
- **Files modified:** 5 (4 source + CHANGELOG.md), 1 file created (tests/test_timer_coloring.py)

## Accomplishments
- Added `timer_elapsed_pct()` and `timer_severity_rgb()` to `progress.py`, banded on fresh module-level `TIMER_WARNING_THRESHOLD`/`TIMER_CRITICAL_THRESHOLD` (65.0/85.0) that are never aliased to the bar's configurable `DEFAULT_WARNING_THRESHOLD`/`DEFAULT_CRITICAL_THRESHOLD`.
- Classic style's `format_status_line` colors the 5h/7d `⏰` text via the new helper, falling back to the prior bar-inherited color (`color_5h`/`color_7d`) when elapsed is undefined.
- Threaded `timer_elapsed_5h`/`timer_elapsed_7d` through `core.py` (has_official quota branch only), `render_capsule`, `render_hairline`, and `preview.py` so all three styles plus `cs preview` render the countdown color identically for the same elapsed%.
- `tests/test_timer_coloring.py` (34 tests): boundary checks at 64/65/84/85/86 for both flipped and normal mappings, elapsed% clamp/None cases, independence from the bar's customizable thresholds, signal-separation cases where timer color diverges from bar color, and crash-free edge-case fallbacks across all three styles.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add fixed-cutoff timer band helpers and color the classic ⏰ timer** - `b28e836` (feat)
2. **Task 2: Thread elapsed% through core, all styles, and preview** - `c2427d5` (feat)
3. **Task 3: Tests for boundaries, threshold independence, and edge-case fallbacks** - `79bcd6d` (test)

## Files Created/Modified
- `src/claude_statusbar/progress.py` — `TIMER_WARNING_THRESHOLD`/`TIMER_CRITICAL_THRESHOLD`/`TIMER_5H_WINDOW_S`/`TIMER_7D_WINDOW_S` constants, `timer_elapsed_pct()`, `timer_severity_rgb()`, and `format_status_line` wired to color the classic ⏰ text
- `src/claude_statusbar/styles.py` — `render_classic` forwards timer kwargs; `render_capsule`/`render_hairline` color their reset text via `timer_severity_rgb`
- `src/claude_statusbar/core.py` — computes `timer_elapsed_5h`/`timer_elapsed_7d` in the `has_official` quota branch and threads them into `_render_style`
- `src/claude_statusbar/preview.py` — computes elapsed% from cached `resets_at` (mirroring core's live path) plus demo-data elapsed values, passed into every `render()` call
- `CHANGELOG.md` — Unreleased entry noting the new elapsed%-driven timer coloring
- `tests/test_timer_coloring.py` — new test file (34 tests)

## Decisions Made
- Timer band constants deliberately duplicated (not aliased) from the bar's `DEFAULT_*` constants, per the LOCKED "config coupling" decision (D-03) — verified structurally via `inspect.signature(timer_severity_rgb)` showing no threshold parameters exist to leak the bar's config through.
- `core.py`'s waiting/stale/exception `_render_style` call sites intentionally do NOT receive `timer_elapsed_5h`/`7d` kwargs — those branches have no rolling window to band on, so the renderer's own `None` default correctly falls back to prior coloring (D-01 edge case), matching the plan's explicit exclusion list.
- hairline's reset-text color-wrap emits an extra `RESET`+`MUTE` pair around the reset value even when elapsed is undefined, rather than reproducing the exact prior single-wrap bytes — visually identical (still MUTE), and proven equivalent to the omitted-kwargs baseline by a dedicated test rather than a byte-diff assertion.

## Deviations from Plan

### Auto-fixed Issues

None — all three tasks executed as specified in the plan; no Rule 1/2/3 fixes were required.

**Out-of-scope discovery (logged, not fixed):** `tests/test_version_sync.py::test_marketplace_and_plugin_versions_match_pyproject` fails on a pre-existing version drift (`.claude-plugin/marketplace.json` at `3.29.11` vs `pyproject.toml` at `3.30.0`) unrelated to this task. Confirmed failing identically on HEAD before any of this task's changes (verified via `git stash` + re-run). Logged to `deferred-items.md` per the SCOPE BOUNDARY rule — left unfixed as a release-time housekeeping item, not part of this task's file set.

---

**Total deviations:** 0 auto-fixed; 1 out-of-scope item deferred (pre-existing, unrelated).
**Impact on plan:** None — plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The timer-coloring feature is complete, tested, and verified against `cs preview` across all themes/styles.
- No blockers. The deferred `test_version_sync` drift should be resolved at the next release cut (bump `.claude-plugin/marketplace.json` to match `pyproject.toml`).

---
*Task: 260715-lm1-timer-countdown-threshold-coloring-elaps*
*Completed: 2026-07-15*

## Self-Check: PASSED

All 3 task commits (b28e836, c2427d5, 79bcd6d) verified present in git log.
All modified/created files verified present on disk: progress.py, styles.py,
core.py, preview.py, tests/test_timer_coloring.py, CHANGELOG.md, this SUMMARY,
and deferred-items.md.
