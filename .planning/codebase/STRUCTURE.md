# Codebase Structure

**Analysis Date:** 2026-07-15

## Directory Layout

```
claude-code-usage-bar/
├── src/claude_statusbar/        # Main package
│   ├── __init__.py              # Lazy-load __version__ and main (PEP 562)
│   ├── cli.py                   # CLI router, subcommand dispatchers
│   ├── render_thin.py           # Fast-path thin client (reads daemon cache)
│   ├── daemon.py                # Background pre-render service
│   │
│   ├── core.py                  # Stdin parsing, quota extraction, cache-age compute
│   ├── activity.py              # Transcript scanning, todo/tool/agent parsing
│   ├── party.py                 # AgentParty local cache reader
│   ├── predict.py               # Rate-limit projection, ETA computation
│   ├── cache.py                 # Atomic file I/O, session cleanup helpers
│   ├── git_cache.py             # Cached git status (dirty, ahead/behind)
│   ├── balance_cache.py         # Relay account balance probing
│   ├── ip_risk.py               # IP geolocation warnings
│   ├── fp_risk.py               # Relay fingerprint-risk warnings
│   │
│   ├── config.py                # Load/persist user config, resolution order
│   ├── styles.py                # Three layout renderers (classic/capsule/hairline)
│   ├── themes.py                # Nine color palettes
│   ├── progress.py              # Bar rendering, fill/empty/color/shimmer
│   ├── preview.py               # Test all style×theme combos
│   │
│   ├── setup.py                 # Install statusLine hook, slash commands, daemon
│   ├── service.py               # OS service lifecycle (LaunchAgent/systemd)
│   ├── updater.py               # PyPI version check, auto-upgrade
│   ├── doctor.py                # Self-diagnostic output
│   │
│   ├── commands/                # Slash command YAML descriptors
│   │   └── *.md                 # claude-statusbar skill commands
│   └── skills/                  # Installed skill modules
│       └── claude-statusbar/
│           └── *.md
│
├── tests/                       # Test suite (320+ tests)
│   ├── conftest.py              # Pytest fixtures (fixtures for temp dirs, mock stdin, etc.)
│   ├── test_*.py                # ~70 test modules (see naming pattern below)
│   └── __init__.py
│
├── pyproject.toml               # Package metadata, entry points, dependencies
├── README.md                    # User guide (49KB)
├── CONTRIBUTING.md              # Developer setup, test commands, architecture
├── CHANGELOG.md                 # Per-version release notes (58KB)
├── SECURITY.md                  # Security policy
│
├── tools/                       # Development utilities
│   └── backtest.py              # Rate-limit projection backtesting script
│
├── scripts/                     # Installation / CI helpers
│   ├── run-tests.sh
│   └── version-sync.sh
│
├── demo/                        # Demo / screenshot assets
│   └── *.txt, *.json
│
├── promotion/                   # Marketing / release materials
│   └── various media files
│
├── .claude-plugin/              # Claude Code plugin metadata
│   └── plugin.json
│
├── .github/                     # GitHub Actions CI, issue templates
│   ├── workflows/
│   └── ISSUE_TEMPLATE/
│
├── .planning/                   # Post-execute drift detection
│   └── codebase/                # Codebase analysis documents (this directory)
│       ├── ARCHITECTURE.md
│       ├── STRUCTURE.md
│       ├── CONVENTIONS.md
│       ├── TESTING.md
│       ├── STACK.md
│       ├── INTEGRATIONS.md
│       └── CONCERNS.md
│
└── docs/                        # Internal design documentation
    ├── images/                  # Screenshots, diagrams
    ├── superpowers/             # GSD skill definitions
    │   ├── plans/               # Release / feature plans
    │   └── specs/               # Detailed design specs (e.g. rate-limit forecast)
    └── README.md
```

## Directory Purposes

