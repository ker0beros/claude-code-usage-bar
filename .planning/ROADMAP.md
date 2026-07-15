# Roadmap: Claude Status Bar

## Overview

Claude Status Bar is an existing, shipped product (**v3.29.11**). This roadmap reverse-maps the
delivered feature areas — from the ingested SPECs and the mapped codebase — into seven completed
phases (the delivered milestone), plus **one active phase (Phase 6)** whose SPEC is written but
not yet implemented, then leaves the roadmap open with one planned hardening phase drawn from the
repo's own documented backlog (`.planning/codebase/CONCERNS.md`). Phases 1–5, 7, 8 are already TRUE
in the product; Phase 6 (context-window bar in quota mode) is the current in-progress work; Phase 9
is candidate future work, not yet started.

## Milestones

- ✅ **v3.29.11 Delivered** — Phases 1–5, 7, 8 (shipped, current)
- 🔨 **Active** — Phase 6 (Context Window Bar in Quota Mode) — SPEC written, implementation in progress
- 📋 **Hardening (Planned)** — Phase 9 (candidate, from documented concerns)

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Foundation & Render Pipeline** - Fast dual-render pipeline, daemon, cache, setup, config
- [x] **Phase 2: Rate-Limit Focused Status Bar** - Dual 5h/7d color-coded progress bars with timer + model
- [x] **Phase 3: Multi-Style Rendering & Theming** - Classic/capsule/hairline styles, nine themes, per-segment color
- [x] **Phase 4: Project & Branch Identity Segment** - Opt-in second line with cached git branch + dirty marker
- [x] **Phase 5: Rate-Limit Prediction & Learning** - ⚠~ETA chip, always-on →NN% projection, burn-regime detection
- [ ] **Phase 6: Context Window Bar in Quota Mode** - Context as a bar segment per style with severity bands (ACTIVE — in progress)
- [x] **Phase 7: Live Activity, Local Bridges & Safety Signals** - Activity, cost, AgentParty, relay balance, IP risk
- [x] **Phase 8: Distribution, Packaging & Auto-Update** - PyPI packaging, upgrade, launchd/systemd, plugin submission
- [ ] **Phase 9: Reliability & Maintainability Hardening (Planned)** - Health-check/repair commands, error visibility, module splits

## Phase Details

<details>
<summary>✅ v3.29.11 Delivered (Phases 1–8) — SHIPPED</summary>

### Phase 1: Foundation & Render Pipeline

**Goal**: The status line renders fast and reliably on every Claude Code tick, backed by a daemon fast path with safe fallbacks.
**Depends on**: Nothing (first phase)
**Requirements**: CORE-01, CORE-02, CORE-03, CORE-04, CORE-05, CORE-06, CORE-07, CORE-08
**Success Criteria** (what must be TRUE):

  1. The status line updates on every Claude Code refresh, with the fast path returning well within the refresh budget.
  2. `cs`, `cstatus`, and `claude-statusbar` all invoke the tool; `cs --setup` wires the statusLine hook idempotently.
  3. Multiple Claude Code windows render independently, and a stale/dead daemon falls back to inline render with no frozen bar.
  4. Malformed stdin, a missing transcript, or corrupt config never crash the render — the bar always prints something.
  5. `cs doctor` reports binary/settings/daemon/config health; the tool installs with zero required third-party dependencies.

**Plans**: Delivered (not GSD-tracked)

### Phase 2: Rate-Limit Focused Status Bar

**Goal**: Developers see 5h and 7d rate-limit usage as color-coded progress bars with reset timer and active model.
**Depends on**: Phase 1
**Requirements**: QUOTA-01, QUOTA-02, QUOTA-03, QUOTA-04, QUOTA-05
**Success Criteria** (what must be TRUE):

  1. The bar shows independent 5h and 7d usage percentages as filled/empty blocks.
  2. Each bar is colored by its own percentage (green <30, yellow 30–70, red >70).
  3. The reset timer and active model name appear alongside the bars.
  4. Extreme states render correctly: >100% shows full-red `100%+`, unavailable shows dimmed `--%`, any usage >0 shows ≥1 filled block.
  5. A bypass indicator appears when permission-skip / bypass mode is active.

**Plans**: Delivered (not GSD-tracked)

### Phase 3: Multi-Style Rendering & Theming

**Goal**: Developers can choose among three layout styles and nine themes, with each segment colored by its own severity.
**Depends on**: Phase 2
**Requirements**: STYLE-01, STYLE-02, STYLE-03, STYLE-04, STYLE-05
**Success Criteria** (what must be TRUE):

  1. The same metrics render in classic, capsule, and hairline styles.
  2. Any of nine built-in themes (or a custom hex) can be selected via config or env var.
  3. No color bleed — each segment (5h, 7d, context, cache) owns its own severity color.
  4. The classic style honors the active theme's colors instead of raw ANSI.
  5. `cs preview` shows every style × theme combination.

**Plans**: Delivered (not GSD-tracked)

### Phase 4: Project & Branch Identity Segment

**Goal**: Developers can optionally see the current project and git branch as a second status line without slowing the render.
**Depends on**: Phase 3
**Requirements**: IDENT-01, IDENT-02, IDENT-03, IDENT-04
**Success Criteria** (what must be TRUE):

  1. Enabling the option shows a second line with project name and git branch.
  2. A dirty marker appears when the working tree has changes, sourced from a cached git read (no `git` subprocess on the render path).
  3. Outside a git repo the segment collapses to `(no git)`.
  4. The segment renders in all three styles and respects the active theme.

**Plans**: Delivered (not GSD-tracked)

### Phase 5: Rate-Limit Prediction & Learning

