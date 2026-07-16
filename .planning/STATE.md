---
gsd_state_version: 1.0
milestone: v3.29.11
milestone_name: milestone
current_phase: 9
current_phase_name: Reliability & Maintainability Hardening (Planned)
status: planning
stopped_at: "Phase 12 complete & verified — per-account rate-limit store isolation (5h bar now per-account, not cross-account-max); autonomous --from 12 run finished. Phase 9 (Hardening) remains planned."
last_updated: "2026-07-16T10:04:15.267Z"
last_activity: 2026-07-16
last_activity_desc: "Phase 12 complete (per-account rate-limit store isolation) — 3/3 plans, code review clean, verification passed 10/10, full suite 1102 passing with ambient CLAUDE_CONFIG_DIR. Transitioned to Phase 9 (planned)."
progress:
  total_phases: 12
  completed_phases: 11
  total_plans: 3
  completed_plans: 3
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-16)

**Core value:** At-a-glance rate-limit / context / model / cost visibility in the Claude Code status line — fast, within budget, zero required deps.
**Current focus:** Phase 12 complete (per-account rate-limit store isolation, implemented & unreleased). Phase 9 — Reliability & Maintainability Hardening — remains the only planned, not-started phase.

## Current Position

Phase: 9 — Reliability & Maintainability Hardening (Planned)
Plan: Not started
Status: Ready to plan
Last activity: 2026-07-16 — Phase 12 complete, transitioned to Phase 9

Progress: [█████████░] 92% (11 of 12 phases complete; Phase 6, 10, 11 & 12 implemented & verified, unreleased; Phase 9 the only planned/not-started phase)

## Performance Metrics

**Velocity:**

- Total plans completed: 3 (Phase 6, GSD-tracked; delivered Phases 1–5/7/8 predate GSD tracking — brownfield ingest)
- Average duration: ~25min (3 data points)
- Total execution time: ~75min (GSD-tracked)

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1–5, 7, 8 (delivered) | not GSD-tracked | - | - |
| 6 (complete) | 3 of 3 done | ~75min | ~25min |
| 9 (planned) | TBD | - | - |
| 12 | 3 | - | - |

**Recent Trend:**

- Last 5 plans: 06-02 (20min), 06-03 (35min)
- Trend: Stable

*Updated after each plan completion*

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 06 P02 | 20min | 2 tasks | 2 files |
| Phase 06 P03 | 35min | 2 tasks | 4 files (+2 created) |
| Phase 12 P01 | 25min | 2 tasks | 1 files |
| Phase 12 P02 | 20min | 2 tasks | 2 files |
| Phase 12 P03 | 12min | 1 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. Recent decisions affecting current work:

