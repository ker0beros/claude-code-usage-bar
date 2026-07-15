---
phase: 260715-ux9
plan: 01
subsystem: ui
tags: [statusline, rendering, search-credits, firecrawl, tavily]

requires:
  - phase: 260715-pic
    provides: fc/tv search-credit fuel-gauge bars (opt-in show_search_credits)
provides:
  - fc/tv search-credit bars render on their own dedicated row directly below the primary quota line, in all three styles (classic, capsule, hairline)
  - new format_search_credit_line() helper in progress.py, reusable across renderers
affects: [statusbar-rendering, search-credits]

tech-stack:
  added: []
  patterns:
    - "Row-below-primary-line pattern: a style renderer builds its complete primary line (including any line-1-only suffix like cache-age) first, then appends a secondary '\\n'-joined row using the style's own idiom (separator/spacer/sep), so ordering guarantees hold by construction rather than by careful interleaving."

key-files:
  created: []
  modified:
    - src/claude_statusbar/progress.py
    - src/claude_statusbar/styles.py
    - tests/test_provider_usage_render.py

key-decisions:
  - "format_status_line() no longer renders fc/tv inline in any branch (no_quota, quota_stale, normal); the search_credits parameter is retained on its signature for stability but is now inert there — the row is emitted by the style renderer via the new format_search_credit_line() helper."
  - "render_classic appends the credit row strictly AFTER the cache-age suffix is added to the primary line, guaranteeing cache-age always stays on line 1 regardless of future edits."
  - "render_capsule/render_hairline build the credit row BEFORE their final `_strip(line)` no-color call, so no-color mode strips the whole multi-line string together (no stray ANSI on the new row)."
  - "Each style reuses its OWN existing separator for the new row (classic ' | ', capsule spacer 'EDGE ╱ ', hairline sep '┊'), keeping the visual idiom consistent within a style."

requirements-completed: [UX9-01]

coverage:
  - id: D1
    description: "fc/tv search-credit bars render on their own row directly below the primary quota line in classic, capsule, and hairline"
    requirement: "UX9-01"
    verification:
      - kind: unit
        ref: "tests/test_provider_usage_render.py::test_classic_search_credit_battery_no_quota, test_classic_search_credit_battery_quota_mode, test_classic_search_credit_battery_stale_mode, test_capsule_search_credit_chip, test_hairline_search_credit_chip"
        status: pass
      - kind: manual_procedural
        ref: "cs preview --no-color --style {classic,capsule,hairline} --theme graphite"
        status: pass
    human_judgment: false
  - id: D2
    description: "Cache-age text stays on the primary line in classic style, never pushed onto the fc/tv row"
    requirement: "UX9-01"
    verification:
      - kind: unit
        ref: "tests/test_provider_usage_render.py::test_classic_cache_age_stays_on_quota_line"
        status: pass
    human_judgment: false
  - id: D3
    description: "Empty/None search_credits produces no extra line and no stray blank-line artifact, in every mode and style"
    requirement: "UX9-01"
    verification:
      - kind: unit
        ref: "tests/test_provider_usage_render.py::test_classic_empty_search_credits_renders_nothing, test_classic_none_search_credits_renders_nothing, test_capsule_empty_search_credits_renders_nothing, test_hairline_empty_search_credits_renders_nothing"
        status: pass
    human_judgment: false

metrics:
  duration: ~25min
  completed: 2026-07-15

status: complete
---

# Quick Task 260715-ux9: Move fc/tv search-credit bars onto their own row Summary

Moved the Firecrawl (`fc`)/Tavily (`tv`) search-credit fuel-gauge bars off the tail of the primary quota line onto a dedicated row directly below it, in classic, capsule, and hairline styles — each keeping its own idiom (bracket batteries, pills, chips).

## What Changed

**`src/claude_statusbar/progress.py`:**
- Added `format_search_credit_line(search_credits, theme=None, use_color=True)` — resolves the theme, calls the existing `_search_credit_parts()`, and joins the resulting parts with the same muted `" | "` separator the primary classic line uses. Returns `""` for a falsy/empty list so callers can append unconditionally.
- Removed the three `parts.extend(_search_credit_parts(...))` calls inside `format_status_line` (no_quota branch, quota_stale branch, normal branch). `format_status_line` no longer renders fc/tv inline in any branch.
- Kept the `search_credits` parameter on `format_status_line`'s signature (for stability) and added a docstring note that it is now inert there — fc/tv render via the style renderer instead.

