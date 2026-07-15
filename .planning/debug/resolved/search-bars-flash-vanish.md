---
slug: search-bars-flash-vanish
status: resolved
trigger: Search-credit bars (fc/tv) flash for a split second on a freshly-opened iTerm2, then disappear
created: 2026-07-15T21:40:00
updated: 2026-07-15T22:45:00
---

# Debug Session: search-bars-flash-vanish

## Symptoms

- **Trigger (user, verbatim):** Search-credit bars (fc/tv) flash for a split second on a freshly-opened iTerm2, then disappear. Previously the fix was render_thin.py refreshing the search-credit cache from its own live os.environ. Now: fully closed iTerm2, reopened it, bars showed briefly then vanished.
- **Expected behavior:** fc/tv search-credit bars render and STAY in the status line
- **Actual behavior:** fc/tv bars appear for a split second on a freshly-opened iTerm2, then disappear
- **Persistence (user):** Gone for good — bars do NOT come back in that window; not a flicker
- **Scope (user):** Every session / every new window shows the flash-then-vanish
- **Other segments (user):** Only fc/tv vanish — the rest of the status line (model name, relay balance, etc.) renders fine and stays
- **Timeline:** Appeared after the prior fix (render_thin `_maybe_refresh_search_credits`) shipped; user fully quit iTerm2 and reopened a genuinely fresh window
- **Reproduction:** Fully close iTerm2 → reopen → launch claude → watch the status line: fc/tv flash then vanish

## Recent related changes (git log)

- dd94397 fix(search-credits): refresh credit cache from render_thin's live env
- d6a1a10 fix(relay-balance): fall back to os.environ for the relay key so bal gauge renders live
- a7571e1 fix(260715-pic): source search-provider keys from os.environ so bars render live
- 00f8b69 docs(quick-260715-pic): search-provider credit bars (Firecrawl + Tavily)
- 9265e55 feat(260715-pic): daemon heartbeat + render-path isolation/edge-case tests + CHANGELOG

## Related prior session

`.planning/debug/resolved/search-credit-bars-missing.md` — its root_cause note already predicted this exact pattern: "bars appear at best fleetingly (during a brief inline-render fallback) then vanish for good." The prior fix's end-to-end test drove `cs render` under `zsh -ic` (likely inline / fresh-daemon path) and never exercised the steady-state STALE persisted daemon.

## Current Focus

status_now: RESOLVED. User confirmed in a fresh iTerm2 window that the fc/tv bars now render and persist ("its showing now"). Session archived. See Resolution below for full detail. Historical reasoning that led to the fix is preserved below for the record.