**Goal**: Developers get both an at-risk exhaustion warning and an always-on end-of-window projection that improves with use.
**Depends on**: Phase 2
**Requirements**: PREDICT-01, PREDICT-02, PREDICT-03, PREDICT-04, PREDICT-05
**Success Criteria** (what must be TRUE):

  1. A `⚠~ETA` chip appears next to a window's timer only when that window is projected to hit 100% before it resets.
  2. An always-on `→NN%` projection shows expected usage at reset for each window, working from a cold start.
  3. The projection collects local history, improves with observation, and stores snapshots so its accuracy is measurable.
  4. After a model or fleet burn-rate switch, the estimate re-anchors onto the new regime instead of chasing the old one.
  5. The at-risk chip and the always-on projection coexist as distinct signals.

**Plans**: Delivered (not GSD-tracked)

### Phase 7: Live Activity, Local Bridges & Safety Signals

**Goal**: Developers see live session activity, cost, and optional local/account context without blocking the render.
**Depends on**: Phase 1
**Requirements**: LIVE-01, LIVE-02, LIVE-03, LIVE-04, LIVE-05, ENRICH-01, ENRICH-02
**Success Criteria** (what must be TRUE):

  1. The bar surfaces the in-progress todo, running tool, and active subagents parsed from the transcript via a bounded tail-read.
  2. A prompt-cache age countdown shows with an auto-detected TTL, and session cost is displayed.
  3. When AgentParty is active for the session, its channel/identity/unread status appears from the local cache and never leaks another session's state.
  4. On a third-party relay an account-balance gauge appears; optional IP / fingerprint risk signals surface when enabled.

**Plans**: Delivered (not GSD-tracked)

### Phase 8: Distribution, Packaging & Auto-Update

**Goal**: Developers can install, upgrade, and run the tool as a managed background service across platforms.
**Depends on**: Phase 1
**Requirements**: DIST-01, DIST-02, DIST-03, DIST-04
**Success Criteria** (what must be TRUE):

  1. The package installs from PyPI via pip/uv/pipx and exposes the `cs` / `cstatus` / `claude-statusbar` entrypoints.
  2. `cs upgrade` detects the install channel and updates; a background PyPI version check runs at most once per day.
  3. The daemon can install as a launchd (macOS) or systemd (Linux) service.
  4. The tool is packaged as a Claude Code statusLine plugin (`plugin.json`), with launch/marketing materials prepared.

**Plans**: Delivered (not GSD-tracked)

</details>

### 🔨 Active

### Phase 6: Context Window Bar in Quota Mode

**Goal**: Developers see context-window fill as a bar segment consistent with the rest of the status line.
**Depends on**: Phase 3
**Requirements**: CTX-01, CTX-02, CTX-03
**Success Criteria** (what must be TRUE):

  1. In quota mode, context renders as a bar segment in each style's idiom (not just a suffix on the model name).
  2. Context severity shows yellow at ≥70% and red at ≥85%.
  3. The `show_context` toggle (default on) controls it; quota and no-quota modes render context identically.

**Plans**: 2/3 plans executed. SPEC: `docs/superpowers/specs/2026-07-15-context-bar-quota-mode-design.md`

- [x] 06-01-PLAN.md — show_context config toggle (field, persistence, `cs config show`) [Wave 1]
- [x] 06-02-PLAN.md — per-style ctx bar/pill/mini-bar renderers + severity band [Wave 1]
- [ ] 06-03-PLAN.md — core + preview integration (drop model suffix, thread show_context) [Wave 2]

### 📋 Hardening (Planned)

**Milestone Goal:** Harden the fragile areas the codebase already documents — daemon lifecycle,
error visibility, and the prediction store — and split the monolithic modules for maintainability.

### Phase 9: Reliability & Maintainability Hardening (Planned)

**Goal**: Make failures diagnosable and the hot modules maintainable, closing the documented reliability gaps.
**Depends on**: Phases 1–8 (delivered)
**Requirements**: HARD-01, HARD-02, HARD-03, HARD-04, HARD-05
**Success Criteria** (what must be TRUE):

  1. `cs daemon status` reports whether the daemon is alive and recent, and `cs doctor` incorporates the result.
  2. `cs cache repair` validates cache files, repairs or quarantines corrupt ones, and reports what changed.
  3. Broad exception handlers log context before returning a default, so silent render failures become diagnosable.
  4. `predict.py` and `core.py` are split into focused modules with regime-boundary and concurrent-daemon test coverage.

**Plans**: TBD

## Progress

**Execution Order:**
Phases 1–8 are delivered (shipped in v3.29.11). Phase 9 is planned and not started.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation & Render Pipeline | v3.29.11 | Delivered | Complete | 2026-07-15 |
| 2. Rate-Limit Focused Status Bar | v3.29.11 | Delivered | Complete | 2026-03-25 |
| 3. Multi-Style Rendering & Theming | v3.29.11 | Delivered | Complete | 2026-05-07 |
| 4. Project & Branch Identity Segment | v3.29.11 | Delivered | Complete | 2026-05-21 |
| 5. Rate-Limit Prediction & Learning | v3.29.11 | Delivered | Complete | 2026-07-02 |
| 6. Context Window Bar in Quota Mode | Active | 2/3 | In Progress | - |
| 7. Live Activity, Local Bridges & Safety Signals | v3.29.11 | Delivered | Complete | 2026-07-15 |
| 8. Distribution, Packaging & Auto-Update | v3.29.11 | Delivered | Complete | 2026-07-15 |
| 9. Reliability & Maintainability Hardening | Hardening | 0/TBD | Not started | - |