**`src/claude_statusbar/`:**
- Purpose: Core Python package for the `cs` CLI tool
- Contains: All render logic, CLI commands, daemon service, configuration
- Key files: `cli.py` (entry), `render_thin.py` (fast path), `core.py` (data extract), `daemon.py` (background service)

**`tests/`:**
- Purpose: Comprehensive test suite (pytest, 320+ tests, ~1.5s total)
- Contains: Unit tests for every major module, integration tests for daemon, end-to-end CLI tests
- Patterns: Fixtures in `conftest.py`, test modules named `test_<feature>.py`

**`tools/`:**
- Purpose: Developer utilities and analysis scripts
- Contains: `backtest.py` (rate-limit projection backtesting against historical data)

**`scripts/`:**
- Purpose: CI/CD and installation helpers
- Contains: Shell scripts for running tests, syncing version across files

**`demo/`:**
- Purpose: Screenshot and demo materials
- Contains: Sample JSON transcripts, rendered output examples

**`promotion/`:**
- Purpose: Release marketing materials
- Contains: Blog post previews, social media assets, release announcement drafts

**`.claude-plugin/`:**
- Purpose: Claude Code plugin package definition
- Contains: `plugin.json` with plugin metadata (name, version, commands, permissions)

**`.github/`:**
- Purpose: GitHub infrastructure (CI, issue templates, workflows)
- Contains: GitHub Actions YAML, issue/PR templates

**`.planning/codebase/`:**
- Purpose: Codebase mapping for GSD (generated post-execute by `gsd-map-codebase`)
- Contains: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, STACK.md, INTEGRATIONS.md, CONCERNS.md

**`docs/`:**
- Purpose: Internal design documentation (not user-facing README)
- Contains: Architecture diagrams, GSD skill specs (plans, release specs), design decisions

## Key File Locations

**Entry Points:**
- `src/claude_statusbar/cli.py` line 199: `main()` — CLI router, all command dispatch starts here
- `src/claude_statusbar/render_thin.py` line ~120: `render()` — Fast-path entry, called by Claude Code every statusLine tick
- `src/claude_statusbar/daemon.py` line ~300: `run_forever()` — Daemon main loop, invoked by `cs daemon start`
- `src/claude_statusbar/__init__.py` line 10-28: `__getattr__` — Lazy `__version__` and `main` resolution (PEP 562)

**Configuration:**
- `src/claude_statusbar/config.py` line 16: `CONFIG_PATH = ~/.claude/claude-statusbar.json` — User settings persist here
- `pyproject.toml` line 44-47: Entry point script definitions (`cs`, `cstatus`, `claude-statusbar` → `cli:main`)

**Core Logic:**
- `src/claude_statusbar/core.py` line 33: `parse_stdin_data()` — Parse Claude Code JSON payload
- `src/claude_statusbar/core.py` line ~260: `get_cache_age_text()` — Compute prompt-cache countdown
- `src/claude_statusbar/activity.py` line ~140: `parse_live_activity()` — Extract todos, tools, agents from transcript
- `src/claude_statusbar/predict.py` line ~120: `get_projection()` — Project end-of-window usage
- `src/claude_statusbar/party.py` line ~200: `read_party_status()` — Read local AgentParty cache

**Rendering:**
- `src/claude_statusbar/styles.py` line ~500: `RENDERERS` dict — Maps style name to render function
- `src/claude_statusbar/styles.py` line ~600: `render_classic()`, `render_capsule()`, `render_hairline()` — Layout engines
- `src/claude_statusbar/progress.py` line ~140: `render_bar()` — Single quota/context/balance bar
- `src/claude_statusbar/themes.py` line 39-200: `BUILTIN_THEMES` — Nine color palettes

**Testing:**
- `tests/conftest.py` — Pytest fixtures (temp dirs, mock stdin, mocked config)
- `tests/test_core.py` — Core render path tests (parsing, validation, defaults)
- `tests/test_daemon.py` — Daemon lifecycle and multi-session isolation
- `tests/test_styles.py` — Render output (all style×theme combos)
- `tests/test_cache_*.py` — Cache countdown computation and TTL detection

