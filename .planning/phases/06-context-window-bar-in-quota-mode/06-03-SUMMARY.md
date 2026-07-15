---
phase: 06-context-window-bar-in-quota-mode
plan: 03
subsystem: ui
tags: [rendering, status-line, context-window, preview]

# Dependency graph
requires:
  - phase: 06-context-window-bar-in-quota-mode (plan 01)
    provides: show_context config field (StatusbarConfig, config show)
  - phase: 06-context-window-bar-in-quota-mode (plan 02)
    provides: show_context kwarg on format_status_line / render_classic / render_capsule / render_hairline
provides:
  - "core.main() gates the (used/size) model suffix on cfg.show_context in the official-quota and waiting branches, and passes show_context=cfg.show_context into every _render_style call (official, waiting, no-quota)"
  - "preview.py threads show_context through _real_data/_demo_data (suffix gating) and run() (config-default resolution + ctx_pct/show_context passthrough into render())"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "preview.py mirrors core.py's suffix-gating logic exactly (same guard, same strip-then-conditionally-append shape) so `cs preview` is a faithful preview of the live status line"

key-files:
  created:
    - tests/test_core_context_bar.py
    - tests/test_preview_context.py
  modified:
    - src/claude_statusbar/core.py
    - src/claude_statusbar/preview.py
    - tests/test_no_quota_integration.py
    - tests/test_preview.py

key-decisions:
  - "Pinned show_context=False in tests/test_no_quota_integration.py's config fixture rather than leaving it unset. That suite tests the quota/no-quota env-switch and predates the toggle being wired to core.py; since show_context now defaults to True (from plan 06-01) and is live (this plan), its pre-existing 'ctx[ not in out' assertions on the quota layout would otherwise fail — not because of a bug, but because the toggle's new default-on behavior is exactly what this plan intentionally ships. Pinning the toggle off keeps that file's tests isolated to the concern they were written for."
  - "Drove the core.py seam tests end-to-end (real stdin + real on-disk config via HOME/CONFIG_PATH monkeypatch) rather than mocking styles.render as a capture stub, matching the established tests/test_no_quota_integration.py pattern already in the repo. This exercises the actual wiring (cfg load -> branch dispatch -> render) instead of a mocked internal seam, at the cost of asserting on rendered text substrings ('ctx[', '/1.0M)') instead of captured kwargs."
  - "_demo_data() now uses 520.0k/1.0M (~52%) instead of the old hardcoded 45.0k/1.0M, per the plan's 'pick coherent demo numbers (~52% of a 1M window)' guidance, so the demo bar and the demo suffix (when shown instead) reflect the same used/size figures."

requirements-completed: [CTX-01, CTX-03]

coverage:
  - id: D1
    description: "core.main()'s official-quota branch stops appending the (used/size) model suffix and passes show_context=cfg.show_context into _render_style when show_context is on; off reproduces today's suffix + no bar."
    requirement: "CTX-01, CTX-03"
    verification:
      - kind: unit
        ref: "tests/test_core_context_bar.py#test_official_show_context_on_drops_suffix_and_shows_bar"
        status: pass
      - kind: unit
        ref: "tests/test_core_context_bar.py#test_official_show_context_off_keeps_suffix_no_bar"
        status: pass
    human_judgment: false
  - id: D2
    description: "core.main()'s waiting (session-start) branch is gated identically to the official-quota branch."
    requirement: "CTX-01, CTX-03"
    verification:
      - kind: unit
        ref: "tests/test_core_context_bar.py#test_waiting_show_context_on_drops_suffix_and_shows_bar"
        status: pass
      - kind: unit
        ref: "tests/test_core_context_bar.py#test_waiting_show_context_off_keeps_suffix_no_bar"
        status: pass
    human_judgment: false
  - id: D3
    description: "preview.py mirrors the same gating: show_context on/off toggles the ctx bar vs the suffix, and an unset show_context resolves from load_config()."
    requirement: "CTX-01, CTX-03"
    verification:
      - kind: unit
        ref: "tests/test_preview_context.py#test_preview_context_on_shows_ctx_bar_no_suffix"
        status: pass
      - kind: unit
        ref: "tests/test_preview_context.py#test_preview_context_off_keeps_suffix_no_bar"
        status: pass
      - kind: unit
        ref: "tests/test_preview_context.py#test_preview_defaults_to_config"
        status: pass
    human_judgment: false
  - id: D4
    description: "cs preview manual check: show_context on renders the ctx bar between 7d and model with no suffix; off renders the suffix with no bar."
    requirement: "CTX-01, CTX-03"
    verification:
      - kind: manual
        ref: "cs preview --no-color --style classic --theme graphite with show_context true/false in ~/.claude/claude-statusbar.json"
        status: pass
    human_judgment: true

