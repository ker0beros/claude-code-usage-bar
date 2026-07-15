# Quick Task 260715-pic: Search-provider credit bars (Firecrawl + Tavily) — Context

**Gathered:** 2026-07-15
**Status:** Ready for planning
**Origin:** Approved plan (`~/.claude-account1/plans/i-wonder-if-the-refactored-engelbart.md`) after research + a plan-mode design pass. Decisions below are LOCKED.

<domain>
## Task Boundary

Surface **remaining API credits for the user's MCP search providers** as per-provider mini bars in the status line — the same at-a-glance treatment the tool gives Claude rate limits and third-party relay balance.

**In scope:** Firecrawl + Tavily (both expose a real remaining/limit endpoint). Opt-in, default-off. Per-provider mini fuel-gauge bars, each shown ONLY when that provider's API key is present in the environment.
**Out of scope:** Exa (no programmatic remaining-balance API — dashboard-only per Exa docs). Reset-countdowns for the provider windows.
</domain>

<decisions>
## Implementation Decisions (LOCKED)

### Feasibility / endpoints (confirmed from official docs)
- **Firecrawl:** `GET https://api.firecrawl.dev/v2/team/credit-usage`, header `Authorization: Bearer <FIRECRAWL_API_KEY>` → `data.remainingCredits`, `data.planCredits`, `data.billingPeriodEnd` (nullable). pct = `remainingCredits / planCredits * 100`.
- **Tavily:** `GET https://api.tavily.com/usage`, header `Authorization: Bearer <TAVILY_API_KEY>` → prefer `account.plan_limit - account.plan_usage`; fall back to `key.limit - key.usage`. pct accordingly. **Rate-limited 10 req / 10 min**; no reset-date field. On `429`/`retry-after` → negative cache + back off.

### Architecture — clone the proven patterns (no new architecture)
- **Sourcing/caching = relay-balance gauge:** render path reads a cache file ONLY; a **detached subprocess** does the `urllib` probe and writes a TTL/negative-cached file behind an inflight lock. Templates: `core.relay_balance` → `_balance_refresh.py` → `balance_cache.py`.
- **Opt-in network signal = IP-risk trio:** `ip_risk.py` + `_ip_risk_refresh.py` + `daemon.py` heartbeat + default-off toggle. API key read from an env var, **fingerprinted (never written to disk)**, forwarded to the prober via a `CS_*` env var.
- **Invariants (must hold):** render path stays **stdlib-only and never touches the network**; **zero new third-party deps** (stdlib `urllib`); raw keys never on disk; render path never blocks.

### New modules
- **`src/claude_statusbar/provider_usage.py`** (model on `ip_risk.py` + `balance_cache.py`): `PROVIDERS` table (`firecrawl`→`FIRECRAWL_API_KEY` label `fc`, `tavily`→`TAVILY_API_KEY` label `tv`); `ensure_fresh(env)` (spawns detached prober for providers whose env key is present, if stale & not inflight; forwards keys via `CS_SEARCH_KEYS` JSON); `segments(env)` (returns ordered `{label, pct, text, remaining, limit}` for providers with a key present AND a fresh, supported, computable-pct cache entry — omit otherwise). Cache: positive TTL **300s**, negative TTL **3600s**, inflight ~60s; dir `~/.cache/claude-statusbar/provider_usage/`; per-provider fingerprint `sha1(name+key)` (reuse `balance_cache.fingerprint` style).
- **`src/claude_statusbar/_provider_usage_refresh.py`** (model on `_balance_refresh.py`/`_ip_risk_refresh.py`): detached prober; per provider in `CS_SEARCH_KEYS` call the endpoint (urllib, ~6s timeout, custom UA — mirror `_balance_refresh._get_json`), compute remaining/limit/pct, atomic-write cache. Any per-provider failure → `{"supported": false}` negative entry; **`sys.exit(0)` always**, never raise.

