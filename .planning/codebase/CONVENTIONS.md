# Coding Conventions

**Analysis Date:** 2026-07-15

## Naming Patterns

**Files:**
- Snake case with descriptive names: `config.py`, `core.py`, `cli.py`, `service.py`
- Private/internal modules prefixed with underscore: `_git_refresh.py`, `_balance_refresh.py`
- Test files: `test_<feature>.py` (e.g., `test_config_show_keys.py`, `test_setup.py`)

**Functions:**
- Snake case: `load_config()`, `set_value()`, `parse_stdin_data()`, `atomic_write_text()`
- Private functions prefixed with underscore: `_to_bool()`, `_get_logger()`, `_platform()`
- Test helpers prefixed with underscore: `_run()`, `_run_cli()`

**Variables:**
- Snake case: `result`, `debug_file`, `session_env`, `cached_rate_limits`
- Module-level singletons prefixed with underscore: `_logger`, `_LATEST_PATH`, `_PROJECTION_PATH`
- Constants in UPPERCASE with underscores: `CONFIG_PATH`, `DEFAULT_STYLE`, `LAUNCHD_LABEL`, `SYSTEMD_UNIT`

**Types/Classes:**
- PascalCase: `StatusbarConfig` (dataclass)
- Enum values as descriptors in lowercase: `"compact"`, `"regular"`, `"cozy"`

## Code Style

**Formatting:**
- No explicit formatter config (relies on Ruff for linting)
- 4-space indentation (Python standard)
- Type hints throughout (comprehensive use of `Optional[X]`, `Dict`, `List`, `Tuple`, union types)
- Line continuation and multi-line patterns as needed for readability

**Linting:**
- Tool: Ruff (`ruff check .`)
- Configuration: Minimal (no ruff.toml or [tool.ruff] in pyproject.toml)
- Run in CI/CD: Yes (`.github/workflows/ci.yml` line 60-61, continue-on-error=true)

**Code Structure:**
- Module docstrings at file top explaining purpose, design decisions, and architectural notes
- Comments explain performance optimizations and architectural rationale
- Heavy imports deferred to functions that use them to reduce startup cost (e.g., `cli.py` line 6, `core.py` line 14-17)
- Lazy initialization of expensive resources (logger in `core.py` lines 21-30)

## Import Organization

**Order:**
1. `from __future__ import annotations` (when used, for forward references)
2. Standard library imports (`sys`, `os`, `json`, `pathlib`, etc.)
3. Third-party imports (rarely used; only `claude-monitor` optional)
4. Local/relative imports (`from . import config`, `from .cache import atomic_write_text`)

**Path Aliases:**
- Relative imports only: `from .cache import atomic_write_text`
- No path aliases defined; structure is flat enough

**Deferred Imports:**
- Heavy modules imported inside functions, not at module level
- Example from `cli.py` (line 31): `from . import config as cfg_mod` inside `_run_config_subcommand()`
- Rationale: `cs render` must execute in ~60ms per render tick; avoiding import tax is critical

## Error Handling

**Patterns:**
- Specific exception types caught, not bare `except:`
  - Example: `except (OSError, json.JSONDecodeError)` in `config.py` line 123
  - Exception chaining with `from e` in `config.py` lines 215, 236
- Defensive parsing with type checks before extraction
  - Example: `if isinstance(raw, dict):` in `config.py` line 125
  - Example: `if isinstance(model_obj, dict):` in `core.py` line 86
- Graceful fallbacks to defaults on parse failure
  - `load_config()` returns default `StatusbarConfig()` if file missing/corrupt (line 120, 124, 126)
  - `parse_stdin_data()` returns partial dict on partial failure (core.py line 55 marks `_has_stdin=True` before field extraction)
- Comments explain swallowed exceptions and recovery strategy
  - Example: `core.py` line 51-54 explains why partial stdin data is acceptable

**Critical Validation:**
- Cross-field validation in `set_value()` (`config.py` lines 217-236)
- Atomic writes prevent corruption on Ctrl+C (`cache.py` lines 15-43)

## Logging

**Framework:** Python `logging` module

**Pattern:**
- Lazy logger initialization via `_get_logger()` in `core.py` (lines 23-30)
  - Logger built on first use, not module import
  - Avoids ~2ms import cost when rendering doesn't need logs
- Logger level: ERROR (minimal verbosity)
- Handler: NullHandler (logs discarded unless user configures logging)

**When to Log:**
- Errors and warnings only (not info/debug in render path)
- Example: `core.py` uses `_get_logger()` only in exception fallback paths

## Comments

**When to Comment:**
- Explain **why**, not **what** — code shows what it does
- Architectural decisions and trade-offs
- Performance-critical sections (deferred imports, lazy init)
- Non-obvious fallback/recovery logic
- Example from `cli.py` line 204-207: explains `cs render` fast-path and import deferral strategy
- Example from `config.py` line 26-30: explains DEPRECATED field and why it's kept

**JSDoc/TSDoc:**
- Python docstrings (not JSDoc) using triple quotes
- Function docstrings explain purpose, parameters, and returns
- Module docstrings at file top with context and design
- Example from `cache.py` lines 15-21: detailed docstring for `atomic_write_text()`

## Function Design

**Size:** Generally small, focused functions (10-50 lines typical)
- Example: `_to_bool()` in `config.py` is 4 lines
- Example: `atomic_write_text()` in `cache.py` is 28 lines with full error recovery

**Parameters:**
- Type hints required (`path: Optional[Path] = None`)
- Default parameters for optional paths/env: `path: Optional[Path] = None` then `path = CONFIG_PATH if path is None else path`
- Explicit env parameter for testing: `env: Optional[dict] = None` in `config.py` line 304

**Return Values:**
- Setup functions return `(ok: bool, message: str)` tuples
  - Example: `ensure_statusline_configured()` in `setup.py`
- Monadic returns for success/failure with details
- Complex data as dataclasses: `StatusbarConfig`
- Helper functions return raw values (dicts, strings, bools)

**Validation & Cross-Field Checks:**
- Input validation at function entry
- Cross-field validation before state mutation
- Example: `set_value()` validates pair constraint before saving (lines 217-236)

## Module Design

**Exports:**
- Public functions/classes: no prefix
- Private functions/modules: `_` prefix
- All module-level variables documented in docstrings

**Barrel Files:**
- No barrel files (index.py); direct imports from submodules
- `__init__.py` in `src/claude_statusbar/` exists but minimal

**Dataclasses:**
- Used for configuration holding (`StatusbarConfig` in `config.py`)
- Fields with detailed comments explaining each option
- Example: `config.py` lines 33-108 (75 lines of class def + inline docs)

## Type Hints

**Coverage:** Comprehensive throughout codebase
- Function parameters: `def load_config(path: Optional[Path] = None) -> StatusbarConfig:`
- Return types always specified: `-> bool`, `-> Tuple[bool, str]`, `-> Dict[str, Any]`
- Union types using `|` (Python 3.10+ syntax in `cli.py` line 455)
- Generic collections: `Dict[str, Any]`, `List[str]`, `Tuple[str, ...]`
- Optional: `Optional[X]` or `X | None`

## Environment Variables

**Convention:**
- Uppercase with underscore separation: `NO_COLOR`, `CLAUDE_STATUSBAR_JSON`, `CLAUDE_RESET_HOUR`
- Env helpers: `env_bool()`, `env_float()` in `cli.py` (lines 451-466) parse and validate
- Validation messages in stderr when env var is malformed

---

*Convention analysis: 2026-07-15*
