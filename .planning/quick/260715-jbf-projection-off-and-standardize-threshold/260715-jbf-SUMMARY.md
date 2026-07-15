---
phase: 260715-jbf-projection-off-and-standardize-threshold
plan: 01
subsystem: ui
tags: [config, progress-bar, statusline, thresholds, cli, docs]

requires: []
provides:
  - "show_forecast and show_projection default to False (config-only flip; predict.py and both toggles untouched)"
  - "Unified 65/85 color band across DEFAULT_WARNING/CRITICAL, PROJECTION_WARNING/CRITICAL, and CONTEXT_WARNING/CRITICAL thresholds in progress.py"
  - "styles.py/preview.py/cli.py out-of-band callers and help text aligned to 65/85"
  - "README.md and CHANGELOG.md updated for the new defaults and band"
affects: [progress-bar-rendering, statusline-cli, config]

tech-stack:
  added: []
  patterns:
    - "Defaults-only flip via dataclass default + from_dict fallback, no new gating logic"
    - "Single source of truth for severity bands: reuse _severity_color/color_for_percent/window_severity_rgb/normalize_thresholds, never duplicate coloring logic"

key-files:
  created: []
  modified:
    - src/claude_statusbar/config.py
    - src/claude_statusbar/progress.py
    - src/claude_statusbar/styles.py
    - src/claude_statusbar/preview.py
    - src/claude_statusbar/cli.py
    - tests/test_config_projection.py
    - tests/test_config_forecast.py
    - tests/test_threshold_resolution.py
    - tests/test_progress.py
    - tests/test_projection_coloring.py
    - tests/test_per_segment_colors.py
    - tests/test_config.py
    - tests/test_context_bar_render.py
    - tests/test_no_quota_render.py
    - README.md
    - CHANGELOG.md

key-decisions:
  - "D-01: show_forecast/show_projection default off via config dataclass + from_dict fallback only — no core.py gating changes, predict.py untouched"
  - "D-02: retuned the four progress.py band constants (DEFAULT_WARNING/CRITICAL, PROJECTION_WARNING, CONTEXT_WARNING) to 65/85; left the two *_CRITICAL constants already at 85, and BALANCE_*/_cache_severity untouched"
  - "D-03: mechanical signature/string default swaps in styles.py, preview.py, cli.py help text — no logic changes"
  - "D-04: reused existing severity helpers throughout; wrote no new coloring code"
  - "D-05: TDD — updated all test assertions to the new expected values first, confirmed RED against old source, then flipped source, confirmed GREEN"
  - "D-06: README/CHANGELOG updated to describe off-by-default projection/forecast and the unified 65/85 band; added a new CHANGELOG Unreleased entry rather than rewriting history"

patterns-established:
  - "Cross-field threshold validation tests (test_config.py) reworked around the new 65/85 defaults rather than just swapping numbers"

requirements-completed: [D-01, D-02, D-03, D-04, D-05, D-06]

coverage:
  - id: D1
    description: "show_projection and show_forecast default to False; absent config keys resolve to off; explicit set_and_load toggles unaffected"
    requirement: "D-01"
    verification:
      - kind: unit
        ref: "tests/test_config_projection.py#test_projection_default_off"
        status: pass
      - kind: unit
        ref: "tests/test_config_forecast.py#test_default_off"
        status: pass
    human_judgment: false
  - id: D2
    description: "All three usage bars (5h, 7d, ctx) share one 65/85 color band via progress.py's four constants; the two *_CRITICAL constants and BALANCE_*/_cache_severity are untouched"
    requirement: "D-02"
    verification:
      - kind: unit
        ref: "tests/test_progress.py, tests/test_threshold_resolution.py, tests/test_projection_coloring.py, tests/test_per_segment_colors.py, tests/test_config.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "Out-of-band callers (styles.py render_capsule/render_hairline/render_classic signature defaults, preview.py render() call sites) and cli.py --help text reflect 65/85"
    requirement: "D-03"
    verification:
      - kind: unit
        ref: "grep verification for warning_threshold=65.0/critical_threshold=85.0 in styles.py and preview.py; 'default: 65'/'default: 85' in cli.py; tests/test_context_bar_render.py, tests/test_no_quota_render.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "README.md and CHANGELOG.md reflect the off-by-default projection/forecast and the unified 65/85 band"
    requirement: "D-06"
    verification: []
    human_judgment: true
    rationale: "Documentation prose accuracy is a readability/correctness judgment call, not something a unit test can assert."

duration: ~20min
completed: 2026-07-15
status: complete
---

# Quick Task 260715-jbf: Projection/Forecast Default-Off + Threshold Standardization Summary

**Flipped show_projection/show_forecast to default-off and unified all three usage-bar color bands (5h/7d/ctx) onto a single green<65 / yellow 65-84 / red>=85 scale, reusing existing severity helpers with no new coloring logic.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-15T06:09:20Z
- **Tasks:** 3 (all `type="auto" tdd="true"` for Tasks 1-2, plain `type="auto"` for Task 3)
- **Files modified:** 16

## Accomplishments
- `StatusbarConfig().show_projection` and `.show_forecast` now default `False`; `load_config` on a config file missing either key resolves to `False`. `predict.py` and both `cs config set ... on/off` toggles remain fully intact.
- `progress.py`'s four usage-band constants (`DEFAULT_WARNING_THRESHOLD`, `DEFAULT_CRITICAL_THRESHOLD`, `PROJECTION_WARNING_THRESHOLD`, `CONTEXT_WARNING_THRESHOLD`) are now `65.0`/`85.0`, so the 5h/7d comfort band, the projection band, and the context band all read on one shared scale for the first time.
- Out-of-band callers (`styles.py`'s three `render_*` signature defaults, `preview.py`'s two `render()` call sites) and `cli.py`'s `--warning-threshold`/`--critical-threshold` help text now match the new 65/85 band.
- README.md and CHANGELOG.md updated: headline examples drop the (now off-by-default) `→NN%` chip, the `show_projection`/`show_forecast` config table rows document the off default with `on` opt-in, the 30%/70% and 70%/85% threshold prose is now 65%/85% everywhere, and a new CHANGELOG "Unreleased" entry documents both changes without rewriting history.