reasoning_checkpoint:
  hypothesis: "H2 CONFIRMED. provider_usage.segments(env) gates display per-provider on `key = env.get(env_var)` being truthy (provider_usage.py:188-190) — it cannot locate a provider's cache entry without the raw key because the cache filename IS fingerprint(name, key). core.py's search-credit block (line 1249) calls `provider_usage.segments(os.environ)` from INSIDE daemon.py's `_render_payload()` (daemon.py:425-426 runs `core.main()` in the daemon's own process), so `os.environ` there is the daemon's env frozen at spawn time. The prior fix (dd94397) added render_thin._maybe_refresh_search_credits() which correctly refreshes the on-disk CACHE using render_thin's own live env — but did nothing to help the DAEMON's segments() call locate that cache entry, since the daemon still lacks the raw key needed to compute the fingerprint. Net effect: cache is fresh and valid, but the daemon's rendered.ansi permanently omits the bars once it renders that session for the first time. A brand-new iTerm2 session has no per-session bucket yet, so render_thin's FIRST tick takes the inline-fallback path (core.main() runs in render_thin's OWN live-keyed process) → bars flash correctly. The already-running persisted daemon then renders that same session on its next 1Hz tick using its own keyless env → writes empty segments to rendered.ansi → every subsequent tick takes the fast daemon-cat path and serves that permanently-empty render → bars vanish for good, matching the user's exact symptom."
  confirming_evidence:
    - "provider_usage.py segments(): `key = env.get(env_var); if not key: continue` (line 188-190) — no cache-only fallback path exists; the raw key is structurally required to compute the fingerprint that locates the cache file."
    - "daemon.py _render_payload() (line 397-426) runs `from .core import main as core_main; core_main(_suppress_side_effects=True)` directly inside the daemon process — os.environ read anywhere inside that call (including core.py:1249's `provider_usage.segments(os.environ)`) is the daemon's own process environment, never the calling session's."
    - "Live reproduction on this machine: daemon pid 25274 (`ps eww -p 25274`) has NEITHER FIRECRAWL_API_KEY nor TAVILY_API_KEY; daemon started 2026-07-15 21:04:19 (persisted continuously since then). The current live shell env DOES have both keys. Confirms the daemon is exactly the frozen-keyless process the hypothesis requires."
    - "Cache files ~/.cache/claude-statusbar/provider_usage/*.json are fresh (written ~60s ago vs TTL_SECONDS=300) with `supported:true` and valid computable `pct` (100.0, 99.9) — proving the render_thin-side cache refresh (dd94397) works correctly. The bars are STILL missing from the daemon's render despite a perfectly good cache — isolating the bug to the DISPLAY gate (segments requiring key-in-env), not the cache-refresh mechanism (already fixed once, and not reclobbered)."
    - "core.py's own comment (lines 1235-1243) already documents this exact residual gap: 'when this code path runs INSIDE the shared daemon... os.environ here is the daemon's env frozen at its own spawn time... a key exported/rotated after the daemon started is invisible here too' — and notes the render_thin refresh call is kept only because 'still useful when the daemon happens to have the key,' i.e. the prior fix's author flagged but did not close this gap."
    - "The prior session's OWN regression test (tests/test_search_credits_daemon_env.py::test_live_env_sees_key_that_a_frozen_snapshot_would_miss) already asserts `provider_usage.segments(frozen_daemon_env) == []` even with a valid fresh cache entry present — this is the exact new-bug mechanism, captured as an assertion but never turned into a fix."
    - "Established precedent in this same codebase: relay_balance() (core.py:380-445, fixed by d6a1a10) faced the identical daemon-frozen-env class of bug for the relay balance gauge and was fixed by having callers source the effective env preferentially from render_thin's per-session-stamped `_cs_env` payload — the same architecture this fix extends (fingerprint stamp instead of a raw secret, per the repo's explicit no-secrets-on-disk convention)."
  falsification_test: "If daemon pid 25274's env DID contain the keys (contradicting the hypothesis) yet bars still vanished, OR if the on-disk cache were stale/missing (implicating H1's cache-clobber instead), this hypothesis would be false. Both checked and ruled out: daemon env confirmed keyless via ps eww; cache confirmed fresh+valid via direct file read. H1 (render_thin clobbers a good cache with an empty probe result) is separately eliminated below."
  fix_rationale: "Root cause is that segments() needs the raw key only to compute a fingerprint (a one-way SHA1 hash) locating the cache file — it never needs the key for anything else. render_thin already computes this same fingerprint correctly (it has the live key) inside _maybe_refresh_search_credits() on every tick. Stamping that fingerprint (NOT the raw key — same one-way hash value already used as the world-readable cache filename) into the per-session `_cs_env` payload lets core.py's segments() call, even when running inside a keyless daemon, locate the correct cache entry via the session-stamped fingerprint instead of requiring env.get(env_var). This fixes the DISPLAY gate directly (the actual root cause) without touching the cache-refresh mechanism (already correct) and without ever persisting a raw secret to disk — mirroring the exact pattern already used for _session_env/_effective_env and the already-fixed relay_balance() case."
  blind_spots: "Have not yet verified the fix end-to-end through a real daemon process (only via direct function calls / will add unit + integration tests mirroring test_search_credits_daemon_env.py). Have not restarted the live daemon after applying the fix — full live verification requires either `cs daemon stop` + a fresh render tick, or waiting for the daemon to pick up the code-drift restart signal (render_thin._is_outdated_daemon), since the running daemon (pid 25274) predates this fix and needs to reload code. Also have not tested key-rotation edge case (old fingerprint stamped, key changes mid-session) — acceptable since ensure_fresh()/segments() already handle this per-fingerprint, and a rotated key simply produces a new fingerprint on the next render_thin tick."

## Evidence

- timestamp: 2026-07-15T22:00
  checked: src/claude_statusbar/provider_usage.py segments() (lines 178-205)
  found: "`key = env.get(env_var); if not key: continue` — segments() has no cache-only path; it structurally requires the raw key (to compute fingerprint(name, key)) in order to locate which cache file to read. No amount of cache freshness matters if the key is absent from the passed-in `env`."
  implication: Confirms the DISPLAY gate (not the cache) is the blocking mechanism — distinguishes H2 from H1.

