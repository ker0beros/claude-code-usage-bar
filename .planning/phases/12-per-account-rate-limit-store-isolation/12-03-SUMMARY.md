---
phase: 12-per-account-rate-limit-store-isolation
plan: 03
subsystem: api
tags: [core.py, account-isolation, rate-limit, wiring, render-path]

# Dependency graph
requires:
  - phase: 12-per-account-rate-limit-store-isolation (12-02)
    provides: predict.account_id(stdin=None, *, env=None, home=None) per-session resolver and account_uuid= params threaded through reconcile_account/projection/forecast/quota_cache_status
  - phase: 11-account-email-indicator
    provides: the never-raise, per-session resolution call convention (resolve_account_email at core.py:1171-1180) mirrored here for account_id
provides:
  - core.main() resolves _resolved_account_uuid once per render, guarded to never raise into the render path
  - account_uuid=_resolved_account_uuid threaded into all four predict.py store-consumer call sites (reconcile_account, projection, forecast, quota_cache_status)
  - The R3 regression test (test_two_accounts_share_5h_reset_render_own_values) flips GREEN — this was the final wiring piece Phase 12 needed
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: ["never-raise per-session resolution mirrored from the Phase 11 email-chip convention", "resolve-once-per-render, thread-by-keyword into every store consumer"]

key-files:
  created: []
  modified: [src/claude_statusbar/core.py]

key-decisions:
  - "Resolved _resolved_account_uuid once, immediately after _effective_env (core.py ~1065), rather than at each of the four call sites — matches the plan's explicit non-goal (do not re-resolve per call, would re-stat .claude.json unnecessarily)."
  - "Appended account_uuid=_resolved_account_uuid as the final keyword argument at all four call sites, changing nothing else in those call blocks, per the plan's explicit instruction."

patterns-established:
  - "Session-scoped resolution guarded in a bare try/except Exception, assigning None on any failure, placed as a standalone block right after the per-session env is computed — reusable template for any future per-session, daemon-safe resolver."

requirements-completed: [R2, R3]

coverage:
  - id: D1
    description: "core.main() resolves the session's account uuid once per render via predict.account_id(stdin_data, env=_effective_env), guarded so a resolution failure never raises into the render path"
    requirement: "R2"
    verification:
      - kind: unit
        ref: "python -c \"assert open('src/claude_statusbar/core.py').read().count('account_id(stdin_data') == 1\""
        status: pass
    human_judgment: false
  - id: D2
    description: "account_uuid=_resolved_account_uuid threaded into all four predict.py store-consumer call sites: reconcile_account, projection, forecast, quota_cache_status"
    requirement: "R2"
    verification:
      - kind: unit
        ref: "python -c \"assert open('src/claude_statusbar/core.py').read().count('account_uuid=_resolved_account_uuid') == 4\""
        status: pass
    human_judgment: false
  - id: D3
    description: "Two accounts logged in concurrently with an identical 5h resets_at each render their OWN 5h value (account1 100%, account2 50%) — the live cross-account collision is closed"
    requirement: "R3"
    verification:
      - kind: e2e
        ref: "tests/test_account_rate_isolation.py::test_two_accounts_share_5h_reset_render_own_values"
        status: pass
    human_judgment: false
  - id: D4
    description: "Manual FAILS-pre-fix / PASSES-post-fix proof: with core.py reverted to its pre-12-03 state (git checkout), the regression test fails with out2 showing '100%' instead of '50%'; restoring the wiring flips it green"
    requirement: "R3"
    verification:
      - kind: manual_procedural
        ref: "git checkout -- src/claude_statusbar/core.py; pytest test_two_accounts_share_5h_reset_render_own_values (RED, confirmed AssertionError showing 100% in out2); git apply <saved diff> (GREEN)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Full suite green with zero regressions (1090 baseline + 12 new = 1102), single-account/no-transcript render byte-for-byte unchanged"
    verification:
      - kind: unit
        ref: "pytest tests/ -q (run with CLAUDE_CONFIG_DIR unset — see Known Issue below)"
        status: pass
    human_judgment: false

duration: ~12min
completed: 2026-07-16
status: complete
---

# Phase 12 Plan 03: core.py Per-Session Account Uuid Wiring Summary

**core.main() now resolves the session's own account uuid once per render (guarded, never-raise) and threads it into reconcile_account/projection/forecast/quota_cache_status, closing the live cross-account 5h rate-limit collision — the R3 e2e regression test is confirmed GREEN post-fix and RED pre-fix via a manual git-revert proof.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-16T09:33:00Z
- **Completed:** 2026-07-16T09:45:11Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added a guarded, one-time `_resolved_account_uuid = predict.account_id(stdin_data, env=_effective_env)` resolution immediately after `_effective_env` (core.py ~1065), wrapped in `try/except Exception: _resolved_account_uuid = None`, mirroring the Phase 11 email-chip's never-raise convention exactly.
- Threaded `account_uuid=_resolved_account_uuid` into all four predict.py store consumers: `reconcile_account` (~1424), `projection` (~1500), `forecast` (~1517), and `quota_cache_status` (~1572) — every other argument in those call blocks left untouched.
- Flipped `test_two_accounts_share_5h_reset_render_own_values` GREEN — the phase's terminal R3 acceptance criterion.
- Performed the plan's literal manual "FAILS pre-fix, PASSES post-fix" proof: reverted core.py to its pre-12-03 committed state via `git checkout --`, confirmed the regression test fails (`out2` wrongly showed `100%` instead of `50%`), then restored the fix via `git apply` on a saved diff and confirmed it passes.
- Full suite: 1102 passed (1090 baseline + 12 new isolation tests), zero regressions.

