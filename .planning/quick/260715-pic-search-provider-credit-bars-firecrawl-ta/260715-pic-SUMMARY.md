---
phase: quick-260715-pic
plan: 01
subsystem: statusline-rendering
tags: [firecrawl, tavily, urllib, ttl-cache, opt-in, detached-prober, statusline]

requires:
  - phase: ip_risk.py + _ip_risk_refresh.py + daemon.py heartbeat
    provides: opt-in network-signal spawn discipline (ensure_fresh is the sole spawn path)
  - phase: balance_cache.py + _balance_refresh.py
    provides: fingerprinted TTL/negative-cache + inflight-lock mechanics
  - phase: progress._build_dimension + progress._balance_fill_rgb
    provides: reusable fuel-gauge battery renderer + remaining-% severity coloring
provides:
  - "provider_usage.py: PROVIDERS table, ensure_fresh(env), segments(env), fingerprint/cache/TTL helpers"
  - "_provider_usage_refresh.py: detached Firecrawl + Tavily prober, never raises"
  - "show_search_credits config toggle (default off), wired across config.py's 4 spots + cs config show"
  - "fc/tv mini fuel-gauge bars in classic style, severity-colored chips in capsule/hairline"
  - "core.main() search_kwargs spliced into all 4 _render_style() branches"
  - "daemon.run_forever heartbeat gated on show_search_credits"
  - "cs preview demo + best-effort live search_credits"
affects: [progress.py, styles.py, core.py, config.py, daemon.py, preview.py, cli.py]

tech-stack:
  added: []
  patterns:
    - "Detached-prober + TTL/negative-cache + inflight-lock (cloned from balance_cache.py verbatim, per-provider fingerprint bucketing)"
    - "ensure_fresh()-is-the-only-spawn-path discipline (cloned from ip_risk.py)"
    - "Opt-in toggle default off, gated identically in core.main() and daemon.run_forever heartbeat"

key-files:
  created:
    - src/claude_statusbar/provider_usage.py
    - src/claude_statusbar/_provider_usage_refresh.py
    - tests/test_provider_usage.py
    - tests/test_provider_usage_render.py
    - tests/test_config_search_credits.py
  modified:
    - src/claude_statusbar/config.py
    - src/claude_statusbar/core.py
    - src/claude_statusbar/progress.py
    - src/claude_statusbar/styles.py
    - src/claude_statusbar/preview.py
    - src/claude_statusbar/daemon.py
    - src/claude_statusbar/cli.py
    - CHANGELOG.md
    - .planning/STATE.md

key-decisions:
  - "Also added show_search_credits to cli.py's manual `cs config show` print list — not in the plan's files_modified, but required by the plan's own must-have ('the key appears in cs config show') and by test_config_show_lists_show_search_credits. show_context was already in that list; show_search_credits follows the same pattern."
  - "Daemon heartbeat reuses the existing IP_HEARTBEAT_S cadence (20s) rather than introducing a new interval constant — ensure_fresh() self-throttles via its own 300s/3600s TTL + 60s inflight lock, so firing the daemon check generously is cheap (mirrors show_ip_risk's heartbeat exactly)."
  - "preview.py's _real_data path adds a best-effort _real_search_credits() (reads provider_usage.segments(os.environ), never spawns) so cs preview matches the live status line when real env keys are present; falls back to None on any failure, matching the file's existing defensive style."

requirements-completed: [QT-260715-pic-search-credits]