- Dual-render pipeline (daemon + stdlib-only thin client) — keeps the per-tick fast path <20ms.
- Zero required third-party dependencies (Python 3.9+ stdlib only) on the render path.
- Forecast (⚠~ETA) and projection (→NN%) coexist as distinct signals on one predict module.
- Rate/projection state keyed by account UUID; transcripts read via bounded reverse tail (≤320KB).
- (06-02) The quota-mode ctx segment reuses the exact no-quota ctx-rendering code path via shared helpers (`_context_dimension()` in progress.py; `ctx_pill()`/`ctx_segment()` closures in styles.py) rather than parallel copies, so quota and no-quota modes are byte-identical by construction.
- (06-03) core.py's official-quota and waiting branches gate the `(used/size)` model suffix on `cfg.show_context` (append only when off) and pass `show_context=cfg.show_context` into every `_render_style` call; `preview.py` mirrors the same gating and computes `ctx_pct` so `cs preview` matches the live status line.
- (260715-jbf) `show_projection`/`show_forecast` now default off (config-only flip; `predict.py` and both toggles untouched). All three usage bars (5h/7d/ctx) now share one unified 65/85 color band via `progress.py`'s four band constants, reusing the existing severity helpers with no new coloring logic.
- (260715-lm1) Reset-timer `⏰` countdowns now color by **elapsed % of the window** on a fixed 65/85 band that is the timer's OWN (`TIMER_WARNING_THRESHOLD`/`TIMER_CRITICAL_THRESHOLD` in `progress.py`, never the bar's configurable thresholds). Polarity flips per window: 5h FLIPPED (near reset → green, fresh quota imminent), 7d NORMAL (near reset → red, week running out). One shared helper `timer_severity_rgb(elapsed_pct, *, flip, theme)` drives classic/capsule/hairline + preview; bar fill/label and the ✨/⚡/🎉 emoji untouched; core computes elapsed% in the quota branch only (waiting/stale/custom-reset_hour fall back to prior color).
- (260715-pic) Opt-in `show_search_credits` (default off) surfaces remaining API credits for search providers as per-provider mini fuel-gauge bars (`fc` Firecrawl, `tv` Tavily), each shown only when its env key (`FIRECRAWL_API_KEY`/`TAVILY_API_KEY`) is present. New `provider_usage.py` + `_provider_usage_refresh.py` clone the ip_risk opt-in signal + balance_cache mechanics: render path reads cache only and NEVER touches the network; a detached `urllib` prober (Firecrawl `/v2/team/credit-usage`, Tavily `/usage`, Bearer auth) is the sole spawn path (TTL 300s/neg 3600s/inflight 60s), keys fingerprinted (sha1, never on disk). Reuses `_build_dimension`/`_balance_fill_rgb` (25/10 remaining thresholds); wired into all 4 `_render_style` branches + daemon heartbeat. Stdlib-only, zero new deps. Exa deferred (no remaining-balance API). **Fast follow-up fix:** `core.main()`'s search block now sources the provider keys from `os.environ` (not `_effective_env`) — the per-session env deliberately omits secrets (persisted to disk), so reading it left `segments()` blind to `FIRECRAWL_API_KEY`/`TAVILY_API_KEY` and the bars never rendered live; `os.environ` matches the daemon heartbeat and keeps keys off disk. Regression test drives the full `core.main()` daemon-path render (key only in `os.environ`, `_cs_env` lacking it) — the render-layer tests couldn't catch it.
- (relay-balance env fix) The shipped relay-balance gauge (`show_balance`, ENRICH-01) had the **same latent env-sourcing bug**: `relay_balance()` read `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` via plain `env.get()` from the per-session env, which omits secrets → the guard tripped → the `bal $…` gauge never rendered under the shared daemon. Fixed by falling those secrets back to `os.environ` (the documented pattern at `core.py:704-714`), while **`base_url` stays session-only** (never falls back — a non-relay session must not inherit the daemon's base and wrongly show a gauge). 2 regression tests guard both halves. Operational note (both fixes): the daemon must be started in a shell with the relevant keys exported (or restarted after exporting) since it reads `os.environ` frozen at start.
- [Phase ?]: (12-01) test_predict_module_imports_no_network_or_subprocess bans {subprocess, socket, urllib.request} not bare urllib — pathlib transitively pulls in network-free urllib.parse on this Python version, unrelated to predict.py.
- [Phase ?]: (12-01) e2e regression test computes its shared 5h resets_at as time.time()+3600 instead of the SPEC-literal historical epoch, so reconcile_account's anti-poison reset-plausibility guard never rejects it regardless of run date — keeps the FAILS-pre-fix proof deterministic.
- [Phase ?]: [Rule 1] Relaxed _read_keyed_account_id's uuid regex bound to {1,64} (legacy reader's {8,64} unchanged) to accept short test-fixture uuids
- [Phase ?]: [Rule 3] Fixed tests/conftest.py's autouse account_id stub to pass through to the real resolver for stdin-bearing calls, preserving the zero-arg pin
- [Phase ?]: (12-03) core.main() resolves _resolved_account_uuid once (guarded, never-raise) after _effective_env and threads it into reconcile_account/projection/forecast/quota_cache_status; the R3 e2e regression test is GREEN post-fix / RED pre-fix (manual proof performed).
- [Phase ?]: (12-03) Flagged (not fixed, out-of-scope per plan's file boundary): tests/test_regime_detection.py's 2 core.main() tests don't isolate CLAUDE_CONFIG_DIR, causing spurious failures on any machine with it exported — recommend a follow-up quick task adding monkeypatch.delenv.

### Quick Tasks Completed

| Task ID | Date | Summary | Commits |
|---------|------|---------|---------|
| 260715-jbf | 2026-07-15 | Projection/forecast chips default-off; standardized 5h/7d/ctx bars to one 65/85 color band | 3cd54f7, 2b36824, 1dacffc |
| 260715-lm1 | 2026-07-15 | Reset-timer countdowns color by elapsed% on a fixed 65/85 band (5h flipped green-when-fresh, 7d normal red-when-late), decoupled from the bar's thresholds; 34 new tests | b28e836, c2427d5, 79bcd6d |
| 260715-pic | 2026-07-15 | Opt-in search-provider credit bars (Firecrawl `fc` + Tavily `tv`), default off; detached prober + TTL/negative cache clones ip_risk + balance_cache; render path never touches the network; 52 new tests | 3640e0e, 3dee232, 9265e55 |
| 260715-ux9 | 2026-07-15 | Moved fc/tv search-credit bars onto their own status-line row directly below the primary quota bar, each style in its own idiom (classic batteries · capsule/hairline pills); cache-age stays on the quota line; empty/None → no blank row; placement + cache-line-guard tests added | ea46202, 1605f6b |

### Pending Todos

None yet.

### Roadmap Evolution

- Phase 12 added (2026-07-16): Per-Account Rate-Limit Store Isolation. Diagnosed live — the 5h bar showed 100% on account2 (real 50%) because `predict._read_account_id()` hardcodes `~/.claude.json` and ignores `CLAUDE_CONFIG_DIR`, collapsing all logged-in accounts into one shared reconcile store; the clock-aligned 5h window makes accounts share a `resets_at` bucket, and monotonic-up healing pins it to account1's 100%. Fix: key the store per-session via account.py's resolver. Depends on Phase 5 + Phase 11.
- Phase 12 COMPLETE (2026-07-16): shipped the fix — `predict.account_id(stdin, env=, home=)` resolves the uuid from the session's own config dir (reusing `account.resolve_config_dir()`), a `_UNSET` sentinel tri-states `_account_path` (omitted→legacy hardcoded / explicit `None`→legacy unsuffixed no-borrow / uuid→suffixed), a path-keyed `_SESSION_ACCOUNT_CACHE`, and an R5b-strict keying reader that never borrows `$HOME/.claude.json` for a named dir. Threaded `account_uuid` through reconcile/forecast/projection/quota_cache_status **plus the two hidden landmines** `regime_changed_at()` and `_projection_result_key()`; core.py resolves it once per render. Both `rate_latest.*` and `rate_projection.*` re-keyed; fix-forward (no store migration). +12 isolation tests incl. the e2e collision regression (proven FAILS-pre-fix / PASSES-post-fix); conftest autouse fixture now neutralizes `CLAUDE_CONFIG_DIR` so the suite is hermetic in the maintainer's multi-account shell. Full suite 1102 passing.

### Blockers/Concerns

From .planning/codebase/CONCERNS.md — these motivate Phase 9:

- Daemon lifecycle / cross-platform locking is fragile (TOCTOU spawn dedup on Windows fallback path).
- `predict.py` (~1200 lines) and `core.py` (~1531 lines) are monolithic and hard to test.
- Prediction store can grow to 300KB+, adding to render startup cost.
- Broad `except Exception:` / bare `except:` handlers swallow errors silently (hard to diagnose).
- No daemon health-check or cache-repair command; stale output can look current for up to ~5s.

## Deferred Items

Items acknowledged and carried forward:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Hardening | Daemon health-check + cache-repair commands (HARD-01/02) | Planned (Phase 9) | 2026-07-15 |
| Hardening | Error-handler logging + module splits (HARD-03/04/05) | Planned (Phase 9) | 2026-07-15 |
| Search credits | Exa credit bar — no remaining-balance API (dashboard-only); needs a user-entered starting balance/limit + polled spend subtraction, or a spend-only chip | Deferred | 2026-07-15 |
| Search credits | Reset-countdown for Firecrawl `billingPeriodEnd` (could reuse the reset-timer elapsed% coloring work, 260715-lm1) | Deferred | 2026-07-15 |

## Session Continuity

Last session: 2026-07-16
Stopped at: Phase 12 (Per-Account Rate-Limit Store Isolation) COMPLETE & verified via autonomous `--from 12` run — discuss → research → plan (3 plans) → execute (3 waves) → code review (clean) → verification (passed 10/10). predict.py + core.py now key the reconcile/projection stores by the session's own account; the live account2-shows-100% collision is closed. +12 tests, full suite 1102 passing with ambient CLAUDE_CONFIG_DIR. Milestone lifecycle NOT run — Phase 9 (Hardening) is still planned, so the milestone is not complete. Pushed to origin/main 2026-07-16 (Phase 11 + Phase 12, `11dae5f..764cbbe`).

Prior session: 2026-07-15
Stopped at: Completed quick task 260715-pic (opt-in Firecrawl+Tavily search-provider credit bars), then two fast env-sourcing fixes for the shared-daemon render path: (1) search block sources provider keys from os.environ; (2) relay_balance() falls back to os.environ for ANTHROPIC_API_KEY/AUTH_TOKEN (base_url stays session-only) so the bal $… gauge renders live. +3 regression tests total, full suite 1024 passed (1 pre-existing version_sync failure deferred).
Resume file: None