**`src/claude_statusbar/styles.py`:**
- `render_classic`: dropped the inert `search_credits=search_credits` kwarg passed into `format_status_line(...)`. After the existing cache-age append block (and before `return result`), computes `credit_row = format_search_credit_line(search_credits, theme, use_color)` and appends `"\n" + credit_row` when truthy. Because this runs strictly after the cache-age suffix, cache-age is guaranteed to stay on the primary line.
- `render_capsule`: removed the inline fc/tv pill loop from the primary `parts` list. After `line = spacer.join(parts)` and the `bypass` append, and before the `if not use_color: return _strip(line)` guard, builds credit pills (`pill(_balance_fill_rgb(entry.get("pct"), theme), entry.get("text", ""))`) and appends `"\n" + spacer.join(credit_pills)` when non-empty — reusing the same spacer (`EDGE ╱ `) as the primary pills, and landing before `_strip` so no-color mode strips the whole multi-line string together.
- `render_hairline`: removed the inline fc/tv chip loop from `parts`. After `line = sep.join(parts)` and before the no-color guard, builds credit chips (`f"{_fg(_balance_fill_rgb(...))}{entry.get('text','')}{RESET}"`) and appends `"\n" + sep.join(credit_chips)` when non-empty, reusing the same `sep` (`┊`).
- No changes to `core.py` or `preview.py` — both already route through `styles.render`, so the new row appears automatically for both the live status line and `cs preview`.

**`tests/test_provider_usage_render.py`:**
- Converted the three classic battery tests (`test_classic_search_credit_battery_no_quota`, `_quota_mode`, `_stale_mode`) from calling `progress.format_status_line(...)` directly to calling `styles.render_classic(...)` — the real production path, since `format_status_line` no longer renders fc/tv inline. Added placement assertions in each (`first, _, rest = out.partition("\n"); assert "fc[" in rest and "fc[" not in first`).
- Converted the two "renders nothing" classic tests to `styles.render_classic(...)` and added `assert "\n" not in out` (proves no stray blank row).
- Added a new test `test_classic_cache_age_stays_on_quota_line` guarding the cache/credit-row interaction directly: cache-age text is asserted on the first line, `fc[` on the second, and `"cache"` is asserted absent from the second line.
- Extended `test_capsule_search_credit_chip` and `test_hairline_search_credit_chip` with the same placement assertion pattern (chip text on the row after the first newline, absent from the primary line).

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

- `tests/test_provider_usage_render.py`: 14 passed.
- `-k "search_credit or provider_usage or daemon_env"`: 70 passed, 972 deselected.
- Full suite (`pytest -q`): 1041 passed, 1 failed — `tests/test_version_sync.py::test_marketplace_and_plugin_versions_match_pyproject` (pre-existing, unrelated, acknowledged-deferred version-bump mismatch: `marketplace.json` 3.29.11 vs pyproject 3.30.0). No other regressions.

## Visual Verification

Ran `cs preview --no-color --style {classic,capsule,hairline} --theme graphite` against live cached data (fc/tv and cache-age render with real values from the local cache, not the demo dataset, since a real cache/env was present):

- **classic:** `... | Opus 4.8 | $ 14.21 | cache 55m06s` on line 1; `fc[███100%███] | tv[███100%███]` on line 2. Cache-age stayed on line 1; fc/tv landed cleanly on their own row with no blank line between.
- **capsule:** primary pill row (5H/7D/CTX/model/$/cache) on line 1; ` fc 100%  ╱  tv 100% ` pill row on line 2, same `╱` idiom.
- **hairline:** primary segment row (5h/7d/ctx/model/$/cache) on line 1; `fc 100% ┊ tv 100%` chip row on line 2, same `┊` idiom.

All three confirmed: fc/tv on their own row directly under the primary quota bar, cache-age text stays on the quota line, no stray blank-line artifact.

## Self-Check: PASSED

- FOUND: src/claude_statusbar/progress.py
- FOUND: src/claude_statusbar/styles.py
- FOUND: tests/test_provider_usage_render.py
- FOUND commit: ea46202
- FOUND commit: 1605f6b