coverage:
  - id: D1
    description: "Firecrawl + Tavily credit parsing (account-level + key-level Tavily fallback) computes correct remaining/limit/pct, clamped to [0,100]"
    requirement: QT-260715-pic-search-credits
    verification:
      - kind: unit
        ref: "tests/test_provider_usage.py::test_firecrawl_parse_computes_remaining_and_pct"
        status: pass
      - kind: unit
        ref: "tests/test_provider_usage.py::test_tavily_parse_account_level"
        status: pass
      - kind: unit
        ref: "tests/test_provider_usage.py::test_tavily_parse_key_level_fallback"
        status: pass
    human_judgment: false
  - id: D2
    description: "Omission holds: missing/zero limit, absent key, negative cache, or prober failure all omit the provider's bar silently (no --, no crash)"
    requirement: QT-260715-pic-search-credits
    verification:
      - kind: unit
        ref: "tests/test_provider_usage.py::test_firecrawl_missing_plan_credits_is_unsupported"
        status: pass
      - kind: unit
        ref: "tests/test_provider_usage.py::test_segments_both_keys_absent_returns_empty_even_with_cache"
        status: pass
      - kind: unit
        ref: "tests/test_provider_usage.py::test_fresh_negative_cache_entry_omitted_and_not_reprobed"
        status: pass
      - kind: unit
        ref: "tests/test_provider_usage.py::test_main_writes_negative_cache_on_probe_failure"
        status: pass
    human_judgment: false
  - id: D3
    description: "Render path (segments()) opens no socket and never spawns; ensure_fresh() is the sole spawn path and never raises"
    requirement: QT-260715-pic-search-credits
    verification:
      - kind: unit
        ref: "tests/test_provider_usage.py::test_segments_opens_no_socket"
        status: pass
      - kind: unit
        ref: "tests/test_provider_usage.py::test_segments_does_not_spawn_subprocess"
        status: pass
      - kind: unit
        ref: "tests/test_provider_usage.py::test_ensure_fresh_never_raises_on_popen_oserror"
        status: pass
    human_judgment: false
  - id: D4
    description: "fc/tv bars render across classic (fuel-gauge battery), capsule/hairline (severity-colored chips), and cs preview, in every quota mode"
    requirement: QT-260715-pic-search-credits
    verification:
      - kind: unit
        ref: "tests/test_provider_usage_render.py::test_classic_search_credit_battery_no_quota"
        status: pass
      - kind: unit
        ref: "tests/test_provider_usage_render.py::test_classic_search_credit_battery_quota_mode"
        status: pass
      - kind: unit
        ref: "tests/test_provider_usage_render.py::test_classic_search_credit_battery_stale_mode"
        status: pass
      - kind: unit
        ref: "tests/test_provider_usage_render.py::test_capsule_search_credit_chip"
        status: pass
      - kind: unit
        ref: "tests/test_provider_usage_render.py::test_hairline_search_credit_chip"
        status: pass
      - kind: unit
        ref: "tests/test_provider_usage_render.py::test_preview_output_contains_search_credit_text"
        status: pass
      - kind: manual_procedural
        ref: "manual cs preview run (uv run) — classic/capsule/hairline all showed fc[███82%] and tv[█18%]/tv 18% with correct green/warn coloring"
        status: pass
    human_judgment: false
  - id: D5
    description: "show_search_credits config toggle: default off, round-trips through set_value/load_config, lists in cs config show"
    requirement: QT-260715-pic-search-credits
    verification:
      - kind: unit
        ref: "tests/test_config_search_credits.py::test_default_off"
        status: pass
      - kind: unit
        ref: "tests/test_config_search_credits.py::test_set_and_load"
        status: pass
      - kind: unit
        ref: "tests/test_config_search_credits.py::test_config_show_lists_show_search_credits"
        status: pass
    human_judgment: false
  - id: D6
    description: "daemon.run_forever gates provider_usage.ensure_fresh behind cfg.show_search_credits — zero calls when off"
    requirement: QT-260715-pic-search-credits
    verification:
      - kind: unit
        ref: "tests/test_provider_usage.py::test_search_credits_heartbeat_gated_on_show_search_credits"
        status: pass
    human_judgment: false
  - id: D7
    description: "Fingerprint bucketing: sha1(name+key), raw key never written to the cache file"
    requirement: QT-260715-pic-search-credits
    verification:
      - kind: unit
        ref: "tests/test_provider_usage.py::test_written_cache_file_never_contains_raw_key"
        status: pass
      - kind: unit
        ref: "tests/test_provider_usage.py::test_prober_output_never_persists_raw_key"
        status: pass
    human_judgment: false

duration: ~55min
completed: 2026-07-15
status: complete
---

# Quick Task 260715-pic: Search-Provider Credit Bars (Firecrawl + Tavily) Summary