duration: 35min
completed: 2026-07-15
status: complete
---

# Phase 6 Plan 3: core.py + preview.py show_context wiring Summary

**Wired the show_context toggle (06-01) and the per-style ctx renderers (06-02) into core.main()'s official-quota and waiting branches — dropping the model's `(used/size)` suffix and passing `show_context=cfg.show_context` into every render call — and mirrored the identical gating in preview.py so `cs preview` shows exactly what the live status line will show.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-07-15 (approx, continuing from 06-02)
- **Completed:** 2026-07-15T13:15:39+08:00
- **Tasks:** 2
- **Files modified:** 4 (+2 test files created)

## Accomplishments

- `core.main()`'s official-quota branch (`ctx_size > 0` block, ~1383): the `(… context)` descriptor strip stays unconditional, but the `(used/size)` suffix append now runs only `if not cfg.show_context`.
- `core.main()`'s waiting branch (`_has_stdin` block, ~1469): identical gating applied.
- `show_context=cfg.show_context` added to all three `_render_style(...)` calls in `core.main()` — official-quota, waiting, and no-quota (the last one is a no-op today since `no_quota=True` already draws the bar unconditionally; added for uniformity per the plan's discretion note).
- `preview.py`: `_real_data(show_context)` and `_demo_data(show_context)` gate their independently-built model suffix the same way, and both now compute and return `ctx_pct` (previously never computed/passed, so the bar could never render even after 06-02's renderer support landed).
- `_demo_data()` switched from the arbitrary `45.0k/1.0M` demo figure to `520.0k/1.0M` (~52%) so the demo bar's percentage and the demo suffix (when shown instead) are numerically consistent.
- `preview.run()` gained `show_context: Optional[bool] = None`; when unset it resolves `load_config().show_context`, so `cs preview` (no CLI flag needed) reflects the user's persisted setting exactly like the live status line does. Both `render()` call sites (theme-agnostic and per-theme) now receive `ctx_pct=` and `show_context=`.
- Manually verified end-to-end: `cs preview --style classic --theme graphite` with `show_context: true` in config renders `ctx[███52%░░░░] | Opus 4.7` (no suffix); with `show_context: false` it renders `Opus 4.7(520.0k/1.0M)` (no bar) — matching the design spec's before/after exactly.

## Task Commits

Both tasks followed RED → GREEN (TDD):

1. **Task 1 RED:** `12d3f1c` (test) — `tests/test_core_context_bar.py`, 4 seam tests driving `core.main()` end-to-end for the official and waiting branches; confirmed failing before any core.py change.
2. **Task 1 GREEN:** `42bd7d0` (feat) — suffix gating + `show_context` passthrough in core.py's three render branches; also fixed `tests/test_no_quota_integration.py`'s config fixture (pinned `show_context: False`) so that unrelated env-switch suite stays isolated from the newly-live default-on toggle.
3. **Task 2 RED:** `63c6934` (test) — `tests/test_preview_context.py`, 3 tests for preview's suffix gating and config-default resolution; confirmed failing (`preview.run()` didn't accept `show_context` yet).
4. **Task 2 GREEN:** `114d5de` (feat) — `show_context` threading + `ctx_pct` computation in preview.py; fixed a pre-existing monkeypatch lambda signature in `tests/test_preview.py` that the new `_real_data(show_context)` parameter broke.

## Files Created/Modified

- `tests/test_core_context_bar.py` (new) — 4 end-to-end tests: official-quota and waiting branches × show_context on/off, driven via real stdin + on-disk config (mirrors the existing `test_no_quota_integration.py` harness pattern).
- `tests/test_preview_context.py` (new) — 3 tests: preview show_context on/off, and defaulting from `load_config()`. Includes an autouse fixture pointing `CACHED_STDIN` at a nonexistent path so the tests don't pick up the developer machine's real `~/.cache/claude-statusbar/last_stdin.json`.
- `src/claude_statusbar/core.py` — suffix-append gated by `if not cfg.show_context:` in the official-quota and waiting branches; `show_context=cfg.show_context` added to all three `_render_style` calls.
- `src/claude_statusbar/preview.py` — `_real_data`/`_demo_data` take `show_context`, gate the suffix, compute+return `ctx_pct`; `run()` resolves `show_context` from config when unset and forwards `ctx_pct=`/`show_context=` into both `render()` calls.
- `tests/test_no_quota_integration.py` — pinned `show_context: False` in the shared config fixture (deviation, see below).
- `tests/test_preview.py` — fixed a monkeypatch lambda's signature to accept the new `show_context` positional arg on `_real_data` (deviation, see below).

## Decisions Made

- See `key-decisions` in frontmatter: pinned `show_context=False` in `test_no_quota_integration.py`'s fixture; drove core seam tests end-to-end rather than mocking `styles.render`; picked `520.0k/1.0M` (~52%) as the new demo figure.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test bug exposed by newly-live default] `tests/test_no_quota_integration.py` broke once `show_context` was actually wired**
- **Found during:** Task 1, running the plan's required regression suite (`test_core_ctx_pct.py tests/test_ctx_env_override.py tests/test_quota_stale.py tests/test_no_quota_integration.py`).
- **Issue:** `show_context` defaults to `True` (LOCKED in plan 06-01/06-CONTEXT.md), but before this plan the config value had zero effect on `core.main()`. Once wired, 6 of `test_no_quota_integration.py`'s tests — which assert `"ctx[" not in out` for the *quota* layout while testing an unrelated concern (the relay/official env-switch) — started failing because the quota layout now legitimately shows the ctx bar by default.
- **Fix:** Added `"show_context": False` to that file's shared `_write_config()` base dict, isolating the env-switch tests from this plan's (separately and directly tested) toggle. Verified this doesn't affect any of that file's `"ctx[" in out` assertions for the no-quota layout, since the no-quota branch draws its bar unconditionally (`no_quota=True`) regardless of `show_context`.
- **Files modified:** `tests/test_no_quota_integration.py`
- **Commit:** `42bd7d0`

**2. [Rule 1 - Bug] `tests/test_preview.py`'s `_real_data` monkeypatch lambda broke on the new parameter**
- **Found during:** Task 2, running `python -m pytest tests/test_preview.py -q` as required by the plan's acceptance criteria.
- **Issue:** `test_preview_classic_varies_by_theme` monkeypatches `preview._real_data` with `lambda: None` to force demo data. `_real_data` now takes a `show_context` positional/keyword argument, so `preview.run()`'s new `_real_data(show_context)` call raised `TypeError: takes 0 positional arguments but 1 was given`.
- **Fix:** Changed the lambda to `lambda show_context=False: None`.
- **Files modified:** `tests/test_preview.py`
- **Commit:** `114d5de`

## Issues Encountered

None beyond the two auto-fixed test-signature issues above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- CTX-01 and CTX-03 are now fully closed end-to-end: the ctx bar appears in real quota-mode renders (official + waiting), and the `show_context` toggle controls it with byte-for-byte-unchanged off behavior.
- `cs config set show_context on|off` (06-01) + `cs preview` (this plan) + the live status line (this plan) are all consistent.
- Full test suite: 936 passed (up from 929 at the start of phase 06, +7 net across this plan's two new files after accounting for the 2 pre-existing tests that needed signature/fixture fixes).
- No blockers for closing phase 06.

---
*Phase: 06-context-window-bar-in-quota-mode*
*Completed: 2026-07-15*

## Self-Check: PASSED
