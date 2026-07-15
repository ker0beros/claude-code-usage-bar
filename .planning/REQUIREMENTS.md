# Requirements: Claude Status Bar

**Defined:** 2026-07-15
**Core Value:** At-a-glance rate-limit, context, model, and cost visibility in the Claude Code
status line — fast, within the refresh budget, with zero required dependencies.

> This is an existing, shipped project (v3.29.11). v1 requirements below are **already delivered**
> and reverse-mapped from the codebase + ingested SPECs. v2 requirements are the repo's documented
> backlog (from `.planning/codebase/CONCERNS.md`) — tracked, not yet committed.

## v1 Requirements

Shipped in v3.29.11. Each maps to exactly one delivered roadmap phase.

### Core & Render Pipeline

- [x] **CORE-01**: Status line renders on every Claude Code tick, fast path within the refresh budget (<~20ms)
- [x] **CORE-02**: Three CLI entrypoints (`cs`, `cstatus`, `claude-statusbar`) route to render and subcommands
- [x] **CORE-03**: Background daemon pre-renders per session; stale/dead daemon falls back to inline render
- [x] **CORE-04**: Atomic cache writes; missing/malformed stdin, transcript, or config never crash the render
- [x] **CORE-05**: `cs --setup` wires the `statusLine` hook and installs slash commands idempotently
- [x] **CORE-06**: User config persists (style/theme/`show_*` toggles) with CLI → env → file → default resolution
- [x] **CORE-07**: `cs doctor` self-diagnoses binary, settings, daemon, git, and config
- [x] **CORE-08**: Zero required third-party dependencies; Python 3.9+ stdlib-only render path

### Rate-Limit Status Bar (QUOTA)

- [x] **QUOTA-01**: Dual 5h and 7d usage progress bars rendered from the stdin rate-limit payload
- [x] **QUOTA-02**: Each bar colored by its own percentage (green <30, yellow 30–70, red >70)
- [x] **QUOTA-03**: Reset timer and active model name shown alongside the bars
- [x] **QUOTA-04**: Extreme states handled — >100% full-red `100%+`, unavailable `--%`, ≥1 filled block when >0
- [x] **QUOTA-05**: Bypass indicator shown when skip-permissions / bypass mode is active

### Styles & Theming (STYLE)

- [x] **STYLE-01**: Same metrics render in three styles — classic, capsule, hairline
- [x] **STYLE-02**: Nine built-in themes selectable via config or env; custom hex accepted
- [x] **STYLE-03**: Per-segment color management — no color bleed; each segment owns its severity
- [x] **STYLE-04**: Classic style adopts the active theme's colors instead of raw 8-color ANSI
- [x] **STYLE-05**: `cs preview` renders every style × theme combination with real session data

### Project & Branch Identity (IDENT)

- [x] **IDENT-01**: Opt-in second status line shows project name and git branch
- [x] **IDENT-02**: Dirty marker (`●`) from a cached git read — no `git` subprocess on the render path
- [x] **IDENT-03**: Outside a git repo the segment collapses to `(no git)`
- [x] **IDENT-04**: Identity segment renders in all three styles and respects the active theme

### Rate-Limit Prediction & Learning (PREDICT)

- [x] **PREDICT-01**: `⚠~ETA` chip appears next to a window's timer only when it is projected to exhaust before reset
- [x] **PREDICT-02**: Always-on `→NN%` end-of-window projection per window, working from a cold start
- [x] **PREDICT-03**: Projection collects local history, improves with observation, and stores snapshots for accuracy measurement
- [x] **PREDICT-04**: Burn-rate regime detection re-anchors the estimate on a model / fleet switch instead of chasing the old regime
- [x] **PREDICT-05**: Forecast (`⚠~ETA`) and projection (`→NN%`) coexist as distinct signals on one predict module

### Context Window Bar (CTX)

- [x] **CTX-01**: Context renders as a bar segment in each style's idiom in quota mode (not just a model-name suffix)
- [x] **CTX-02**: Context severity bands — yellow ≥70%, red ≥85%
- [ ] **CTX-03**: `show_context` toggle (default on); quota and no-quota modes render context identically

### Live Activity & Local Bridges (LIVE)

- [x] **LIVE-01**: Live activity (in-progress todo, running tool, active subagents) parsed from the transcript via bounded tail-read
- [x] **LIVE-02**: Prompt-cache age countdown with auto-detected TTL (5m/1h/override)
- [x] **LIVE-03**: Session cost displayed
- [x] **LIVE-04**: AgentParty channel/identity/unread shown from the local cache, gated on session-specific evidence
- [x] **LIVE-05**: Session-mode line (effort / thinking / style) rendered

