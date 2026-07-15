<!-- refreshed: 2026-07-15 -->
# Architecture

**Analysis Date:** 2026-07-15

## System Overview

Claude Status Bar is a lightweight token-usage monitor that integrates with Claude Code's `statusLine` hook. It renders real-time metrics (quota usage, rate limits, cache age, activity) to a single status line. The architecture balances performance (invoked 60×/min at `refreshInterval: 1`) with feature richness.

```text
┌─────────────────────────────────────────────────────────────┐
│              Claude Code (every 1s at 1Hz)                   │
│        Calls `cs render` + sends JSON via stdin              │
└──────────────────────┬──────────────────────────────────────┘
                       │
         ┌─────────────┴──────────────┐
         ▼                            ▼
   ┌──────────────┐          ┌─────────────────┐
   │ render_thin  │ (fast)   │ Fallback inline │
   │ Fast client  │          │  Full render    │
   └──────┬───────┘          └────────┬────────┘
          │                           │
          │ Read cache               │ Compute everything
          │ (if fresh)               │
          │                           │
          └───────────┬───────────────┘
                      │
         ┌────────────▼────────────┐
         │   Daemon (background)   │
         │  Pre-renders to cache   │
         │  `rendered.ansi` file   │
         │   Sessions isolated     │
         └────────────┬────────────┘
                      │
         ┌────────────▼────────────────────────────────────┐
         │        Data Collection & Rendering             │
         ├────────────┬─────────────┬─────────────────────┤
         │  core.py   │activity.py  │   styles.py/       │
         │ (stdin)    │ (transcript)│  themes.py (render)│
         │ predict.py │ party.py    │  progress.py       │
         │ cache.py   │ (AgentParty)│  (bars/colors)     │
         └────────────┴─────────────┴─────────────────────┘
                      │
                      ▼
              ~/.cache/claude-statusbar/
              └── sessions/{session_id}/
                  ├── last_stdin.json
                  ├── rendered.ansi
                  └── rendered.meta.json
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| CLI Router | Parse args, route subcommands, defer heavy imports | `cli.py` |
| Thin Client | Read daemon cache, fallback to inline render, forward stdin | `render_thin.py` |
| Daemon | Pre-render to file, manage refresh cadence, multi-session isolation | `daemon.py` |
| Stdin Parser | Extract quota, model, context, rate limits, timestamps from Claude Code JSON | `core.py` |
| Activity Scanner | Tail-read transcript JSONL, extract todos, running tools, subagents | `activity.py` |
| Party Reader | Read local AgentParty cache, workspace context, session identity | `party.py` |
| Predictor | Project end-of-window usage, compute ETA to rate-limit cap | `predict.py` |
| Cache Manager | Atomic file writes, session state storage, freshness tracking | `cache.py` |
| Renderer (Styles) | Three layout engines (classic/capsule/hairline) | `styles.py` |
| Theme Engine | Nine color palettes, per-severity colors | `themes.py` |
| Progress Bars | Render filled/empty bars, color severity, shimmer particles | `progress.py` |
| Config | Load/persist user settings from `~/.claude/claude-statusbar.json` | `config.py` |
| Setup/Install | Wire `statusLine` hook, install slash commands, manage daemon | `setup.py` |
| Daemon Lifecycle | Start/stop service, LaunchAgent/systemd management | `service.py` |
| Update Checker | PyPI version polling, auto-update flow | `updater.py` |
| Diagnostics | Self-check (binary, settings, daemon, git, config) | `doctor.py` |

## Pattern Overview

**Overall:** Dual-render pipeline with deferred heavy imports and multi-session isolation.

**Key Characteristics:**
- **Performance-first:** Fast path imports only ~4 stdlib modules (json, os, sys, time, pathlib)
- **Lazy loading:** Heavy modules (core, styles, themes, daemon) defer until their subcommand/path runs
- **Session isolation:** Each Claude Code window gets its own cache bucket, preventing multi-window render collisions
- **Bounded resource reads:** Transcript scanning capped at 320KB reverse-tail, never full-file slurp
- **Atomic writes:** All file updates go through `atomic_write_text` (sibling tempfile + `os.replace`)
- **Fail-safe fallback:** Daemon timeout (>5s stale) → seamless inline render, user never sees frozen bar

## Layers

**CLI Layer:**
- Purpose: Command-line interface, route to subcommands, lazy-defer heavy work
- Location: `cli.py`
- Contains: Argument parsing, subcommand handlers (config, daemon, setup, preview, doctor)
- Depends on: argparse (stdlib), config.py for lightweight subcommands
- Used by: Entry points (`cs`, `cstatus`, `claude-statusbar`) in pyproject.toml

**Render Client Layer (Phase B):**
- Purpose: Fast-path render command, pre-render cache reading, stdin forwarding
- Location: `render_thin.py`
- Contains: Cache file reading, staleness checks, fallback trigger logic
- Depends on: stdlib only (json, os, sys, time, pathlib)
- Used by: Claude Code statusLine hook (invoked every `refreshInterval` seconds)

**Background Service Layer:**
- Purpose: Long-lived render daemon, pre-compute heavy data, multi-session management
- Location: `daemon.py`
- Contains: Render loop, freshness tracking, session isolation, lifecycle management
- Depends on: core.py (for actual render), cache.py, pathlib
- Used by: render_thin.py (reads cache), manual `cs daemon start` commands

**Data Extraction Layer:**
- Purpose: Parse raw inputs into structured data ready for rendering
- Location: `core.py` (stdin/quota), `activity.py` (transcript), `party.py` (AgentParty), `predict.py` (projection)
- Contains:
  - `core.py`: JSON parsing, rate-limit extraction, cache-age computation, validation
  - `activity.py`: Reverse-tail transcript read, todo/tool/agent extraction
  - `party.py`: Local AgentParty cache read, workspace context detection
  - `predict.py`: Window projection, ETA computation, learning local rhythms
- Depends on: stdlib only (json, re, pathlib, datetime)
- Used by: daemon.py, inline render paths

**Configuration Layer:**
- Purpose: Load/persist user settings, resolution order (CLI flag → env var → file → default)
- Location: `config.py`
- Contains: Config dataclass, load/save, field validators, defaults
- Depends on: json, pathlib, dataclasses
- Used by: CLI subcommands, render paths (styles/themes choice)

**Rendering Layer:**
- Purpose: Turn structured data into ANSI terminal strings
- Location: `progress.py` (bars), `styles.py` (layout), `themes.py` (palette), `preview.py` (multi-combo preview)
- Contains:
  - `progress.py`: Bar rendering (fill/empty), color by severity, shimmer particles
  - `styles.py`: Three layout engines (classic, capsule, hairline)
  - `themes.py`: Nine built-in palettes (graphite, twilight, nord, etc.)
  - `preview.py`: Test/demo all style×theme combos with real session data
- Depends on: themes.py (for color tuples), pure functions (no I/O)
- Used by: daemon.py, inline render paths

**Setup/Lifecycle Layer:**
- Purpose: Installation, configuration hook management, daemon service installation
- Location: `setup.py` (hook + skill install), `service.py` (LaunchAgent/systemd), `updater.py` (PyPI check)
- Contains: settings.json modification, slash command install, OS service registration
- Depends on: json, pathlib, platform detection, optional systemd/launchd APIs
- Used by: `cs --setup`, `cs install-commands`, `cs daemon install`, background auto-update checks

**Utilities:**
- `cache.py`: Atomic file I/O, debounce helpers, session cleanup
- `git_cache.py`: Cached git status reads (dirty marker, ahead/behind)
- `balance_cache.py`: Relay account balance probing and caching
- `ip_risk.py` / `fp_risk.py`: IP geolocation and relay fingerprint warnings
- `doctor.py`: Self-diagnostic output

## Data Flow

### Primary Request Path (per statusLine tick)

1. **Claude Code invokes `cs render`** (`cli.py` line 205-207)
   - Fast path: `sys.argv[1] == "render"` → import `render_thin` only

2. **Thin client reads cached state** (`render_thin.py` line ~130)
   - Check session dir `~/.cache/claude-statusbar/sessions/{session_id}/`
   - Read `last_stdin.json` (forwarded by previous render), `rendered.ansi` (pre-rendered), `rendered.meta.json` (freshness)

3. **Validate daemon freshness** (`render_thin.py` line 74-82)
   - `generated_at` must be within 5s AND daemon started after latest .py code on disk
   - If stale: fall through to inline render (next step)

4. **Read pre-rendered output** (`render_thin.py` line ~170)
   - Print `rendered.ansi` to stdout (3-5ms, ~0.1KB)
   - EXIT (fast path ends here, ~8ms total)

5. **If cache miss/stale, inline render** (`cli.py` line 305-350)
   - Import core, styles, themes (heavy modules now)
   - Call `core.main()` to produce status string
   - Print to stdout

### core.main() — Full Render Compute

1. **Parse stdin from Claude Code** (`core.parse_stdin_data()` line 33)
   - Read JSON payload with rate limits, model, context, session_id, transcript_path
   - Extract rate_limit.five_hour.used_percentage, resets_at, etc.
   - Cache to `~/.cache/claude-statusbar/last_stdin.json` if valid (used by daemon on next tick)

2. **Compute cache age** (`core.get_cache_age_text()` line ~260)
   - Tail-read transcript JSONL (max 320KB, newest-first)
   - Find most recent assistant entry, read timestamp
   - Read cache_creation buckets to auto-detect TTL (1h vs 5m)
   - Return countdown string or "COLD"

3. **Read transcript activity** (`activity.parse_live_activity()` line ~140)
   - Tail-read same transcript
   - Find newest TodoWrite (in-progress todo), newest tool_use without result (active tool), running agents
   - Return activity dataclass with counts, names, timestamps

4. **Read AgentParty context** (`party.read_party_status()` line ~200)
   - Check for `~/.agentparty/state/{workspace_id}/statusline.json`
   - Extract channel, identity, listener mode, unread count, last message
   - If missing or stale (>10min): return empty PartyStatus (line rendered as disconnected)

5. **Load user config** (`config.load_config()`)
   - Parse `~/.claude/claude-statusbar.json` OR return defaults
   - Apply env var overrides (CLAUDE_STATUSBAR_STYLE, etc.)
   - Apply CLI flag overrides (--style, --theme, etc.)

6. **Project end-of-window usage** (`predict.get_projection()` line ~120)
   - Per window (5h, 7d): compute elapsed since window open, avg pace, extrapolate
   - Return projected % at reset time
   - If projected ≥ 100% AND imminent (<1h to cap): return ETA string for warning chip

7. **Select style renderer** (`styles.RENDERERS[config.style]` line ~500)
   - Three options: classic, capsule, hairline (each a function that returns ANSI string)
   - Pass all computed fields + theme + config flags

8. **Render layout** (e.g., `styles.render_classic()` line ~600)
   - Invoke `progress.render_bar()` to produce quota bars with fill/empty/color
   - Construct project/branch line with git status, dirty marker
   - Construct activity line with todo, active tool, completed-tool rollup
   - Construct session-mode line (effort/thinking/fast/style) with gradient
   - Concat all lines with newlines, ANSI codes

9. **Return ANSI string**
   - Stdout: multiline terminal text with SGR codes (escape sequences for colors)

### Daemon Pre-Render Loop

1. **Daemon starts** (`daemon.cmd_start()` line ~180)
   - Detach subprocess or run foreground (for debugging)
   - Acquire lock on `~/.cache/claude-statusbar/daemon.lock` (one per user)

2. **Light tick cadence (~1s)** (`daemon.run_forever()` line ~300)
   - For each active session in `~/.cache/claude-statusbar/sessions/`:
     - Read `last_stdin.json` (forwarded by `render_thin` on every tick)
     - Compute fresh cache age (age changes every second)
     - Call render path with cached heavy data + fresh cache age
     - Write `rendered.ansi` atomically
     - Write `rendered.meta.json` with `generated_at` timestamp

3. **Heavy tick cadence (~30s)** (configurable)
   - If available, run `claude-monitor` subprocess for richer rate-limit analysis
   - Cache the result in-memory
   - Check for PyPI updates in background (non-blocking)
   - Clean up stale session dirs (>1 day idle)

**State Management:**
- **Shared account-level state** (`~/.cache/claude-statusbar/rate_latest.json`): Last-writer-wins newest 5h/7d reading across all windows
- **Per-session state** (`~/.cache/claude-statusbar/sessions/{session_id}/`): Isolated stdin, rendered output, metadata
- **Config** (`~/.claude/claude-statusbar.json`): Persistent user settings
- **Update cache** (`~/.cache/claude-statusbar/update_check.json`): PyPI version check (once per day)

## Key Abstractions

**StatusbarConfig:**
- Purpose: Immutable user settings with 30+ boolean/string/numeric fields
- Examples: `src/claude_statusbar/config.py` line 33-120
- Pattern: Dataclass, load from JSON, env var + CLI flag override chains

**Theme:**
- Purpose: Palette of 9 RGB tuples (ink, mute, severity colors, pill backgrounds)
- Examples: `src/claude_statusbar/themes.py` line 39-200
- Pattern: Frozen dataclass, indexed by name, no layout logic

**Progress Segment:**
- Purpose: One colored bar (quota/context/balance) with fill%, labels, timestamp
- Examples: `src/claude_statusbar/progress.py` line ~140 (render_bar)
- Pattern: Pure function, returns ANSI string, no I/O

**Activity (dataclass):**
- Purpose: Live-session state parsed from transcript: todo, active tool, agents
- Examples: `src/claude_statusbar/activity.py` line 115-150
- Pattern: Named tuple with optional fields, null when not present

**PartyStatus (dataclass):**
- Purpose: AgentParty local cache state: channel, identity, listener mode, unread
- Examples: `src/claude_statusbar/party.py` line 44-62
- Pattern: Frozen, immutable, all fields optional

## Entry Points

**CLI Entry (public):**
- Location: `src/claude_statusbar/cli.py` line 199 (`main()`)
- Triggers: User runs `cs`, `cstatus`, or `claude-statusbar` command
- Responsibilities:
  - Parse `sys.argv`, detect fast-path render or subcommand
  - Route to subcommand handler (config, daemon, preview, doctor, etc.)
  - For default (no args), invoke full render via `core.main()`
  - Return exit code to shell

**Render Fast-Path Entry:**
- Location: `src/claude_statusbar/render_thin.py` line ~120 (`render()`)
- Triggers: `cs render` (invoked by Claude Code statusLine hook every ~1s)
- Responsibilities:
  - Forward Claude Code's stdin to session cache
  - Try to read daemon's pre-rendered `rendered.ansi`
  - If fresh: print and exit (8ms)
  - If stale/missing: fall back to inline render path

**Daemon Entry:**
- Location: `src/claude_statusbar/daemon.py` line ~300 (`run_forever()`)
- Triggers: `cs daemon start` or lazy-spawn on first stale render
- Responsibilities:
  - Loop forever at ~1Hz rendering ticks
  - Per-session isolation, atomic cache writes
  - Crash-safe (exit on SIGTERM/SIGINT)

**Setup Entry:**
- Location: `src/claude_statusbar/setup.py` line ~50 (`run()`)
- Triggers: `cs --setup`
- Responsibilities:
  - Modify `~/.claude/settings.json` to add statusLine hook
  - Install slash commands to `~/.claude/commands/`
  - Auto-start daemon in background
  - Print summary + restart instructions

## Architectural Constraints

- **Threading:** Single-threaded event loop. No concurrency primitives (no locks, no queues). All state is process-local or file-backed with atomic writes.
  
- **Global state:** None in render paths. Config is loaded once per process. Stdin is read-once per render. Transcript is tail-read on-demand. Session isolation prevents multi-window collisions.

- **Circular imports:** Deliberately avoided. cli.py imports conditionally within subcommand branches (deferred imports). render_thin.py imports only stdlib. Heavy modules (core, styles, themes) are bottom-level and don't re-import cli.

- **No external dependencies:** stdlib only. Optional `claude-monitor` as subprocess (for Bedrock/Vertex analysis), not imported.

- **Per-render budget:** <20ms for fast path (thin client + daemon read), <100ms for inline render, <500ms for daemon tick (may spawn subprocess).

- **Session safety:** Daemon uses file locking (fcntl on Unix, msvcrt on Windows) + session_id dir isolation so multiple Claude windows in the same repo never overwrite each other's rendered output.

- **Clock skew defense:** If `generated_at` timestamp is in the future, treat daemon output as stale (NTP correction or container restart can warp time).

- **Account switching:** Rate-limit data is keyed by account UUID (from `~/.claude.json`), so logging into a different account doesn't show the previous account's 7d limits for days.

## Anti-Patterns

### Slurping Large Transcript Files

**What happens:** Early versions read entire transcript into memory, causing multi-second hangs on sessions >10MB

**Why it's wrong:** Render is invoked 60×/min on keystroke; users perceive >50ms latency. Long sessions freeze the status line.

**Do this instead:** Tail-read only the most recent 320KB in reverse chunks, seeking newest-first for cache age and activity. See `core._last_assistant_info()` line ~170 and `activity.parse_live_activity()` line ~180.

### Spawning Claude-Monitor on Every Render

**What happens:** Early daemon design called `claude-monitor` subprocess on every light tick (~1s), costing ~100ms per render

**Why it's wrong:** Subprocess overhead is 30-50ms in Python startup alone; renders pile up during network latency

**Do this instead:** Separate heavy tick (~30s) that spawns claude-monitor and caches the result in-memory; light ticks (1s) only update cache age. See `daemon.run_forever()` line ~320.

### Hardcoding Cache TTL to 5min

**What happens:** Early versions showed `cache 4m59s` for all users, but subscription users have 1h TTL. Subscribers saw COLD alerts that were wrong.

**Why it's wrong:** TTL is plan-level (5min vs 1h vs 1h w/override), account setting (FORCE_PROMPT_CACHING_5M), and over-quota state. Hardcoding can't know all three.

**Do this instead:** Auto-detect from transcript's `message.usage.cache_creation` buckets (ephemeral_1h_input_tokens vs ephemeral_5m_input_tokens). Per-turn signal that already reflects all policy. See `core.get_cache_age_text()` line ~260.

### Multi-Window Render Collisions

**What happens:** Two Claude Code windows in the same repo both run daemon, both write to `~/.cache/claude-statusbar/rendered.ansi`. The file becomes corrupted or shows the wrong window's metrics.

**Why it's wrong:** One daemon, one rendered.ansi file — only one window can own the output at a time.

**Do this instead:** Daemon isolates each session in its own dir: `~/.cache/claude-statusbar/sessions/{session_id}/rendered.ansi`. Session_id comes from Claude Code's stdin (unique per window). See `daemon.session_dir()` line ~75 and `render_thin.render()` line ~130.

## Error Handling

**Strategy:** Fail gracefully, never crash the render, always produce some output.

**Patterns:**
- Stdin missing/unparseable → render with defaults (empty quota bars, no model name)
- Transcript missing/unreadable → omit cache age + activity, render everything else
- Config parse error → ignore user config, fall back to defaults
- Daemon stale (>5s) → inline render transparently, no user-facing error
- Rate-limit field malformed (NaN, inf, >100k) → coerce to safe value or 0
- Account UUID missing → use unsuffixed paths (pre-v3.7 behavior)
- AgentParty cache stale/missing → render as "disconnected" (line 59 of party.py)

See `core.parse_stdin_data()` line 33 for comprehensive try-except wrapping.

## Cross-Cutting Concerns

**Logging:** Disabled on render paths (NullHandler). Stderr only when user runs `cs doctor`. Daemon runs detached, logs to `~/.cache/claude-statusbar/daemon.log` (for crash diagnosis).

**Validation:** 
- Rate-limit percentages coerced to int, clamped [0, ∞), reject >100k (leak indicator)
- Cache countdown never negative (clock-skew defense, clamp to 0)
- TTL auto-detected, fallback to 300s conservative default
- Session_id sanitized to alphanumeric + `-_`, max 64 chars (filesystem safety)

**Authentication:** None. All data is from Claude Code's stdin (authenticated by Claude Code's own process). AgentParty data is local-only (no token read). IP-risk check is passive (IP geolocation, no auth). Relay account balance probes with user's own API key (passed in stdin environment).

---

*Architecture analysis: 2026-07-15*
