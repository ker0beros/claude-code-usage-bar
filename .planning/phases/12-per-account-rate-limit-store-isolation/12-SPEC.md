# Phase 12: Per-Account Rate-Limit Store Isolation — Specification

**Created:** 2026-07-16
**Ambiguity score:** 0.15 (gate: ≤ 0.20)
**Requirements:** 5 locked

## Goal

The rate-limit reconcile and projection stores are keyed by the *session's own* Claude account (resolved daemon-safe from `transcript_path` → `CLAUDE_CONFIG_DIR` → `~/.claude`), so that when a second account with the same clock-aligned 5h `resets_at` is logged in concurrently, each window's 5h bar shows only its own account's usage — the 5h bar changes from cross-account-max (wrong) to per-account (correct).

## Background

`predict._read_account_id()` (`src/claude_statusbar/predict.py:76`) reads a module-constant `_CLAUDE_JSON_PATH = ~/.claude.json` (`predict.py:72`) and never consults `CLAUDE_CONFIG_DIR` or the session's `transcript_path`. Every logged-in account therefore resolves to whichever `accountUuid` happens to sit in the default `~/.claude.json`, and all accounts write into one shared store file `rate_latest.<uuid>.json` (and `rate_projection.<uuid>.json`), both via `_account_path()` (`predict.py:102`).

Anthropic clock-aligns the 5h window, so different accounts share the *same* 5h `resets_at`. Reconcile buckets are keyed by `(window, resets_at)` (`reconcile_account`, `predict.py:349`), so two accounts' 5h readings land in the *same* bucket; the monotonic-up healing rule pins that bucket to the **max** reading across accounts, and it re-confirms every render so it never heals down.

Observed live 2026-07-16 (same machine, `CLAUDE_CONFIG_DIR` multi-account):
- `.claude-account1` (uuid `e1605250`, spiraswift@gmail.com): real 5h **100%**, 7d reset `1784304000`
- `.claude-account2` (uuid `c87262ba`, khairul.rashid@…): real 5h **50%**, 7d reset `1784505600`
- Both accounts' 5h reset: `1784191800` (identical) → shared bucket pinned to 100 → **both** bars render 100% (account2 wrong; account1 right only by coincidence of being the max).
- The 7d bar is unaffected because the two accounts' 7d `resets_at` differ → separate buckets.

