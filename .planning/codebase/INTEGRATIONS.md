# External Integrations

**Analysis Date:** 2026-07-15

## APIs & External Services

**Package Management:**
- PyPI (`https://pypi.org/pypi/claude-statusbar/json`)
  - What: Auto-update version checking for claude-statusbar package
  - SDK/Client: urllib.request (stdlib)
  - Implementation: `src/claude_statusbar/updater.py:get_latest_version()` — queries PyPI JSON API for latest published version
  - Cache: `~/.cache/claude-statusbar/latest_version.json` — cached for 24h to avoid spam

**IP Risk Detection:**
- ipify.org (`https://api.ipify.org`)
  - What: Detect user's egress IP address for risk evaluation
  - SDK/Client: urllib.request (stdlib)
  - Timeout: 8 seconds
  - Implementation: `src/claude_statusbar/_ip_risk_refresh.py:egress_ip()`
  - Cadence: Cheap tier — every render to detect VPN toggles fast
  - Load: Unlimited quota (~negligible per-user cost)

- ipapi.is (`https://api.ipapi.is/`)
  - What: Full IP risk evaluation (datacenter/VPN/proxy/Tor/abuser detection) + ASN + country
  - SDK/Client: urllib.request (stdlib)
  - Timeout: 8 seconds
  - Implementation: `src/claude_statusbar/_ip_risk_refresh.py:evaluate_ip()`
  - Cadence: Full tier only when IP changed or risk reading aged out (user's own quota)
  - Load: ~1000/day per user, distributed (does not concentrate load on shared quota)
  - Config: Opt-in via `show_ip_risk` config (default: off)
  - Cache: `~/.cache/claude-statusbar/ip_risk.json` — fingerprint + risk verdict cached locally

**Third-Party Relay Billing:**
- OpenAI-compatible relay endpoints (`/v1/dashboard/billing/subscription` and `/v1/dashboard/billing/usage`)
  - What: Query relay account balance (for users on third-party API relay instead of Anthropic official API)
  - SDK/Client: urllib.request (stdlib)
  - Timeout: 6 seconds
  - Implementation: `src/claude_statusbar/_balance_refresh.py` — probes relay with OpenAI/new-api/one-api compatible billing endpoints
  - Auth: Bearer token from `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` env var (passed detached via `CS_BALANCE_KEY`/`CS_BALANCE_AUTH`)
  - Detection: Auto-detected when `ANTHROPIC_BASE_URL` env var points off `api.anthropic.com`
  - Endpoints tried in order: `/v1/dashboard/billing`, `/dashboard/billing` (different relay layouts)
  - Cache: `~/.cache/claude-statusbar/balance_cache.json` — negative cache (5 min) for unsupported relays to avoid re-probing
  - Config: Opt-in via `show_balance` (default: on), `balance_bar` renders as fuel gauge (default: on)

## Data Storage

**Databases:**
- None — no database integrations

**File Storage:**
- Local filesystem only
  - Config: `~/.claude/claude-statusbar.json` (JSON)
  - Cache directory: `~/.cache/claude-statusbar/`
    - `last_stdin.json` — Most recent Claude Code session data payload
    - `sessions/<session-id>/last_stdin.json` — Per-session stdin cache
    - `sessions/<session-id>/rendered.ansi` — Daemon's pre-rendered status bar ANSI output
    - `sessions/<session-id>/rendered.meta.json` — Metadata about the last render (timestamp, freshness)
    - `ip_risk.json` — Cached IP risk evaluation
    - `latest_version.json` — Cached latest PyPI version
    - `balance_cache.json` — Cached relay account balance
    - `.tmp/` — Temporary files cleaned up periodically
    - `daemon.pid` — Daemon process ID (for lifecycle management)
    - `daemon.sock` — Optional Unix socket for daemon communication (platform-dependent)

**Caching:**
- None (external services) — All caching is local filesystem JSON
- Cache invalidation: TTL-based (5 min for most, 24h for version check)

## Authentication & Identity

**Auth Provider:**
- No dedicated auth provider
- Custom: Environment-based authentication
  - `ANTHROPIC_API_KEY` - Primary API key for accessing Anthropic/relay services
  - `ANTHROPIC_AUTH_TOKEN` - Fallback auth token (some relay setups use this)
  - `ANTHROPIC_BASE_URL` - Relay/custom API base URL detection (when set, enables no-quota relay mode)
  - Implementation: `src/claude_statusbar/core.py:is_no_quota_mode()` — detects third-party relay via env var
  - Session-scoped: Per-session env stamped in stdin by Claude Code, not using daemon's frozen os.environ

**Claude Code Integration:**
- Native statusLine hook integration
  - Data source: stdin JSON payload from Claude Code on every render
  - Contains: session_id, rate_limits (5h/7d), model, context_window, session_cost, transcript_path, transcript_metadata
  - Implementation: `src/claude_statusbar/core.py:parse_stdin_data()`
  - Refresh interval: Configurable in `~/.claude/settings.json` (default: 1 second)

## Monitoring & Observability

**Error Tracking:**
- None — errors logged locally only to stderr/logging module

**Logs:**
- Deferred logging: heavy imports deferred to reduce startup time
- Logger: Python logging module (`import logging`)
- Level: ERROR (default, minimal verbosity)
- Handler: NullHandler (suppresses noise) + optional file output
- Implementation: `src/claude_statusbar/core.py:_get_logger()`

**Status/Health:**
- Daemon health check via process existence + socket/pidfile
- Render freshness detection: last write timestamp + package code mtime comparison
- Implementation: `src/claude_statusbar/render_thin.py:_is_fresh()` — detects stale daemon output and falls back to inline render

## CI/CD & Deployment

**Hosting:**
- PyPI (package distribution)
- GitHub (source + releases)

**CI Pipeline:**
- GitHub Actions (mentioned in README, e.g. `pytest` runs)
- Test command: `pytest` (from `pyproject.toml` dev dependencies)

**Distribution:**
- PyPI: `pip install claude-statusbar`
- Alternative: `uv tool install claude-statusbar`
- Alternative: `pipx install claude-statusbar`
- Auto-upgrade: Built-in `cs upgrade` command that detects install channel and runs appropriate upgrade

## Environment Configuration

**Required env vars:**
- None required (all optional for different features)

**Conditionally Required:**
- `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` - Only needed for relay balance checking (auto-detects if relay is in use)
- `ANTHROPIC_BASE_URL` - Only needed when using third-party relay (auto-detects if set)

**Optional env vars:**
- `CLAUDE_STATUSBAR_STYLE` - Override configured style (classic | default | capsule)
- `CLAUDE_STATUSBAR_THEME` - Override configured theme (9 builtin themes + custom hex)
- `CLAUDE_SKIP_PERMISSIONS` - Skip Claude Code permission prompts (Claude Code specific)
- `CLAUDE_STATUSBAR_NO_UPDATE` - Disable auto-update checks
- `NO_COLOR` - Disable color output (standard UNIX convention)
- `TZ` - Timezone (used for fingerprint risk detection with relays)
- `AGENTPARTY_HOME` - AgentParty installation directory (defaults to `~/.agentparty`)
- `AGENTPARTY_CONFIG` - Path to AgentParty config file (parsed from shell commands)
- `XDG_CONFIG_HOME` - XDG Base Directory for config (falls back to `~/.config`)

**Secrets location:**
- `ANTHROPIC_API_KEY` - In Claude Code environment, or in shell profile
- `.env` files - Not supported by this tool (reads from environment only)
- Never cached: Tokens are never written to logs or disk

## Webhooks & Callbacks

**Incoming:**
- None — statusbar does not expose any webhook endpoints

**Outgoing:**
- None — statusbar makes read-only queries only (GET requests to PyPI, ipify, ipapi.is, relay billing)
- Relay balance probing: Non-blocking, detached subprocess (`_balance_refresh.py`)
- IP risk probing: Non-blocking, detached subprocess (`_ip_risk_refresh.py`)

## Git Integration

**Local Git Repository:**
- Read-only access to `.git/HEAD` for current branch name
- Read-only access to `git status` for dirty marker and file counts
- Implementation: `src/claude_statusbar/git_cache.py` — lightweight git operations with 5-second cache
- Shows: Branch name, dirty state (`●`), commits ahead/behind (`↑N↓M`), file additions/deletions (`+N -M`)
- Cache: `~/.cache/claude-statusbar/git_cache.json` per-repo

## Local Service Bridges

**AgentParty Status Bridge:**
- Local filesystem read only (no network, no tokens)
- Reads: `~/.agentparty/state/<workspaceId>/statusline.json` written by AgentParty daemon
- Parses: channel name, agent identity, listener state, unread count, last message
- Shows: AgentParty context only when locally present (no AgentParty API calls)
- Implementation: `src/claude_statusbar/party.py`
- Config: Opt-in via `show_party` (default: on)

---

*Integration audit: 2026-07-15*
