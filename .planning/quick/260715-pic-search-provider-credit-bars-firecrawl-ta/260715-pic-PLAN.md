---
phase: quick-260715-pic
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/claude_statusbar/provider_usage.py
  - src/claude_statusbar/_provider_usage_refresh.py
  - src/claude_statusbar/config.py
  - src/claude_statusbar/core.py
  - src/claude_statusbar/progress.py
  - src/claude_statusbar/styles.py
  - src/claude_statusbar/preview.py
  - src/claude_statusbar/daemon.py
  - tests/test_provider_usage.py
  - tests/test_provider_usage_render.py
  - tests/test_config_search_credits.py
  - CHANGELOG.md
  - .planning/STATE.md
autonomous: true
requirements: [QT-260715-pic-search-credits]

must_haves:
  truths:
    - "With show_search_credits on and FIRECRAWL_API_KEY set, the status line shows an `fc` mini fuel-gauge bar for remainingCredits/planCredits."
    - "With TAVILY_API_KEY set, a `tv` bar shows remaining from account.plan_limit − account.plan_usage (key.limit − key.usage fallback)."
    - "With the toggle off (default), no provider bar renders and zero provider network calls are made."
    - "A provider whose key is absent, whose limit is missing/0, whose probe failed, or that is negative-cached is silently omitted — no `--`, no crash."
    - "The render path (segments) opens no socket and reads cache files only; a detached prober does the HTTP probe."
    - "Bars render across classic (battery), capsule/hairline (chips), and cs preview."
    - "Full test suite stays green and no new third-party dependency is added (stdlib urllib only)."
  artifacts:
    - src/claude_statusbar/provider_usage.py
    - src/claude_statusbar/_provider_usage_refresh.py
    - "config field: StatusbarConfig.show_search_credits (default False)"
    - tests/test_provider_usage.py
    - tests/test_provider_usage_render.py
    - tests/test_config_search_credits.py
  key_links:
    - "core.main() calls provider_usage.ensure_fresh(_effective_env) then splices provider_usage.segments(_effective_env) into all four _render_style() calls."
    - "daemon.run_forever() gates provider_usage.ensure_fresh(env) behind cfg.show_search_credits, next to the IP-risk heartbeat."
    - "progress.format_status_line reuses _build_dimension + _balance_fill_rgb for each provider battery."
    - "prober forwards keys via CS_SEARCH_KEYS JSON and keys buckets by fingerprint sha1(name+key) so the raw key never touches disk."
---

<objective>
Surface remaining API credits for the user's MCP search providers (Firecrawl + Tavily) as opt-in, default-off, per-provider mini fuel-gauge bars in the status line — the same at-a-glance treatment the tool already gives Claude rate limits and the third-party relay balance. Each bar shows ONLY when that provider's API key is present in the environment.

This is a near-mechanical CLONE of two proven in-repo patterns:
- the opt-in network-signal trio (`ip_risk.py` + `_ip_risk_refresh.py` + `daemon.py` heartbeat + default-off toggle), and
- the detached-prober + TTL/negative cache mechanics (`_balance_refresh.py` + `balance_cache.py`), plus the reusable battery builder (`progress._build_dimension` / `_balance_fill_rgb`).

Purpose: give search-provider quota the same visibility as rate limits, without adding architecture, dependencies, or any network work on the render path.
Output: two new modules (`provider_usage.py`, `_provider_usage_refresh.py`), a `show_search_credits` config toggle, wiring across core/progress/styles/preview/daemon, three test files, a CHANGELOG entry, and a STATE deferred note.

Traceability: every task implements the LOCKED decisions in `260715-pic-CONTEXT.md`. Exa is OUT OF SCOPE (no remaining-balance API) — recorded as a STATE deferred item only, never planned.
</objective>

<execution_context>
@$HOME/.claude-account1-account1/gsd-core/workflows/execute-plan.md
@$HOME/.claude-account1-account1/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/260715-pic-search-provider-credit-bars-firecrawl-ta/260715-pic-CONTEXT.md

# Clone targets — read the exact signatures/idioms before writing
@src/claude_statusbar/ip_risk.py
@src/claude_statusbar/_ip_risk_refresh.py
@src/claude_statusbar/_balance_refresh.py
@src/claude_statusbar/balance_cache.py
@src/claude_statusbar/progress.py
@src/claude_statusbar/config.py
@src/claude_statusbar/styles.py
@src/claude_statusbar/preview.py

