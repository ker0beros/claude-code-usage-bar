# Phase 11: Account Email Indicator — Specification

**Created:** 2026-07-16
**Ambiguity score:** 0.10 (gate: ≤ 0.20)
**Requirements:** 5 locked

## Goal

The status bar shows the logged-in Claude account's email (e.g. `khairul.rashid@silentmode.my`)
as an opt-in `👤 <email>` chip on the identity line, resolved locally per-session so that a user
running multiple accounts (via `CLAUDE_CONFIG_DIR`) can see at a glance which account is active.

## Background

The maintainer runs several Claude accounts in parallel, each isolated by `CLAUDE_CONFIG_DIR`
(`~/.claude`, `~/.claude-account1`, `~/.claude-account2`, …). Nothing in the bar reveals which
account a given window is on. Claude Code stores the logged-in identity at
`oauthAccount.emailAddress` inside the config dir's `.claude.json` — at `<CONFIG_DIR>/.claude.json`
for a named account, or `$HOME/.claude.json` for the default `~/.claude`. Every statusLine stdin
payload carries `transcript_path`, which is rooted at the active config dir
(`<CONFIG_DIR>/projects/<enc>/<session>.jsonl`), so the config dir — and therefore the correct
`.claude.json` — is derivable per-session. This matters under the shared daemon, whose own
`os.environ` is frozen at spawn time and does not reflect a per-session `CLAUDE_CONFIG_DIR`.

The closest existing analogs: `predict.py._read_account_id()` already scans `~/.claude.json` for
`oauthAccount.accountUuid` via an anchored, mtime-memoized regex; `render_identity_line` already
appends optional chips (cwd, worktree, version) to the identity line.

## Requirements

1. **Account-email reader**: A pure-filesystem module resolves the active account's email or
   returns `None`.
   - Current: no module reads account identity for display; `predict.py` reads only the UUID from
     the hardcoded `~/.claude.json`.
   - Target: `account.resolve_account_email(stdin, *, env, home)` derives the config dir from
     `transcript_path` (falling back to `CLAUDE_CONFIG_DIR`, then `~/.claude`), locates that dir's
     `.claude.json` (falling back to `$HOME/.claude.json`), and returns `oauthAccount.emailAddress`
     via an anchored regex scan memoized on (path, mtime_ns, size). No network, no subprocess.
   - Acceptance: given a fake config dir + `.claude.json`, returns the stored email; returns `None`
     when the file/field is absent or the payload has no usable path.

2. **Per-session config-dir resolution**: The reader picks the config dir for *this* session, not
   the daemon's.
   - Current: n/a — no such resolution exists.
   - Target: `transcript_path` is trusted first (only when its `parents[1]` is `projects`), so the
     shared daemon reads the right account even though its `os.environ` is frozen; `CLAUDE_CONFIG_DIR`
     is stamped into `_cs_env` by `render_thin` as a fallback for paths without a transcript.
   - Acceptance: a transcript under `~/.claude-account2/projects/…` resolves to
     `~/.claude-account2/.claude.json`; with no transcript, `CLAUDE_CONFIG_DIR` is used.

3. **Opt-in config toggle**: A `show_email` flag gates the feature, default **off**.
   - Current: no such flag.
   - Target: `StatusbarConfig.show_email: bool = False`, round-tripped by `load_config`/`save_config`,
     registered in `VALID_KEYS` + `_BOOL_KEYS`, settable via `cs config set show_email on`. Default
     off because it surfaces PII in a widely-distributed tool (matches `show_cwd`/`show_ip_risk`).
   - Acceptance: `StatusbarConfig().show_email is False`; `cs config set show_email on` persists.

4. **Identity-line chip**: When on and resolvable, the email renders as `👤 <email>` on the identity
   line, after the cwd/worktree segment and before the version.
   - Current: the identity line has no account chip.
   - Target: `render_identity_line(..., email_text=…)` appends ` · 👤 <email>` (color path: mute
     glyph + ink email); `render()` pops `email_text` and forwards it. Empty `email_text` appends
     nothing.
   - Acceptance: with `email_text="a@b.com"`, the no-color identity line contains `· 👤 a@b.com`
     positioned before ` · v<version>`; with `email_text=""`, no chip and no stray separator.

5. **Auto-hide + no regression**: The chip appears only when the toggle is on AND an email resolves,
   and changes nothing otherwise.
   - Current: n/a.
   - Target: `core.main()` adds `email_text` to `identity_kwargs` only inside the existing
     `show_project_branch` block, only when `cfg.show_email` and the reader returns non-empty
     (wrapped in try/except). API-key users / missing `.claude.json` → no chip. The chip rides the
     identity line, so it requires `show_project_branch` on (documented boundary).
   - Acceptance: `show_email` off → identity line byte-for-byte unchanged; on but unresolvable →
     unchanged; reader never raises into render.

## Boundaries

**In scope:**
- New `src/claude_statusbar/account.py` reader (config-dir resolution + `.claude.json` email scan).
- `show_email` config field (default off) + validation registration.
- `email_text` param on `render_identity_line` + `render()` dispatcher pop/forward.
- `CLAUDE_CONFIG_DIR` added to `render_thin._SESSION_ENV_KEYS` (per-session env fallback).
- `core.main()` wiring inside the `show_project_branch` block.
- Tests: reader (resolution + email scan + None paths), config round-trip/keys, renderer chip,
  render() plumbing, and the off/unresolvable no-regression guards.

