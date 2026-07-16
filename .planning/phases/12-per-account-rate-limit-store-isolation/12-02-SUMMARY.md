---
phase: 12-per-account-rate-limit-store-isolation
plan: 02
subsystem: api
tags: [predict.py, account-isolation, rate-limit, sentinel-pattern, memoization]

# Dependency graph
requires:
  - phase: 12-per-account-rate-limit-store-isolation (12-01)
    provides: tests/test_account_rate_isolation.py — the fixed green target (11 unit/landmine/prohibition tests) and the e2e regression test this plan intentionally leaves RED
  - phase: 11-account-email-indicator
    provides: account.py's resolve_config_dir() (transcript_path → CLAUDE_CONFIG_DIR → ~/.claude precedence), reused verbatim
provides:
  - predict.account_id(stdin=None, *, env=None, home=None) — per-session account resolution, backward-compatible zero-arg default
  - predict._account_path/_latest_path/_projection_path(aid=_UNSET) — sentinel tri-state store-path keying
  - predict._claude_json_path_for_keying — R5b-strict locator (no $HOME/.claude.json borrow for named dirs)
  - predict._read_keyed_account_id — dedicated memoized accountUuid-only reader
  - account_uuid threaded through reconcile_account/forecast/projection/quota_cache_status/_projection_result_key, including the regime_changed_at landmine fix inside projection()
affects: [12-per-account-rate-limit-store-isolation (12-03 — core.py wiring, the only remaining piece before the e2e regression turns green)]

# Tech tracking
tech-stack:
  added: []
  patterns: ["_UNSET sentinel for tri-state optional-arg threading (omitted/None/value)", "dedicated per-purpose memoization cache instead of reusing an existing one", "keyword-safe append-only parameter threading across a call chain"]

key-files:
  created: []
  modified: [src/claude_statusbar/predict.py, tests/conftest.py]

key-decisions:
  - "[Rule 1] Relaxed _read_keyed_account_id's uuid regex lower bound from {8,64} (legacy _read_account_id, kept unchanged) to {1,64}. The 12-01 test fixture's default uuid (\"abc-123\", 7 chars) is shorter than the legacy reader's 8-char floor; this is a NEW, separate reader so relaxing its bound doesn't touch the unchanged legacy regex, and it still only ever matches the anchored accountUuid key (never an adjacent secret field)."
  - "[Rule 3] tests/conftest.py's autouse _isolate_rate_latest fixture pinned predict.account_id to a zero-arg lambda for test isolation; this broke on the new stdin/env/home-accepting signature (TypeError on any call with args). Changed the stub to pass through to the real resolver whenever stdin is not None, preserving the zero-arg pin (returns None, keeping every legacy test's unsuffixed-path expectations intact) while letting the new per-session tests exercise real resolution logic."

patterns-established:
  - "_UNSET module-level sentinel distinguishes 'argument omitted' (legacy hardcoded behavior) from 'argument explicitly None' (a failed resolution attempt) — used across _account_path/_latest_path/_projection_path/quota_cache_status/reconcile_account/forecast/projection/_projection_result_key."
  - "New account_uuid params always appended as the FINAL keyword-safe parameter — every existing call site (tests, core.py) passes by keyword, so zero call-site changes were needed for any pre-Phase-12 caller."

requirements-completed: [R1, R2, R4, R5]