### Wiring into existing files (follow the `show_ip_risk` template)
- **`config.py`:** add `show_search_credits: bool = False` in four spots — dataclass field+default, `load_config()` mapping (`_to_bool(..., False)`), `VALID_KEYS`, `_BOOL_KEYS`. Persistence automatic; `cs config set/get show_search_credits` then works with no CLI change.
- **`core.py` `main()`:** gated `search_kwargs = {"search_credits": provider_usage.segments(env)}` block (call `provider_usage.ensure_fresh(env)` first) when `cfg.show_search_credits`; splice `**search_kwargs` into **ALL FOUR** `_render_style(...)` calls (no-quota, official-quota, and the two waiting/fallback branches). Renders in every quota mode.
- **`progress.py` `format_status_line`:** accept `search_credits=None` (list); render each as a mini fuel-gauge battery reusing **`_build_dimension(label, pct, …, fill_rgb=_balance_fill_rgb(pct))`** so remaining-% coloring matches the relay gauge (green > `BALANCE_LOW_THRESHOLD` 25 > yellow > `BALANCE_CRITICAL_THRESHOLD` 10 > red). Append after the balance/cost segments (end of line).
- **`styles.py`:** `render_classic` forwards `search_credits`; `render_capsule`/`render_hairline` accept it and render each provider as a severity-colored text chip (full battery is classic-only, matching `balance_pct`/`balance_amount` today). Others keep `**_ignored`.
- **`daemon.py` `run_forever`:** config-gated `provider_usage.ensure_fresh(env)` next to the IP-risk heartbeat (~lines 631–643), so opted-out users make zero provider calls.
- **`preview.py`:** add demo `search_credits` to `_demo_data` (optionally `_real_data`) and pass into the `render(...)` calls so `cs preview` shows the mini-bars across styles×themes.
- **`CHANGELOG.md`:** Unreleased entry.

### Claude's Discretion
- Provider glyph/label (`fc`/`tv` vs 🔥/icons) — cosmetic, pick during execution; keep consistent with existing 2–3 char labels (`bal`/`ctx`/`5h`/`7d`).
- Exact segment placement/ordering if two providers present.
- Whether a missing/zero limit shows a raw remaining count as text or omits (default: omit).

### Edge cases (must handle, never crash)
- Key absent → omit that provider; both keys absent → no segment at all (even with toggle on).
- API error / `429` / negative cache → omit that provider (no noisy `--`); back off via negative TTL.
- `planCredits`/`limit` missing or `0` → no computable pct → omit that provider's bar.
- Nullable fields: Firecrawl `billingPeriodEnd` may be null; Tavily has no reset field — MVP shows fill % only.
- Values are eventually-consistent (Firecrawl credits can go up via feedback refunds) — treat as a snapshot, not monotonic.
</decisions>

<specifics>
## Tests (required)
- Parse a sample Firecrawl v2 body → correct pct; parse a sample Tavily body → `plan_limit − plan_usage` pct (and `key`-level fallback).
- Provider omitted when key absent / limit missing / negative-cached.
- Fill color at the 25 / 10 remaining thresholds (reuse balance semantics).
- **Render-path isolation** (mirror `ip_risk` tests): render path opens no socket — reads cache files only.
- Prober writes negative cache and `exit(0)` on simulated failure, never raises.
- Rendering: classic mini-bars, capsule/hairline chips, `cs preview` demo all render with a stub `search_credits`.
- Full suite stays green: `uv run --with pytest -m pytest -q` (ignore the 1 pre-existing, unrelated `test_version_sync.py::test_marketplace_and_plugin_versions_match_pyproject` v3.30.0 marketplace-drift failure).

## Deferred (note in STATE.md deferred items)
- **Exa** credit bar — needs a user-entered starting balance/limit + polled spend subtraction, or a spend-only chip; no remaining-balance API exists.
- Reset-countdown for Firecrawl `billingPeriodEnd` (could reuse the new timer-coloring work).
</specifics>

<canonical_refs>
## Canonical References
- `~/.claude-account1/plans/i-wonder-if-the-refactored-engelbart.md` — the full approved plan (source of these decisions).
- Reuse targets in-repo: `src/claude_statusbar/ip_risk.py` + `_ip_risk_refresh.py` (opt-in network-signal template), `_balance_refresh.py` + `balance_cache.py` (detached prober + cache mechanics), `core.py` `relay_balance`/`main()` render branches, `progress.py` `_build_dimension`/`_balance_fill_rgb` (battery + remaining-% coloring), `styles.py` `render()` dispatch, `config.py` `show_ip_risk` toggle pattern, `daemon.py` `run_forever` IP-risk heartbeat, `preview.py` `_demo_data`/`_real_data`.
- Provider docs: Firecrawl `https://docs.firecrawl.dev/api-reference/endpoint/credit-usage`; Tavily `https://docs.tavily.com/documentation/api-reference/endpoint/usage` + rate limits `https://docs.tavily.com/documentation/rate-limits`.
</canonical_refs>
