# Claude Status Bar

## What This Is

Claude Status Bar (`claude-statusbar` on PyPI; `cs` / `cstatus` / `claude-statusbar` CLIs) is a
lightweight, fast status-line monitor for Claude Code. It renders at-a-glance 5h/7d rate-limit
usage, context-window fill, active model, and session cost into the Claude Code `statusLine` — and
also runs as a standalone CLI. It targets Claude Code Max/Pro subscribers who want to see how close
they are to their limits without leaving their terminal. Current shipped version: **v3.29.11**.

## Core Value

At-a-glance visibility of rate-limit usage, context fill, active model, and cost in the status line
— rendered well within the `statusLine` refresh budget, with **zero required third-party
dependencies**. If everything else fails, the bar must still render fast and never freeze the editor.

## Business Context

- **Customer**: Claude Code Max/Pro subscribers (claude.ai login) who want live rate-limit awareness.
- **Revenue model**: Free / open-source; distributed via PyPI. Value is adoption, not revenue.
- **Success metric**: The status line renders 5h/7d usage, context, model, and cost within the
  per-tick refresh budget (<~20ms fast path) with no required dependencies.
- **Strategy notes**: Launch materials and an Anthropic plugin-directory submission live in `docs/`.

## Requirements

### Validated

<!-- Shipped in v3.29.11 and relied upon. Each maps to a delivered roadmap phase. -->

- ✓ Dual-render pipeline: stdlib-only fast thin client + background daemon with per-session
  isolation and inline fallback — Phase 1
- ✓ Rate-limit-focused dual progress bars (5h/7d) with per-percentage color severity — Phase 2
- ✓ Three layout styles (classic/capsule/hairline), nine themes, per-segment color management — Phase 3
- ✓ Opt-in project + git-branch identity segment (cached dirty status, no git on render path) — Phase 4
- ✓ Rate-limit prediction: at-risk ⚠~ETA chip + always-on →NN% projection + burn-regime detection — Phase 5
- ◻ Context-window bar in quota mode with severity bands — Phase 6 (ACTIVE — SPEC written, not yet implemented)
- ✓ Live activity (todos/tools/subagents), cache-age, session cost, AgentParty bridge, relay
  balance, IP/fingerprint risk signals — Phase 7
- ✓ PyPI packaging + three entrypoints, `cs upgrade`, launchd/systemd service, plugin submission — Phase 8

### Active

<!-- Planned next work. Grounded in .planning/codebase/CONCERNS.md — the repo's own documented
     tech-debt / known-bug / missing-feature backlog. Not yet committed or started. -->

- [ ] Daemon health-check command (`cs daemon status`) surfaced in `cs doctor` — Phase 9
- [ ] Cache-repair command (`cs cache repair`) that validates and repairs corrupt cache files — Phase 9
- [ ] Diagnosable error handling: broad exception handlers log context before returning defaults — Phase 9
- [ ] Split monolithic `predict.py` / `core.py` into focused modules — Phase 9
- [ ] Prediction-store size-based compaction + regime-boundary / concurrent-daemon test coverage — Phase 9

### Out of Scope

<!-- Explicit boundaries with reasoning (from SPEC non-goals + codebase intel). -->

- Push / desktop notifications — on-bar signals only; forecast design keeps notifications separate.
- `$`-cost burn-rate signal, model burn-weight table, Fable-specific 7d bucket, session-departure
  detection — explicit non-goals of the burn-regime design.
- Non-git VCS support, remote URL / commit SHA in the identity segment — identity is git-only, minimal.
- Databases, servers, or a web/GUI frontend — this is a terminal ANSI status line.
- `.env` file reading — the tool reads environment variables only; never persists secrets.

## Context

- **Runtime**: Python ≥3.9, stdlib-only default (optional deps guarded). Runs primarily as a Claude
  Code `statusLine` command invoked ~60×/min; also a standalone CLI.
