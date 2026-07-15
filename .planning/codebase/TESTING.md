# Testing Patterns

**Analysis Date:** 2026-07-15

## Test Framework

**Runner:**
- pytest (>=8.4.2)
- Config: `pyproject.toml` lines 56-58 (dev dependency group)

**Assertion Library:**
- pytest built-in assertions (no pytest-assertions or custom helpers)
- `assert` statements with optional match patterns in `pytest.raises()`

**Run Commands:**
```bash
pytest -q                    # Run all tests (quiet mode)
pytest tests/test_setup.py   # Run specific test file
pytest -xvs                  # Verbose mode with full output
```

**CI/CD:**
- GitHub Actions (`.github/workflows/ci.yml`)
- Runs on Python 3.9, 3.10, 3.11, 3.12
- Command: `pytest -q` (line 44)

## Test File Organization

**Location:**
- Co-located in `tests/` directory (not alongside source)
- Directory structure mirrors source (e.g., `test_config.py` for `src/claude_statusbar/config.py`)

**Naming:**
- `test_<module_name>.py` (e.g., `test_config.py`, `test_setup.py`, `test_preview.py`)
- Test functions: `test_<feature>_<expected_behavior>()` (e.g., `test_config_show_lists_all_show_flags()`)
- Helper functions: `_<operation>()` (prefixed with underscore)

**Structure:**
```
tests/
├── conftest.py                  # Shared fixtures
├── test_config.py               # Tests for config.py
├── test_setup.py                # Tests for setup.py
├── test_preview.py              # Tests for preview.py
├── test_cli.py                  # Tests for cli.py
└── ... (73+ test files)
```

## Test Structure

**Module Docstring:**
```python
"""Tests for the install / repair flow.

Setup is the most fragile module — first-install reliability lives or dies
here. Use monkeypatching to redirect SETTINGS_PATH and COMMANDS_DIR into a
tmp dir so tests can never touch the real ~/.claude.
"""
```

**Test Organization:**
- Module-level docstring explaining test focus and strategy
- Imports organized: `import pytest`, then module under test, then helpers
- Fixtures defined at top
- Test functions grouped by feature (comments separating sections)
- Helper functions prefixed with `_`

**Test Function Pattern:**
```python
def test_creates_statusline_when_missing(isolated):
    """Docstring explaining what is being tested."""
    _, settings, _ = isolated                    # Arrange (setup from fixture)
    changed, msg = setup_mod.ensure_statusline_configured()  # Act
    assert changed is True                       # Assert
    assert "Added" in msg
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["statusLine"]["type"] == "command"
```

## Fixtures

**Autouse Fixtures (conftest.py):**
```python
@pytest.fixture(autouse=True)
def _isolate_rate_latest(tmp_path, monkeypatch):
    """Keep every test off the real ~/.cache/claude-statusbar/rate_latest.json.
    
    Monkeypatches module-level state into tmp_path so tests don't pollute
    developer's real cache."""
    import claude_statusbar.predict as predict
    monkeypatch.setattr(predict, "_LATEST_PATH", tmp_path / "rate_latest.json")
    monkeypatch.setattr(predict, "account_id", lambda: None)
```

**Custom Fixtures (example from test_setup.py):**
```python
@pytest.fixture
def isolated(monkeypatch, tmp_path: Path):
    """Redirect setup module's paths into tmp_path."""
    settings = tmp_path / ".claude" / "settings.json"
    commands = tmp_path / ".claude" / "commands"
    monkeypatch.setattr(setup_mod, "SETTINGS_PATH", settings)
    monkeypatch.setattr(setup_mod, "COMMANDS_DIR", commands)
    return tmp_path, settings, commands
```

**Built-in pytest Fixtures Used:**
- `monkeypatch`: Replace module attributes, environment variables, sys.argv
- `capsys`: Capture stdout/stderr output
- `tmp_path`: Temporary directory unique per test
- `monkeypatch.setenv()`: Set environment variables
- `monkeypatch.setattr()`: Replace module-level state (most common)

## Mocking

**Framework:** pytest's monkeypatch (no external mocking library)

**Patterns:**

1. **Module-level state replacement:**
```python
monkeypatch.setattr(setup_mod, "SETTINGS_PATH", settings)
monkeypatch.setattr(predict, "_LATEST_PATH", tmp_path / "rate_latest.json")
```

2. **Function replacement:**
```python
def fail(*args, **kwargs):
    raise OSError("simulated error")
monkeypatch.setattr(os, "replace", fail)
```

3. **Argument interception:**
```python
monkeypatch.setattr(sys, "argv", ["cs", "config", "show"])
```

4. **Environment isolation:**
```python
monkeypatch.setenv("NO_COLOR", "1")
monkeypatch.delenv("CLAUDE_STATUSBAR_JSON", raising=False)
```

**What to Mock:**
- File system operations (use tmp_path fixture instead for isolation)
- External command execution (subprocess calls)
- Module-level configuration paths
- Environment variables
- System clock / datetime