# Wiring reference points in core/daemon
@tests/test_ip_risk.py
@tests/test_balance_refresh.py
@tests/test_balance_render.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: provider_usage module + detached prober + cache/parse unit tests</name>
  <files>src/claude_statusbar/provider_usage.py, src/claude_statusbar/_provider_usage_refresh.py, tests/test_provider_usage.py</files>
  <behavior>
    - Firecrawl parse: body {"data": {"remainingCredits": 820, "planCredits": 1000, "billingPeriodEnd": null}} → remaining 820, limit 1000, pct 82.0, supported True.
    - Tavily parse (account-level): {"account": {"plan_limit": 1000, "plan_usage": 250}} → remaining 750, limit 1000, pct 75.0.
    - Tavily parse (key-level fallback): {"key": {"limit": 400, "usage": 100}} with no usable account → remaining 300, limit 400, pct 75.0.
    - Omission: planCredits/plan_limit missing or 0 → no computable pct → cache entry {"supported": false} (segments omits it).
    - Prober fail-safe: a probe that raises / returns non-200 / bad JSON / HTTP 429 → writes {"supported": false} negative entry, clears inflight, and main() returns 0 (never raises).
    - segments(env): returns ordered [{label,pct,text,remaining,limit}] ONLY for providers whose key is present AND whose cache entry is fresh + supported + has a computable pct; omits all others. Reads cache only — never spawns, never opens a socket.
    - Fingerprint: fingerprint(name, key) = sha1(name + b"\x00" + key) — the raw key never appears in any written file (only the hex digest is the filename, and no key field is persisted).
    - pct is clamped to [0, 100] (eventual-consistency / refund overshoot never leaves the rail).
  </behavior>
  <action>
Create `src/claude_statusbar/provider_usage.py`, modeled on `ip_risk.py` (freshness/inflight/ensure_fresh spawn) fused with `balance_cache.py` (fingerprint + atomic write + positive/negative TTL). Define:
- `PROVIDERS`: an ordered table mapping provider name → (env var, short label). Exactly two entries per CONTEXT "New modules": `firecrawl` → (`FIRECRAWL_API_KEY`, `fc`) and `tavily` → (`TAVILY_API_KEY`, `tv`). Order defines segment order.
- TTL constants: positive `TTL_SECONDS = 300`, negative `NEGATIVE_TTL_SECONDS = 3600`, `INFLIGHT_MAX_AGE_S = 60` (mirror balance_cache values per CONTEXT).
- `_cache_root()` returning `~/.cache/claude-statusbar/provider_usage` (expanduser). Keep it a function so tests can monkeypatch it exactly like `ip_risk._cache_root`.
- `fingerprint(name, key)`: `hashlib.sha1(name-bytes + b"\x00" + key-bytes).hexdigest()` — reuse the balance_cache style; the raw key is NEVER written to disk.
- `cache_path_for(fp)`, `read_cache(fp)`, `write_cache_atomic(fp, entry)` (reuse `.cache.atomic_write_text` like ip_risk, or tempfile+os.replace like balance_cache — either, but atomic), `is_fresh(entry, now=None)` (positive TTL when `supported` else negative TTL — copy balance_cache.is_fresh semantics), `_inflight_path(fp)`, `is_inflight(fp)`, `mark_inflight(fp)`, `clear_inflight(fp)`.
- `ensure_fresh(env)`: for each provider in PROVIDERS whose `env.get(env_var)` is truthy, compute fp; if `read_cache(fp)` is NOT fresh and NOT inflight, mark it inflight and add name→key to a dict. If that dict is non-empty, spawn ONE detached `python -m claude_statusbar._provider_usage_refresh` via `subprocess.Popen` (stdin/out/err DEVNULL, close_fds, start_new_session) with a child env that copies os.environ plus `CS_SEARCH_KEYS` = `json.dumps({name: key, ...})`. On Popen OSError/ValueError, clear the inflight markers you set. Wrap the whole body so it NEVER raises (mirror `ip_risk.ensure_fresh`). This is the ONLY spawn path.
- `segments(env)`: read-only. For each provider in PROVIDERS order, if the key is present in `env`, read its cache; include a `{"label": label, "pct": pct, "text": f"{label} {pct:.0f}%", "remaining": remaining, "limit": limit}` entry ONLY when the cache is `is_fresh` AND `supported` AND carries a numeric `pct`. Omit otherwise. Never spawn, never import subprocess/urllib in this function.

