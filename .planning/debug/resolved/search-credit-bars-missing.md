---
slug: search-credit-bars-missing
status: resolved
trigger: Tavily and Firecrawl search-provider credit bars are not showing up in the usage bar
created: 2026-07-15T20:11:18
updated: 2026-07-15T21:22:00
---

# Debug Session: search-credit-bars-missing

## Symptoms

- **Trigger (user, verbatim):** Tavily and Firecrawl search-provider credit bars are not showing up in the usage bar
- **Expected behavior:** Firecrawl and Tavily search-provider credit bars render in the usage bar
- **Actual behavior:** Nothing renders for either provider; other bars appear fine
- **API keys:** User reports both Firecrawl and Tavily keys ARE set in the environment
- **Config toggle (`show_search_credits`):** User is NOT sure whether it is enabled
- **Timeline:** Never showed — the bars have never appeared since the feature was added
- **Reproduction:** Run/render the usage bar; expected search-credit bars are absent

## Recent related changes (git log)

- d6a1a10 fix(relay-balance): fall back to os.environ for the relay key so bal gauge renders live
- a7571e1 fix(260715-pic): source search-provider keys from os.environ so bars render live
- 00f8b69 docs(quick-260715-pic): search-provider credit bars (Firecrawl + Tavily)
- 9265e55 feat(260715-pic): daemon heartbeat + render-path isolation/edge-case tests + CHANGELOG
- 3dee232 feat(260715-pic): show_search_credits config toggle + core/progress/styles/preview wiring

## Current Focus

- hypothesis: CONFIRMED and FIXED — root cause verified end-to-end through the REAL render path (see 21:15–21:22 evidence). Fix mechanism proven live: a `cs render` run with a keys-present env spawned the prober, refreshed the cache, and the next render emitted `fc[ 100% ] | tv[ 100% ]`.
- test: PASSED end-to-end. Remaining gap is NOT a code defect — it is the user's shell-launch env (their live Claude Code session was launched from a stale pane-shell that predates the ~/.zshrc key exports, so it has no keys to forward).
- expecting: the fc/tv bars will appear in the user's live status line as soon as Claude Code is launched from a shell that actually has the keys — i.e. a brand-new interactive iTerm2 pane/window (confirmed: `zsh -ic` inherits the keys), OR after moving the exports to ~/.zshenv so every launch method inherits them.
- next_action: user launches Claude Code from a fresh interactive shell (or moves the two exports from ~/.zshrc → ~/.zshenv), then confirms the bars show in the live status line. No further code change needed.

reasoning_checkpoint:
  hypothesis: "The search-credit bars never render because provider_usage.ensure_fresh()/segments() calls embedded in core.py's render path execute almost exclusively inside the long-lived render daemon (daemon.py's _render_payload -> core.main()), whose os.environ is captured once at daemon-spawn time and never refreshed. FIRECRAWL_API_KEY/TAVILY_API_KEY are visible to the daemon only if present in its env at the exact moment it was (lazily) spawned. Since the daemon serves virtually all statusline renders after warmup, and there is no live-env forwarding path for these two keys (unlike the already-solved API-mode env-var problem, which render_thin.py explicitly forwards via _SESSION_ENV_KEYS/_cs_env), any key exported/rotated after the daemon's spawn is invisible to it forever — any cache entry it manages to write goes stale after TTL_SECONDS=300 and is never refreshed."
  confirming_evidence:
    - "ps eww -p 5219 (the live daemon process on this machine) shows NO FIRECRAWL_API_KEY/TAVILY_API_KEY in its environment, while ~/.zshrc (sourced by the user's interactive shell) DOES export both (confirmed via grep)."
    - "Existing provider_usage cache files (84d4ee2...json, a71961d...json) contain exactly ONE successful probe (supported:true, valid pct) written at ts~20:03:13-15, now 646s+ old (>2x TTL_SECONDS=300), with zero .inflight markers and zero refresh since — proving ensure_fresh() has not successfully re-probed despite the cache being stale for 10+ minutes."
    - "Direct reproduction: calling provider_usage.ensure_fresh(os.environ) + segments(os.environ) in a process whose env DOES have the keys (sourced ~/.zshrc, correct .venv interpreter matching sys.executable) produced valid segments (fc 100%, tv 100%) within ~8s — proving provider_usage/segments logic itself is correct; the ONLY blocker is env availability at the call site."
    - "core.py's own comment (lines 1227-1233) and render_thin.py's _SESSION_ENV_KEYS docstring (lines 226-229) both explicitly document 'the shared daemon's os.environ is frozen at its own start and is NOT this session's' — an architecture hazard the codebase already solved for API-mode vars but never extended to the search-credit keys (deliberately, to keep secrets off disk)."
  falsification_test: "If the daemon's os.environ DID contain the keys (per ps eww) yet the cache still failed to refresh, this hypothesis would be false and a different bug (stuck inflight lock, probe-parsing bug) would be implicated. Checked and ruled out: zero .inflight files exist, and a direct call with valid env produces working segments immediately — confirming the code itself works and only frozen/absent env blocks it."
  fix_rationale: "Add a render_thin-driven ensure_fresh() call that runs on EVERY `cs render` invocation (fast daemon-cat path AND inline fallback alike), using render_thin's own os.environ — which, unlike the daemon, is re-established fresh at every invocation from whatever process spawns it. This mirrors the codebase's existing pattern for API-mode vars, but instead of persisting secrets through _cs_env (a plaintext on-disk stdin cache — explicitly rejected for secrets per existing code comments), it triggers the EXISTING ensure_fresh() API directly from a process with a live env, so the raw key only ever exists transiently in that process + the detached prober's child env, never touching disk. This targets the root cause directly: it gives the search-credit cache a refresh path independent of the daemon's one-time environment snapshot."
  blind_spots: "This fix cannot retroactively grant an ALREADY-running Claude Code session (and everything it has spawned) access to keys exported into ~/.zshrc after that session started — no code change can force a running process tree to re-inherit a shell profile. Verified live: all 4 currently running `claude` processes on this machine lack these vars right now, so full end-to-end verification requires the user to fully quit and relaunch Claude Code (or at minimum run `cs daemon stop`) AFTER confirming the keys are exported, so a freshly spawned process tree inherits them. Have not tested this fix against a live daemon-serving-a-session scenario end-to-end (only via direct function calls), since spawning a fully fresh daemon here requires the same fresh-env prerequisite this sandbox doesn't currently have."

