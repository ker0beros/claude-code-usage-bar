---
phase: quick-260715-pic
verified: 2026-07-15T00:00:00Z
status: passed
score: 7/7 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Quick Task 260715-pic: Search-Provider Credit Bars (Firecrawl + Tavily) Verification Report

**Task Goal:** Opt-in per-provider (Firecrawl + Tavily) search-credit mini fuel-gauge bars in the status line, cloning the relay-balance gauge + IP-risk opt-in pattern, with the render path never touching the network.

**Verified:** 2026-07-15
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | With `show_search_credits` on and `FIRECRAWL_API_KEY` set, the status line shows an `fc` mini fuel-gauge bar for remainingCredits/planCredits | ✓ VERIFIED | `_provider_usage_refresh._probe_firecrawl` (`src/claude_statusbar/_provider_usage_refresh.py:52-70`) parses `data.data.remainingCredits`/`planCredits` from `GET https://api.firecrawl.dev/v2/team/credit-usage` with `Authorization: Bearer`; `progress._search_credit_parts` (`progress.py:367-385`) builds the battery via `_build_dimension`+`_balance_fill_rgb`; `tests/test_provider_usage.py::test_firecrawl_parse_computes_remaining_and_pct` and `tests/test_provider_usage_render.py::test_classic_search_credit_battery_no_quota` pass and assert `fc[` / `82%` literally in rendered output. |
| 2 | With `TAVILY_API_KEY` set, a `tv` bar shows remaining from `account.plan_limit − account.plan_usage` (`key.limit − key.usage` fallback) | ✓ VERIFIED | `_probe_tavily` (`_provider_usage_refresh.py:73-98`) implements account-first then key-level fallback exactly as specified; `tests/test_provider_usage.py::test_tavily_parse_account_level` and `test_tavily_parse_key_level_fallback` pass. |
| 3 | With the toggle off (default), no provider bar renders and zero provider network calls are made | ✓ VERIFIED | `StatusbarConfig.show_search_credits: bool = False` (`config.py:103`); `core.main()` only imports/calls `provider_usage.ensure_fresh`/`segments` inside `if cfg.show_search_credits:` (`core.py:1215-1224`); `daemon.run_forever` only calls `provider_usage.ensure_fresh` inside `if load_config().show_search_credits:` (`daemon.py:654-660`); `tests/test_provider_usage.py::test_search_credits_heartbeat_gated_on_show_search_credits` confirms zero calls when off. |
| 4 | A provider whose key is absent, whose limit is missing/0, whose probe failed, or that is negative-cached is silently omitted — no `--`, no crash | ✓ VERIFIED | `segments()` (`provider_usage.py:178-205`) requires key present AND `is_fresh(entry)` AND `entry.get("supported")` AND numeric `pct`, else the provider is skipped (no placeholder text is ever appended). `_probe_firecrawl`/`_probe_tavily` return `None` on missing/zero limit, which `main()` (`_provider_usage_refresh.py:107-133`) turns into `{"supported": False}`. Tests: `test_firecrawl_missing_plan_credits_is_unsupported`, `test_segments_both_keys_absent_returns_empty_even_with_cache`, `test_fresh_negative_cache_entry_omitted_and_not_reprobed`, `test_main_writes_negative_cache_on_probe_failure` all pass. |
| 5 | The render path (`segments()`) opens no socket and reads cache files only; a detached prober does the HTTP probe | ✓ VERIFIED | `segments()` has no `subprocess`/`urllib`/`socket` import in `provider_usage.py`; `ensure_fresh()` is the only function that imports `subprocess` (`provider_usage.py:158-159`, function-local import). `tests/test_provider_usage.py::test_segments_opens_no_socket` monkeypatches `socket.socket` to raise and confirms `segments()` still returns the cached entry; `test_segments_does_not_spawn_subprocess` monkeypatches `subprocess.Popen` and confirms no spawn. Both pass. |
| 6 | Bars render across classic (battery), capsule/hairline (chips), and cs preview | ✓ VERIFIED | `progress.py` splices `_search_credit_parts` into all 3 `format_status_line` branches (lines 633, 658, 738); `styles.py` `render_capsule` (line 239) and `render_hairline` (line 375) render severity-colored text chips; `render_classic` forwards `search_credits` (line 452); `preview.py` adds demo data (line 147-152) and a best-effort live `_real_search_credits()` (line 106-115), passed into both `render(...)` calls (lines 242, 262). Tests `test_classic_search_credit_battery_{no_quota,quota_mode,stale_mode}`, `test_capsule_search_credit_chip`, `test_hairline_search_credit_chip`, `test_preview_output_contains_search_credit_text` all pass and assert literal `fc[`/`82%`/`fc 82%` substrings from direct calls into `progress.format_status_line` / `styles.render_capsule` / `styles.render_hairline` / `preview.run` — not mocked-away shortcuts. |
| 7 | Full test suite stays green and no new third-party dependency is added (stdlib urllib only) | ✓ VERIFIED | `uv run --with pytest -m pytest -q --deselect tests/test_version_sync.py::test_marketplace_and_plugin_versions_match_pyproject` → **1021 passed, 1 deselected**. The deselected test fails standalone too (`marketplace.json metadata.version='3.29.11' != pyproject '3.30.0'`), confirmed pre-existing/unrelated — it's a marketplace.json version-drift check against the v3.30.0 release commit (`15162c6`) that predates this quick task's dispatch commit (`93c03b5`). `pyproject.toml` `dependencies = []` unchanged; `_provider_usage_refresh.py` imports only `json`, `os`, `sys`, `time`, `urllib.error`, `urllib.request` — stdlib only. |