Create `src/claude_statusbar/_provider_usage_refresh.py`, modeled on `_balance_refresh.py`:
- `_get_json(url, key)`: mirror `_balance_refresh._get_json` — urllib.request.Request with headers `Authorization: Bearer {key}`, `Accept: application/json`, a descriptive `User-Agent` (e.g. `claude-statusbar-search/1.0`); `_TIMEOUT_S = 6`; `urlopen` then reject non-200; `resp.read(65536)` size cap; `json.loads` with `isinstance(data, dict)` guard; return None on any `urllib.error.URLError`/`OSError`/`ValueError`/`json.JSONDecodeError`. This is the untrusted-JSON trust boundary — parse defensively.
- `_probe_firecrawl(key)`: GET `https://api.firecrawl.dev/v2/team/credit-usage`; from `data.data`, read `remainingCredits` (remaining) and `planCredits` (limit); if limit is a positive number and remaining is numeric, return `{remaining, limit, pct: clamp(remaining/limit*100, 0, 100), billing_period_end: data.data.get("billingPeriodEnd")}` (billingPeriodEnd may be null — carry it but do not require it); else None.
- `_probe_tavily(key)`: GET `https://api.tavily.com/usage`; prefer `account.plan_limit`/`account.plan_usage` → remaining = limit − usage; if that pair is not usable, fall back to `key.limit`/`key.usage`. When a usable (limit>0, both numeric) pair is found, return `{remaining, limit, pct: clamp(...)}`; else None. A non-200 (incl. HTTP 429 rate limit) surfaces as `_get_json` → None, so a rate-limited call becomes a negative-cache entry and the 3600s negative TTL backs off well past Tavily's 10-req/10-min window.
- `main()`: parse `CS_SEARCH_KEYS` JSON from env; for each `name → key`, dispatch to the right prober; compute `fp = provider_usage.fingerprint(name, key)`; on a usable result write `{"ts": time.time(), "supported": True, **result}`, else write `{"ts": time.time(), "supported": False}`; ALWAYS `provider_usage.clear_inflight(fp)` in a finally. Catch per-provider exceptions so one bad provider never blocks the other. Return 0.
- `if __name__ == "__main__": sys.exit(main())` wrapped in try/except → `sys.exit(0)` (never crash a detached refresh), exactly like `_balance_refresh`.

Do NOT hand-roll HTTP or add any dependency — stdlib `urllib` only, per CONTEXT "Invariants". Use a clamp helper `max(0.0, min(100.0, pct))` for pct.

Create `tests/test_provider_usage.py` mirroring `tests/test_balance_refresh.py` + `tests/test_ip_risk.py`: stub `_provider_usage_refresh._get_json` to return canned Firecrawl/Tavily bodies; isolate the cache dir by monkeypatching `provider_usage._cache_root` to `tmp_path` (like `ip_risk._iso`). Cover: Firecrawl pct, Tavily account pct, Tavily key-level fallback, missing/0 limit → supported False, prober failure (raise + non-200) writes negative cache and returns 0, fill-color thresholds via `progress._balance_fill_rgb` at 25/10 remaining, `segments()` includes only fresh+supported+computable and preserves PROVIDERS order, and a fingerprint assertion that the written cache file contains no raw key substring.
  </action>
  <verify>
    <automated>uv run --with pytest -m pytest tests/test_provider_usage.py -q</automated>
  </verify>
  <done>provider_usage.py and _provider_usage_refresh.py exist; both provider bodies parse to correct pct (with Tavily key fallback); omission cases and prober fail-safe (negative cache + exit 0, never raises) hold; segments() reads cache only in PROVIDERS order; the raw key never appears in a written cache file; tests/test_provider_usage.py passes.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: config toggle + core.main() wiring (all 4 render branches) + classic/capsule/hairline/preview rendering</name>
  <files>src/claude_statusbar/config.py, src/claude_statusbar/core.py, src/claude_statusbar/progress.py, src/claude_statusbar/styles.py, src/claude_statusbar/preview.py, tests/test_provider_usage_render.py, tests/test_config_search_credits.py</files>
  <behavior>
    - Config: StatusbarConfig().show_search_credits is False by default; set_value("show_search_credits","on") persists and load_config reads it back True; the key appears in `cs config show`.
    - Classic: format_status_line(..., search_credits=[{"label":"fc","pct":82.0,...}]) appends an `fc[...82%...]` battery reusing _build_dimension + _balance_fill_rgb; empty/None list appends nothing.
    - Capsule + hairline: render each provider as a severity-colored text chip (label + pct), colored by _balance_fill_rgb(pct); omitted when the list is empty.
    - Rendering happens in every quota mode (no-quota, official-quota, waiting/stale) — the segment lives at the end of the line after balance/cost.
    - Preview: `cs preview` demo data carries search_credits so the mini-bars appear across styles × themes.
  </behavior>
  <action>
