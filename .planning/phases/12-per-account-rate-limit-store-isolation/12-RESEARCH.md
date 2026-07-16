# Phase 12: Per-Account Rate-Limit Store Isolation - Research

**Researched:** 2026-07-16
**Domain:** Internal bug-fix — Python stdlib-only render-path code (predict.py/core.py), no external library research required
**Confidence:** HIGH (all claims verified by direct source read + a live full-suite test run; nothing in this phase depends on external packages, docs, or unfamiliar APIs)

## Summary

This phase is a surgical, code-archaeology research job, not a stack-selection job. The SPEC/CONTEXT (ambiguity 0.15) already lock the design: thread an explicit, optional, already-resolved account-UUID parameter through `predict.py`'s four public store consumers down into `_account_path()`, resolved once per render in `core.py` via a new per-session `predict.account_id(stdin, env)` that reuses `account.resolve_config_dir()`. My job was to confirm the exact call graph the plan must touch, verify the reconcile invariants that must survive threading untouched, and — most importantly — design the regression test architecture, because R3's acceptance criterion ("reproduces the collision, FAILS pre-fix, PASSES post-fix") is the phase's real deliverable.

Three findings materially sharpen the plan beyond what CONTEXT.md states:

1. **The "no function overloading" problem has one clean, unambiguous solution**: a private module-level sentinel (`_UNSET = object()`) distinguishing "caller passed no session context" (→ legacy hardcoded resolver, zero risk to the 1090-test suite) from "caller passed a resolved uuid of `None`" (→ legacy **unsuffixed** path, never falls through to the legacy resolver). Using plain `aid=None` as the default would silently violate R5b (home-uuid borrow) the moment core.py passes a resolved-but-empty uuid down — this is the single highest-risk implementation detail in the phase and CONTEXT.md does not spell it out.
2. **`regime_changed_at()` is a second-order call site inside `projection()`** (predict.py:1185) that CONTEXT's line-number list already covers as an internal `_latest_path()` caller (line 341) but the *call from `projection()`* is easy to miss when threading — if the plan threads the account param into `load_projection_store`/`save_projection_store` but forgets `regime_changed_at()`, the regime-boundary logic silently reads the wrong (default) account's reconcile store while the projection data itself is correctly isolated. This is a subtle, hard-to-catch bug distinct from a wrong % — it is a silent shift in smoothing behavior with no null render to catch it.
3. **The exact prohibition tests already have a reusable harness in this codebase**: `tests/test_import_perf.py::_list_imports_for` is the established pattern for "module X must not import Y" assertions — reuse it verbatim for the no-network/no-subprocess prohibition rather than inventing a new mechanism.

**Primary recommendation:** Implement via a sentinel-based `_account_path(base, aid=_UNSET)` (see Code Examples), give the new per-session UUID reader its own dedicated memoized cache (do not touch `_ACCOUNT_CACHE`), and build the regression test as a true end-to-end `core.main()` invocation with real `.claude.json`/transcript fixtures under `tmp_path` — not a mocked/monkeypatched `reconcile_account` call — because only an end-to-end test proves the wiring from stdin through to render output, which is what actually broke in production.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Session account-UUID resolution (dir precedence) | API/Backend (predict.py, reusing account.py) | — | Pure filesystem logic inside the render-path module; no client/server split in this CLI |
| Store path selection (`_account_path`/`_latest_path`/`_projection_path`) | API/Backend (predict.py) | — | Internal to predict.py; never crosses a process/module boundary |
| Store read/write (reconcile + projection JSON files) | Database/Storage (local filesystem cache) | API/Backend (predict.py owns the schema) | `~/.cache/claude-statusbar/*.json` is the persistence layer; predict.py is its only reader/writer |
| Session-context threading (stdin → resolved uuid) | API/Backend (core.py `main()`) | — | `core.py` is the only caller with access to `stdin_data`/`_effective_env`; predict.py must stay a pure function of its arguments |
| Regression/isolation testing | Test tier (tests/) | — | New test file exercises core.py→predict.py→filesystem end-to-end |

This is a single-tier CLI (no browser/frontend-server split), so the map above substitutes the project's own module boundaries for the usual browser/API/DB tiers. Nothing in this phase crosses a network or process boundary — confirmed by the constraint (stdlib-only, no subprocess/network) and by `tests/test_import_perf.py`'s existing render-path import guards.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| R1 | Per-session account resolution in predict.py via `account.resolve_config_dir()` reuse | Call graph (below) confirms `account.resolve_config_dir` is the single source of dir precedence and is safely reusable as-is; a **new**, keying-specific `.claude.json` locator is required (not `account._claude_json_path`) to satisfy R5b — exact diff given in Code Examples |
| R2 | Session context threaded through `reconcile_account`/`projection`/`forecast`/`quota_cache_status` | Exact signatures, current call sites, and the sentinel-based threading pattern that preserves all existing zero-arg callers are documented below |
| R3 | No cross-account collision on shared 5h `resets_at` (+ regression test) | Full Validation Architecture section designs the exact regression test, fixtures, and assertions reproducing the live incident |
| R4 | Both `_latest_path()` and `_projection_path()` re-keyed | Confirmed both route through the same `_account_path()`; a single threading fix covers both, but `projection()`'s indirect `regime_changed_at()` call (landmine #2) must not be missed |
| R5 | Unresolvable session → legacy path; named dir w/o own `.claude.json` → legacy path, no home-borrow (R5a/R5b) | Sentinel design in Code Examples makes R5a and R5b mechanically satisfied — the "aid explicitly None" branch never invokes the legacy hardcoded resolver, so it cannot borrow `$HOME/.claude.json` |
</phase_requirements>

## Package Legitimacy Audit

