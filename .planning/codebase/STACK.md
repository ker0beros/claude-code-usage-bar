# Technology Stack

**Analysis Date:** 2026-07-15

## Languages

**Primary:**
- Python 3.9+ - Core application, CLI tool, all business logic

## Runtime

**Environment:**
- Python 3.9 - Minimum supported version
- Python 3.10, 3.11, 3.12 - Tested and supported

**Package Manager:**
- pip - Primary installation method (via `pip install claude-statusbar`)
- setuptools - Build system and entry point management
- uv tool - Alternative modern Python package manager
- pipx - Alternative isolated installation method
- Lockfile: Not used (pyproject.toml with no lock file approach)

## Frameworks

**Core:**
- setuptools 61.0+ - Build backend and package management
- No external application frameworks (pure stdlib, minimal dependencies)

**Testing:**
- pytest 8.4.2+ - Test runner and assertion library

**Build/Dev:**
- None detected (manual scripts in `scripts/` and `publish.sh`)

## Key Dependencies

**Core Runtime:**
- Zero required dependencies - All code uses Python standard library only

**Optional Runtime:**
- claude-monitor 3.0.0+ - Optional monitoring integration (in `full` extras group)

## Configuration

**Environment:**
- Configured via environment variables or CLI flags
- Config persisted to `~/.claude/claude-statusbar.json` (JSON)
- Alternative config via `CLAUDE_STATUSBAR_STYLE` and `CLAUDE_STATUSBAR_THEME` env vars
- Daemon state cache: `~/.cache/claude-statusbar/` directory
- Session cache: `~/.cache/claude-statusbar/sessions/<session-id>/` per-session

**Build:**
- `pyproject.toml` - Main project metadata (setuptools format)
- Entry points: `claude-statusbar`, `cstatus`, `cs` (CLI aliases for same entry point)
- Package data: Includes `*.py` files and markdown docs from `commands/` and `skills/` subdirectories

## Platform Requirements

**Development:**
- Python 3.9+
- pip or uv or pipx
- pytest for running tests
- Git (for install.sh and developer workflows)
- LaTeX/XeLaTeX (optional, for docs building if needed)

**Production:**
- Python 3.9+
- pip/uv/pipx for installation
- Claude Code IDE (as primary runtime environment)
- macOS/Linux/Windows compatible (OS independent per classifier)
- Internet access (for PyPI version checks and optional IP risk evaluation)
- Optional: launchd (macOS) or systemd (Linux) for daemon management

---

*Stack analysis: 2026-07-15*