## Naming Conventions

**Files:**
- Core modules (no prefix): `core.py`, `activity.py`, `daemon.py`, `styles.py` (public API)
- Private/internal modules (underscore prefix): `_git_refresh.py`, `_balance_refresh.py`, `_ip_risk_refresh.py` (background refresh loops)
- Test files: `test_<feature>.py` (e.g. `test_cache_age.py`, `test_projection.py`, `test_daemon.py`)
- Config/static: `config.py`, `themes.py`, `styles.py`

**Directories:**
- Package root: `src/claude_statusbar/` (per setuptools convention, importable as `claude_statusbar`)
- Tests: `tests/` (pytest auto-discovers)
- Slash commands: `commands/` (YAML descriptors read by skill system)
- Skills: `skills/claude-statusbar/` (copied to `~/.claude/commands/` on install)

**Functions:**
- Public: `snake_case` (e.g., `parse_stdin_data`, `load_config`, `render_thin`)
- Private: `_leading_underscore` (e.g., `_get_logger`, `_pct`, `_validate_rate_limit`)
- Render paths: Explicit `render_<style>` (e.g., `render_classic`, `render_bar`)
- Helpers for subprocess/system calls: `_run_...` (e.g., `_run_git_status`)

**Classes & Types:**
- Config: `StatusbarConfig` — user-facing settings dataclass
- Data containers: `PartyStatus`, `Activity`, `SegmentData` — frozen dataclasses (immutable)
- Theme: `Theme` — palette dataclass

## Where to Add New Code

**New Feature (e.g., display a new metric):**
1. **Data extraction:** Add parsing logic to `core.py` (if from stdin) or `activity.py` (if from transcript)
   - File: `src/claude_statusbar/core.py` or `src/claude_statusbar/activity.py`
2. **Computation:** If complex (e.g., projection), create new module like `src/claude_statusbar/<metric>.py`
3. **Configuration:** Add boolean `show_<metric>` to `StatusbarConfig` in `config.py`
4. **Rendering:** Add segment rendering to each style renderer
   - Files: `src/claude_statusbar/styles.py` (all three functions: `render_classic`, `render_capsule`, `render_hairline`)
   - Color logic: `src/claude_statusbar/progress.py` if needing bar/severity
5. **Tests:** Add test module `tests/test_<metric>.py` with fixtures from `conftest.py`

**New CLI Subcommand:**
1. **Handler:** Add function `_run_<subcommand>_subcommand()` in `cli.py`
   - File: `src/claude_statusbar/cli.py` line ~30-190
2. **Router:** Add to `SUBCOMMANDS` tuple and `if sub == "<subcommand>"` branch in `main()` line ~210
3. **Implementation:** Create new module if complex
   - File: `src/claude_statusbar/<subcommand>.py`
4. **Tests:** Add CLI tests to `tests/test_cli.py` or new module `tests/test_<subcommand>.py`

**New Render Style (layout engine):**
1. **Define renderer:** Add function `render_<name>(...)` returning ANSI string
   - File: `src/claude_statusbar/styles.py` line ~600
   - Signature: matches existing `render_classic` (all fields + config + theme)
2. **Register:** Add to `RENDERERS` dict
   - File: `src/claude_statusbar/styles.py` line ~500
3. **List:** Update `list_styles()` function
   - File: `src/claude_statusbar/styles.py` line ~700
4. **Config:** Verify `config.py` accepts the new name in `DEFAULT_STYLE`
5. **Tests:** Add to `tests/test_styles.py` (render with sample data, check no crashes)

**New Color Theme:**
1. **Define palette:** Add `Theme(...)` to `BUILTIN_THEMES` list
   - File: `src/claude_statusbar/themes.py` line 39-200
2. **Colors:** Pick RGB tuples for ink, mute, edge, s_ok, s_warn, s_hot, pill_* colors
3. **Test:** Run `cs preview --theme <name>` to visualize all styles
4. **Register:** Function `get_theme(name)` auto-discovers from list