## Task Commits

Each task was committed atomically:

1. **Task 1: Resolve session account uuid once and thread it into all four predict call sites; prove the regression green** - `1ada591` (feat)

**Plan metadata:** (this commit, immediately following)

## Files Created/Modified
- `src/claude_statusbar/core.py` - Added the guarded `_resolved_account_uuid` resolution block after `_effective_env`; appended `account_uuid=_resolved_account_uuid` to the `reconcile_account`, `projection`, `forecast`, and `quota_cache_status` call sites.

## Decisions Made
- Resolved the uuid exactly once per render (not per call site), per the plan's explicit budget constraint — avoids re-stat'ing `.claude.json` up to four times per render.
- No new imports beyond the existing `from .predict import ...` pattern already used at each call site; the resolver import (`from .predict import account_id as _predict_account_id`) is scoped locally inside the guarded block, matching the local-import style already used throughout `core.main()`.

## Deviations from Plan

None - plan executed exactly as written. The task's action, verification, and acceptance criteria were followed literally: one resolution block, four keyword-argument additions, no other changes to the four call blocks.

## Issues Encountered

**Ambient `CLAUDE_CONFIG_DIR` in the execution shell caused 2 pre-existing tests to fail — not a code regression.**

This executor's shell has `CLAUDE_CONFIG_DIR=/Users/khairulazmi/.claude-account2` exported (the maintainer's own multi-account Claude Code setup, per project memory). Before this plan, `core.py` never consulted `CLAUDE_CONFIG_DIR` when keying `reconcile_account`'s store path — only this session's per-session resolver now does, by design (that's precisely R1/R2's intended fix). Two tests in `tests/test_regime_detection.py` (`test_core_main_passes_model_into_regime_detection`, `test_core_main_passes_session_id_into_sessions_map`) don't pass `_session_env` in their payload and don't `delenv("CLAUDE_CONFIG_DIR", ...)` (they do delenv `ANTHROPIC_BASE_URL`/`CS_API_MODE`, but not this var), so `_effective_env` falls back to the real `os.environ` — which, in this specific shell, points `resolve_config_dir` at a real account directory with its own `.claude.json`, causing `reconcile_account` to write to a suffixed store path the tests never check (`rate_latest.json` unsuffixed, not found → `FileNotFoundError`).

- **Confirmed root cause:** `env -u CLAUDE_CONFIG_DIR .venv/bin/python -m pytest tests/test_regime_detection.py -q` → 13/13 passed. `env -u CLAUDE_CONFIG_DIR .venv/bin/python -m pytest tests/ -q` → 1102/1102 passed, zero regressions.
- **Not fixed:** this plan's `files_to_read`/wave-boundary note explicitly scopes `files_modified` to `src/claude_statusbar/core.py` only and instructs "Do NOT modify predict.py or the tests." Adding `monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)` to those two tests would be the correct long-term fix (any developer/CI environment with this variable set will see the same spurious failure), but is out of scope for this plan's declared file boundary.
- **Recommendation for a future quick task:** add `monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)` to `tests/test_regime_detection.py`'s two affected tests (and audit other tests that read real `os.environ` without isolating this var), since this phase's whole point is that `CLAUDE_CONFIG_DIR` now legitimately affects render-path keying.
- **Verification used throughout this plan:** all pytest runs quoted in this SUMMARY and used for the plan's acceptance criteria were run with `CLAUDE_CONFIG_DIR` unset (`env -u CLAUDE_CONFIG_DIR ...`), representative of a clean/CI environment.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 12 is functionally complete: predict.py's per-session keying (12-02) and core.py's wiring (12-03) together close the live cross-account 5h rate-limit collision.
- The R3 regression test is proven both GREEN post-fix and RED pre-fix (manual proof performed this session).
- Full suite green (1102/1102) in a clean environment; no regressions to the 1090-test baseline.
- Known env-isolation gap in `tests/test_regime_detection.py` (2 tests don't isolate `CLAUDE_CONFIG_DIR`) is flagged above as a candidate quick-task follow-up — does not block phase completion since it's a test-isolation gap, not a code defect, and doesn't manifest in a clean environment.

---
*Phase: 12-per-account-rate-limit-store-isolation*
*Completed: 2026-07-16*

## Self-Check: PASSED
- FOUND: src/claude_statusbar/core.py
- FOUND commit: 1ada591 (Task 1)
- FOUND commit: 2f69511 (SUMMARY docs commit)