CONFIG (`config.py`) — clone the `show_ip_risk` toggle across the four spots per CONTEXT "Wiring":
1. Add dataclass field `show_search_credits: bool = False` with a short comment (opt-in; reads FIRECRAWL_API_KEY / TAVILY_API_KEY, default off because it makes third-party calls).
2. Add `show_search_credits=_to_bool(raw.get("show_search_credits", False))` to the `load_config()` StatusbarConfig(...) construction.
3. Add `"show_search_credits"` to `VALID_KEYS`.
4. Add `"show_search_credits"` to `_BOOL_KEYS`.

PROGRESS (`progress.py`) — add `search_credits=None` (list) as a keyword param to `format_status_line`. Add a module-level helper `_search_credit_parts(search_credits, theme, use_color)` that returns a list of rendered classic battery strings: for each entry, `fill = _balance_fill_rgb(entry["pct"], theme)` then `_build_dimension(entry["label"], entry["pct"], _fg(fill), use_color, BALANCE_LOW_THRESHOLD, BALANCE_CRITICAL_THRESHOLD, theme, fill_rgb=fill)` — identical to the existing `bal` battery. Returns `[]` for a falsy list. Append `parts.extend(_search_credit_parts(...))` in ALL THREE return branches (no_quota, quota_stale, and the main quota branch) AFTER the cost/lang segments and BEFORE the bypass segment, so the credits sit at the end of the line in every mode.

STYLES (`styles.py`):
- `render_classic`: add `search_credits=None` param and forward it into the `format_status_line(...)` call.
- `render_capsule` and `render_hairline`: add `search_credits=None` param (they currently swallow unknowns via `**_ignored`, so make it explicit). After the balance/cost chips, for each entry append a severity-colored text chip: color from `progress._balance_fill_rgb(entry["pct"], theme)`. Capsule → a pill tinted by that severity (consistent with its other pills); hairline → `{_fg(fill)}{label} {pct:.0f}%{RESET}` joined into parts. Full battery stays classic-only (matching how `balance_pct`/`balance_amount` render today). Exact glyph/label styling is Claude's discretion per CONTEXT — keep labels consistent with the 2–3 char `bal`/`ctx`/`5h` family.

CORE (`core.py` `main()`) — clone the `ip_line_kwargs` block:
- Just after the `fp_line_kwargs` block (around line 1209, BEFORE the `try:` at ~1239 so it is in scope for the exception branch), add a `search_kwargs = {}` block gated on `cfg.show_search_credits`. Inside a try/except (never raise): `from . import provider_usage; provider_usage.ensure_fresh(_effective_env); segs = provider_usage.segments(_effective_env)` and if `segs`, set `search_kwargs = {"search_credits": segs}`. Use `_effective_env` (the per-session env), matching how balance/no-quota detection already reads it.
- Splice `**search_kwargs` into ALL FOUR `_render_style(...)` calls: the no_quota branch (~1318), the has_official branch (~1452), the waiting/stale branch (~1510), and the exception/fallback branch (~1542) — add it alongside the existing `**ip_line_kwargs, **fp_line_kwargs` (and `**activity_kwargs` where present).

PREVIEW (`preview.py`): add a demo `search_credits` list (e.g. `[{"label":"fc","pct":82.0,"text":"fc 82%","remaining":820,"limit":1000}, {"label":"tv","pct":18.0,"text":"tv 18%","remaining":180,"limit":1000}]`) to `_demo_data`, and pass `search_credits=data.get("search_credits")` into both `render(...)` calls in `run()` so the matrix shows the mini-bars. (Optional: derive `_real_data` search_credits from `provider_usage.segments(os.environ)` — keep it best-effort/omit on any failure.)