**Out of scope:**
- **Standalone email line** when `show_project_branch` is off — the chip rides the identity line
  only (mirrors cwd's primary placement; a standalone fallback can be added later if wanted).
- **`displayName` / masking / local-part-only** — full email exactly as stored (maintainer choice).
- **`cs preview` output** — preview never renders the identity line, so no email there.
- Any network call, subprocess, or Claude Code invocation; reading OAuth tokens or any secret.
- Multi-account switching UI or cross-account aggregation.

## Constraints

- Reader is pure filesystem, no network/subprocess; must not raise into the render path (guarded,
  returns `None` on any error) — a missing/malformed `.claude.json` must never break the bar.
- Reads only `oauthAccount.emailAddress` via an anchored regex; never parses/loads OAuth tokens or
  other secrets, and never writes the email to disk/cache.
- Memoize on (path, mtime_ns, size) like `predict._read_account_id` so steady-state renders pay
  only a `stat()`; the file is 60–160KB.
- No new third-party dependency (stdlib only).
- Default off — PII must be opt-in in a distributed tool.

## Acceptance Criteria

- [ ] `resolve_account_email` returns the stored email for a fake named-account config dir.
- [ ] Default `~/.claude` config dir falls back to `$HOME/.claude.json`.
- [ ] Missing `.claude.json` / missing `emailAddress` / no path → `None`.
- [ ] `StatusbarConfig().show_email is False`; `show_email` in `VALID_KEYS` and `_BOOL_KEYS`.
- [ ] `render_identity_line(email_text=…)` yields `· 👤 <email>` before the version.
- [ ] `render("classic", show_project_branch=True, identity=…, email_text=…)` puts the chip on the `⤷` line.
- [ ] `show_email` off (or email unresolvable) → identity line byte-for-byte unchanged.
- [ ] Full test suite passes including the new tests.

## Edge Coverage

**Coverage:** 5/5 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| empty/absent input | R1 | ✅ covered | No `.claude.json` / no `emailAddress` / no path → reader returns `None` → no chip |
| malformed input | R1 | ✅ covered | Unparseable JSON bytes → anchored regex simply misses → `None`; reader try/excepts |
| default vs named account | R2 | ✅ covered | `~/.claude` (no per-dir `.claude.json`) falls back to `$HOME/.claude.json` |
| stale daemon env | R2 | ✅ covered | `transcript_path` (per-session) trusted before frozen `os.environ`; `CLAUDE_CONFIG_DIR` stamped into `_cs_env` |
| API-key / no oauthAccount | R5 | ✅ covered | No `oauthAccount` block → `None` → chip auto-hidden, no error |

## Prohibitions (must-NOT)

**Coverage:** 4/4 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT raise into the render path on any missing/malformed `.claude.json` | R1, R5 | resolved | verification: test — reader returns `None`; core wiring try/excepts |
| MUST NOT alter rendered output when `show_email` is off or email unresolvable | R5 | resolved | verification: test — byte-for-byte-unchanged assertions |
| MUST NOT read/parse OAuth tokens or any secret, nor persist the email to disk | R1 | resolved | verification: judgment — only `emailAddress` scanned; nothing written |
| MUST NOT perform any network call or subprocess | R1 | resolved | verification: judgment — pure filesystem reads only (mirrors `predict._read_account_id`) |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                             |
|--------------------|-------|------|--------|---------------------------------------------------|
| Goal Clarity       | 0.93  | 0.75 | ✓      | Exact format (`👤 <full email>`) + source locked  |
| Boundary Clarity   | 0.90  | 0.70 | ✓      | Explicit out-of-scope (standalone line, displayName, preview) |
| Constraint Clarity | 0.88  | 0.65 | ✓      | Pure-fs, no-dep, memoized, no-secret, opt-in      |
| Acceptance Criteria| 0.88  | 0.70 | ✓      | 8 pass/fail criteria                              |
| **Ambiguity**      | 0.10  | ≤0.20| ✓      |                                                   |

## Interview Log

| Round | Perspective     | Question summary              | Decision locked                                    |
|-------|-----------------|-------------------------------|----------------------------------------------------|
| 1     | Researcher      | What to show?                 | Logged-in account **email** (was: profile dir name) |
| 1     | Boundary Keeper | Placement?                    | Chip on the identity line (before version)         |
| 2     | Simplifier      | Format?                       | Full email exactly as stored (no displayName/mask) |
| 2     | Failure Analyst | Which account under daemon?   | Derive config dir from `transcript_path` (per-session) |
| 3     | Boundary Keeper | Default on/off?               | Off (opt-in) — PII in a distributed tool           |
| 3     | Seed Closer     | Process?                      | Full GSD phase (SPEC → plans [11-01/02] → tests)   |

---

*Phase: 11-account-email-indicator*
*Spec created: 2026-07-16*
*Next step: implemented directly per approved plan (account.py reader + show_email → identity chip + core wiring → tests)*
