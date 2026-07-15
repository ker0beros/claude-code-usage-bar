---
phase: 06-context-window-bar-in-quota-mode
plan: 01
subsystem: config
tags: [config, cli, dataclass, toggle]

requires: []
provides:
  - "StatusbarConfig.show_context: bool field, default True"
  - "show_context parse/validate/persist wiring in config.py (load_config, VALID_KEYS, _BOOL_KEYS)"
  - "show_context line in `cs config show` output"
affects: [06-02-renderers, 06-03-core-preview-integration]

tech-stack:
  added: []
  patterns: ["boolean toggle field mirroring show_forecast/show_projection sibling pattern"]

key-files:
  created:
    - tests/test_config_context.py
  modified:
    - src/claude_statusbar/config.py
    - src/claude_statusbar/cli.py

key-decisions:
  - "show_context defaults to True per the LOCKED Control toggle decision in 06-CONTEXT.md"
  - "Mirrored the exact show_forecast/show_projection pattern (dataclass field, load_config parse, VALID_KEYS, _BOOL_KEYS, config-show print line) for consistency"

patterns-established:
  - "New show_* toggles: add dataclass field with comment, load_config parse with same default, VALID_KEYS + _BOOL_KEYS membership, config-show print line"

requirements-completed: [CTX-03]

coverage:
  - id: D1
    description: "StatusbarConfig().show_context defaults to True"
    requirement: "CTX-03"
    verification:
      - kind: unit
        ref: "tests/test_config_context.py::test_default_on"
        status: pass
    human_judgment: false
  - id: D2
    description: "cs config set show_context off|on persists and round-trips through load_config"
    requirement: "CTX-03"
    verification:
      - kind: unit
        ref: "tests/test_config_context.py::test_set_and_load"
        status: pass
    human_judgment: false
  - id: D3
    description: "cs config show lists show_context with its current value"
    requirement: "CTX-03"
    verification:
      - kind: unit
        ref: "tests/test_config_context.py::test_config_show_lists_show_context"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-15
status: complete
---

# Phase 6 Plan 01: show_context config toggle Summary

**Added the `show_context` boolean config field (default on) that will gate the quota-mode context bar, persisted through `cs config set`/`cs config show` exactly like the existing `show_forecast`/`show_projection` toggles.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-15T04:47:00Z
- **Completed:** 2026-07-15T04:59:00Z
- **Tasks:** 2 completed
- **Files modified:** 3 (2 source, 1 test — new file)

## Accomplishments
- `StatusbarConfig.show_context: bool = True` added to the dataclass, placed with the sibling `show_*` toggles and documented with a comment explaining it gates the quota-mode context bar (CTX-03).
- `load_config` now parses `show_context` with `_to_bool(raw.get("show_context", True))`, so pre-existing config files that omit the key upgrade to `show_context=True`.
- `show_context` added to both `VALID_KEYS` and `_BOOL_KEYS`, so `cs config set show_context on|off` routes through the existing boolean path and persists via `asdict`/`save_config`.
- `cs config show` now prints a `show_context = <value>` line alongside `show_forecast`/`show_projection`.
- `tests/test_config_context.py` created with `test_default_on`, `test_set_and_load` (off→on round-trip through `set_value`/`load_config`), and `test_config_show_lists_show_context` (capsys assertion on `cli.main()` output).

## Task Commits

Each task was committed atomically, TDD (RED confirmed before implementing):

1. **Task 1: Add show_context field to StatusbarConfig (parse, keys, persistence)** - `bac5f17` (feat)
2. **Task 2: Surface show_context in `cs config show`** - `336b8c8` (feat)

**Plan metadata:** commit pending below (docs: complete plan)

_Note: Each task's test was written first and confirmed to fail (AttributeError / missing substring) before the corresponding implementation was added, per the plan's `tdd="true"` requirement._

## Files Created/Modified
- `src/claude_statusbar/config.py` - added `show_context: bool = True` field, `load_config` parse line, `VALID_KEYS`/`_BOOL_KEYS` membership
- `src/claude_statusbar/cli.py` - added `show_context` print line to the `cs config show` block in `_run_config_subcommand`
- `tests/test_config_context.py` - new test file: `test_default_on`, `test_set_and_load`, `test_config_show_lists_show_context`

## Decisions Made
- Followed the plan's instruction to mirror the `show_forecast`/`show_projection` pattern exactly, including test structure (copied from `tests/test_config_forecast.py`) and the config-show capsys pattern (copied from `tests/test_config_show_keys.py`). No deviation from the established convention.

## Deviations from Plan

None - plan executed exactly as written. No new package installs; no architectural changes; no bugs found requiring Rule 1/2/3 fixes.

## Issues Encountered

- No local Python environment had `pytest` installed and the system `python` binary was aliased away (`python` → "command not found", only `python3` present, no `pytest` module). Used `uv run --with pytest -m pytest ...` (created a gitignored `.venv/` via `uv`) to run the test suite without touching global site-packages or the project's runtime dependency footprint (`dependencies = []` in `pyproject.toml` is preserved — `pytest` is a dev-only, ephemeral test runner, never added to the package's own dependency list). This is a local tooling workaround, not a plan deviation.
- Avoided running the plan's illustrative manual verification command (`cs config set show_context off && cs config show | grep show_context`) against the real `~/.claude/claude-statusbar.json`, since that would mutate the user's live statusbar config as a side effect of plan execution. Equivalent coverage is provided by `tests/test_config_context.py::test_set_and_load`, which exercises the identical `set_value`/`load_config` round-trip against an isolated `tmp_path` config file.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `cfg.show_context` is now available for 06-02 (renderers: classic/capsule/hairline ctx segment) and 06-03 (core.py official-quota + waiting branch integration, preview.py) to consume as the gate for drawing the quota-mode context bar.
- No blockers. Full test suite (`uv run --with pytest -m pytest -q`) passes at 920/920 after this plan's changes — no regression to any existing config or CLI test.

---
*Phase: 06-context-window-bar-in-quota-mode*
*Completed: 2026-07-15*

## Self-Check: PASSED

- FOUND: src/claude_statusbar/config.py
- FOUND: src/claude_statusbar/cli.py
- FOUND: tests/test_config_context.py
- FOUND: .planning/phases/06-context-window-bar-in-quota-mode/06-01-SUMMARY.md
- FOUND: bac5f17
- FOUND: 336b8c8
