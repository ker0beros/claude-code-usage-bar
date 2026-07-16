---
phase: 12-per-account-rate-limit-store-isolation
plan: 01
subsystem: testing
tags: [pytest, tdd, account-isolation, rate-limit, predict.py, core.py]

# Dependency graph
requires:
  - phase: 11-account-email-indicator
    provides: account.py's resolve_config_dir()/transcript-based config-dir resolution, reused by the target predict.account_id() API these tests pin
provides:
  - tests/test_account_rate_isolation.py — the complete 12-test isolation suite (Nyquist Wave 0), all collectable, 11 of 12 RED against current predict.py/core.py
  - A live, deterministic end-to-end reproduction of the 2026-07-16 cross-account 5h collision (test_two_accounts_share_5h_reset_render_own_values), confirmed to fail with the exact real symptom (account2 renders account1's 100% instead of its own 50%)
  - Exact green targets for 12-02 (predict.py: sentinel, keying reader, threading) and 12-03 (core.py: _resolved_account_uuid wiring)
affects: [12-per-account-rate-limit-store-isolation (12-02, 12-03)]

# Tech tracking
tech-stack:
  added: []
  patterns: [Nyquist Wave 0 tests-first authoring, sentinel-based optional-arg threading target API, _list_imports_for reuse for import-graph prohibitions]

key-files:
  created: [tests/test_account_rate_isolation.py]
  modified: []

key-decisions:
  - "[Rule 1] test_predict_module_imports_no_network_or_subprocess bans {subprocess, socket, urllib.request} instead of the RESEARCH-literal {subprocess, socket, urllib, urllib.request}: pathlib itself transitively imports urllib.parse (network-free) on this Python version even from a bare `import json, math, os; from datetime import datetime; from pathlib import Path` — confirmed by direct measurement with zero predict.py code involved. Banning the parent package name false-positived on that pre-existing, unrelated stdlib artifact; the actual network-capable submodule (urllib.request) is the one that matters and is still banned."
  - "[Rule 1] test_two_accounts_share_5h_reset_render_own_values computes its shared 5h resets_at as `time.time() + 3600` instead of the RESEARCH/SPEC-literal historical epoch (1784191800). reconcile_account's _reset_plausible guard rejects any resets_at more than 60s in the past relative to wall-clock now (anti-poison guard); a hardcoded historical literal recedes further into the past every day this suite runs and would eventually make the reset implausible, silently turning the two reconcile calls into independent passthroughs that never share a bucket — a false-negative collision that defeats the FAILS-pre-fix acceptance proof. A wall-clock-relative near-future reset keeps the identical-bucket collision deterministic regardless of when the suite executes, while preserving the exact defect shape (two accounts, one shared clock-aligned 5h bucket, 100 vs 50 real usage)."

patterns-established:
  - "Wave 0 tests-first: author the full behavior spec as pytest tests before any implementation exists, using the exact target API signatures from RESEARCH.md's Code Examples so 12-02/12-03 have a fixed, executable green target."

requirements-completed: [R1, R2, R3, R4, R5]

coverage:
  - id: D1
    description: "tests/test_account_rate_isolation.py exists with all 12 named tests, each collectable (pytest --collect-only exits 0)"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/test_account_rate_isolation.py --collect-only -q"
        status: pass
    human_judgment: false
  - id: D2
    description: "Suite encodes R1 (transcript beats $HOME/.claude.json), R4 (both store paths carry the uuid), R5a (unresolvable -> legacy unsuffixed), R5b (named dir w/o own .claude.json never borrows $HOME uuid), the identity edge (same uuid two dirs -> same store), and the sentinel 3-way branch"
    requirement: "R1, R4, R5"
    verification:
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_account_id_resolves_from_transcript_over_home_json"
        status: fail
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_store_paths_carry_session_uuid"
        status: fail
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_unresolvable_session_uses_legacy_path"
        status: fail
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_named_dir_without_own_json_does_not_borrow_home"
        status: fail
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_same_account_two_dirs_shares_store"
        status: fail
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_account_path_three_way_branch"
        status: fail
    human_judgment: false
  - id: D3
    description: "Suite encodes the two landmines (regime_changed_at reads the per-account path from projection(); _projection_result_key differs per account) and the three prohibitions (only accountUuid read; no destructive fs op on existing store files; no network/subprocess import)"
    verification:
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_projection_threads_account_into_regime_check"
        status: fail
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_projection_result_cache_keys_by_account"
        status: fail
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_keying_reader_reads_only_account_uuid"
        status: fail
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_no_destructive_fs_ops_on_existing_stores"
        status: fail
      - kind: unit
        ref: "tests/test_account_rate_isolation.py#test_predict_module_imports_no_network_or_subprocess"
        status: pass
    human_judgment: false
  - id: D4
    description: "test_two_accounts_share_5h_reset_render_own_values is a true core.main() end-to-end reproduction of the live 2026-07-16 collision — RED against current code (the phase's FAILS-pre-fix / PASSES-post-fix acceptance proof for R3)"
    requirement: "R3"
    verification:
      - kind: e2e
        ref: "tests/test_account_rate_isolation.py#test_two_accounts_share_5h_reset_render_own_values"
        status: fail
    human_judgment: false

duration: 25min
completed: 2026-07-16
status: complete
---

# Phase 12 Plan 01: Isolation Test Suite (Nyquist Wave 0) Summary

**Authored the full 12-test `tests/test_account_rate_isolation.py` isolation suite up front — 11 of 12 tests confirmed RED against current predict.py/core.py, including a genuine core.main() end-to-end reproduction of the live cross-account 5h collision (account2's real 50% renders account1's 100%).**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-16T09:04:00Z (approx.)
- **Completed:** 2026-07-16T09:28:30Z
- **Tasks:** 2
- **Files modified:** 1 (new file)

## Accomplishments
- All 12 target node-ids from 12-VALIDATION.md/12-RESEARCH.md are authored, collectable (`pytest --collect-only` exits 0), and named local fixture helpers `_write_claude_json`, `_payload_with_limits`, `_write_config` copy the exact shape of `tests/test_account.py`/`tests/test_core_projection.py`.
- `test_two_accounts_share_5h_reset_render_own_values` genuinely reproduces the live incident through `claude_statusbar.core.main()` end-to-end: with two accounts sharing an identical clock-aligned 5h `resets_at` and real usage of 100% vs 50%, the second render's output is `5h[███100%███]` — i.e. it shows account1's value, not its own 50% — confirming this is a real, structural collision and not a mocked stand-in.
- 11 of 12 tests are RED (fail or error) against current code as designed; the 12th (`test_predict_module_imports_no_network_or_subprocess`) already passes because predict.py is already stdlib-only — an already-satisfied prohibition, not a gap.
- Full existing suite (1090 tests) verified unchanged and still green after adding the new file (1091 total, 11 new failures isolated to the new file only).

## Task Commits

Each task was committed atomically:

1. **Task 1: Resolution + keying + store-path unit tests** - `d4afccf` (test)
2. **Task 2: Threading/landmine + prohibition-import + e2e regression tests** - `402e215` (test)

**Plan metadata:** (this commit, immediately following)

## Files Created/Modified
- `tests/test_account_rate_isolation.py` - New 12-test isolation suite + 3 local fixture helpers (`_write_claude_json`, `_payload_with_limits`, `_write_config`)

## Decisions Made
- **[Rule 1] Narrowed the no-network banned-import set.** `{"subprocess", "socket", "urllib.request"}` instead of the RESEARCH-literal set that also banned bare `"urllib"`. Measured directly: `pathlib` alone (imported nowhere near predict.py's own code) transitively pulls in the network-free `urllib.parse` submodule on this Python 3.12 build. Banning the parent package name produced a false positive unrelated to any code this phase touches; the real concern (an actual networking call via `urllib.request`) is still enforced.
- **[Rule 1] Made the e2e regression's shared reset wall-clock-relative.** `resets_5h = time.time() + 3600` instead of the SPEC/RESEARCH's literal historical epoch `1784191800`. `reconcile_account`'s `_reset_plausible` anti-poison guard rejects any `resets_at` more than 60 seconds in the past relative to real `now`; a fixed historical literal recedes into the past every day this suite runs post-authoring and would eventually make the reset implausible, silently turning both reconcile calls into independent passthroughs that never share a bucket — a false-negative collision that would defeat the "FAILS pre-fix" acceptance proof this test exists to deliver. The wall-clock-relative version keeps the collision deterministic on every future run while preserving the exact defect shape (two accounts, one shared clock-aligned 5h bucket, 100 vs 50 real usage).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Narrowed the no-network/subprocess banned-import set**
- **Found during:** Task 2 (`test_predict_module_imports_no_network_or_subprocess`)
- **Issue:** The RESEARCH-literal banned set `{"subprocess", "socket", "urllib", "urllib.request"}` false-positived: `urllib`/`urllib.parse` are pulled in transitively by `pathlib` itself (confirmed with a standalone `import json, math, os; from datetime import datetime; from pathlib import Path` reproduction, zero predict.py involvement), and `urllib.parse` has no network capability.
- **Fix:** Dropped bare `"urllib"` from the banned set, keeping `"urllib.request"` (the actual networking-capable submodule), `"subprocess"`, and `"socket"`.
- **Files modified:** tests/test_account_rate_isolation.py
- **Verification:** `test_predict_module_imports_no_network_or_subprocess` now passes; documented inline in the test's docstring with the measurement that justifies the exclusion.
- **Committed in:** 402e215 (Task 2 commit)

**2. [Rule 1 - Bug] Made the e2e regression test's shared reset wall-clock-relative**
- **Found during:** Task 2 (`test_two_accounts_share_5h_reset_render_own_values`)
- **Issue:** The SPEC/RESEARCH-literal historical epoch `1784191800` is a fixed point in time that recedes further into the past every day the suite runs after authoring; `reconcile_account`'s reset-plausibility guard (`now - 60 <= reset`) would eventually reject it, causing both reconcile calls to become independent passthroughs that never collide — silently defeating the very "FAILS pre-fix" proof R3 requires.
- **Fix:** Compute `resets_5h = time.time() + 3600` (and the two accounts' distinct-but-plausible 7d resets similarly) at test-run time instead of hardcoding the historical literal, preserving the identical-bucket-collision shape deterministically regardless of execution date.
- **Files modified:** tests/test_account_rate_isolation.py
- **Verification:** Ran the test against current (pre-fix) code — confirmed it fails with the exact real symptom: `out2` contains `5h[███100%███]` (account1's value) instead of `50%`. This is the literal FAILS-pre-fix proof required by R3's acceptance criterion.
- **Committed in:** 402e215 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — test-design bug fixes needed for the tests to actually assert what they claim to assert, deterministically and without false positives).
**Impact on plan:** Both fixes were necessary for the suite to genuinely encode its own acceptance criteria; no scope creep — no src/ changes were made (tests-only, as required by this plan).

## Issues Encountered
None beyond the two auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `tests/test_account_rate_isolation.py` gives 12-02 (predict.py: sentinel `_UNSET`, `_read_keyed_account_id`, threaded `account_uuid` params) and 12-03 (core.py: `_resolved_account_uuid` wiring) exact, fixed green targets — no ambiguity about what "done" means for the fix.
- The e2e regression (`test_two_accounts_share_5h_reset_render_own_values`) is confirmed to fail with the real, live symptom now, which is the concrete pre-fix baseline 12-03 must flip to green.
- No blockers. Full existing suite (1090 tests) unaffected; 11 of the 12 new tests are the expected RED state, 1 already green (an already-satisfied prohibition).

---
*Phase: 12-per-account-rate-limit-store-isolation*
*Completed: 2026-07-16*

## Self-Check: PASSED
- FOUND: tests/test_account_rate_isolation.py
- FOUND: .planning/phases/12-per-account-rate-limit-store-isolation/12-01-SUMMARY.md
- FOUND commit: d4afccf (Task 1)
- FOUND commit: 402e215 (Task 2)