**Daemon Enhancement (background service):**
1. **Logic:** Modify `run_forever()` loop
   - File: `src/claude_statusbar/daemon.py` line ~300
2. **Session isolation:** Use `session_dir(session_id)` for any per-session state
3. **Atomic writes:** Use `cache.atomic_write_text()` for all file updates
4. **Tests:** Add to `tests/test_daemon.py` with mock processes/files

**New Configuration Option:**
1. **Define field:** Add to `StatusbarConfig` dataclass
   - File: `src/claude_statusbar/config.py` line 33-120
2. **Default value:** Set in the field definition
3. **Validation:** Add `set_value()` branch if non-trivial parsing
   - File: `src/claude_statusbar/config.py` line ~150
4. **Usage:** Reference in render paths (styles, progress, core)
5. **CLI exposure:** Update `_run_config_subcommand("show")` to print the new field
   - File: `src/claude_statusbar/cli.py` line 39-70
6. **Tests:** Add to `tests/test_config.py`

**Utilities & Helpers:**
- Shared file I/O: `src/claude_statusbar/cache.py`
- Git status caching: `src/claude_statusbar/git_cache.py`
- Balance probing: `src/claude_statusbar/balance_cache.py`
- Risk checks (IP, fingerprint): `src/claude_statusbar/ip_risk.py`, `fp_risk.py`

## Special Directories

**`~/.cache/claude-statusbar/` (runtime state, created by the tool):**
- Purpose: Session caches, daemon state, update checks
- Generated: Yes (auto-created on first run)
- Committed: No (local state, git-ignored)
- Contents:
  - `daemon.pid` — daemon process ID
  - `daemon.lock` — file-lock for single-daemon enforcement
  - `daemon.log` — daemon stderr (if running detached)
  - `sessions/{session_id}/last_stdin.json` — Claude Code's latest payload (per session)
  - `sessions/{session_id}/rendered.ansi` — pre-rendered status line (per session)
  - `sessions/{session_id}/rendered.meta.json` — freshness metadata
  - `rate_latest.json` — shared account-level quota snapshot (last-writer-wins)
  - `update_check.json` — PyPI version cache (once/day)

**`~/.claude/claude-statusbar.json` (user config, created on first config change):**
- Purpose: Persistent user settings (style, theme, show_* toggles, thresholds)
- Generated: No (user-created via `cs config set` or auto-init on first use)
- Committed: No (local to user)
- Contents: JSON serialization of `StatusbarConfig` dataclass

**`~/.claude/commands/` (installed by `cs --setup` or `npx skills add`, not in repo):**
- Purpose: Slash command descriptors for Claude Code
- Generated: Yes (copied from `src/claude_statusbar/commands/` on install)
- Committed: No (user-level, per-machine)

## Import Structure (Dependency Graph)

**Minimal dependency chain (fast path, <8ms):**
- `cli.py` → `render_thin.py` (when `sys.argv[1] == "render"`)
- `render_thin.py` → stdlib only (json, os, sys, time, pathlib)

**Full dependency chain (inline render, ~100ms):**
- `cli.py` → `core.py` → `activity.py`, `party.py`, `predict.py`, `cache.py`
- `core.py` → `styles.py` → `progress.py`, `themes.py`
- All → stdlib only (no external packages)

**Heavy subcommands (conditional, loaded only when used):**
- `cs daemon` → `daemon.py` → `core.py` (full render chain)
- `cs setup` → `setup.py` → `config.py`, `service.py`
- `cs preview` → `preview.py` → `styles.py`, `themes.py`
- `cs doctor` → `doctor.py` → all modules (diagnostic scan)

**Circular import prevention:**
- cli.py never imports core.py at module level (defers to function branches)
- render_thin.py never imports anything heavy (isolation from cli.py)
- No module imports cli.py (cli is the top-level router)

---

*Structure analysis: 2026-07-15*