**Score:** 7/7 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/claude_statusbar/provider_usage.py` | PROVIDERS table, TTL/fingerprint/cache helpers, `ensure_fresh`, `segments` | ✓ VERIFIED | All present exactly as specified: `PROVIDERS = (("firecrawl","FIRECRAWL_API_KEY","fc"), ("tavily","TAVILY_API_KEY","tv"))`, `TTL_SECONDS=300`, `NEGATIVE_TTL_SECONDS=3600`, `INFLIGHT_MAX_AGE_S=60`, `fingerprint()`=sha1(name+\x00+key), `ensure_fresh()` is sole subprocess spawn path, `segments()` is cache-read-only. |
| `src/claude_statusbar/_provider_usage_refresh.py` | Detached prober, both endpoints, Bearer auth, never raises | ✓ VERIFIED | `_get_json` uses `Authorization: Bearer {key}`, 6s timeout, 64KB read cap; `_probe_firecrawl` hits `/v2/team/credit-usage`; `_probe_tavily` hits `/usage`; `main()` always writes a cache entry and returns 0; `__main__` guard wraps in try/except → `sys.exit(0)`. |
| `config field: StatusbarConfig.show_search_credits (default False)` | Present in dataclass, load_config, VALID_KEYS, _BOOL_KEYS | ✓ VERIFIED | Confirmed at `config.py:103` (field), `:167` (load_config mapping), `:195` (VALID_KEYS), `:211` (_BOOL_KEYS). Bonus: `cli.py:65` prints it in `cs config show` (undeclared in plan's files_modified but required by the plan's own must-have and documented as a Rule-2 deviation in SUMMARY). |
| `tests/test_provider_usage.py` | Parsing/omission/isolation/fingerprint tests | ✓ VERIFIED | 37 tests, all pass. |
| `tests/test_provider_usage_render.py` | Classic/capsule/hairline/preview render tests | ✓ VERIFIED | 12 tests, all pass. |
| `tests/test_config_search_credits.py` | Default off / round-trip / config show listing | ✓ VERIFIED | 3 tests, all pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `core.main()` | `provider_usage.ensure_fresh` / `segments` | gated `search_kwargs` block, spliced into all 4 `_render_style()` calls | ✓ WIRED | `core.py:1215-1224` builds `search_kwargs`; splice sites confirmed at lines 1334, 1468, 1526, 1558 — all 4 `_render_style(` call sites at 1316, 1449, 1511, 1547. |
| `daemon.run_forever` | `provider_usage.ensure_fresh` | config-gated heartbeat next to IP-risk heartbeat | ✓ WIRED | `daemon.py:649-660`, shares `IP_HEARTBEAT_S` cadence, gated on `load_config().show_search_credits`, wrapped in try/except. |
| `progress.format_status_line` | `_build_dimension` + `_balance_fill_rgb` | `_search_credit_parts` helper | ✓ WIRED | `progress.py:367-385`, identical construction to the existing `bal[...]` battery. |
| `_provider_usage_refresh` prober | `CS_SEARCH_KEYS` env var | fingerprint bucketing, no raw key on disk | ✓ WIRED | `provider_usage.py:160-161` sets `child_env["CS_SEARCH_KEYS"]`; `_provider_usage_refresh.py:109` reads it; `tests/test_provider_usage.py::test_written_cache_file_never_contains_raw_key` and `test_prober_output_never_persists_raw_key` confirm the raw key never appears in the written cache file. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Task-scoped test files pass | `uv run --with pytest -m pytest tests/test_provider_usage.py tests/test_provider_usage_render.py tests/test_config_search_credits.py -q` | `52 passed in 1.74s` | ✓ PASS |
| Full suite green (minus pre-existing unrelated failure) | `uv run --with pytest -m pytest -q --deselect tests/test_version_sync.py::test_marketplace_and_plugin_versions_match_pyproject` | `1021 passed, 1 deselected` | ✓ PASS |
| Deselected test genuinely pre-existing/unrelated | `uv run --with pytest -m pytest tests/test_version_sync.py::test_marketplace_and_plugin_versions_match_pyproject -q` | Fails with `marketplace.json metadata.version='3.29.11' != pyproject '3.30.0'` — a release-bump drift, unrelated to search-credit code | ✓ PASS (confirmed pre-existing) |
| No new third-party dependency | `grep -A2 "^dependencies" pyproject.toml` | `dependencies = []` (unchanged); no `uv.lock`/`pyproject.toml` diff on this task's commits | ✓ PASS |
| Render-path socket isolation | `pytest -k test_segments_opens_no_socket` (included in full run above) | pass | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| QT-260715-pic-search-credits | 260715-pic-PLAN.md | Opt-in Firecrawl+Tavily search-credit bars, clone relay-balance + IP-risk pattern, network-free render path | ✓ SATISFIED | All 7 must-have truths verified above; 52 new tests pass; full suite green. |

### Anti-Patterns Found

None. Scanned all 8 modified/created source files (`provider_usage.py`, `_provider_usage_refresh.py`, `config.py`, `core.py`, `progress.py`, `styles.py`, `preview.py`, `daemon.py`) for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER|not yet implemented|coming soon` — zero matches.

### Exa Scope Check

Confirmed NOT implemented: no `exa`/`Exa`/`EXA` identifiers anywhere in `src/claude_statusbar/`. `provider_usage.py:32` comments "Exa is explicitly OUT OF SCOPE (no remaining-balance API)". `.planning/STATE.md` Deferred Items table (lines 111-112) records Exa credit bar and Firecrawl `billingPeriodEnd` reset-countdown as deferred-only, matching CONTEXT.

### CHANGELOG / STATE Documentation

- `CHANGELOG.md` (lines 14-19+): Unreleased entry describing opt-in `fc`/`tv` bars, default-off toggle, detached prober + TTL/negative cache — confirmed present.
- `.planning/STATE.md` (line 87): Quick Tasks Completed row for 260715-pic with all 3 task commit hashes (`3640e0e, 3dee232, 9265e55`) — confirmed present.
- `.planning/STATE.md` (lines 111-112): Exa + billingPeriodEnd deferred items — confirmed present.

### Human Verification Required

None. All must-haves resolved programmatically via direct code inspection, direct test execution (not just SUMMARY claims), and a full-suite run performed independently in this verification session.

### Gaps Summary

No gaps found. All 7 PLAN must-have truths, all 4 config spots, all 4 core render-branch splices, all 3 progress.py branches, both capsule/hairline render functions, the daemon heartbeat gate, and the render-path network isolation are verified directly against the codebase (not inferred from SUMMARY.md). The one documented deviation (adding `show_search_credits` to `cli.py`'s `cs config show` print list, outside the plan's declared `files_modified`) is a necessary, narrowly-scoped fix required by the plan's own must-have and is itself test-covered — not treated as a gap.

---

*Verified: 2026-07-15*
*Verifier: Claude (gsd-verifier)*