coverage:
  - id: D1
    description: "predict.account_id(stdin, env, home) resolves the session's own account uuid via account.resolve_config_dir(), even when $HOME/.claude.json holds a different account's uuid (R1)"
    requirement: "R1"
    verification:
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_account_id_resolves_from_transcript_over_home_json"
        status: pass
    human_judgment: false
  - id: D2
    description: "_latest_path(aid) and _projection_path(aid) both carry the resolved session uuid (R4)"
    requirement: "R4"
    verification:
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_store_paths_carry_session_uuid"
        status: pass
    human_judgment: false
  - id: D3
    description: "Unresolvable session and named-dir-without-own-.claude.json both fall to the legacy unsuffixed path, never borrowing $HOME's uuid (R5a/R5b)"
    requirement: "R5"
    verification:
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_unresolvable_session_uses_legacy_path"
        status: pass
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_named_dir_without_own_json_does_not_borrow_home"
        status: pass
    human_judgment: false
  - id: D4
    description: "Identity edge (same real uuid via two config dirs shares one store) and the _account_path sentinel three-way branch (omitted/None/uuid all distinct) both hold"
    verification:
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_same_account_two_dirs_shares_store"
        status: pass
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_account_path_three_way_branch"
        status: pass
    human_judgment: false
  - id: D5
    description: "_read_keyed_account_id extracts only accountUuid, never an adjacent accessToken/emailAddress in the same oauthAccount block"
    verification:
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_keying_reader_reads_only_account_uuid"
        status: pass
    human_judgment: false
  - id: D6
    description: "projection() threads account_uuid into regime_changed_at's path arg (the Pitfall 2 landmine) so the regime boundary marker is read from the correct account's reconcile store"
    requirement: "R2"
    verification:
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_projection_threads_account_into_regime_check"
        status: pass
    human_judgment: false
  - id: D7
    description: "_projection_result_key differs per account_uuid so the 1s projection result cache never crosses accounts"
    requirement: "R2"
    verification:
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_projection_result_cache_keys_by_account"
        status: pass
    human_judgment: false
  - id: D8
    description: "reconcile_account never deletes/renames/replaces a pre-existing, different store file; predict.py stays subprocess/socket/urllib.request-free"
    verification:
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_no_destructive_fs_ops_on_existing_stores"
        status: pass
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_predict_module_imports_no_network_or_subprocess"
        status: pass
    human_judgment: false
  - id: D9
    description: "Zero regression to the pre-existing 1090-test suite; e2e regression test remains the sole intentional RED, awaiting 12-03's core.py wiring"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/ -q --deselect tests/test_account_rate_isolation.py::test_two_accounts_share_5h_reset_render_own_values"
        status: pass
    human_judgment: false

duration: ~20min
completed: 2026-07-16
status: complete
---

# Phase 12 Plan 02: predict.py Per-Session Store Keying Summary

**predict.py now resolves each session's own account uuid via account.resolve_config_dir() reuse and keys both the reconcile and projection stores to it, with an R5b-strict no-home-borrow locator, a dedicated memoized reader, and account_uuid threaded through every store consumer including the two RESEARCH landmines (regime_changed_at inside projection(), and _projection_result_key).**

## Performance

- **Duration:** ~20 min
- **Tasks:** 2
- **Files modified:** 2 (src/claude_statusbar/predict.py, tests/conftest.py)