**Not applicable.** This phase adds zero external dependencies (SPEC constraint: "no new third-party dependency; render path is Python 3.9+ stdlib only"). No packages to audit. Skip the Package Legitimacy Gate protocol entirely.

## Standard Stack

**Not applicable in the usual sense** — this is a bug fix inside an existing stdlib-only module, not new-stack selection. The "stack" is: Python 3.9+ stdlib (`pathlib`, `re`, `json`, `os`), the project's own `account.py` (Phase 11) and `predict.py` modules, and `pytest`/`monkeypatch` for tests (already in `.venv`, verified below).

**Version verification (environment, not packages):**
```
$ .venv/bin/python -m pytest tests/ -q
1090 passed in 4.54s
```
`[VERIFIED: local run]` — confirms the baseline the plan must not regress, and that pytest/monkeypatch are already set up exactly as CONTEXT.md assumes.

## Architecture Patterns

### System Architecture Diagram

```
statusLine stdin (JSON: transcript_path, _cs_env, rate_limits{...})
        │
        ▼
core.parse_stdin_data() ──► stdin_data dict (+ _session_env)
        │
        ▼
core.main()
  _effective_env = stdin_data['_session_env'] or os.environ
        │
        ├─► [NEW] predict.account_id(stdin_data, env=_effective_env)
        │         │
        │         ├─ stdin.transcript_path ─► account._config_dir_from_transcript()
        │         ├─ env['CLAUDE_CONFIG_DIR']                    │  (Phase 11, reused as-is)
        │         └─ default: home/.claude                       ▼
        │                                          account.resolve_config_dir() → config_dir
        │         │
        │         └─► [NEW] _claude_json_path_for_keying(config_dir, home)  (R5b: no home-borrow
        │                    │                                                for a NAMED dir)
        │                    ▼
        │             <config_dir>/.claude.json  (or $HOME/.claude.json only when config_dir == default)
        │                    │
        │                    ▼
        │             regex-extract oauthAccount.accountUuid, memoized on (path, mtime_ns, size)
        │                    │
        │                    ▼
        │             resolved_uuid: Optional[str]   (None ⇒ R5a/R5b legacy path, never home-borrow)
        │
        ▼
  reconcile_account(..., account_uuid=resolved_uuid)
  projection(..., account_uuid=resolved_uuid)          ──► _account_path(base, aid=resolved_uuid)
  forecast(..., account_uuid=resolved_uuid)                    │
  quota_cache_status(account_uuid=resolved_uuid)                ├─ aid is _UNSET (arg omitted) → legacy account_id() [unchanged]
        │                                                       ├─ aid is None (resolved, unresolvable) → base (unsuffixed) [R5a/R5b]
        │                                                       └─ aid is "uuid..." → base.<uuid[:12]>.json [R1-R4]
        ▼
  ~/.cache/claude-statusbar/rate_latest[.<uuid12>].json
  ~/.cache/claude-statusbar/rate_projection[.<uuid12>].json
        │
        ▼
  rendered 5h/7d bars (per-account, no cross-account collision)
```

### Recommended file changes (no new files in src/)
```
src/claude_statusbar/
├── account.py     # UNCHANGED (Phase 11 resolver reused as-is; email fallback untouched)
├── predict.py     # MODIFIED: sentinel _UNSET, _account_path(base, aid=_UNSET), _latest_path/_projection_path
│                   #   gain aid param; reconcile_account/forecast/projection/quota_cache_status gain
│                   #   account_uuid=_UNSET; new account_id(stdin=None, *, env=None, home=None); new
│                   #   _claude_json_path_for_keying(); new dedicated memoized cache for the keying reader
└── core.py        # MODIFIED: resolve predict.account_id(stdin_data, env=_effective_env) once, thread into
                    #   the 3 call sites (reconcile_account ~1423, projection ~1500, quota_cache_status ~1571)
```

### Pattern 1: Sentinel-based optional threading (the phase's core technique)
**What:** A private sentinel object distinguishes "argument omitted" (legacy behavior) from "argument explicitly `None`" (a resolution attempt that failed).
**When to use:** Any time a function must tell apart "caller doesn't know/care about X" from "caller knows X is absent" — exactly this phase's R5a/R5b requirement.
**Example:**
```python
# Source: derived from predict.py's existing path=None DI idiom (predict.py:297,349,568,593),
# extended with a sentinel because None itself is now a meaningful, distinct value.
_UNSET = object()

def _account_path(base: Path, aid=_UNSET) -> Path:
    """Per-account variant of a shared-store path.

    aid is _UNSET (arg omitted) -> legacy hardcoded resolver, unchanged behavior.
    aid is None (session resolved, but unresolvable) -> legacy unsuffixed path,
      NEVER the legacy resolver (R5a/R5b: no $HOME/.claude.json borrow).
    aid is a uuid string -> per-account suffixed path.
    """
    if aid is _UNSET:
        aid = account_id()          # today's hardcoded ~/.claude.json resolver
    if not aid:
        return base
    return base.with_name(f"{base.stem}.{aid[:12]}{base.suffix}")
```

### Pattern 2: Keying-specific `.claude.json` locator (R5b, do NOT reuse account.py's email locator)
**What:** A locator that only falls back to `$HOME/.claude.json` for the *default* `~/.claude` config dir — not for any other named dir.
**When to use:** Exactly the account-UUID keying path. `account._claude_json_path()` is intentionally different (always falls back to home-level) and must stay that way for the email feature — CONTEXT.md explicitly forbids mutating it.
**Example:**
```python
# Source: contrast with account.py:81-94 (_claude_json_path), which ALWAYS falls
# back to home_level for any config_dir — that is exactly the behavior R5b forbids
# for keying (it would silently borrow $HOME/.claude.json's uuid for a named,
# not-yet-populated CLAUDE_CONFIG_DIR).
def _claude_json_path_for_keying(config_dir: Path, home: Path) -> Optional[Path]:
    per_dir = config_dir / ".claude.json"
    if per_dir.is_file():
        return per_dir
    if config_dir == home / ".claude":       # ONLY the default dir may borrow
        home_level = home / ".claude.json"
        if home_level.is_file():
            return home_level
    return None
```

