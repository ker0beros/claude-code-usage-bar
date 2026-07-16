# Phase 12: Per-Account Rate-Limit Store Isolation - Context

**Gathered:** 2026-07-16
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous) — 1 grey area (implementation threading); all other decisions pre-locked in 12-SPEC.md (ambiguity 0.15)

<domain>
## Phase Boundary

The rate-limit reconcile store (`rate_latest.<uuid>.json`) **and** the projection/forecast store
(`rate_projection.<uuid>.json`) are keyed by the *session's own* Claude account, resolved daemon-safe
from `transcript_path` → `CLAUDE_CONFIG_DIR` → `~/.claude` (the Phase 11 precedence). When two accounts
are logged in concurrently and share an identical clock-aligned 5h `resets_at`, each window's 5h bar
shows only its own account's usage — the 5h value changes from cross-account-max (wrong) to per-account
(correct).

Backend / render-path correctness fix only. No new user-facing UI, no visual/UX decisions. Pure
filesystem, daemon-safe, stdlib-only, never-raise. Fix-forward: no migration/cleanup of the existing
mis-keyed store files.

</domain>

<decisions>
## Implementation Decisions

### predict.py session-context threading (accepted 2026-07-16)
- **Threading mechanism:** explicit optional parameter threaded through the four public store consumers
  (`reconcile_account`, `forecast`, `projection`, `quota_cache_status`) down into `_account_path(base, aid)`.
  Mirrors predict.py's existing `path=None` dependency-injection idiom. **No module-level global / contextvar**
  — a shared mutable global is unsafe under the multi-session shared daemon (successive/concurrent sessions
  would stomp it), which is precisely the class of bug this phase fixes.
- **Value threaded:** the resolved account **UUID**. `core.py` resolves it once per render from the
  already-available `stdin_data` (via a new per-session `predict.account_id(stdin, env)`), then threads the
  uuid down to `_account_path`. `_account_path` already needs only the uuid.
- **Resolver reuse + R5b:** reuse `account.resolve_config_dir(stdin, env, home)` (Phase 11) for the
  `transcript_path` → `CLAUDE_CONFIG_DIR` → `~/.claude` dir precedence. Add a **keying-specific** UUID reader
  in predict.py that does **NOT** borrow `$HOME/.claude.json` for a *named* config dir that lacks its own
  `.claude.json` (→ legacy unsuffixed path, never the home account's uuid — R5b no-borrow). The default
  `~/.claude` dir still correctly reads `$HOME/.claude.json`. (Do **not** reuse `account._claude_json_path`
  as-is — its home-level fallback would re-introduce the cross-account collision.)
- **Backward-compat default:** when no session context is passed, preserve today's behavior (the existing
  hardcoded `~/.claude.json` resolver stays the default) so only core's render path flips to per-session
  keying — zero risk to the existing 1090-test suite and to any non-core caller / test that injects `path=`.

### Pre-locked in 12-SPEC.md (Interview Log)
- **Both stores in scope:** re-key `rate_latest.<uuid>.json` *and* `rate_projection.<uuid>.json` (same defect,
  same `_account_path()`).
- **Fix-forward only:** no migration, quarantine, rename, or deletion of the already-poisoned shared store
  files — once keying separates, the stale shared bucket is simply no longer read and ages out via existing
  GC/grace logic.
- **Reconcile algorithm untouched:** monotonic-up / grace / confirm-refresh healing is correct; only *store
  selection* was wrong.
- **Secret-minimal:** read only `oauthAccount.accountUuid`; never read/log/persist any OAuth token or secret.
- **Regression test required:** reproduce the live collision (two accounts, identical 5h `resets_at`
  `1784191800`, `used_percentage` 100 vs 50) — FAILS pre-fix, PASSES post-fix.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `account.resolve_config_dir(stdin, *, env, home)` — `src/claude_statusbar/account.py:55`. Exact
  `transcript_path` → `CLAUDE_CONFIG_DIR` → `~/.claude` precedence; daemon-safe (transcript rides in stdin,
  not the daemon's frozen `os.environ`). Returns a `Path`, never `None`. **Reuse directly.**
- `account._config_dir_from_transcript` (`account.py:37`) — the `parents[1] == "projects"` guard against
  malformed transcript shapes; reused transitively via `resolve_config_dir`.
- `predict._read_account_id` (`predict.py:76`) — the anchored `"oauthAccount"` → `accountUuid` regex +
  `(mtime_ns, size)` memoization pattern to adapt (currently reads hardcoded `_CLAUDE_JSON_PATH`).

### Established Patterns
- **DI via `path=None`:** `reconcile_account`/`forecast`/`projection`/`quota_cache_status` all accept
  `path=None` and fall back to `_latest_path()`/`_projection_path()`. Add the account/session param the same
  way (optional, backward-compatible default).
- **Anchored regex + stat-memoization:** both `account._read_email` and `predict._read_account_id` scan a
  60–270KB `.claude.json` with an `"oauthAccount"`-anchored regex, memoized on `(path, mtime_ns, size)` so a
  steady-state render pays only a `stat()`. New keying reader must keep this budget (memoize on path too, since
  different sessions read different files).
- **Never-raise:** any resolution/IO/parse failure yields the legacy fallback (mirrors account.py's contract).

### Integration Points
- `core.py:1423-1428` — `reconcile_account(...)` call (has `stdin_data`, `session_id`, `model_id`).
- `core.py:~1490-1506` — projection/forecast call site (`session_id=stdin_data.get("session_id")`).
- `core.py:1571-1572` — `quota_cache_status()` call.
- `_effective_env = _session_env if isinstance(_session_env, dict) else os.environ` already computed at
  `core.py:1064-1065` — pass `stdin_data` + `_effective_env` into the new `predict.account_id(...)`.
- Store-path helpers to re-key: `_account_path` (`predict.py:102`), `_latest_path` (111), `_projection_path`
  (115); internal call sites at predict.py 313, 341, 375, 569, 594, 1086-1087.

</code_context>

<specifics>
## Specific Ideas

- **Live incident (2026-07-16):** `.claude-account1` (uuid `e1605250`, spiraswift@gmail.com) real 5h **100%**;
  `.claude-account2` (uuid `c87262ba`, khairul.rashid@…) real 5h **50%**. Both share 5h reset `1784191800` →
  shared bucket pinned to max (100) → account2 wrongly rendered 100%. 7d bars differed only because the two
  accounts' 7d `resets_at` differ (separate buckets). The regression test must reproduce exactly this.
- **Acceptance from SPEC:** given stdin `transcript_path` under `~/.claude-account1/projects/…`, resolution
  must yield account1's uuid even when `~/.claude.json` holds account2's uuid.
- **R5b (must-not-borrow):** `CLAUDE_CONFIG_DIR=~/.claude-accountX` whose `~/.claude-accountX/.claude.json`
  does not exist → legacy unsuffixed path, **NOT** `rate_latest.<home-uuid>.json`.

</specifics>

<deferred>
## Deferred Ideas

- Migrating / quarantining / deleting the existing mis-keyed `rate_latest*` / `rate_projection*` files — out
  of scope (fix-forward only; avoids risky data-mutation in a delicate module). Stale shared bucket ages out
  via existing GC/grace logic.
- Changing the reconcile healing algorithm (monotonic-up / grace / confirm-refresh) — correct as-is.
- `account.py`'s email-path home-level fallback is intentionally left unchanged (the stricter no-borrow rule
  applies to *keying* only, implemented in predict.py — not by mutating account.py's email behavior).

</deferred>
