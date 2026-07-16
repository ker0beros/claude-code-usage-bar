---
phase: 12-per-account-rate-limit-store-isolation
verified: 2026-07-16T18:20:00Z
status: passed
score: 10/10 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification: null
---

# Phase 12: Per-Account Rate-Limit Store Isolation Verification Report

**Phase Goal:** The rate-limit reconcile store AND projection store are keyed by the *session's own* Claude account (resolved daemon-safe from `transcript_path` → `CLAUDE_CONFIG_DIR` → `~/.claude`), so multiple simultaneously logged-in accounts (via `CLAUDE_CONFIG_DIR`) never share a store bucket — each window's 5h/7d bars reflect only its own account's usage.
**Verified:** 2026-07-16T18:20:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | R1: `predict.account_id(stdin, env=, home=)` resolves the uuid from `transcript_path` over `~/.claude.json` | ✓ VERIFIED | `src/claude_statusbar/predict.py:159-183` — `account_id()` with `stdin is None` keeps legacy path; with `stdin` given, calls `account.resolve_config_dir()` (transcript-first) then `_claude_json_path_for_keying`/`_read_keyed_account_id`. `tests/test_account_rate_isolation.py::test_account_id_resolves_from_transcript_over_home_json` PASSES (ran directly: `.venv/bin/python -m pytest tests/test_account_rate_isolation.py -q` → 12 passed) |
| 2 | R2/R3: e2e regression `test_two_accounts_share_5h_reset_render_own_values` PASSES post-fix and FAILS pre-fix | ✓ VERIFIED | Independently reproduced (not just trusting the SUMMARY): checked out pre-12-02/03 `predict.py`/`core.py`/`conftest.py` via `git show 7066173:...`, ran the single test — FAILED with `AssertionError: assert '50%' in '5h[███100%███]...'` (the exact live symptom). Restored current files (`git diff --stat` empty afterward), re-ran — 12 passed. |
| 3 | R4: both `_latest_path()` and `_projection_path()` carry the per-session uuid | ✓ VERIFIED | `predict.py:201-206` — `_latest_path(aid=_UNSET)`/`_projection_path(aid=_UNSET)` both forward to `_account_path`, which appends `aid[:12]` to the filename stem. `test_store_paths_carry_session_uuid` PASSES. |
| 4 | R5a: unresolvable session → legacy unsuffixed path | ✓ VERIFIED | `predict.py:186-198` `_account_path`: explicit `None` → `return base` (unsuffixed). `test_unresolvable_session_uses_legacy_path` PASSES. |
| 5 | R5b: named dir without own `.claude.json` → legacy path, NOT `$HOME/.claude.json`'s uuid (no borrow) | ✓ VERIFIED | `predict.py:110-125` `_claude_json_path_for_keying`: home-level file consulted ONLY when `config_dir == home/".claude"`; contrasted against `account._claude_json_path` (`account.py:81-94`) which unconditionally falls back to `home/.claude.json` for ANY dir — confirmed predict.py's locator does NOT reuse that unconditional fallback. `test_named_dir_without_own_json_does_not_borrow_home` PASSES. |
| 6 | Prohibition: only `accountUuid` read, no secret | ✓ VERIFIED | `predict.py:128-156` `_read_keyed_account_id` — regex anchored to `oauthAccount` → `accountUuid` only. `test_keying_reader_reads_only_account_uuid` PASSES (decoy `accessToken`/`emailAddress` never leak). |
| 7 | Prohibition: no destructive fs op on existing stores | ✓ VERIFIED | `test_no_destructive_fs_ops_on_existing_stores` PASSES — monkeypatches `os.unlink`/`os.replace`/`Path.rename` and asserts no call targets a pre-existing differently-named store file; `reconcile_account`'s own path-selection line change (predict.py:465) is the only touched line, healing algorithm untouched. |
| 8 | Prohibition: no network/subprocess import | ✓ VERIFIED | `grep -n "^import\|^from" src/claude_statusbar/predict.py` shows only `json, math, os, datetime, pathlib, typing` (stdlib, no `subprocess`/`socket`/`urllib.request`). `test_predict_module_imports_no_network_or_subprocess` PASSES. |
| 9 | Full suite passes WITH ambient `CLAUDE_CONFIG_DIR` set | ✓ VERIFIED | Ran directly in this shell (which has `CLAUDE_CONFIG_DIR=/Users/khairulazmi/.claude-account2` ambiently set, confirmed via `echo $CLAUDE_CONFIG_DIR`): `.venv/bin/python -m pytest tests/ -q` → **1102 passed**. The `tests/conftest.py` hermeticity fix (`monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)`, commit `9e8420d`) neutralizes the var in the autouse fixture, confirmed present in the current file. |
| 10 | Single-account / no-`.planning` render unchanged | ✓ VERIFIED | `.venv/bin/python -m pytest tests/test_account_switch.py tests/test_regime_detection.py tests/test_core_projection.py tests/test_core_forecast_guard.py -q` → 25 passed, zero regressions. Byte-identical single-account render path confirmed by code review (12-REVIEW.md) and unit test `test_same_account_two_dirs_shares_store`. |

