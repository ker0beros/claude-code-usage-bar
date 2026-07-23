---
phase: quick-260723-bp4
plan: 01
subsystem: config
tags: [config, defaults, python, statusline]

requires: []
provides:
  - Fresh-install shipped defaults now match the maintainer's preferred look (tokyo-night theme, email chip on, cache-age/lines/version off)
affects: [config, README, CHANGELOG]

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - src/claude_statusbar/config.py
    - tests/test_config.py
    - tests/test_config_activity.py
    - tests/test_account.py
    - tests/test_project_branch_render.py
    - README.md
    - CHANGELOG.md

key-decisions:
  - "Flipped exactly 5 shipped defaults in config.py, changing both the @dataclass field default AND the load_config() raw.get(...) loader fallback for each key so the two locations never disagree."
  - "show_email ships ON by default (deliberate PII trade-off, per plan's threat_model disposition: accept, low severity, documented in README)."

patterns-established: []

requirements-completed: [QUICK-260723-bp4]

coverage:
  - id: D1
    description: "Fresh install (no config file) renders theme=tokyo-night, show_email=True, show_cache_age=False, show_lines=False, show_version=False, with show_context/style/density unchanged."
    requirement: "QUICK-260723-bp4"
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_show_cache_age_default_false, tests/test_config_activity.py#test_defaults, tests/test_account.py#test_show_email_defaults_on, tests/test_project_branch_render.py#test_show_version_config_default_off"
        status: pass
    human_judgment: false
  - id: D2
    description: "Dataclass field defaults and load_config() loader fallbacks agree for all 5 flipped keys (Location A == Location B)."
    requirement: "QUICK-260723-bp4"
    verification:
      - kind: unit
        ref: "Task 1 inline verification script (asserts DEFAULT_THEME, per-key loader-vs-dataclass equality, and untouched show_context/style/density) — see commit b9ee121"
        status: pass
    human_judgment: false
  - id: D3
    description: "Full pytest suite passes and README/CHANGELOG document the new defaults."
    requirement: "QUICK-260723-bp4"
    verification:
      - kind: unit
        ref: "full suite (.venv/bin/python -m pytest -q), 1114 passed"
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-07-23
status: complete
---

# Quick Task 260723-bp4: Ship Maintainer-Preferred Status Bar Look Summary

**Flipped 5 shipped defaults in `config.py` (theme=tokyo-night, show_email=True, show_cache_age/show_lines/show_version=False) so fresh installs render the maintainer's preferred look, keeping the dataclass and loader fallback in agreement, with tests/README/CHANGELOG updated to match.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-07-23T00:32Z (approx, from first commit)
- **Completed:** 2026-07-23T00:36Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- `DEFAULT_THEME` flipped `"graphite"` → `"tokyo-night"`; `show_cache_age`/`show_lines`/`show_version` flipped `True` → `False`; `show_email` flipped `False` → `True` — in BOTH the `@dataclass StatusbarConfig` field defaults and the `load_config()` loader fallbacks, verified programmatically to agree for every key.
- `show_context`, `style`, and `density` left untouched.
- Updated 4 test files (renamed and re-asserted default-value tests; explicit-override tests like roundtrip/persist untouched).
- Updated README's theme table, per-key config table, narrative default claims, and example config JSON; added a CHANGELOG Unreleased entry clarifying this is a fresh-install-only behavior change (existing config files unaffected).

## Task Commits

Each task was committed atomically:

1. **Task 1: Flip the 5 shipped defaults in config.py** - `b9ee121` (feat)
2. **Task 2: Update tests asserting the OLD defaults** - `f41d1bb` (test)
3. **Task 3: Update README.md and CHANGELOG.md** - `fa0540b` (docs)