## Evidence

- timestamp: 2026-07-15T20:15
  checked: src/claude_statusbar/config.py StatusbarConfig.show_search_credits default + user's actual ~/.claude/claude-statusbar.json
  found: Default is False, but the user's actual config file already has "show_search_credits": true
  implication: Toggle-off hypothesis ELIMINATED — feature is genuinely enabled; bars still don't show

- timestamp: 2026-07-15T20:16
  checked: src/claude_statusbar/provider_usage.py (segments/ensure_fresh) and _provider_usage_refresh.py (detached prober)
  found: Logic looks correct — fingerprint/cache/TTL/inflight mechanics are sound; Firecrawl/Tavily API parsing matches expected response shapes
  implication: No obvious logic bug in the provider_usage module itself; look at env-sourcing and call sites next

- timestamp: 2026-07-15T20:18
  checked: ~/.cache/claude-statusbar/provider_usage/*.json cache files
  found: Two cache files exist with supported:true and valid pct (100.0, 99.9), written at ts~1784116993-995 (20:03:13-15), now 646s+ old vs TTL_SECONDS=300 — stale by >2x
  implication: A probe DID succeed once, but has not refreshed since — points to an intermittent/one-time env availability rather than a permanent logic bug

- timestamp: 2026-07-15T20:19
  checked: `env | grep -i FIRECRAWL/TAVILY` in a fresh bash tool shell; ~/.cache/claude-statusbar/daemon.pid + daemon.log; `ps -p 5219`
  found: Current shell lacks both vars; daemon (pid 5219) has been running continuously since 19:36:29 (confirmed alive)
  implication: Need to check the daemon's OWN inherited environment, not just the current shell's

- timestamp: 2026-07-15T20:20
  checked: `ps eww -p 5219` (daemon process full environment listing)
  found: No FIRECRAWL_API_KEY or TAVILY_API_KEY present in the daemon's environment
  implication: Confirms the daemon cannot ever probe these providers — its ensure_fresh(os.environ) call always sees `key=None` and skips via `if not key: continue`

- timestamp: 2026-07-15T20:21
  checked: ~/.zshrc, ~/.zshenv, ~/.zprofile, ~/.bashrc for FIRECRAWL_API_KEY/TAVILY_API_KEY exports
  found: Both keys ARE exported in ~/.zshrc (interactive-shell-only file); not present in .zshenv/.zprofile
  implication: User's claim "keys ARE set" is genuinely true for their interactive shell — the gap is purely about which processes inherit that shell's env

- timestamp: 2026-07-15T20:22
  checked: ~/.cache/claude-statusbar/provider_usage/*.inflight
  found: No inflight marker files exist
  implication: Rules out a "stuck lock" bug as an alternative explanation for the lack of refresh

- timestamp: 2026-07-15T20:24
  checked: daemon.py subprocess.Popen calls (cmd_start, spawn_if_dead) — no explicit env= parameter
  found: Daemon inherits whatever env its spawning parent (a `cs render` invocation, ultimately Claude Code) had at that exact moment; never updated afterward
  implication: Matches architecture already documented/solved for API-mode vars (render_thin._SESSION_ENV_KEYS / _cs_env) but never extended to search-credit keys

- timestamp: 2026-07-15T20:26
  checked: Currently running `claude --permission-mode auto` processes (pids 18985, 25730, 49717, 27871) via `ps eww`
  found: None of the 4 live Claude Code processes on this machine currently have FIRECRAWL_API_KEY/TAVILY_API_KEY in their environment
  implication: Even a fresh render_thin invocation spawned by any of these live sessions would currently lack the keys too — full verification will require the user to restart their Claude Code session/terminal after confirming the keys are exported, independent of any code fix

- timestamp: 2026-07-15T20:30
  checked: Direct call to provider_usage.ensure_fresh(os.environ) + segments(os.environ) using .venv/bin/python3 with ~/.zshrc sourced (keys present)
  found: Probe succeeded; segments() returned [{'label': 'fc', 'pct': 100.0, ...}, {'label': 'tv', 'pct': 99.9, ...}] within ~8s
  implication: Confirms provider_usage logic is fully correct; the ONLY blocker is environment availability at the call site (daemon-frozen env), not a bug in fingerprinting/caching/parsing

# --- Continuation cycle 2026-07-15T21:xx (/gsd-debug continue) ---

- timestamp: 2026-07-15T21:05
  checked: THIS live Claude Code session's own environment (the process rendering the user's status line) — printenv FIRECRAWL_API_KEY/TAVILY_API_KEY; process ancestry via ps
  found: Current claude (pid 25134, started 21:04) has NEITHER key. Ancestry: /bin/zsh(tool) -> claude 25134 -> -zsh 68091 (login shell, started 11:41:18) -> login 68090 -> iTerm2. The parent login shell 68091 ALSO lacks both keys.
  implication: The user's "restart" launched a fresh claude (21:04) but from a stale pane-shell alive since 11:41 — which predates today's ~/.zshrc key exports and was never re-sourced. A fresh claude inherits its parent shell's frozen env, so it has no keys to forward. This is precisely why the live bars are still absent despite the code fix.

- timestamp: 2026-07-15T21:10
  checked: Which shell init files export the keys, and which shell types actually receive them — grep ~/.zshrc; zsh -ic / zsh -lc / zsh -c "printenv FIRECRAWL_API_KEY"
  found: Keys are exported ONLY in ~/.zshrc (interactive-only). zsh -ic (interactive) → PRESENT; zsh -lc (login non-interactive) → ABSENT; zsh -c (plain non-interactive) → ABSENT. ~/.zshenv does NOT contain the keys (an earlier "keys ARE in zshenv" reading was a false positive from a `grep|sed && echo` pipeline whose exit status came from sed, not grep).
  implication: Only interactive shells (a genuinely new iTerm2 pane/window) inherit the keys. Any non-interactive or GUI launch of Claude Code is blind to them. Robust remedy: move the two exports from ~/.zshrc to ~/.zshenv (sourced by ALL zsh invocations).

- timestamp: 2026-07-15T21:22
  checked: END-TO-END through the real render path — piped a session JSON payload to `cs render` inside `zsh -ic` (keys present); watched cache/inflight; re-rendered after the prober finished
  found: Run 1 created .inflight markers for BOTH providers (proving render_thin's new _maybe_refresh_search_credits fired with the live env — something the daemon never did). Prober refreshed the cache (age dropped to ~50s). Re-render output: `5h[ --% ] ⏰ -- | 7d[ --% ] | Opus 4.8 | fc[   100%   ] | tv[   100%   ]` — both bars present.
  implication: DEFINITIVE end-to-end confirmation. The fix works through the actual `cs render` code path, not just direct function calls. The only remaining requirement is that the process serving the status line actually holds the keys — a user-side launch/env action, not a code defect.

## Eliminated

- hypothesis: show_search_credits config toggle defaults off and user never enabled it
  evidence: User's actual ~/.claude/claude-statusbar.json already has "show_search_credits": true
  timestamp: 2026-07-15T20:15

- hypothesis: Stuck/leaked inflight lock is blocking re-probes
  evidence: No .inflight files exist in ~/.cache/claude-statusbar/provider_usage/
  timestamp: 2026-07-15T20:22

- hypothesis: provider_usage.py has a logic/parsing bug preventing segments from ever being produced
  evidence: Direct call with a live, key-containing environment produced correct segments within seconds
  timestamp: 2026-07-15T20:30

- hypothesis: The applied render_thin fix is insufficient / does not fire through the real render path
  evidence: `cs render` (real path) with a keys-present env created .inflight markers and, after the prober refreshed, rendered `fc[ 100% ] | tv[ 100% ]` end-to-end
  timestamp: 2026-07-15T21:22

- hypothesis: Keys are already available to all shells via ~/.zshenv (so a plain relaunch should suffice)
  evidence: ~/.zshenv does NOT export the keys; zsh -c and zsh -lc both return empty. Only ~/.zshrc (interactive) has them. Earlier "keys ARE in zshenv" was a bash pipeline exit-status artifact, not a real match.
  timestamp: 2026-07-15T21:10

## Resolution

- root_cause: The search-credit render/probe path (provider_usage.ensure_fresh()/segments()) is invoked almost exclusively inside the long-lived render daemon (daemon.py), whose os.environ is a frozen snapshot captured once at daemon-spawn time. FIRECRAWL_API_KEY/TAVILY_API_KEY are never forwarded through the codebase's existing session-live-env mechanism (render_thin._SESSION_ENV_KEYS/_cs_env — deliberately, to keep secrets off disk), so the daemon can only ever see these keys if it happened to inherit them at the exact moment it was spawned. Since the daemon serves virtually all statusline renders after warmup, any key exported/rotated after that moment is permanently invisible to it, so the cache goes stale (TTL_SECONDS=300) and never refreshes — bars appear at best fleetingly (during a brief inline-render fallback) then vanish for good. Confirmed empirically: the live daemon's environment (ps eww) lacks both keys even though the user's ~/.zshrc exports them, and a single stale cache entry (10+ minutes old) with zero refresh proves this exact failure mode. (Related, non-code factor: the currently-running Claude Code process itself predates the .zshrc export and also lacks the keys — full verification requires the user to restart their Claude Code session so a fresh process tree inherits the exported keys; no code change can retroactively update an already-running process's environment.)
- fix: Added `_maybe_refresh_search_credits()` to render_thin.py, called unconditionally at the top of `render()` (before the fast daemon-cat path AND the inline fallback). It reads the config toggle and, if enabled, calls the existing `provider_usage.ensure_fresh(os.environ)` using render_thin's own process environment — which is re-established fresh on every `cs render` invocation from whatever spawns it (Claude Code), unlike the daemon's one-time snapshot. This gives the search-credit cache a refresh path that is independent of the daemon's frozen env, without ever persisting the raw secret to disk (ensure_fresh only writes a non-secret inflight marker; the key itself only ever lives transiently in this process and the detached prober's child env).
- verification: Self-verified — 7 new regression tests pass (tests/test_search_credits_daemon_env.py), covering (a) toggle-off no-op, (b) live os.environ actually passed to ensure_fresh, (c) exceptions swallowed, (d) fast daemon-cat path still triggers the refresh, (e) fallback path still triggers the refresh, (f) end-to-end proof that a "frozen" env misses a key the live os.environ sees. Full suite: 1031 passed, 1 pre-existing unrelated failure (test_version_sync.py — marketplace.json version lag, confirmed present before this change via git stash). Directly reproduced the fix's mechanism live (not just tests): sourced ~/.zshrc + used the project's .venv interpreter, called provider_usage.ensure_fresh(os.environ)/segments(os.environ) directly — got real segments (fc 100%, tv 100%) within seconds, confirming the underlying logic is sound and the ONLY blocker was env availability at the call site.
  VERIFIED end-to-end (2026-07-15T21:22): driving the real `cs render` path with a keys-present env spawned the prober, refreshed the cache, and rendered `fc[ 100% ] | tv[ 100% ]`. The code fix is proven through the actual render code path, not just direct function calls.
  REMAINING (user-side, not a code defect): the user's live Claude Code session (pid 25134) was launched at 21:04 from a stale iTerm2 pane-shell (pid 68091) alive since 11:41 — before today's ~/.zshrc key exports — so it holds no keys to forward. To make the live status-line bars appear, the user must launch Claude Code from a shell that actually has the keys: EITHER (a) open a brand-new interactive iTerm2 pane/window (confirmed `zsh -ic` inherits the keys) and start `claude` there, OR (b) move the two exports from ~/.zshrc → ~/.zshenv so every launch method (including GUI) inherits them, then relaunch.
- files_changed:
  - src/claude_statusbar/render_thin.py
  - src/claude_statusbar/core.py (comment only — points future readers at the render_thin-side fix)
  - CHANGELOG.md
  - tests/test_search_credits_daemon_env.py (new)