**Score:** 10/10 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/claude_statusbar/predict.py` | `_UNSET`, `_SESSION_ACCOUNT_CACHE`, `_claude_json_path_for_keying`, `_read_keyed_account_id`, new `account_id(stdin=None,*,env,home)`, tri-state `_account_path`/`_latest_path`/`_projection_path`, `account_uuid` threaded through `reconcile_account`/`forecast`/`projection`/`quota_cache_status`/`_projection_result_key`, `regime_changed_at` landmine fix | ✓ VERIFIED | All symbols confirmed present at exact expected lines (79, 86, 110, 128, 159, 186, 201, 205, 387, 439, 631, 1172, 1258, 1283) |
| `src/claude_statusbar/core.py` | `_resolved_account_uuid` resolved once (guarded), threaded into 4 call sites | ✓ VERIFIED | `core.py:1071-1075` guarded resolution; `account_uuid=_resolved_account_uuid` at lines 1439 (reconcile_account), 1518 (projection), 1535 (forecast), 1585 (quota_cache_status) — exactly 4 occurrences, exactly 1 `account_id(stdin_data` call site (line 1073) |
| `tests/test_account_rate_isolation.py` | 12 tests + 3 helpers | ✓ VERIFIED | `--collect-only` lists all 12 node-ids; `pytest tests/test_account_rate_isolation.py -q` → 12 passed |
| `tests/conftest.py` | `CLAUDE_CONFIG_DIR` isolation in autouse fixture | ✓ VERIFIED | `monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)` present (line 18); `account_id` stub passes through to real resolver for stdin-bearing calls |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `core.py:1073` | `predict.account_id` | `_predict_account_id(stdin_data, env=_effective_env)` | ✓ WIRED | Guarded try/except, resolved once, `_effective_env` is per-session (not daemon-frozen `os.environ`) |
| `core.py:1439/1518/1535/1585` | `predict.reconcile_account/projection/forecast/quota_cache_status` | `account_uuid=_resolved_account_uuid` kwarg | ✓ WIRED | All 4 call sites confirmed via direct file read |
| `predict.account_id` | `account.resolve_config_dir` | lazy `from . import account` (predict.py:175) | ✓ WIRED | Reuses Phase 11 resolver verbatim, transcript-first precedence |
| `predict.projection` | `predict.regime_changed_at` | `path=_latest_path(account_uuid)` (predict.py:1283) | ✓ WIRED | Landmine fix confirmed — regime marker reads from the per-account reconcile store, not the legacy default |
| `predict._projection_result_key` | account-suffixed cache key | `str(_projection_path(account_uuid))`/`str(_latest_path(account_uuid))` (predict.py:1178-1179) | ✓ WIRED | Landmine fix confirmed — 1s result cache cannot cross accounts |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 12-test isolation suite | `.venv/bin/python -m pytest tests/test_account_rate_isolation.py -q` | 12 passed | ✓ PASS |
| Full suite w/ ambient `CLAUDE_CONFIG_DIR` | `.venv/bin/python -m pytest tests/ -q` (shell had `CLAUDE_CONFIG_DIR=/Users/khairulazmi/.claude-account2` set) | 1102 passed | ✓ PASS |
| Pre-fix regression proof (independent, not from SUMMARY) | checked out pre-12-02/03 `predict.py`/`core.py`/`conftest.py`, ran the single e2e test, restored current files | FAILED pre-fix (`'50%' in out2` → False, showed account1's `100%`) → restored → 12 passed | ✓ PASS |
| Related suites unregressed | `pytest tests/test_account_switch.py tests/test_regime_detection.py tests/test_core_projection.py tests/test_core_forecast_guard.py -q` | 25 passed | ✓ PASS |
| No network/subprocess import | `grep -n "^import\|^from" src/claude_statusbar/predict.py` | only stdlib (`json, math, os, datetime, pathlib, typing`) | ✓ PASS |

### Requirements Coverage

| Requirement | Source | Description | Status | Evidence |
|-------------|--------|-------------|--------|----------|
| R1 | 12-SPEC.md | Per-session account resolution in predict.py | ✓ SATISFIED | `account_id()` R1 test passes; transcript beats home decoy |
| R2 | 12-SPEC.md | Session context threaded through every store consumer | ✓ SATISFIED | All 4 core.py call sites + `_projection_result_key`/`regime_changed_at` landmines threaded |
| R3 | 12-SPEC.md | No cross-account collision on shared 5h `resets_at` (+ regression test) | ✓ SATISFIED | e2e regression independently confirmed FAILS pre-fix / PASSES post-fix |
| R4 | 12-SPEC.md | Both persisted stores re-keyed | ✓ SATISFIED | `_latest_path`/`_projection_path` both carry uuid |
| R5 | 12-SPEC.md | Unresolvable session → unchanged legacy behavior; no cross-account borrow | ✓ SATISFIED | R5a/R5b unit tests pass; `_claude_json_path_for_keying` contrasted against `account._claude_json_path`'s unconditional fallback |

No orphaned requirements — Phase 12's R1-R5 are scoped locally to 12-SPEC.md (ROADMAP explicitly defers to it: "Requirements: R1, R2, R3, R4, R5 (defined in 12-SPEC.md)"); `.planning/REQUIREMENTS.md` predates this phase and does not carry a separate Phase-12 entry to reconcile against.

### Anti-Patterns Found

None. Scanned `src/claude_statusbar/predict.py`, `src/claude_statusbar/core.py`, `tests/test_account_rate_isolation.py`, `tests/conftest.py` for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` (case-sensitive) and `placeholder|coming soon|not yet implemented|not available` (case-insensitive). Only hits were `DEBUG_PLACEHOLDER` (predict.py:51, 1221) — a pre-existing, legitimate display-string constant unrelated to Phase 12's diff, not a debt marker.