TESTS:
- `tests/test_config_search_credits.py`: mirror `tests/test_config_context.py` — default off, set→load round-trip, and `cs config show` lists `show_search_credits`.
- `tests/test_provider_usage_render.py`: mirror `tests/test_balance_render.py` — classic battery via `progress.format_status_line(..., search_credits=[...])` shows `fc[` and `82%`; capsule and hairline chips show the label + pct; empty list renders nothing; a preview smoke test asserts `cs preview` output contains the demo provider label. Use `use_color=False` for stable assertions.
  </action>
  <verify>
    <automated>uv run --with pytest -m pytest tests/test_config_search_credits.py tests/test_provider_usage_render.py tests/test_preview.py -q</automated>
  </verify>
  <done>show_search_credits defaults off and round-trips through config + `cs config show`; classic renders an fc/tv battery via _build_dimension+_balance_fill_rgb; capsule/hairline render severity-colored chips; core splices search_credits into all four render branches gated by the toggle; cs preview shows the mini-bars; the three test files pass.</done>
</task>

<task type="auto">
  <name>Task 3: daemon heartbeat + render-path isolation & edge-case tests + CHANGELOG + STATE deferred note</name>
  <files>src/claude_statusbar/daemon.py, tests/test_provider_usage.py, tests/test_provider_usage_render.py, CHANGELOG.md, .planning/STATE.md</files>
  <behavior>
    - Daemon: when cfg.show_search_credits is on, run_forever calls provider_usage.ensure_fresh(env) on the heartbeat; when off, it makes ZERO provider calls.
    - Render-path isolation: calling provider_usage.segments(env) opens no socket — monkeypatch socket.socket to raise and assert segments() still returns cleanly (reads cache only), mirroring the ip_risk isolation intent.
    - Edge cases: both keys absent → segments() returns [] even with the toggle on; a fresh negative-cache entry → that provider omitted and NOT re-probed by segments().
  </behavior>
  <action>
DAEMON (`daemon.py` `run_forever`): next to the IP-risk heartbeat (the `if t0 - last_ip > IP_HEARTBEAT_S:` block around lines 631-643), add a config-gated `provider_usage.ensure_fresh` call. Reuse the SAME heartbeat cadence/gate structure: inside the existing try/except (or a sibling one), `from .config import load_config; cfg = load_config()` — if `cfg.show_search_credits`, `from . import provider_usage; provider_usage.ensure_fresh(os.environ)`. Opted-out users (default) MUST make zero provider calls, exactly like show_ip_risk. Wrap so a failure never breaks the loop. Reuse the existing `load_config()` read if the ip block already loaded it in the same tick to avoid a double read (optional micro-opt; correctness first).

TESTS — append to the existing files (do not create new ones):
- In `tests/test_provider_usage.py`, add a render-path isolation test: isolate the cache dir, write a fresh supported entry for one provider, monkeypatch `socket.socket` to raise AssertionError, and assert `provider_usage.segments(env)` returns the entry without raising (proves no network on the render path). Add an edge test: both keys absent → `segments({})` == []; and a fresh `{"supported": false}` entry → provider omitted and (with `subprocess.Popen` monkeypatched to record) segments() records no spawn.
- In `tests/test_provider_usage_render.py` (or test_provider_usage.py), add a daemon-gate test if practical: with the toggle OFF, `provider_usage.ensure_fresh` is not invoked (or spawns nothing) — assert via a monkeypatched spawn/marker that no probe launches. Keep it lightweight; the core gate is already covered by the toggle default.

CHANGELOG (`CHANGELOG.md`): add a bullet under the existing `## Unreleased` section describing the opt-in search-provider credit bars (Firecrawl `fc` + Tavily `tv`), default-off via `cs config set show_search_credits on`, detached prober + TTL/negative cache, render path never touches the network, zero new deps.

STATE (`.planning/STATE.md`): add two rows to the `## Deferred Items` table per CONTEXT "Deferred": (1) Exa credit bar — no remaining-balance API; needs a user-entered starting balance + polled spend subtraction (or a spend-only chip). (2) Reset-countdown for Firecrawl `billingPeriodEnd` — could reuse the timer-coloring work. Also add a `## Quick Tasks Completed` row for 260715-pic once implemented (leave the commit column to the executor).