**What NOT to Mock:**
- Core business logic (test real functions)
- Built-in types and methods (use real values)
- Standard library unless necessary (e.g., json.loads should be real)

## Fixtures and Factories

**Test Data:**
```python
@pytest.mark.parametrize("entry,expected", [
    ({"type": "command", "command": "cs"}, True),
    ({"type": "command", "command": "cstatus"}, True),
    ({"type": "command", "command": "starship"}, False),
    ({}, False),
    ("string-not-dict", False),
    (None, False),
])
def test_is_our_statusline(entry, expected):
    assert setup_mod._is_our_statusline(entry) is expected
```

**Parametrization:**
- `@pytest.mark.parametrize()` for testing multiple input/output pairs
- Inline test data (no separate fixtures file)

**Location:**
- No separate fixtures directory
- Fixtures defined in `conftest.py` or inline in test modules
- Example shared fixture: `isolated(monkeypatch, tmp_path)` in `test_setup.py`

## Coverage

**Requirements:** None enforced (no coverage config in CI)

**View Coverage:**
```bash
pip install pytest-cov
pytest --cov=src/claude_statusbar
```

**Test Coverage Focus:**
- Edge cases explicitly tested (corrupt files, missing files, permission errors)
- Idempotency verified (calling same function twice produces same state)
- State preservation checked (unrelated config keys survive modification)
- Error paths covered (invalid input, invalid state transitions)
- CLI argument parsing thoroughly tested (both forms: `--flag value` and `--flag=value`)

## Test Types

**Unit Tests:**
- Scope: Individual functions and modules
- Approach: Test single function in isolation
- Examples: `test_parse_hex_rejects_invalid_chars()`, `test_set_value_rejects_invalid_density()`
- Pattern: Call function directly with test data, assert output

**Integration Tests:**
- Scope: Multiple modules together (e.g., config loading + CLI parsing)
- Approach: Exercise end-to-end flows
- Examples: `test_run_setup_returns_zero_on_clean_install()`, `test_preview_classic_varies_by_theme()`
- Pattern: Monkeypatch paths, call setup functions, verify state changes persist

**CLI Tests:**
- Scope: Argument parsing and command dispatch
- Approach: Monkeypatch `sys.argv`, call `cli.main()`, check return code and output
- Examples: `test_preview_accepts_theme_equals_form()`, `test_cli_rejects_invalid_thresholds()`
- Pattern: Set argv, capture stdout/stderr, verify output and exit code

**E2E Tests:**
- Not used (no browser/external service testing needed)

## Common Patterns

**Async Testing:**
Not used (no async code in this project)

**Error Testing:**
```python
def test_parse_hex_rejects_invalid_chars():
    with pytest.raises(ValueError, match="invalid hex"):
        parse_hex_color("#zzzzzz")
```

**Output Verification:**
```python
def test_config_show_lists_all_show_flags(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cs", "config", "show"])
    rc = cli.main()
    out = capsys.readouterr().out
    assert rc == 0
    for key in ("show_project_branch", "show_ahead_behind"):
        assert key in out, f"{key} missing from output"
```

**State Verification:**
```python
def test_preserves_other_settings_keys(isolated):
    _, settings, _ = isolated
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({
        "theme": "dark",
        "permissions": {"foo": "bar"},
    }) + "\n", encoding="utf-8")

    setup_mod.ensure_statusline_configured()
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"
    assert data["permissions"] == {"foo": "bar"}
    assert "statusLine" in data
```

**Idempotency Testing:**
```python
def test_idempotent_when_already_configured(isolated):
    _, settings, _ = isolated
    setup_mod.ensure_statusline_configured()
    changed, msg = setup_mod.ensure_statusline_configured()  # Call twice
    assert changed is False
    assert msg == "statusLine already configured"
```

**Defensive Edge Cases:**
```python
def test_handles_corrupt_settings_json(isolated):
    """If settings.json is corrupt, we treat it as empty rather than crash."""
    _, settings, _ = isolated
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text("{ this is not json", encoding="utf-8")

    changed, msg = setup_mod.ensure_statusline_configured()
    assert changed is True
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert "statusLine" in data
```

## Test Organization Best Practices

**Arrange-Act-Assert:**
- Fixture setup (Arrange) via fixtures and helper functions
- Action (Act) is the code under test
- Verification (Assert) via pytest assertions

**Test Naming:**
- Descriptive: `test_project_setup_preserves_existing_keys()` > `test_project_setup_works()`
- Behavior-focused: What should happen, not what is being tested
- Example: `test_install_commands_force_overwrites_user_edits()` (specific behavior)

**Comments in Tests:**
- Explain **why** a test exists (regression fix, edge case discovered)
- Example from `test_preview.py` line 78: "# Codex-flagged: argv parsing must accept both..."

**Test Isolation:**
- Autouse fixtures ensure no global state leaks between tests
- tmp_path ensures filesystem operations don't affect real files
- monkeypatch automatically reverts after each test

---

*Testing analysis: 2026-07-15*