## Accomplishments
- Added `_UNSET` sentinel + `_SESSION_ACCOUNT_CACHE` (dedicated, separate from `_ACCOUNT_CACHE`), `_claude_json_path_for_keying` (R5b: never borrows `$HOME/.claude.json` for a named dir lacking its own file), `_read_keyed_account_id` (memoized on `(path, mtime_ns, size)`, accountUuid-only), and the new `account_id(stdin=None, *, env=None, home=None)` signature — legacy zero-arg behavior byte-unchanged.
- `_account_path`/`_latest_path`/`_projection_path` are now correctly tri-state on `aid`: omitted → legacy hardcoded resolver, explicit `None` → legacy unsuffixed path (no borrow), uuid → suffixed path.
- Threaded `account_uuid=_UNSET` (keyword-safe, final param) through `quota_cache_status`, `reconcile_account`, `forecast`, `projection`, and `_projection_result_key` — zero existing call sites needed changes since every one already calls by keyword.
- Fixed both RESEARCH landmines: `projection()` now passes `path=_latest_path(account_uuid)` into its internal `regime_changed_at()` call (previously would have silently read the wrong account's regime boundary), and `_projection_result_key` now includes `account_uuid` in its two path strings so the 1s result cache can't leak one account's `(p5, p7)` tuple to another.
- Full suite: 1101 passed (1090 baseline + the 11 new unit/landmine/prohibition tests), 1 intentionally still RED (the e2e regression, which needs 12-03's core.py wiring).

## Task Commits

Each task was committed atomically:

1. **Task 1: Per-session resolution + keying primitives** - `824497a` (feat)
2. **Task 2: Thread account_uuid through reconcile/forecast/projection/quota_cache_status/_projection_result_key** - `acafd15` (feat)

**Plan metadata:** (this commit, immediately following)

## Files Created/Modified
- `src/claude_statusbar/predict.py` - `_UNSET` sentinel, `_SESSION_ACCOUNT_CACHE`, `_claude_json_path_for_keying`, `_read_keyed_account_id`, new `account_id()` signature, tri-state `_account_path`/`_latest_path`/`_projection_path`, `account_uuid` threaded through `quota_cache_status`/`reconcile_account`/`forecast`/`projection`/`_projection_result_key`, and the `regime_changed_at` path fix inside `projection()`.
- `tests/conftest.py` - autouse `_isolate_rate_latest` fixture's `account_id` stub updated to pass through to the real resolver for stdin-bearing calls (was a zero-arg-only lambda, incompatible with the new signature).

## Decisions Made
- **[Rule 1] Relaxed the new keying reader's uuid regex bound to `{1,64}`.** The legacy `_read_account_id`'s regex (`{8,64}`) is explicitly kept unchanged per the plan; the NEW `_read_keyed_account_id` needed a lower floor because the 12-01 test suite's default fixture uuid (`"abc-123"`, 7 characters) is shorter than 8. This only affects the new reader and still anchors on `oauthAccount` → `accountUuid` exclusively.
- **[Rule 3] Fixed tests/conftest.py's autouse account_id stub.** The pre-existing `_isolate_rate_latest` fixture unconditionally monkeypatched `predict.account_id` to `lambda: None` for every test (to pin zero-arg store-path resolution off the developer's real login). The new per-session signature (`account_id(stdin, env=, home=)`) made every rate-isolation test call this stub with arguments, raising `TypeError: <lambda>() got an unexpected keyword argument 'env'`. Fixed by making the stub delegate to the real resolver whenever `stdin is not None`, while still returning `None` for the legacy zero-arg case — preserving every pre-existing test's unsuffixed-path expectations.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Relaxed _read_keyed_account_id's uuid regex lower bound**
- **Found during:** Task 1 (`test_keying_reader_reads_only_account_uuid`)
- **Issue:** Using the plan's literal legacy regex (`[0-9a-fA-F-]{8,64}`) for the new reader rejected the test fixture's default uuid `"abc-123"` (7 characters), returning `None` instead of the expected uuid.
- **Fix:** Changed the new `_read_keyed_account_id`'s regex lower bound from `{8,64}` to `{1,64}`. The legacy `_read_account_id`'s regex is untouched, as the plan requires.
- **Files modified:** src/claude_statusbar/predict.py
- **Verification:** `test_keying_reader_reads_only_account_uuid` passes; still verified to never match `accessToken`/`emailAddress` (anchored on the `accountUuid` key specifically).
- **Committed in:** 824497a (Task 1 commit)

**2. [Rule 3 - Blocking] Fixed tests/conftest.py's autouse account_id stub incompatibility**
- **Found during:** Task 1 (multiple rate-isolation tests failing with `TypeError`)
- **Issue:** `tests/conftest.py`'s autouse `_isolate_rate_latest` fixture monkeypatched `predict.account_id` to a zero-arg `lambda: None`, incompatible with the new `account_id(stdin=None, *, env=None, home=None)` signature — any call passing `stdin`/`env`/`home` raised `TypeError`.
- **Fix:** Changed the stub to capture the real (unpatched) `account_id` and delegate to it whenever `stdin is not None`, while still returning `None` for the legacy zero-arg case (`stdin is None`) — the exact behavior the fixture originally provided for every pre-existing test.
- **Files modified:** tests/conftest.py
- **Verification:** All 7 Task 1 tests pass; `tests/test_account_switch.py` (7 tests) still passes unchanged; full suite (excluding the e2e regression) is 1101/1101 green.
- **Committed in:** 824497a (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 1 test-compatibility regex fix, 1 Rule 3 blocking test-infra fix).
**Impact on plan:** Both fixes were necessary for the plan's own acceptance tests to pass; no scope creep into core.py or any other file outside predict.py/conftest.py. The conftest.py fix, while outside the plan's declared `files_modified` (predict.py only), was required test infrastructure — the alternative (leaving it broken) would have made the plan's own stated acceptance criteria (the 11 unit/landmine/prohibition tests) impossible to satisfy.

## Issues Encountered
None beyond the two auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- 12-03 can now wire `core.py`'s three call sites (`reconcile_account`, `projection`, `quota_cache_status`) to pass `account_uuid=_resolved_account_uuid`, resolved once near the top of `main()` via `predict.account_id(stdin_data, env=_effective_env)`.
- The e2e regression test (`test_two_accounts_share_5h_reset_render_own_values`) is confirmed still RED with the exact expected symptom (`out2` shows `'100%'` instead of `'50%'`) — this is the fixed, deterministic target 12-03 must flip to green.
- No blockers. Full suite (excluding the e2e regression) is 1101/1101 green; `reconcile_account`'s healing algorithm (monotonic-up/grace/confirm-refresh) is byte-unchanged — only its store-path-selection line changed.

---
*Phase: 12-per-account-rate-limit-store-isolation*
*Completed: 2026-07-16*

## Self-Check: PASSED
- FOUND: src/claude_statusbar/predict.py
- FOUND: tests/conftest.py
- FOUND commit: 824497a (Task 1)
- FOUND commit: acafd15 (Task 2)