## Files Created/Modified
- `src/claude_statusbar/config.py` - Flipped DEFAULT_THEME constant + 4 boolean field defaults + their loader fallbacks
- `tests/test_config.py` - Renamed/updated `show_cache_age` default tests to expect `False`
- `tests/test_config_activity.py` - Updated `test_defaults` to expect `show_lines is False`
- `tests/test_account.py` - Renamed/updated `show_email` default test to expect `True`; updated module docstring
- `tests/test_project_branch_render.py` - Renamed/updated `show_version` default test to expect `False`
- `README.md` - Theme table default marker moved to tokyo-night; per-key table (show_cache_age/show_email/show_lines/show_version) rows updated; narrative rows (cache countdown, identity-line show_lines mention) reworded to opt-in framing; example config JSON booleans updated to match
- `CHANGELOG.md` - Added Unreleased bullet describing the new shipped defaults and the fresh-install-only scope

## Decisions Made
- Both Location A (dataclass field) and Location B (loader `raw.get(key, default)` fallback) were changed for every key in the same edit pass, then verified programmatically that a loader run against an empty-but-existing config file produces values identical to `StatusbarConfig()` — closing the plan's stated #1 risk (silent A/B disagreement).
- `show_email` ships on by default per the plan's explicit, confirmed maintainer choice; documented the privacy trade-off in README per the plan's threat_model (T-bp4-01, disposition: accept).
- Historical CHANGELOG/README version-history lines (e.g. "v3.5.1 — show_cache_age on by default") were left untouched since they document what past releases did, not current defaults.

## Deviations from Plan

None — plan executed exactly as written. One incidental note below (not a deviation, no plan or code changes required):

### Notes (no fix applied — out of scope)

**Ambient dev-shell env var interferes with `test_check_for_updates.py` (pre-existing, unrelated to this plan)**
- **Found during:** Task 2's full-suite run
- **Issue:** This maintainer's dev shell has `CLAUDE_STATUSBAR_NO_UPDATE=1` exported (a supported opt-out env var for the tool itself, not the test suite). With it set, `check_for_updates()` short-circuits before doing anything, causing 4 tests in `tests/test_check_for_updates.py` to fail (they don't isolate/unset that var). Confirmed this failure exists identically on the pre-change baseline (`git stash` before Task 1's commit), so it is not caused by this plan's changes.
- **Resolution:** Ran the full suite with `env -u CLAUDE_STATUSBAR_NO_UPDATE .venv/bin/python -m pytest -q` — 1114/1114 passed. Per the executor's scope-boundary rule, this pre-existing gap in an unrelated test file (`test_check_for_updates.py`, not in this plan's `files_modified` list) was not fixed. A follow-up quick task could add `monkeypatch.delenv("CLAUDE_STATUSBAR_NO_UPDATE", raising=False)` to that file's `isolated_cache` fixture, mirroring the project's existing pattern for `CLAUDE_CONFIG_DIR` isolation (see STATE.md decision log, Phase 12).
- **Files modified:** None.

## Issues Encountered
- During verification, an incidental `git checkout b9ee121~1 -- src/claude_statusbar/config.py` while investigating the above test-isolation issue briefly reverted `config.py` to its pre-Task-1 state. Caught immediately via `git status`/`git diff`, restored with `git restore --staged --worktree src/claude_statusbar/config.py` (matching the already-committed `b9ee121` state), and stashed test-file edits were popped back cleanly. Re-verified `config.py`'s 9 changed lines (grep) matched the intended Task 1 diff before proceeding. No commit was affected.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- This quick task is self-contained; no follow-on phase depends on it.
- Optional follow-up (not required): isolate `CLAUDE_STATUSBAR_NO_UPDATE` in `test_check_for_updates.py`'s fixture so the suite is hermetic on machines that export it for daily use (same class of issue the project already solved for `CLAUDE_CONFIG_DIR` in Phase 12).

---
*Phase: quick-260723-bp4*
*Completed: 2026-07-23*

## Self-Check: PASSED

All 7 modified/created source files and the SUMMARY.md exist on disk; all 3 task commit hashes (b9ee121, f41d1bb, fa0540b) found in git log.
