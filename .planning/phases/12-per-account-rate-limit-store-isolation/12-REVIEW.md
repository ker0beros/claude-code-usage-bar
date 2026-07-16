---
phase: 12-per-account-rate-limit-store-isolation
reviewed: 2026-07-16T00:00:00Z
depth: deep
files_reviewed: 4
files_reviewed_list:
  - src/claude_statusbar/predict.py
  - src/claude_statusbar/core.py
  - tests/test_account_rate_isolation.py
  - tests/conftest.py
findings:
  critical: 0
  warning: 0
  info: 4
  total: 4
status: clean
---

# Phase 12: Code Review Report — Per-Account Rate-Limit Store Isolation

**Reviewed:** 2026-07-16
**Depth:** deep (cross-file call-graph trace + full-suite run)
**Files Reviewed:** 4
**Status:** clean

## Summary

The implementation is careful, matches the SPEC (R1–R5) and RESEARCH landmine
guidance precisely, and adds no actionable BLOCKER/HIGH/MEDIUM defect. I traced
every threaded call site across `core.py → predict.py → filesystem`, verified the
sentinel tri-state, the two landmines (`regime_changed_at`, `_projection_result_key`),
cache keying, the never-raise contract, and all three Prohibitions. Full suite:
**1102 passed** (1090 baseline + 12 new). Below are four LOW/informational
observations only — none require a fix to ship.

### Verified correct (adversarial checklist)

- **Sentinel tri-state** (`_account_path`, predict.py:186–198): `_UNSET` → legacy
  hardcoded resolver; explicit `None` → legacy **unsuffixed** path (no
  `$HOME/.claude.json` borrow); uuid → suffixed. No path where an explicit
  `None` borrows home. R5a/R5b hold. `test_account_path_three_way_branch` and
  `test_named_dir_without_own_json_does_not_borrow_home` pin it.
- **R5b-strict locator** (`_claude_json_path_for_keying`, predict.py:110–125):
  home-level `.claude.json` is consulted *only* when `config_dir == home/.claude`.
  A named `CLAUDE_CONFIG_DIR` lacking its own file returns `None` (→ legacy
  unsuffixed), never the home uuid. Correctly distinct from
  `account._claude_json_path` (which the phase left untouched, per scope).
- **Cache safety** (`_SESSION_ACCOUNT_CACHE`, predict.py:86, 128–156): dedicated
  dict (does not touch `_ACCOUNT_CACHE`); signature is `f"{path}\0{mtime_ns}\0{size}"`
  — path-inclusive. Two different accounts resolve to different paths, so no
  cross-account false-hit is possible under the in-process sequential daemon; a
  re-login (content change) flips mtime/size → re-read. Single-entry thrash across
  interleaved accounts is the known, accepted Phase-11 precedent (perf, out of scope).
- **Both landmines threaded**: `regime_changed_at(path=_latest_path(account_uuid))`
  (predict.py:1283) reads the per-account *reconcile* store, not the projection
  store or the default; `_projection_result_key(..., account_uuid)` (predict.py:1177–1179)
  keys the 1s result cache by the account-suffixed paths. `load_projection_store`
  and `save_projection_store` both take the per-account path (1278, 1288). No store
  read/write reaches the legacy hardcoded path when a session uuid is resolvable.