## Task Commits

Each task was committed atomically (RED → GREEN cycle where `tdd="true"`, single commit for Task 3):

1. **Task 1: Flip projection & forecast to default-off (config only)** - `3cd54f7` (feat) — RED confirmed against old `True` defaults, then flipped `config.py` dataclass defaults + `from_dict` fallbacks to `False`.
2. **Task 2: Standardize the four band constants to 65/85 + retune band tests** - `2b36824` (feat) — RED confirmed against old 30/70 and 70/85 bands across 5 test files, then retuned the four `progress.py` constants; reworked `test_config.py`'s cross-field validation sequences (not just numeric swaps) for the new defaults.
3. **Task 3: Align out-of-band caller/help defaults + docs** - `1dacffc` (docs) — mechanical signature/help-text swaps in `styles.py`/`preview.py`/`cli.py`, comment-only prose refreshes in two render tests (no assertion changes), and README/CHANGELOG updates.

**Plan metadata:** (not yet committed — see below)

_Note: Tasks 1-2 followed the plan's RED-then-GREEN TDD sequence exactly; both files' failing-test runs were confirmed before the source flip._

## Files Created/Modified
- `src/claude_statusbar/config.py` - `show_forecast`/`show_projection` dataclass defaults and `from_dict` fallbacks flipped to `False`
- `src/claude_statusbar/progress.py` - `DEFAULT_WARNING_THRESHOLD=65.0`, `DEFAULT_CRITICAL_THRESHOLD=85.0`, `PROJECTION_WARNING_THRESHOLD=65.0`, `CONTEXT_WARNING_THRESHOLD=65.0`; comments refreshed to describe the unified band
- `src/claude_statusbar/styles.py` - `render_capsule`/`render_hairline`/`render_classic` signature defaults now `65.0`/`85.0`
- `src/claude_statusbar/preview.py` - both `render(...)` call sites now pass `65.0`/`85.0`
- `src/claude_statusbar/cli.py` - `--warning-threshold`/`--critical-threshold` help text now says `default: 65` / `default: 85`
- `tests/test_config_projection.py`, `tests/test_config_forecast.py` - default assertions now expect `False`; tests renamed to `test_projection_default_off` / `test_default_off`
- `tests/test_threshold_resolution.py` - `test_default_thresholds_when_unset` now expects `65.0`/`85.0`
- `tests/test_progress.py` - `test_color_warning`/`test_color_critical` retargeted; boundary tests renamed to `test_color_boundary_65`/`test_color_boundary_85`; stale ctx-band comments refreshed
- `tests/test_projection_coloring.py` - warn-boundary tests moved to 65/64; `test_projection_thresholds_are_65_85` (renamed); fallback-band assertions retuned to 65/85
- `tests/test_per_segment_colors.py` - `weekly_pct` fixture bumped 50→70 so the 7d segment still lands in the new yellow band
- `tests/test_config.py` - cross-field validation tests reworked for 65/85 defaults (not just number tweaks — the invalid-pair trigger values and setup sequences changed)
- `tests/test_context_bar_render.py`, `tests/test_no_quota_render.py` - comment-only band prose refreshed to 65/85; no assertion changes
- `README.md` - threshold prose, config table rows, headline examples, and no-quota context-bar description updated
- `CHANGELOG.md` - new `## Unreleased` entry documenting both changes

## Decisions Made
- Followed the plan's D-01 through D-06 exactly as specified; no deviations required architectural decisions.
- Where the plan didn't explicitly list two README lines (`cs config set show_projection false` / `show_forecast false` in the usage cheatsheet, ~line 430) that had gone stale given the default flip, applied Rule 2 (auto-add missing critical functionality — here, documentation consistency) and updated them to `on` with an "(off by default)" note, since leaving `false` examples next to a documented `false` default would read as a no-op instruction to users.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Refreshed two stale `cs config set show_projection/show_forecast false` cheatsheet lines**
- **Found during:** Task 3 (README docs alignment)
- **Issue:** The plan's explicit edit list covered the config table rows and headline examples but not the usage-cheatsheet command examples (~line 430), which said `show_projection false  # hide the →NN% projection` — misleading once the default is already off.
- **Fix:** Changed both lines to `... on  # show the ... (off by default)`.
- **Files modified:** README.md
- **Committed in:** `1dacffc` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 missing-critical documentation consistency fix)
**Impact on plan:** Minor doc consistency fix; no scope creep, no code behavior changes beyond what the plan specified.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full suite green: `uv run --with pytest -m pytest -q` → 936 passed.
- All plan verification greps pass (constants, defaults, feature-preserved checks).
- Live/manual check (`cs daemon stop && cs daemon start`, `cs preview`, `cs config set show_projection on`) was NOT run in this session — it's marked optional/manual in the plan's `<verification>` step 5. Recommend the user spot-check it before releasing.
- No blockers for a future release/version-bump task (out of scope here per plan).

---
*Quick task: 260715-jbf-projection-off-and-standardize-threshold*
*Completed: 2026-07-15*

## Self-Check: PASSED

All modified/created files found on disk; all three task commit hashes (3cd54f7, 2b36824, 1dacffc) found in git log.