**Opt-in `fc`/`tv` fuel-gauge credit bars for Firecrawl and Tavily, cloning the ip_risk opt-in-spawn pattern fused with balance_cache's TTL/negative-cache mechanics — render path stays stdlib-only and network-free.**

## Performance

- **Duration:** ~55 min
- **Completed:** 2026-07-15T10:43:00Z
- **Tasks:** 3/3
- **Files modified:** 9 (2 new modules, 7 modified; 3 new test files, 2 test files appended)

## Accomplishments

- New `provider_usage.py` + `_provider_usage_refresh.py`: Firecrawl (`GET /v2/team/credit-usage`) and Tavily (`GET /usage`, account-level with key-level fallback) credit probing, TTL 300s positive / 3600s negative, inflight lock, fingerprint bucketing (`sha1(name+key)`, raw key never on disk).
- `show_search_credits` config toggle (default off) wired through all four `config.py` spots plus `cs config show`.
- `fc`/`tv` mini fuel-gauge bars render in classic style (reusing `_build_dimension` + `_balance_fill_rgb`, identical construction to the relay `bal[...]` battery) and as severity-colored text chips in capsule/hairline — spliced into all three `format_status_line` branches and all four `core.main()` `_render_style()` calls.
- `daemon.run_forever` heartbeat gated on `show_search_credits`, sharing the IP-risk heartbeat cadence — default users make zero Firecrawl/Tavily calls.
- `cs preview` shows demo `fc 82%` / `tv 18%` data plus a best-effort live read via `provider_usage.segments(os.environ)`.
- 52 new tests across 3 files covering parsing, omission, prober fail-safe, cache TTL/inflight semantics, render-path socket isolation, edge cases, config round-trip, and rendering in all 3 styles + preview.
- Manually verified end-to-end with `uv run` (`cs config show`, `cs preview` classic/capsule/hairline) — bars render with correct green (82% remaining) / amber (18% remaining, ≤25% threshold) coloring.

## Task Commits