- **Never-raise / daemon-safe**: `account_id(stdin!=None)` wraps all IO/parse in
  `try/except → None` (predict.py:174–183); core.py's resolution is `try/except →
  None` (core.py:1071–1075). Resolution uses `stdin_data` (transcript_path primary)
  + `_effective_env` (per-session `_session_env` preferred over the daemon's frozen
  `os.environ`), so it does not depend on the frozen daemon env. No new raise path
  into the render.
- **Prohibitions**: only `accountUuid` is regex-extracted (anchored to the
  `oauthAccount` object; `decode("ascii")` is safe because the capture class is
  hex+dash only) — no token/secret read. No `unlink`/`replace`/`rename` of any
  existing store file was added (reconcile's own atomic `os.replace` targets only
  its own file). No `subprocess`/`socket`/`urllib.request` import added. All three
  are locked by dedicated tests.
- **Reconcile invariants untouched**: the only change inside `reconcile_account`
  is the path-resolution line (`_latest_path(account_uuid)`); monotonic-up / grace /
  confirm-refresh / `(window, resets_at)` bucket-keying logic is byte-identical.
- **Byte-identical single-account render**: a standard single-account session
  (transcript under `~/.claude/projects`, real file at `~/.claude.json`) resolves
  via the default-dir borrow to the *same* uuid the legacy reader produced → same
  `rate_latest.<uuid12>.json`. No store migration, no output change.
- **Filesystem safety of the suffix**: `aid` used in `base.with_name(...)` can only
  contain `[0-9a-fA-F-]` (both readers), so a crafted `.claude.json` cannot inject
  `/` or `..` into the store filename — no path traversal via the uuid segment.

## Narrative Findings (AI reviewer)

### IN-01: Relaxed `{1,64}` lower bound on the keying reader's uuid regex (LOW)

**File:** `src/claude_statusbar/predict.py:151`
**Issue:** `_read_keyed_account_id` uses `"accountUuid"\s*:\s*"([0-9a-fA-F-]{1,64})"`
(vs the legacy reader's `{8,64}`). The comment explains it accepts short
test-fixture uuids. This is safe in practice — the capture class is hex+dash only
(so no injection, no traversal), the match is anchored to the `accountUuid` key
(so no adjacent-secret match), a real Claude accountUuid is a full 36-char UUID
(greedy match consumes all 36, `< 64`, then requires the closing quote), and an
empty value (`{1,64}` needs ≥1 char) or a value containing a non-hex char yields
no match → `None` → legacy unsuffixed path. The only theoretical effect is that a
1-char or dash-only malformed value would produce an odd-but-safe store filename
(`rate_latest.-.json`), which no real config produces.
**Fix (optional):** keep `{8,64}` to match the legacy reader and instead use
≥8-char uuids in the two short-uuid test fixtures — tightens the reader with no
behavior change for real data. Non-actionable; documenting for parity awareness.

### IN-02: `doctor.py` calls `quota_cache_status()` unthreaded (LOW, out of phase scope)

**File:** `src/claude_statusbar/doctor.py:140`
**Issue:** `quota_cache_status()` here passes no `account_uuid`, so it uses the
`_UNSET` legacy resolver (hardcoded `~/.claude.json`). Under a multi-account
`CLAUDE_CONFIG_DIR` shell, the doctor's cache-status diagnostic may report the
default account's store rather than the shell's active account. This is *unchanged*
from pre-phase behavior (not a regression this phase introduced) and doctor is a
diagnostic outside the render-path scope of Phase 12.
**Fix (optional, future):** if doctor should be account-aware, resolve
`predict.account_id(stdin=None, env=os.environ)` there — but note doctor has no
transcript context, so it can only key off `CLAUDE_CONFIG_DIR`. Deliberately left
for a future phase.

### IN-03: Exact `Path` equality for the default-dir borrow (LOW, edge)

**File:** `src/claude_statusbar/predict.py:121`
**Issue:** `if config_dir == home / ".claude":` uses exact `Path` equality. If a
transcript path presented a non-normalized or symlinked home that differs
literally from `os.path.expanduser("~")` (e.g. `/var` vs `/private/var` on macOS,
or a symlinked home), the default-dir borrow would not trigger, and a genuine
single-account default session would resolve to `None` → legacy *unsuffixed* store
instead of its `<uuid>`-suffixed store. Consequence is benign: non-isolation (not
a cross-account collision) plus a one-time store re-baseline that ages out via
existing GC/grace. In practice statusline transcript paths match `expanduser("~")`,
so this does not fire.
**Fix (optional):** compare resolved paths (`config_dir.resolve() == (home/'.claude').resolve()`)
if symlinked homes are a concern. Not observed in real payloads; non-actionable.

### IN-04: Per-render resolution runs unconditionally, before the has-quota gate (LOW, perf — out of v1 scope)

**File:** `src/claude_statusbar/core.py:1071–1075`
**Issue:** `_resolved_account_uuid` is computed on every render (imports `account`,
`stat()`s / possibly reads `.claude.json`) even in no-quota / API-key mode where no
store consumer runs. Correctness is unaffected (memoized to a `stat()` in steady
state, matching the SPEC's render-fast-path budget and the Phase-11 email-chip
convention). Flagged only for completeness; performance is explicitly out of v1
review scope.
**Fix:** none required.

---

_Reviewed: 2026-07-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