- **Performance regime**: The render is on a hot path. A fast thin client reads a daemon's
  pre-rendered `rendered.ansi`; on staleness it falls back to a full inline render. Heavy imports
  are deferred; transcripts are read via bounded reverse tail (≤320KB), never slurped.
- **State**: Local filesystem only — config at `~/.claude/claude-statusbar.json`; caches under
  `~/.cache/claude-statusbar/` (per-session dirs + account-keyed rate/projection stores).
- **Integrations**: Claude Code stdin payload (authoritative), PyPI (version check), ipify/ipapi.is
  (opt-in IP risk), OpenAI-compatible relay billing (opt-in balance), local AgentParty cache, local
  git. No external API calls on the synchronous render path.
- **Known fragile areas** (see CONCERNS.md): daemon lifecycle / cross-platform locking,
  account-switch handling, transcript parsing, and the prediction-store size growth.

## Constraints

- **Performance**: Fast-path render <~20ms, inline render <~100ms, daemon tick <~500ms — the bar
  refreshes ~60×/min and must never feel laggy or freeze.
- **Dependencies**: Zero required third-party packages; Python 3.9+ stdlib only on the render path —
  keeps install trivial and startup fast (optional `claude-monitor` runs only as a subprocess).
- **Compatibility**: macOS / Linux / Windows; Python 3.9–3.12 tested in CI.
- **Concurrency**: Single-threaded, file-backed state with atomic writes; per-session directory
  isolation so multiple Claude Code windows never collide.
- **Data source**: Rely only on Claude Code's official `statusLine` payload for quota/model/context;
  rate state is keyed by account UUID so account switches don't leak old limits.
- **Privacy**: No secrets written to disk or logs; network calls are read-only and mostly opt-in /
  background.

## Key Decisions

<!-- Design decisions embedded in the shipped SPECs / architecture. None are ADR-LOCKED (no ADRs in
     the ingest set); all are documented and shipped. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Dual-render pipeline: background daemon pre-renders, stdlib-only thin client reads cache, inline fallback | Keep the per-tick fast path <20ms while still computing rich data | ✓ Good |
| Zero required third-party dependencies (Python 3.9+ stdlib only) | Fast startup, trivial install, no supply-chain surface | ✓ Good |
| Bounded reverse tail-read of transcripts (≤320KB) | Never freeze the bar on multi-MB sessions | ✓ Good |
| Auto-detect prompt-cache TTL from `cache_creation` buckets | 5m/1h/override TTL is plan-level; hardcoding shows wrong COLD alerts | ✓ Good |
| Account-UUID-keyed rate-limit / projection state | Switching accounts must not show the previous account's 7d limits | ✓ Good |
| Forecast (⚠~ETA) and projection (→NN%) coexist as distinct signals on one `predict.py` | At-risk warning and always-on estimate serve different purposes | ✓ Good |
| Per-segment color ownership (no line-wide color bleed) | Each metric's severity must read independently | ✓ Good |
| Opt-in second status line for project/branch; git read from `.git/HEAD` + TTL dirty cache | Identity without a `git` subprocess on the render path | ✓ Good |
| Context re-introduced as an opt-out bar segment (supersedes earlier "context is noise") | Consistent bar idiom; user can still hide it via `show_context` | ✓ Good |
| Per-session (per-account) rate-limit store keying — resolve the account UUID from the session's OWN config dir (`transcript_path` → `CLAUDE_CONFIG_DIR` → `~/.claude`), reusing `account.py`; a named dir without its own `.claude.json` never borrows `$HOME`'s uuid (Phase 12, refines the earlier account-UUID-keyed decision) | Concurrent accounts share a clock-aligned 5h `resets_at`, so a single hardcoded-`~/.claude.json` store bucket + monotonic-up healing pinned account2's 5h bar to account1's 100% (live 2026-07-16) | ✓ Fixed (Phase 12) |

---
*Last updated: 2026-07-16 after Phase 12 (per-account rate-limit store isolation)*