### Account Enrichment & Safety Signals (ENRICH)

- [x] **ENRICH-01**: Relay account-balance fuel gauge shown in no-quota / third-party relay mode
- [x] **ENRICH-02**: Opt-in IP + relay-fingerprint risk signals surfaced from background probes

### Distribution & Auto-Update (DIST)

- [x] **DIST-01**: PyPI packaging with three entrypoints; installable via pip / uv / pipx
- [x] **DIST-02**: `cs upgrade` detects install channel and updates; background PyPI version check ≤ once/day
- [x] **DIST-03**: Daemon installs as a launchd (macOS) or systemd (Linux) service
- [x] **DIST-04**: Packaged as a Claude Code `statusLine` plugin (`plugin.json`) with launch/marketing materials

## v2 Requirements

Documented backlog from `.planning/codebase/CONCERNS.md`. Tracked; mapped to the **planned** Phase 9,
not yet started.

### Reliability & Maintainability Hardening (HARD)

- **HARD-01**: `cs daemon status` health-check command, surfaced in `cs doctor`
- **HARD-02**: `cs cache repair` command validates cache files and repairs/quarantines corrupt ones
- **HARD-03**: Broad exception handlers log context before returning a default (failures become diagnosable)
- **HARD-04**: Split monolithic `predict.py` and `core.py` into focused modules
- **HARD-05**: Prediction-store size-based compaction + regime-boundary and concurrent-daemon test coverage

## Out of Scope

| Feature | Reason |
|---------|--------|
| Push / desktop notifications | On-bar signals only; forecast design keeps notifications separate/later |
| `$`-cost burn-rate signal, model burn-weight table, Fable-specific 7d bucket, session-departure detection | Explicit non-goals of the burn-regime design |
| Non-git VCS, remote URL / commit SHA in identity | Identity is git-only and deliberately minimal |
| Database / server / web-GUI frontend | This is a terminal ANSI status line |
| `.env` file reading | Reads environment variables only; never persists secrets |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 1 | Complete |
| CORE-02 | Phase 1 | Complete |
| CORE-03 | Phase 1 | Complete |
| CORE-04 | Phase 1 | Complete |
| CORE-05 | Phase 1 | Complete |
| CORE-06 | Phase 1 | Complete |
| CORE-07 | Phase 1 | Complete |
| CORE-08 | Phase 1 | Complete |
| QUOTA-01 | Phase 2 | Complete |
| QUOTA-02 | Phase 2 | Complete |
| QUOTA-03 | Phase 2 | Complete |
| QUOTA-04 | Phase 2 | Complete |
| QUOTA-05 | Phase 2 | Complete |
| STYLE-01 | Phase 3 | Complete |
| STYLE-02 | Phase 3 | Complete |
| STYLE-03 | Phase 3 | Complete |
| STYLE-04 | Phase 3 | Complete |
| STYLE-05 | Phase 3 | Complete |
| IDENT-01 | Phase 4 | Complete |
| IDENT-02 | Phase 4 | Complete |
| IDENT-03 | Phase 4 | Complete |
| IDENT-04 | Phase 4 | Complete |
| PREDICT-01 | Phase 5 | Complete |
| PREDICT-02 | Phase 5 | Complete |
| PREDICT-03 | Phase 5 | Complete |
| PREDICT-04 | Phase 5 | Complete |
| PREDICT-05 | Phase 5 | Complete |
| CTX-01 | Phase 6 | Active |
| CTX-02 | Phase 6 | Active |
| CTX-03 | Phase 6 | Active |
| LIVE-01 | Phase 7 | Complete |
| LIVE-02 | Phase 7 | Complete |
| LIVE-03 | Phase 7 | Complete |
| LIVE-04 | Phase 7 | Complete |
| LIVE-05 | Phase 7 | Complete |
| ENRICH-01 | Phase 7 | Complete |
| ENRICH-02 | Phase 7 | Complete |
| DIST-01 | Phase 8 | Complete |
| DIST-02 | Phase 8 | Complete |
| DIST-03 | Phase 8 | Complete |
| DIST-04 | Phase 8 | Complete |
| HARD-01 | Phase 9 | Planned |
| HARD-02 | Phase 9 | Planned |
| HARD-03 | Phase 9 | Planned |
| HARD-04 | Phase 9 | Planned |
| HARD-05 | Phase 9 | Planned |

**Coverage:**

- v1 requirements: 37 total
- Mapped to phases: 37
- Unmapped: 0 ✓
- v2 (planned): 5, mapped to Phase 9

---
*Requirements defined: 2026-07-15*
*Last updated: 2026-07-15 after ingest bootstrap (existing shipped project, v3.29.11)*