Each task was committed atomically (CODE only — `src/**`, `tests/**`, `CHANGELOG.md`; `.planning/STATE.md` and this SUMMARY are left for the orchestrator's docs commit per constraints):

1. **Task 1: provider_usage module + detached prober + cache/parse unit tests** - `3640e0e` (feat)
2. **Task 2: config toggle + core.main() wiring (all 4 render branches) + classic/capsule/hairline/preview rendering** - `3dee232` (feat)
3. **Task 3: daemon heartbeat + render-path isolation & edge-case tests + CHANGELOG + STATE deferred note** - `9265e55` (feat)

## Files Created/Modified

- `src/claude_statusbar/provider_usage.py` - PROVIDERS table, TTL/negative-cache/fingerprint/inflight helpers, `ensure_fresh(env)` (sole spawn path), `segments(env)` (render-path read, never spawns)
- `src/claude_statusbar/_provider_usage_refresh.py` - detached prober: `_get_json`, `_probe_firecrawl`, `_probe_tavily`, `main()` (never raises, always exits 0)
- `src/claude_statusbar/config.py` - `show_search_credits: bool = False` dataclass field + `load_config()` mapping + `VALID_KEYS` + `_BOOL_KEYS`
- `src/claude_statusbar/cli.py` - added `show_search_credits` line to `cs config show`'s manual print list (deviation, see below)
- `src/claude_statusbar/core.py` - gated `search_kwargs` block (`ensure_fresh` + `segments`), spliced `**search_kwargs` into all 4 `_render_style()` calls
- `src/claude_statusbar/progress.py` - `_search_credit_parts()` helper, `search_credits=None` param on `format_status_line`, spliced into all 3 return branches (no_quota, quota_stale, main)
- `src/claude_statusbar/styles.py` - `render_classic` forwards `search_credits`; `render_capsule`/`render_hairline` render severity-colored `fc NN%`/`tv NN%` chips
- `src/claude_statusbar/preview.py` - demo `search_credits` in `_demo_data`, best-effort `_real_search_credits()` in `_real_data`, passed into both `render(...)` calls
- `src/claude_statusbar/daemon.py` - `run_forever` heartbeat gated on `cfg.show_search_credits`, sharing the `IP_HEARTBEAT_S` cadence
- `CHANGELOG.md` - Unreleased entry
- `tests/test_provider_usage.py` (new, 37 tests) - parsing, omission, prober fail-safe, cache/TTL, fingerprint/no-raw-key, `ensure_fresh` spawn discipline, render-path socket isolation, edge cases, daemon-gate mirror
- `tests/test_provider_usage_render.py` (new, 12 tests) - classic/capsule/hairline rendering, preview smoke test
- `tests/test_config_search_credits.py` (new, 3 tests) - default off, round-trip, `cs config show` listing

## Decisions Made

- Added `show_search_credits` to `cli.py`'s `cs config show` manual print list even though `cli.py` wasn't in the plan's `files_modified` frontmatter — the plan's own must-have ("the key appears in `cs config show`") and its own `test_config_search_credits.py` spec require it, and `show_context` was already precedent in that same list. Documented as a Rule 2 (missing critical functionality) deviation.
- Daemon heartbeat reuses `IP_HEARTBEAT_S` (20s) rather than a new interval — `ensure_fresh()` self-throttles via its own TTL/inflight gate, so firing generously is free, and it keeps the daemon.py diff minimal and consistent with the existing `show_ip_risk` heartbeat.
- `preview.py`'s live-data path adds a best-effort `_real_search_credits()` (optional per plan) so `cs preview` mirrors the live status line exactly when the user has real Firecrawl/Tavily keys set; falls back to `None` on any failure.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `show_search_credits` to `cs config show`'s print list in `cli.py`**
- **Found during:** Task 2 (writing `test_config_search_credits.py`)
- **Issue:** The plan's `files_modified` frontmatter didn't list `cli.py`, but `cs config show` is implemented as a hand-maintained print list (not an auto-derived `asdict(cfg)` dump) that already omits several existing toggles (`show_ip_risk`, `show_fp_risk`, `show_cwd`, `api_mode` — a pre-existing, out-of-scope gap). Without adding the line, the plan's own must-have ("the key appears in `cs config show`") and behavior spec would be unmet.
- **Fix:** Added `print(f"show_search_credits = {cfg.show_search_credits}")` next to the existing `show_context` line, following the established pattern.
- **Files modified:** `src/claude_statusbar/cli.py`
- **Verification:** `test_config_show_lists_show_search_credits` passes.
- **Committed in:** `3dee232` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical functionality)
**Impact on plan:** Necessary for the plan's own acceptance criteria to hold. No scope creep — pre-existing gaps for `show_ip_risk`/`show_fp_risk`/`show_cwd`/`api_mode` in the same print list were left untouched (out of this task's scope; not caused by this task's changes).

## Issues Encountered

None. The plan's clone-target references (`ip_risk.py`, `_ip_risk_refresh.py`, `balance_cache.py`, `_balance_refresh.py`) mapped cleanly onto the new modules with no structural surprises. One pre-existing test data source (`~/.cache/claude-statusbar/last_stdin.json` present on this dev machine) meant the `cs preview` smoke test needed to monkeypatch `_real_data` to force demo data — matched the existing `test_preview_classic_varies_by_theme` precedent for this exact situation.

## User Setup Required

None — the feature is opt-in and self-hides. Users who want it run `cs config set show_search_credits on` and set `FIRECRAWL_API_KEY` / `TAVILY_API_KEY` in their shell env; no dashboard configuration or code changes needed.

## Next Phase Readiness

- Exa (no remaining-balance API) and a Firecrawl `billingPeriodEnd` reset-countdown are recorded as deferred items in `.planning/STATE.md`'s Deferred Items table — no blockers for either, just future quick tasks if wanted.
- Full test suite is green: 1021 passed (pre-existing, unrelated `test_version_sync.py::test_marketplace_and_plugin_versions_match_pyproject` v3.30.0 marketplace-drift failure deselected, as instructed).

---
*Phase: quick-260715-pic*
*Completed: 2026-07-15*

## Self-Check: PASSED

All created files verified present on disk; all three task commit hashes (`3640e0e`, `3dee232`, `9265e55`) verified present in `git log --oneline --all`.