Do NOT touch the Exa provider anywhere in code — it stays a STATE deferred item only.
  </action>
  <verify>
    <automated>uv run --with pytest -m pytest -q --deselect tests/test_version_sync.py::test_marketplace_and_plugin_versions_match_pyproject</automated>
  </verify>
  <done>daemon.run_forever gates provider_usage.ensure_fresh behind cfg.show_search_credits (zero calls when off); render-path isolation test proves segments() opens no socket; both-keys-absent and negative-cache omission edge tests pass; CHANGELOG has an Unreleased search-credits bullet; STATE records Exa + billingPeriodEnd deferred items; full suite is green (the pre-existing test_version_sync marketplace-drift failure is deselected).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| provider API → prober | Firecrawl / Tavily return untrusted JSON that `_provider_usage_refresh._get_json` parses. |
| env keys → child process | FIRECRAWL_API_KEY / TAVILY_API_KEY are read from the session env and forwarded to the detached prober via `CS_SEARCH_KEYS`. |
| cache file → render path | `segments()` trusts only files it wrote under `~/.cache/claude-statusbar/provider_usage/`. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-pic-01 | Tampering | `_get_json` / `_probe_*` parsing provider JSON | medium | mitigate | `isinstance(dict)` guards on every field, `resp.read(65536)` size cap, numeric checks before pct math, `clamp(pct, 0, 100)`; any parse error → return None → negative-cache entry. |
| T-pic-02 | Denial of Service | prober HTTP call (hang / oversized body / Tavily 429 storm) | medium | mitigate | 6s urlopen timeout, 64KB read cap, negative TTL 3600s (backs off past Tavily's 10-req/10-min window), inflight lock prevents spawn storms, `ensure_fresh` self-throttles per provider. |
| T-pic-03 | Information disclosure | raw API key persisted to disk | high | mitigate | cache bucketed by `fingerprint = sha1(name+\x00+key)`; only the hex digest is the filename; no key field is ever written to the cache entry (mirror balance_cache). |
| T-pic-04 | Information disclosure | key forwarded to child process | low | accept | key travels only via the child's env (`CS_SEARCH_KEYS`), not argv and not disk; same trust model as `_balance_refresh`'s `CS_BALANCE_KEY`. |
| T-pic-05 | Denial of Service | render path blocking on network | high | mitigate | `segments()` is read-only (no subprocess/urllib import); the ONLY spawn path is `ensure_fresh`; render never blocks — enforced by the socket-isolation test. |
| T-pic-06 | Spoofing | MITM of provider endpoint | low | accept | both endpoints are HTTPS; stdlib urllib validates TLS by default; no new trust surface. |
| T-pic-SC | Supply chain | dependency installs | n/a | accept | ZERO new third-party deps — stdlib `urllib` only (CONTEXT invariant). No npm/pip/cargo install, so no package-legitimacy gate applies. |
</threat_model>

<verification>
- `uv run --with pytest -m pytest -q --deselect tests/test_version_sync.py::test_marketplace_and_plugin_versions_match_pyproject` → full suite green.
- Toggle-off default: with `show_search_credits` off, no provider bar renders and no provider network call is made (daemon + core both gated).
- Render-path isolation: `segments()` opens no socket (socket-monkeypatch test passes).
- Prober fail-safe: simulated failure / 429 writes a negative-cache entry and exits 0 without raising.
- Both provider bodies parse to correct pct (Firecrawl remainingCredits/planCredits; Tavily account then key fallback); omission holds for absent key / missing-or-zero limit / negative cache.
- Rendering: classic battery + capsule/hairline chips + `cs preview` all show the mini-bars for a stub `search_credits`.
</verification>

<success_criteria>
- Two new modules (`provider_usage.py`, `_provider_usage_refresh.py`) clone the ip_risk + balance-cache patterns with zero new dependencies.
- `show_search_credits` config toggle exists across all four config spots, default off, round-trips, and lists in `cs config show`.
- `fc` / `tv` mini bars render in every quota mode (classic battery; capsule/hairline chips), each shown only when its env key is present AND its cache is fresh+supported+computable.
- Render path never touches the network; the detached prober does all HTTP; daemon + core spawn only when opted in.
- CHANGELOG has an Unreleased entry; STATE records Exa + billingPeriodEnd as deferred items.
- Full test suite green (ignoring the pre-existing `test_version_sync` marketplace-drift failure).
</success_criteria>

<output>
Create `.planning/quick/260715-pic-search-provider-credit-bars-firecrawl-ta/260715-pic-SUMMARY.md` when done.
</output>