One LOW/informational item was surfaced by the phase's own code review (12-REVIEW.md, IN-02): `src/claude_statusbar/doctor.py:140` calls `quota_cache_status()` unthreaded (legacy resolver). This is explicitly pre-existing behavior (not a regression), and `doctor.py` is a diagnostic tool outside the render-path scope this phase's SPEC declared in scope (`core.py` call sites only). Confirmed non-blocking; correctly out of phase boundary.

### Human Verification Required

None. All must-haves are verifiable via automated tests and direct code inspection; no visual/real-time/external-service behavior is involved (pure filesystem render-path change).

### Gaps Summary

No gaps. All 5 SPEC requirements (R1-R5), all 3 prohibitions, the identity edge (no over-isolation), the sentinel tri-state, and both RESEARCH landmines (`regime_changed_at`, `_projection_result_key`) are implemented, tested, and independently re-verified against the live codebase (not merely trusted from SUMMARY claims). The e2e regression's FAILS-pre-fix / PASSES-post-fix proof was reproduced independently in this verification pass (git-checked-out pre-fix files, ran the test, restored — working tree confirmed clean afterward via `git diff --stat`). The full test suite (1102 tests) passes with the ambient `CLAUDE_CONFIG_DIR` set in this very shell, closing the exact scenario the phase exists to fix.

---

_Verified: 2026-07-16T18:20:00Z_
_Verifier: Claude (gsd-verifier)_