### Pattern 3: `account_id()` gains an optional first param without breaking zero-arg callers
**What:** `stdin=None` as the discriminator (stdin is never `None` in real core.py calls — it's always a dict, possibly `{}` — so `None` cleanly means "no session context requested").
**Example:**
```python
# Source: mirrors account.resolve_account_email's structure (account.py:124-143)
# but keeps the function name account_id() unchanged so _account_path's default
# branch (aid is _UNSET -> account_id()) and every existing zero-arg call site
# (predict.py's own legacy branch, tests/test_account_switch.py's monkeypatched
# `lambda: "uuid"`) continue to work with NO signature change on their end.
def account_id(stdin: Optional[Mapping[str, Any]] = None, *,
                env: Optional[Mapping[str, str]] = None,
                home: Optional[Path] = None) -> Optional[str]:
    if stdin is None:
        return _read_account_id()          # UNCHANGED legacy path
    try:
        from . import account as _account
        home = Path(os.path.expanduser("~")) if home is None else home
        config_dir = _account.resolve_config_dir(stdin, env=env, home=home)
        path = _claude_json_path_for_keying(config_dir, home)
        if path is None:
            return None
        return _read_keyed_account_id(path)   # NEW path-aware reader, see Landmine 2
    except Exception:
        return None
```

### Anti-Patterns to Avoid
- **Plain `aid=None` default (no sentinel):** collapses "omitted" and "resolved-to-None" into one branch. Whichever behavior you pick for that merged branch, it's wrong for the other case — either the 1090-test suite's zero-arg callers change behavior, or R5b's no-home-borrow guarantee breaks the moment core.py passes a real resolved `None`.
- **Reusing `account._claude_json_path` for keying:** it unconditionally falls back to `$HOME/.claude.json`, which is precisely the collision R5b closes. CONTEXT.md already flags this; confirmed by direct read of account.py:81-94.
- **A module-level global/contextvar for the resolved uuid:** explicitly forbidden by CONTEXT.md (daemon serves multiple sessions from one process, confirmed below — a global would let session B's render read/write session A's resolved uuid mid-interleave).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Config-dir precedence (transcript_path → CLAUDE_CONFIG_DIR → ~/.claude) | A new resolver in predict.py | `account.resolve_config_dir()` (Phase 11, account.py:55) | Already daemon-safe, already tested (test_account.py), reusing it is explicitly the locked decision — writing a second implementation would let the two drift apart over time |
| Anchored-regex + stat-memoization JSON field extraction | A JSON-parse-the-whole-file reader | Mirror the existing `_read_account_id`/`account._read_email` anchor+regex+`(mtime_ns,size)` pattern | The whole point of the pattern is avoiding a full `json.loads` of a 60-270KB file every render tick; a naive parse would blow the "stays a stat()" budget constraint |
| "No network/subprocess" verification | A bespoke static-analysis script | `tests/test_import_perf.py::_list_imports_for` (already imports the module in a subprocess and inspects `sys.modules`) | Exact existing harness for this exact class of assertion — reuse, don't reinvent |

**Key insight:** Every piece this phase needs already exists somewhere in the codebase (account.py's resolver, predict.py's memoization idiom, test_import_perf's import-graph check) except the keying-specific `.claude.json` locator and the sentinel-based threading — those two are genuinely new, small, and isolated.

## Common Pitfalls

### Pitfall 1: Collapsing "omitted" and "resolved-None" (the phase's #1 risk)
**What goes wrong:** `_account_path(base, aid=None)` (no sentinel) either (a) always falls back to the legacy resolver when `aid` is falsy, silently reintroducing the R5b home-borrow bug for every unresolvable *named* session, or (b) always returns the legacy unsuffixed path when `aid` is falsy, silently breaking every existing zero-arg caller/test that relies on the legacy resolver still working (e.g., any non-core caller, `cli.py --status`, etc., that never learned about session context).
**Why it happens:** `None` is the natural, idiomatic Python default — it takes deliberate effort to notice it's already a meaningful value in this specific case (an attempted-but-failed resolution).
**How to avoid:** Use the `_UNSET` sentinel pattern in Code Examples above. Verify with a Nyquist-owned test explicitly asserting all three branches (omitted / None / uuid) produce three different paths.
**Warning signs:** Any test that expects "unresolvable session uses legacy path" AND "no-session-context callers keep working" starts failing together — that pairing is the signature of the collapsed-branch bug.

### Pitfall 2: `regime_changed_at()`'s indirect call inside `projection()` (predict.py:1185)
**What goes wrong:** `projection()` internally calls `since = regime_changed_at()` with **no path argument** at all (predict.py line 1185). `regime_changed_at(path=None)` defaults to `_latest_path()` — the *reconcile* store, not the projection store — because the regime-boundary marker (`store["regime"]`) is written by `reconcile_account()` into the 5h/7d reading store. If the plan threads `account_uuid` into `load_projection_store`/`save_projection_store` (both called from `projection()`) but not into this `regime_changed_at()` call, the projection's own store correctly isolates per account, while the regime-boundary check silently keeps reading account A's (or the default account's) reconcile store — producing a subtly wrong smoothing/lookback-clip decision that no acceptance-criteria assertion on used_pct alone would catch.
**Why it happens:** `regime_changed_at` isn't one of the "four public store consumers" CONTEXT.md names as top-level threading targets (`reconcile_account`/`forecast`/`projection`/`quota_cache_status`) — it's a second-order internal call one level down inside `projection()`'s body, easy to miss when scanning for "functions that take `path=`".
**How to avoid:** When threading `account_uuid` through `projection()`, also pass it to `regime_changed_at(path=_latest_path(account_uuid))` (or add an `aid` param to `regime_changed_at` itself, mirroring the others). Add an explicit unit test asserting `regime_changed_at` receives/uses the per-session path when called from `projection()` — e.g. by monkeypatching it and asserting the passed path argument.
**Warning signs:** A regime-boundary ("model-switch"/"fleet-join") smoothing test that passes for the 5h/7d values but a burn-rate-cap test involving model switches behaves as if it read the wrong account's regime timestamp.

### Pitfall 3: Single-entry cache thrashing under the shared daemon (accepted precedent, do not over-engineer)
**What goes wrong:** The daemon is a single long-lived process (confirmed: `daemon.py:_render_payload` calls `core_main()` in-process per session, using `signal.alarm` which only works meaningfully on a single thread/process — i.e., it interleaves renders for *different sessions/accounts sequentially in one process*). A naive single-entry memoized cache for the new keying reader, if it does NOT include the file path in its cache-invalidation signature, will: (a) risk a false-cache-hit collision if two different accounts' `.claude.json` files happen to share `(mtime_ns, size)`, and (b) thrash on every render when the daemon round-robins between two different accounts' sessions, since each render's differing `path` invalidates the previous session's cached entry — defeating the "resolution stays effectively a stat()" render-fast-path budget constraint for BOTH sessions.
**Why it happens:** The *existing* legacy `_read_account_id()`/`_ACCOUNT_CACHE` only ever reads one path (`_CLAUDE_JSON_PATH`), so its `(mtime_ns, size)`-only signature was safe by construction — that assumption breaks the moment there are multiple possible paths.
**How to avoid:** Mirror `account.py`'s already-shipped `_read_email`/`_EMAIL_CACHE` pattern exactly: signature `f"{path}\0{mtime_ns}\0{size}"` (path included). This is the SAME accepted tradeoff Phase 11 already shipped for the email chip (thrashing across interleaved different-account sessions in one daemon process is a known, accepted cost — a multi-entry LRU cache would fix it but is explicitly out of scope; don't introduce one here that Phase 11 didn't need either).
**Warning signs:** A perf-sensitive review flags "cache always misses across daemon ticks in a two-account scenario" — that's expected and matches Phase 11's precedent, not a regression to fix in this phase.

### Pitfall 4: New cache reusing/colliding with `_ACCOUNT_CACHE`
**What goes wrong:** If the new per-session keying reader reuses the existing module-level `_ACCOUNT_CACHE` dict (rather than a dedicated one), a render that calls both the legacy zero-arg `account_id()` (e.g., from a non-core caller, or from `_account_path`'s `_UNSET` branch) and the new per-session `account_id(stdin, env=...)` in the same process will stomp each other's cached signature, causing spurious re-reads or (worse) a stale cross-contaminated `id` value.
**How to avoid:** Give the new reader its own dict, e.g. `_SESSION_ACCOUNT_CACHE: Dict[str, Any] = {"sig": None, "id": None}`, entirely separate from `_ACCOUNT_CACHE`. Confirmed safe: `test_account_switch.py`'s three `_ACCOUNT_CACHE`-touching tests (`test_account_id_reads_oauth_account_uuid`, `test_account_id_tracks_file_change`, `test_account_id_missing_file_is_none`) only reset the legacy cache to blank and never assert its dict identity, so a second, independent cache dict introduces zero conflict.

### Pitfall 5: Positional-argument insertion breaking existing test call sites
**What goes wrong:** Inserting the new `account_uuid` parameter in the *middle* of an existing positional signature (e.g., between `resets_7d` and `path` in `reconcile_account`) would silently reinterpret existing tests' positional args.
**How to avoid:** Confirmed safe by direct inspection — every existing call site in `tests/test_predict.py`/`tests/test_core_projection.py`/`tests/test_core_forecast_guard.py` that passes `path=`/`now=`/`session_id=` does so **by keyword**, and `core.py`'s three call sites (line ~1423, ~1500, ~1571) also pass every argument by keyword. Appending `account_uuid=_UNSET` as the new final parameter on `reconcile_account`, `forecast`, `projection`, and `quota_cache_status` is safe with zero call-site changes required for any existing (non-account-aware) caller.

## Code Examples

### `_latest_path`/`_projection_path` threading (R2, R4)
```python
# Source: derived from predict.py:111-116, extended with the sentinel from Pattern 1.
def _latest_path(aid=_UNSET) -> Path:
    return _account_path(_LATEST_PATH, aid)

def _projection_path(aid=_UNSET) -> Path:
    return _account_path(_PROJECTION_PATH, aid)
```

### `reconcile_account`/`quota_cache_status` threading (append-only, keyword-safe)
```python
# Source: predict.py:297 and :349 — path resolution line changes from
# `_latest_path()` to `_latest_path(account_uuid)`; every other line untouched.
def quota_cache_status(now=None, path=None, account_uuid=_UNSET):
    ...
    p = Path(path) if path is not None else _latest_path(account_uuid)
    ...

def reconcile_account(used_5h, resets_5h, used_7d, resets_7d, path=None, now=None,
                      session_id=None, record=True, model=None, account_uuid=_UNSET):
    ...
    p = Path(path) if path is not None else _latest_path(account_uuid)
    ...
```

### `forecast`/`projection` threading, including the regime_changed_at landmine fix
```python
# Source: predict.py:541-554 and :1166-1200
def forecast(used_5h, resets_5h, used_7d, resets_7d, now: float, account_uuid=_UNSET):
    try:
        u5, r5, u7, r7 = reconcile_account(used_5h, resets_5h, used_7d, resets_7d,
                                           now=now, record=False,
                                           account_uuid=account_uuid)
        ...

def projection(used_5h, resets_5h, used_7d, resets_7d, now: float, session_id: str = "",
               account_uuid=_UNSET):
    try:
        u5, r5, u7, r7 = reconcile_account(used_5h, resets_5h, used_7d, resets_7d,
                                           now=now, record=False,
                                           account_uuid=account_uuid)
        ts = float(now)
        key = _projection_result_key(u5, r5, u7, r7, account_uuid)  # thread here too (line 1086-1087)
        ...
        store = load_projection_store(path=_projection_path(account_uuid))
        since = regime_changed_at(path=_latest_path(account_uuid))  # <-- Pitfall 2 fix
        p5 = _projection_for_window(store, "five_hour", u5, r5, now, session_id, since=since)
        p7 = _projection_for_window(store, "seven_day", u7, r7, now, session_id, since=since)
        save_projection_store(store, path=_projection_path(account_uuid))
        ...
```
`_projection_result_key` (predict.py:1081-1094) already calls `str(_projection_path())`/`str(_latest_path())` with no args — this must also gain the `account_uuid` thread-through so the 1s result cache key differs per account (otherwise account B's render within 1s of account A's could receive A's cached `(p5, p7)` tuple — the same class of bug as Pitfall 2, one level shallower).

### core.py call-site changes (3 sites)
```python
# Source: core.py:1064-1066 (existing) + new resolution line, mirroring the
# Phase 11 email-chip call convention at core.py:1174-1176 exactly.
from .predict import account_id as _predict_account_id
_resolved_account_uuid = _predict_account_id(stdin_data, env=_effective_env)

# core.py:1423-1429
msgs_pct, resets_at, weekly_pct, resets_at_7d = reconcile_account(
    msgs_pct, resets_at, weekly_pct, resets_at_7d,
    session_id=stdin_data.get('session_id') or None,
    model=stdin_data.get('model_id') or None,
    account_uuid=_resolved_account_uuid,
)

# core.py:1500-1507
p5, p7 = projection(
    used_5h=msgs_pct, resets_5h=resets_at, used_7d=weekly_pct, resets_7d=resets_at_7d,
    now=_t.time(), session_id=stdin_data.get("session_id", ""),
    account_uuid=_resolved_account_uuid,
)

# core.py:1571-1572
_st, _ = quota_cache_status(account_uuid=_resolved_account_uuid)
```
Resolve `_resolved_account_uuid` once near the top of `main()` (alongside `_effective_env`, core.py:1064-1066) inside a `try/except Exception: _resolved_account_uuid = None` guard — matching the never-raise contract and the existing style at core.py:1171-1180 for `resolve_account_email`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `predict._read_account_id()` hardcodes `~/.claude.json`, ignores session context | `predict.account_id(stdin, env)` resolves per-session via `account.resolve_config_dir()` | This phase | 5h/7d bars stop leaking cross-account under concurrent multi-account use |
| Reconcile/projection stores keyed by whichever account happens to be at `~/.claude.json` | Stores keyed by the session's own resolved account uuid, with legacy unsuffixed fallback preserved | This phase | Matches the Phase 11 precedent (email chip) already shipped for account resolution |

**Deprecated/outdated:** None — `_read_account_id()`/`_ACCOUNT_CACHE`/`account_id()` zero-arg behavior is explicitly preserved, not deprecated (backward-compat default).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The daemon interleaves renders for different sessions/accounts *sequentially within a single process* (not one process per session) | Pitfall 3 | If wrong (e.g., some deployment forks per session), the single-entry-cache-thrashing tradeoff is moot and the landmine downgrades from "known cost" to "not applicable" — either way, the sentinel/threading design is unaffected, only the cache-cost framing changes. Basis: direct read of `daemon.py:397-441` (`_render_payload` calls `core_main()` in-process, guarded by `signal.alarm` which is documented as POSIX-only and single-thread-oriented) — this is `[VERIFIED: source read]`, not `[ASSUMED]`, but flagging here since it underpins a design recommendation (don't build a multi-entry cache) rather than a hard requirement. |

**All other claims in this research were verified by direct source read** (`predict.py`, `account.py`, `core.py`, `daemon.py`, and the `tests/` directory) or by a live local test run (`.venv/bin/python -m pytest tests/ -q` → 1090 passed). No package/library research was performed because none is needed — no `[ASSUMED]` package-provenance claims exist in this document.

## Open Questions

1. **Should `account_id`'s new per-session branch be exposed as `predict.account_id(stdin, env=...)` (same name, optional first arg) or a distinctly-named function?**
   - What we know: CONTEXT.md explicitly names it `predict.account_id(stdin, env)`; the existing zero-arg `account_id()` is called internally by `_account_path`'s `_UNSET` branch and directly monkeypatched (as a zero-arg lambda) by `tests/test_account_switch.py`.
   - What's unclear: whether the planner prefers a single overloaded-by-optional-arg function (my recommendation, shown in Code Examples — `stdin: Optional[Mapping] = None`) or two distinctly named functions for clarity.
   - Recommendation: keep the single name with `stdin=None` as the discriminator (Code Examples Pattern 3) — it satisfies CONTEXT.md's literal wording, requires zero changes to existing zero-arg call sites/tests, and keeps `_account_path`'s two-sentinel design (`_UNSET` vs `None` vs resolved uuid) the only place a reader needs to reason about tri-state defaults.

2. **Does `_projection_result_key` need an explicit test, or is it covered implicitly by the R3 regression test?**
   - What we know: it's a 1-second result cache; the regression test's two renders are far enough apart in test execution to not collide in practice within pytest, so a bug here (forgetting to thread `account_uuid` into it) would NOT be caught by the primary regression test as designed below.
   - What's unclear: whether the planner wants a dedicated fast-sequential-render test (two `projection()` calls for different accounts within the same wall-clock second) to specifically exercise this cache.
   - Recommendation: add one narrow unit test (see Validation Architecture, `test_projection_result_cache_keys_by_account`) — cheap to write, closes a real gap the end-to-end regression test cannot see.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (`.venv/bin/python -m pytest`), no config file beyond default discovery — confirmed 1090 tests currently pass |
| Config file | none (pytest defaults; `tests/__init__.py` present so cross-test imports work, e.g. reusing `test_import_perf._list_imports_for`) |
| Quick run command | `.venv/bin/python -m pytest tests/test_account_rate_isolation.py -q` (new file, see below) |
| Full suite command | `.venv/bin/python -m pytest tests/ -q` |

### Phase Requirements → Test Map

New file: `tests/test_account_rate_isolation.py` (naming mirrors the existing `tests/test_account_switch.py` convention for the same defect class — cross-account store leakage — and keeps the Phase 11 `tests/test_account.py` fixture idioms).

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| R3 (primary) | Two accounts, identical 5h `resets_at` (1784191800), used 100 vs 50, each renders own value | integration (core.main() end-to-end) | `pytest tests/test_account_rate_isolation.py::test_two_accounts_share_5h_reset_render_own_values -x` | Wave 0 |
| R1 | `transcript_path` under `.claude-account1/projects/…` resolves account1's uuid even when `~/.claude.json` holds account2's | unit | `pytest tests/test_account_rate_isolation.py::test_account_id_resolves_from_transcript_over_home_json -x` | Wave 0 |
| R4 | `_latest_path()`/`_projection_path()` both carry the resolved uuid | unit | `pytest tests/test_account_rate_isolation.py::test_store_paths_carry_session_uuid -x` | Wave 0 |
| R5a | Unresolvable session (no transcript, no CLAUDE_CONFIG_DIR, no accountUuid) → legacy unsuffixed path, unchanged | unit | `pytest tests/test_account_rate_isolation.py::test_unresolvable_session_uses_legacy_path -x` | Wave 0 |
| R5b | Named dir lacking own `.claude.json` → legacy unsuffixed path, NOT `$HOME/.claude.json`'s uuid | unit | `pytest tests/test_account_rate_isolation.py::test_named_dir_without_own_json_does_not_borrow_home -x` | Wave 0 |
| edge: identity | Same real uuid, two different config dirs → same store (no over-isolation) | unit | `pytest tests/test_account_rate_isolation.py::test_same_account_two_dirs_shares_store -x` | Wave 0 |
| prohibition: no secret read | Only `accountUuid` extracted; no OAuth token/secret field read | unit | `pytest tests/test_account_rate_isolation.py::test_keying_reader_reads_only_account_uuid -x` | Wave 0 |
| prohibition: no data mutation | No `unlink`/`replace`/`rename` of existing `rate_latest*`/`rate_projection*` files | unit | `pytest tests/test_account_rate_isolation.py::test_no_destructive_fs_ops_on_existing_stores -x` | Wave 0 |
| prohibition: no network/subprocess | `predict.py` imports no `subprocess`/`socket`/`urllib` | unit | `pytest tests/test_account_rate_isolation.py::test_predict_module_imports_no_network_or_subprocess -x` | Wave 0 |
| landmine coverage | Sentinel branches (omitted / None / uuid) each produce a distinct path | unit | `pytest tests/test_account_rate_isolation.py::test_account_path_three_way_branch -x` | Wave 0 |
| landmine coverage | `regime_changed_at` reads the per-account path when called from `projection()` | unit | `pytest tests/test_account_rate_isolation.py::test_projection_threads_account_into_regime_check -x` | Wave 0 |
| landmine coverage | `_projection_result_key` differs per account (1s cache doesn't leak across accounts) | unit | `pytest tests/test_account_rate_isolation.py::test_projection_result_cache_keys_by_account -x` | Wave 0 |
| regression (byte-identical) | No-`.planning`/single-account render unchanged when no session context passed | smoke | full suite run (existing tests already cover this; no new test needed — see below) | n/a (covered by existing suite) |

### Detailed test designs

**`test_two_accounts_share_5h_reset_render_own_values`** (THE regression test — R3's acceptance criterion, "FAILS pre-fix, PASSES post-fix"):
```python
# Structure (fixture pattern mirrors tests/test_account.py's _write_claude_json +
# tests/test_core_projection.py's _write_config + _payload_with_limits):
def test_two_accounts_share_5h_reset_render_own_values(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_config(tmp_path, show_forecast=False, show_projection=False)  # keep render minimal

    # Two real per-account dirs, each with their OWN .claude.json (live-incident uuids).
    acct1_dir = tmp_path / ".claude-account1"
    acct2_dir = tmp_path / ".claude-account2"
    _write_claude_json(acct1_dir / ".claude.json", uuid="e1605250-...")
    _write_claude_json(acct2_dir / ".claude.json", uuid="c87262ba-...")
    tp1 = acct1_dir / "projects" / "-enc-" / "sid1.jsonl"
    tp2 = acct2_dir / "projects" / "-enc-" / "sid2.jsonl"
    tp1.parent.mkdir(parents=True); tp1.touch()
    tp2.parent.mkdir(parents=True); tp2.touch()

    RESETS_5H = 1784191800  # identical clock-aligned reset — the live collision
    payload1 = _payload_with_limits("s1", 100.0, RESETS_5H, 5.0, 1784304000,
                                     transcript_path=str(tp1))
    payload2 = _payload_with_limits("s2", 50.0, RESETS_5H, 3.0, 1784505600,
                                     transcript_path=str(tp2))

    monkeypatch.setattr(sys, "stdin", io.StringIO(payload1))
    from claude_statusbar.core import main
    main(use_color=False, _suppress_side_effects=True)
    out1 = capsys.readouterr().out

    monkeypatch.setattr(sys, "stdin", io.StringIO(payload2))
    main(use_color=False, _suppress_side_effects=True)
    out2 = capsys.readouterr().out

    assert "100" in out1   # account1 sees its own real 100%
    assert "50" in out2    # account2 sees its own real 50%, NOT account1's 100
    # (exact substring depends on the render style's percentage formatting —
    # confirm the classic style's literal digit sequence via a quick manual
    # `cs preview` check or reuse an existing render-format helper from
    # tests/test_forecast_render.py during implementation.)
```
Why this reproduces the bug precisely and fails pre-fix: pre-fix, both renders resolve `account_id()` to whatever uuid sits in `$HOME/.claude.json` (which this test never writes at all, or writes to a THIRD value) — both `reconcile_account` calls write into the *same* unsuffixed (or same-third-uuid) store bucket keyed by `(five_hour, 1784191800)`, and the monotonic-up healing rule pins the bucket to 100 for both renders (out2 would wrongly contain "100", not "50"). Post-fix, `transcript_path` resolves each render to its own account dir, `_account_path` produces two distinct filenames, and the two bucket writes never collide.

**`test_account_id_resolves_from_transcript_over_home_json`** (R1):
```python
def test_account_id_resolves_from_transcript_over_home_json(tmp_path, monkeypatch):
    home_json = tmp_path / ".claude.json"
    _write_claude_json(home_json, uuid="wrong-home-uuid")   # decoy — must be ignored
    monkeypatch.setattr(predict, "_CLAUDE_JSON_PATH", home_json)  # legacy path, unrelated
    acct1_dir = tmp_path / ".claude-account1"
    _write_claude_json(acct1_dir / ".claude.json", uuid="e1605250-1111-2222-3333-444455556666")
    tp = acct1_dir / "projects" / "-enc-" / "sid.jsonl"
    stdin = {"transcript_path": str(tp)}
    got = predict.account_id(stdin, env={}, home=tmp_path)
    assert got == "e1605250-1111-2222-3333-444455556666"
```

**`test_named_dir_without_own_json_does_not_borrow_home`** (R5b — the sharpest edge):
```python
def test_named_dir_without_own_json_does_not_borrow_home(tmp_path, monkeypatch):
    home_json = tmp_path / ".claude.json"
    _write_claude_json(home_json, uuid="home-account-uuid")
    named_dir = tmp_path / ".claude-accountX"    # exists but has NO .claude.json
    named_dir.mkdir()
    got = predict.account_id({}, env={"CLAUDE_CONFIG_DIR": str(named_dir)}, home=tmp_path)
    assert got is None    # must NOT be "home-account-uuid"
    # and the store path must be the legacy unsuffixed path:
    monkeypatch.setattr(predict, "_LATEST_PATH", tmp_path / "rate_latest.json")
    assert predict._latest_path(got) == tmp_path / "rate_latest.json"
```

**`test_account_path_three_way_branch`** (sentinel landmine, direct unit coverage):
```python
def test_account_path_three_way_branch(tmp_path, monkeypatch):
    base = tmp_path / "rate_latest.json"
    monkeypatch.setattr(predict, "account_id", lambda: "legacy-uuid")  # zero-arg legacy resolver
    assert predict._account_path(base) == base.with_name("rate_latest.legacy-uuid.json")   # omitted
    assert predict._account_path(base, aid=None) == base                                    # resolved-None
    assert predict._account_path(base, aid="new-uuid") == base.with_name("rate_latest.new-uuid.json")
```

**`test_predict_module_imports_no_network_or_subprocess`** (prohibition, reuse existing harness):
```python
# Reuses tests/test_import_perf.py's _list_imports_for — import it directly
# (tests/ has __init__.py, so cross-test imports work).
from tests.test_import_perf import _list_imports_for

def test_predict_module_imports_no_network_or_subprocess():
    loaded = _list_imports_for("claude_statusbar.predict")
    banned = {"subprocess", "socket", "urllib", "urllib.request"}
    leaked = sorted(banned & loaded)
    assert not leaked, f"predict.py must stay network/subprocess-free: {leaked}"
```

**`test_keying_reader_reads_only_account_uuid`** (prohibition — no secret):
```python
def test_keying_reader_reads_only_account_uuid(tmp_path):
    p = tmp_path / ".claude.json"
    p.write_text(json.dumps({
        "oauthAccount": {
            "accountUuid": "abc-123",
            "accessToken": "SECRET-SHOULD-NEVER-BE-TOUCHED",
            "emailAddress": "a@b.c",
        }
    }))
    # Assert the reader's return value never contains/equals the secret,
    # and (implementation detail) that the anchored regex used is scoped to
    # "accountUuid" only — mirrors the existing pattern in predict.py:88-89
    # and account.py:30 (each field has its own dedicated compiled regex).
    result = predict._read_keyed_account_id(p)  # or account_id({}, ...) end-to-end
    assert result == "abc-123"
    assert "SECRET-SHOULD-NEVER-BE-TOUCHED" not in str(result)
```

**`test_no_destructive_fs_ops_on_existing_stores`** (prohibition — fix-forward only):
```python
def test_no_destructive_fs_ops_on_existing_stores(tmp_path, monkeypatch):
    stale = tmp_path / "rate_latest.stale-uuid.json"
    stale.write_text("{}")
    calls = []
    monkeypatch.setattr(os, "unlink", lambda *a, **k: calls.append(("unlink", a)))
    monkeypatch.setattr(os, "replace", lambda *a, **k: calls.append(("replace", a)))
    monkeypatch.setattr(Path, "rename", lambda *a, **k: calls.append(("rename", a)))
    monkeypatch.setattr(predict, "_LATEST_PATH", tmp_path / "rate_latest.json")
    predict.reconcile_account(10.0, 5000, 8.0, 9000, now=0.0, account_uuid="new-account")
    # atomic_write_text uses os.replace internally for ITS OWN target file — only assert
    # no destructive op targets the pre-existing `stale` path specifically:
    assert not any(stale in (str(c[1]) if c[1] else "") for c in calls if stale.name in str(c))
```
Note for the planner: `cache.atomic_write_text` legitimately uses a temp-file + `os.replace` internally for its OWN write target (not a destructive op on a *different* existing file) — the assertion must be scoped to "the pre-existing `stale-uuid` file specifically is never touched," not "no `os.replace` call anywhere," or it will false-positive on the store's own normal atomic-write mechanism.

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/test_account_rate_isolation.py -q`
- **Per wave merge:** `.venv/bin/python -m pytest tests/ -q` (must stay at 1090 + new tests, all passing)
- **Phase gate:** Full suite green before `/gsd-verify-work`; additionally confirm `test_two_accounts_share_5h_reset_render_own_values` fails against a git-stashed pre-fix `predict.py` (temporarily revert just that file, run the one test, confirm RED, restore) — this is the literal "FAILS pre-fix, PASSES post-fix" acceptance criterion and is worth a manual verification step during execution, not just at planning time.

### Wave 0 Gaps
- `tests/test_account_rate_isolation.py` — new file, all tests above start from zero (no existing file to extend for this defect class beyond the analogous `test_account_switch.py`, which covers a related-but-different bug: account *switching*, not concurrent *sharing*).
- No new fixtures/conftest.py additions needed — `tmp_path`/`monkeypatch` (stdlib pytest) plus small local helper functions (`_write_claude_json`, `_payload_with_limits`) already have direct precedent in `tests/test_account.py` and `tests/test_core_projection.py` respectively; copy their exact shape rather than importing across test files (except `_list_imports_for`, which is explicitly designed to be reused).
- Framework install: none — `.venv` already has pytest configured and the full suite already passes (1090 passed, confirmed live).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | This phase reads an existing OAuth session's UUID for cache-keying only; it does not authenticate anything or touch tokens |
| V5 Input Validation | Yes | `transcript_path` (untrusted, attacker-influenced only in the sense that a malicious stdin payload could supply an arbitrary path) is validated by the existing `_config_dir_from_transcript`'s `parents[1] == "projects"` guard (Phase 11, reused as-is) before ever being used to construct a filesystem path |
| V6 Cryptography | No | No crypto in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Path traversal via a crafted `transcript_path` in stdin | Tampering | Already mitigated by Phase 11's `_config_dir_from_transcript` shape guard (must literally have a `projects` parent segment) — this phase reuses that guard unchanged, does not construct any new path from raw untrusted input beyond what account.py already validates |
| Secret exfiltration via over-broad `.claude.json` field extraction | Information Disclosure | Anchored regex scoped to `"accountUuid"` only (mirrors the existing `oauthAccount` anchor pattern) — the new keying reader must use its own tightly-scoped regex, never a generic key-value extractor that could accidentally match `accessToken`/`refreshToken` |
| Never-raise contract violation crashing the render path | Denial of Service (self-inflicted) | Every new function wraps resolution in `try/except Exception: return None`, mirroring `account.resolve_account_email`'s contract exactly |

This phase's actual risk surface is small: a local, unauthenticated single-user CLI reading its own already-trusted config files. The SPEC's prohibitions (no secret read, no network/subprocess, no destructive fs ops) are the operative security controls and are already covered as explicit test cases above.

## Sources

### Primary (HIGH confidence — direct source read)
- `src/claude_statusbar/predict.py` (full read of lines 1-140, 290-710, 1060-1200) — store path helpers, `reconcile_account`, `forecast`, `projection`, `_projection_result_key`, `regime_changed_at`
- `src/claude_statusbar/account.py` (full read) — `resolve_config_dir`, `_config_dir_from_transcript`, `_claude_json_path`, `_read_email`, `resolve_account_email`
- `src/claude_statusbar/core.py` (lines 33-102, 1064-1066, 1145-1180, 1410-1589) — `parse_stdin_data`, `_effective_env`, all three call sites needing threading, the existing Phase 11 email-chip call convention to mirror
- `src/claude_statusbar/daemon.py` (lines 375-441) — confirms single-process, in-process, sequential per-session render model (underpins the cache-thrashing landmine framing)
- `tests/test_account_switch.py`, `tests/test_account.py`, `tests/test_predict.py`, `tests/test_core_projection.py`, `tests/test_core_forecast_guard.py`, `tests/test_import_perf.py` — existing test conventions, fixture idioms, and the reusable `_list_imports_for` harness
- `.venv/bin/python -m pytest tests/ -q` — live run, 1090 passed, confirms the baseline

### Secondary (MEDIUM confidence)
- None — no external documentation was needed for this phase.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Call-graph/architecture: HIGH — every claim traced to an exact file/line via direct read
- Reconcile invariants: HIGH — full body of `reconcile_account`/`projection`/`_projection_for_window` read; monotonic-up/grace/confirm-refresh logic confirmed untouched by the proposed threading
- Regression test design: HIGH — patterned directly off three existing test files' exact conventions in this repo, not invented from scratch
- Landmines (sentinel, regime_changed_at, cache keying): HIGH — each traced to a specific line number and cross-checked against the existing test suite's actual assertions

**Research date:** 2026-07-16
**Valid until:** No expiry concern — this is a fixed snapshot of the current codebase state at the phase's start; re-read the three files directly if the plan is executed more than a few days after this research (in case an unrelated commit lands on predict.py/core.py first).