The correct per-session resolver already exists: `account.py` (Phase 11) has `resolve_config_dir(stdin, env, home)` with exactly the `transcript_path` → `CLAUDE_CONFIG_DIR` → `~/.claude` precedence, daemon-safe (the daemon's `os.environ` is frozen at spawn, but `transcript_path` rides in the per-session stdin payload). This phase re-uses that resolver and adds a UUID reader; it does not re-derive resolution logic.

## Requirements

1. **Per-session account resolution in predict.py**: `predict.account_id()` resolves the logged-in account UUID from *this session's* config dir, not a hardcoded path.
   - Current: `predict._read_account_id()` reads hardcoded `~/.claude.json`; ignores `CLAUDE_CONFIG_DIR` and `transcript_path`.
   - Target: resolution reuses `account.resolve_config_dir()` (precedence `transcript_path` → `CLAUDE_CONFIG_DIR` → `~/.claude`), then reads `oauthAccount.accountUuid` from that dir's `.claude.json` (anchored regex, memoized on `(path, mtime_ns, size)` as today). Daemon-safe: works from the frozen-`os.environ` daemon because `transcript_path` comes from stdin.
   - Acceptance: given a stdin payload whose `transcript_path` is rooted at `~/.claude-account1/projects/<enc>/<sid>.jsonl`, resolution yields `e1605250…` (account1); a payload rooted at `~/.claude-account2/…` yields `c87262ba…` — regardless of what `~/.claude.json` contains or what `os.environ["CLAUDE_CONFIG_DIR"]` is.

2. **Session context threaded through every store consumer**: the store path is keyed by the per-session account in all functions that read/write it.
   - Current: `reconcile_account`, `projection`, `forecast`, `quota_cache_status` reach the store via `_latest_path()`/`_projection_path()` → `_account_path()` → `account_id()` with **no** session context, so they all key by the hardcoded-path uuid.
   - Target: session context (the resolved config dir, or the stdin needed to resolve it) is threaded into these functions so every store read and write keys to the correct per-session account; `core.py` passes it from the already-available `stdin_data` (`transcript_path`, `_session_env`).
   - Acceptance: two simulated sessions — account1 transcript and account2 transcript — with identical 5h `resets_at` and different `used_percentage` (100 vs 50) each cause reconcile to open a *distinct* store file; neither run reads or writes the other's bucket (assert on the resolved path + on returned values).

3. **No cross-account collision on a shared 5h `resets_at`** (+ regression test): concurrent accounts sharing a 5h `resets_at` render their own 5h value.
   - Current: shared store + shared `(window, resets_at)` bucket → monotonic-up pins to cross-account max; account2 (real 50%) renders account1's 100%.
   - Target: distinct store files per account → account2 renders 50%, account1 renders 100%, simultaneously.
   - Acceptance: a regression test reproduces the live collision (two accounts, identical 5h `resets_at` `1784191800`, `used_percentage` 100 vs 50) and asserts each account's render returns its own value; the test FAILS against the current hardcoded-path code and PASSES after the fix.

4. **Both persisted stores re-keyed**: the reconcile store *and* the projection/forecast store isolate per account.
   - Current: both `rate_latest.<uuid>.json` and `rate_projection.<uuid>.json` are produced by the same defective `_account_path()`.
   - Target: both files key by the per-session account UUID.
   - Acceptance: with a resolvable session config dir for account1, both `_latest_path()` and `_projection_path()` return paths whose uuid segment is `e1605250…` (account1), not the default `~/.claude.json` uuid.

5. **Unresolvable session → unchanged legacy behavior (and no cross-account borrow)**: when the session's own account cannot be resolved, keying is byte-identical to today; a *named* config dir never borrows the home account.
   - Current: `account_id()` returning `None` makes `_account_path()` return the legacy unsuffixed base path (`rate_latest.json`).
   - Target: (a) API-key users / missing `.claude.json` / unparseable `transcript_path` with no `CLAUDE_CONFIG_DIR` → legacy unsuffixed path, unchanged. (b) A *named* config dir (from `CLAUDE_CONFIG_DIR` or a non-default transcript) that lacks its **own** `.claude.json` must NOT fall back to `$HOME/.claude.json`'s uuid — that would re-introduce the collision; it uses the legacy unsuffixed path instead. The default `~/.claude` dir still correctly reads `$HOME/.claude.json`.
   - Acceptance: (a) empty stdin + no `CLAUDE_CONFIG_DIR` + no resolvable `accountUuid` → store path is exactly `rate_latest.json` (unchanged from today). (b) `CLAUDE_CONFIG_DIR=~/.claude-accountX` where `~/.claude-accountX/.claude.json` does not exist → store path is the legacy unsuffixed path, NOT `rate_latest.<home-uuid>.json`.

## Boundaries

**In scope:**
- Per-session account-UUID resolution in `predict.py`, reusing `account.resolve_config_dir()`.
- Threading session context through `reconcile_account`, `projection`, `forecast`, `quota_cache_status` (and the `core.py` call sites that invoke them).
- Re-keying **both** `rate_latest.<uuid>.json` and `rate_projection.<uuid>.json`.
- A regression test reproducing the two-account / shared-`resets_at` collision.
- Preserving the legacy unsuffixed fallback for unresolvable sessions.

**Out of scope:**
- Migrating, quarantining, or deleting the existing mis-keyed store files — fix-forward only; once keying separates, the stale shared bucket is simply no longer read and ages out via existing GC/grace logic (chosen boundary; avoids risky data-mutation code in a delicate module).
- Changing the reconcile healing algorithm (monotonic-up, grace, confirm-refresh) — the algorithm is correct; only the *store selection* is wrong.
- Changing the email chip / `account.py`'s existing `_claude_json_path` home-level fallback behavior for email — this phase only adds/uses UUID resolution (the stricter named-dir rule in R5b is applied for keying, not by mutating the email path).
- Any change to how Anthropic reports `resets_at` or `used_percentage` (upstream; not ours).
- Network/subprocess of any kind (this is a pure-filesystem render-path change).

## Constraints

- Pure filesystem; no network, no subprocess, no new third-party dependency (render path is Python 3.9+ stdlib only).
- Daemon-safe: resolution must not depend on the shared daemon's frozen `os.environ`; it must work from per-session stdin (`transcript_path` first), matching `account.py`.
- Render fast-path budget: resolution stays effectively a `stat()` in steady state (reuse `account.py`'s `(path, mtime_ns, size)` memoization on the 60–160KB `.claude.json`); no unbounded reads.
- Reads only `oauthAccount.accountUuid` from `.claude.json` — never any OAuth token or other secret.
- Never raises into the render path — any resolution/IO/parse failure yields the legacy fallback (mirrors `account.py`'s never-raise contract).

## Acceptance Criteria

- [ ] With a stdin `transcript_path` under `~/.claude-account1/projects/…`, resolution yields account1's uuid even when `~/.claude.json` holds account2's uuid.
- [ ] Two accounts with identical 5h `resets_at` and different `used_percentage` (100 vs 50) key to distinct store files; each renders its own 5h value.
- [ ] A regression test reproduces the collision (fails pre-fix, passes post-fix).
- [ ] `_latest_path()` and `_projection_path()` both carry the per-session account uuid for a resolvable session.
- [ ] Unresolvable session (no transcript, no `CLAUDE_CONFIG_DIR`, no `accountUuid`) → store path is the legacy unsuffixed `rate_latest.json`, unchanged.
- [ ] A named config dir lacking its own `.claude.json` does NOT key by `$HOME/.claude.json`'s uuid (uses the legacy unsuffixed path instead).
- [ ] No network/subprocess import is added to the resolution/keying path.
- [ ] The resolver reads only `accountUuid`; no OAuth token or secret is read, logged, or persisted.
- [ ] No existing `rate_latest*`/`rate_projection*` file is deleted, moved, or migrated by the new code.
- [ ] Full existing test suite (1090+) still passes; a no-`.planning`/single-account render is byte-for-byte unchanged.

## Edge Coverage

**Coverage:** 4/5 applicable edges resolved · 0 unresolved · 1 dismissed

> Note: the compiled `edge-probe.cjs` engine could not be invoked during this session due to a transient Bash-classifier outage (`claude-sonnet-5` unavailable). Edges were enumerated and resolved **inline** per the workflow's graceful-degradation rule (never a silent skip). Re-running `/gsd-spec-phase 12 --update` when the engine is available will regenerate this table from the canonical taxonomy.

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| malformed-input (transcript shape) | R1 | ✅ covered | AC: unexpected `transcript_path` shape (parents[1] ≠ `projects`) falls back through `CLAUDE_CONFIG_DIR` → `~/.claude` via reused `account.resolve_config_dir()` guard. |
| fallback / cross-account borrow | R5 | ✅ covered | AC(5b): named config dir without its own `.claude.json` uses legacy unsuffixed path, never borrows `$HOME/.claude.json`'s uuid. |
| concurrency (two accounts, shared reset) | R3 | ✅ covered | AC(R3): distinct files per account → no shared bucket → no monotonic-max collision; regression test asserts both values. |
| identity (same account, two dirs) | R3 | ✅ covered | Same real uuid → same store file (correct sharing); asserted so the fix does not over-isolate a genuinely single account. |
| lifecycle (`/login` account switch mid-session) | R1 | ⛔ dismissed | `transcript_path` is immutable for a session; a re-login spawns a new session with a new transcript, so per-session resolution stays consistent. No in-session switch path exists to handle. |

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable prohibitions resolved · 0 unresolved

> Note: the prohibition probe is a prose recall→precision pass by design (no compiled engine). Routine-engineering candidates (must-not-raise, must-not-exceed-budget) were dropped to the edge/constraint sections; no canon security/compliance item applied.

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT read, log, or persist any OAuth token, API key, or other secret from `.claude.json` — only `oauthAccount.accountUuid` is read. | R1 | resolved | verification: test — assert the UUID reader extracts only `accountUuid` and that no secret-bearing key is read/logged (mirrors `account.py` reading only `emailAddress`). |
| MUST NOT delete, move, rename, or migrate any existing `rate_latest*`/`rate_projection*` store file (fix-forward only). | R2, R4 | resolved | verification: test — assert the new keying path performs no `unlink`/`replace`/`rename` of existing account-store files (guards the chosen fix-forward boundary / user data). |
| MUST NOT introduce any network, socket, or subprocess call into the resolution/keying path. | R1, R2 | resolved | verification: test — assert the resolver module imports no `subprocess`/`urllib`/`socket`; preserves the render-path "never opens a socket" invariant. |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                                        |
|--------------------|-------|------|--------|--------------------------------------------------------------|
| Goal Clarity       | 0.90  | 0.75 | ✓      | Concrete before/after: 5h bar cross-account-max → per-account |
| Boundary Clarity   | 0.85  | 0.70 | ✓      | Both stores in; migration/cleanup + algorithm change out      |
| Constraint Clarity | 0.80  | 0.65 | ✓      | Daemon-safe, stdlib-only, memoized, secret-minimal            |
| Acceptance Criteria| 0.82  | 0.70 | ✓      | 10 pass/fail criteria + regression test                       |
| **Ambiguity**      | 0.15  | ≤0.20| ✓      |                                                              |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

## Interview Log

| Round | Perspective     | Question summary                          | Decision locked                                             |
|-------|-----------------|-------------------------------------------|-------------------------------------------------------------|
| 0     | Researcher      | Root cause of 5h=100% on account2?        | `predict.account_id()` hardcodes `~/.claude.json`; accounts collide in one store bucket on shared 5h `resets_at`. |
| 1     | Boundary Keeper | Which stores in scope?                     | Both `rate_latest` and `rate_projection` (same defect).      |
| 1     | Boundary Keeper | Handle the already-poisoned store?         | Fix-forward only — no migration/cleanup code.                |
| 1     | Simplifier      | How does predict.py get the resolver?      | Reuse `account.py`'s `resolve_config_dir()` (single source). |
| 2     | Failure Analyst | Named dir without own `.claude.json`?      | Must NOT borrow `$HOME/.claude.json`'s uuid → legacy path.   |

---

*Phase: 12-per-account-rate-limit-store-isolation*
*Spec created: 2026-07-16*
*Next step: /gsd-discuss-phase 12 — implementation decisions (how to thread session context through predict.py without breaking the reconcile invariants)*