- timestamp: 2026-07-15T22:02
  checked: src/claude_statusbar/daemon.py _render_payload() (lines 397-441) and _render_session() (444-470)
  found: "`core_main(_suppress_side_effects=True)` is called directly inside the daemon's own process via a plain import + function call (not a subprocess) — so any `os.environ` read during that call (including core.py:1249's `provider_usage.segments(os.environ)`) is literally the daemon process's own environment."
  implication: Confirms the daemon-cat fast path's rendered.ansi content is produced with the daemon's frozen env, never the requesting session's live env.

- timestamp: 2026-07-15T22:04
  checked: "Live daemon pid via `ps eww -p $(cat ~/.cache/claude-statusbar/daemon.pid)`; daemon.pid mtime; current shell env"
  found: "Daemon pid 25274, started 2026-07-15 21:04:19, has been running continuously (elapsed 38:29 at check time). `ps eww -p 25274` shows NO FIRECRAWL_API_KEY or TAVILY_API_KEY. Current live shell env has BOTH keys (FIRECRAWL_API_KEY=fc-..., TAVILY_API_KEY=tvly-...)."
  implication: Direct confirmation that the currently-running, session-persisting daemon is exactly the frozen-keyless process the hypothesis requires.

- timestamp: 2026-07-15T22:05
  checked: ~/.cache/claude-statusbar/provider_usage/*.json cache contents + ages
  found: "Two cache entries, written ~60s before check (well within TTL_SECONDS=300), both `supported: true` with valid computable pct (100.0 and 99.9)."
  implication: The cache-refresh mechanism from the prior fix (dd94397) IS working correctly right now. The bars are missing purely because of the display-side key-gate, not because the cache is stale or was clobbered — ELIMINATES H1 (see below).

- timestamp: 2026-07-15T22:06
  checked: src/claude_statusbar/core.py lines 1222-1253 (search-credit segment block + surrounding comment) and relay_balance() (lines 380-445)
  found: "core.py's own comment already documents this exact gap ('a key exported/rotated after the daemon started is invisible here too... Keep both: this call is still useful when the daemon happens to have the key'). relay_balance() shows the established fix pattern for this same class of bug: prefer a per-session stamped signal (`_cs_env` via `_effective_env`) over the daemon's raw os.environ."
  implication: The codebase already has both (a) a documented acknowledgment that this residual gap exists and (b) a proven architectural pattern (session-env stamping) to close it — confirms the fix direction (stamp a non-secret fingerprint into the per-session payload) is consistent with established convention, not a new pattern.

- timestamp: 2026-07-15T22:07
  checked: tests/test_search_credits_daemon_env.py::test_live_env_sees_key_that_a_frozen_snapshot_would_miss
  found: "This existing test explicitly asserts `provider_usage.segments(frozen_daemon_env) == []` even when a valid, fresh, supported cache entry exists for that key — framed as documenting the (at-the-time deliberate/accepted) gap, not as a regression guard against it."
  implication: The prior session's own test suite already proves this exact failure mode; this new bug is the natural consequence of that documented-but-unclosed gap becoming user-visible once a persisted daemon renders a brand-new session.

## Eliminated

- hypothesis: "H1 — render_thin's own refresh runs in a process WITHOUT the keys and clobbers a previously-good on-disk cache with an empty probe result"
  evidence: "Cache files are fresh (~60s old, well under the 300s TTL) with `supported:true` and valid pct values, and the live process env used by render_thin's refresh call DOES have both keys — there is no clobbering happening. The bars are absent purely because segments()'s key-in-env display gate fails when read from the daemon's keyless os.environ, independent of cache state."
  timestamp: 2026-07-15T22:05

## Resolution

- root_cause: "provider_usage.segments(env) requires the raw provider API key to be present in the passed-in `env` dict, because it uses the key to compute `fingerprint(name, key)` — the identifier used to locate the on-disk cache file. core.py's search-credit segment block calls `provider_usage.segments(os.environ)` from a code path (core.main(), called via daemon.py's _render_payload) that, when running inside the shared long-lived render daemon, sees the DAEMON's own os.environ — frozen at daemon-spawn time and lacking FIRECRAWL_API_KEY/TAVILY_API_KEY on this machine. The prior fix (dd94397) added render_thin._maybe_refresh_search_credits(), which correctly refreshes the on-disk CACHE using render_thin's own always-live env — but did nothing to help the daemon's segments() call locate that cache entry, since the daemon still lacks the raw key needed to compute the fingerprint. Net effect: a brand-new iTerm2 session's first render tick has no per-session daemon output yet, so it takes render_thin's inline-fallback path (core.main() runs in-process with the LIVE key) and the bars render correctly once. The next daemon tick (the daemon persists across iTerm2 restarts via its pidfile) renders that same session using its own keyless env, permanently overwriting the good render with an empty one — every subsequent tick then serves that keyless render via the fast daemon-cat path. Bars flash once, then vanish for good, on every fresh session."
  fix: "Added `provider_usage.session_fingerprints(env)` — a helper that returns a non-secret {provider_name: fingerprint} map (fingerprint is the existing one-way SHA1 hash, already used as the world-readable on-disk cache filename; never the raw key). Extended `provider_usage.segments(env, session_fps=None)` to accept this map as a fallback lookup key: when the raw key is absent from `env`, it uses the stamped fingerprint (if present) to locate the cache entry instead of skipping the provider. Extended render_thin.py's `_inject_session_env()` to compute `session_fingerprints(os.environ)` (gated behind the `show_search_credits` toggle, lazy-imported — zero cost when the feature is off) and stamp it into the per-session payload under `_cs_search_fps`, alongside the existing `_cs_env` marker. Extended core.py's `parse_stdin_data()` to extract `_cs_search_fps` into `stdin_data['_session_search_fps']`, and wired the search-credit segment block to pass it through: `provider_usage.segments(os.environ, session_fps=stdin_data.get('_session_search_fps'))`. This mirrors the codebase's established pattern for this exact class of bug (`_session_env`/`_effective_env` for API-mode vars; the already-fixed `relay_balance()` for the relay gauge) — render_thin computes a fresh, non-secret signal from its own always-live env on every tick, and the daemon's frozen-env code path consumes that stamped signal in preference to (or as a fallback from) its own os.environ. No raw secret is ever persisted to disk."
  verification: "Self-verified via three layers, then confirmed live by the user: (1) Full test suite: 1040 passed, 1 pre-existing unrelated failure (test_version_sync.py marketplace/pyproject version lag — confirmed present before this change via git stash, same as the prior session). (2) 9 new regression tests added to tests/test_search_credits_daemon_env.py, plus 2 existing tests in tests/test_daemon.py updated to account for the new `_cs_search_fps` marker (popped alongside `_cs_env` before equality comparison — those tests' scope is session routing, not this feature). Verified true red→green: stashed only the 3 src changes and reran the new tests — 7 of 9 failed, including `test_core_main_renders_bar_from_session_stamp_when_os_environ_is_keyless` (asserted output was missing 'fc[' — the exact bug), confirming the tests are a genuine regression guard and not tautological. Restored the fix — all 16 pass. (3) Live end-to-end through the REAL `cs render` CLI (the installed uv tool is an editable install pointing at this exact repo, so the fix is live with zero build/install step): piped a synthetic session payload through `cs render` with real FIRECRAWL_API_KEY/TAVILY_API_KEY in env — output showed `fc[100%] | tv[100%]` (inline-fallback path, as expected for a brand-new session), and the persisted `~/.cache/claude-statusbar/sessions/<sid>/last_stdin.json` contained `_cs_search_fps: {firecrawl: 84d4ee24..., tavily: a71961d3...}` (matching the real on-disk cache filenames) with NO raw key substring found in the file. Then fed that EXACT persisted payload into `core.main()` with FIRECRAWL_API_KEY/TAVILY_API_KEY explicitly unset via `env -u` (faithfully simulating the daemon's frozen keyless os.environ) — output still rendered `fc[100%] | tv[100%]`, proving the fix closes the gap through the actual production code path, not just mocked unit tests. FINAL RE-CONFIRMATION at finalize time: reran the exact same regression suite (tests/test_search_credits_daemon_env.py + tests/test_daemon.py) against the untouched working tree via .venv/bin/python — all 73 tests pass (16 + 57), zero failures. HUMAN VERIFICATION (2026-07-15, post-finalize checkpoint): user fully quit and reopened a fresh iTerm2 window, launched Claude Code, and confirmed the fc/tv bars now render AND persist ('its showing now') — the flash-then-vanish symptom is gone in the real, unscripted daily-use environment, closing the loop the prior session's own end-to-end test never exercised (steady-state persisted-daemon rendering a brand-new session)."
  files_changed:
    - src/claude_statusbar/provider_usage.py (added session_fingerprints(); segments() accepts session_fps fallback)
    - src/claude_statusbar/render_thin.py (added _session_search_fingerprints(); _inject_session_env() stamps _cs_search_fps)
    - src/claude_statusbar/core.py (parse_stdin_data() extracts _session_search_fps; search-credit block passes it to segments())
    - tests/test_search_credits_daemon_env.py (9 new regression tests)
    - tests/test_daemon.py (2 existing tests updated to pop the new _cs_search_fps marker before comparison)
