---
phase: 260715-jbf-projection-off-and-standardize-threshold
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/claude_statusbar/config.py
  - src/claude_statusbar/progress.py
  - src/claude_statusbar/styles.py
  - src/claude_statusbar/preview.py
  - src/claude_statusbar/cli.py
  - tests/test_config_projection.py
  - tests/test_config_forecast.py
  - tests/test_threshold_resolution.py
  - tests/test_progress.py
  - tests/test_projection_coloring.py
  - tests/test_per_segment_colors.py
  - tests/test_config.py
  - tests/test_context_bar_render.py
  - tests/test_no_quota_render.py
  - README.md
  - CHANGELOG.md
autonomous: true
requirements: [D-01, D-02, D-03, D-04, D-05, D-06]

must_haves:
  truths:
    - "Default render (no user config) on 5h/7d/ctx bars shows no →NN% projection chip and no ⚠~ETA forecast chip."
    - "Each usage bar (5h, 7d, ctx) colors on one shared band: green <65, yellow 65–84, red ≥85 (inclusive lower edge)."
    - "cs config set show_projection on re-adds →NN%; show_forecast on re-adds ⚠~ETA — both toggles and predict.py stay intact."
    - "Full suite passes: uv run --with pytest -m pytest -q (no tests removed)."
  artifacts:
    - "src/claude_statusbar/config.py — show_forecast/show_projection dataclass defaults and from_dict fallbacks all False."
    - "src/claude_statusbar/progress.py — DEFAULT_WARNING=65.0, DEFAULT_CRITICAL=85.0, CONTEXT_WARNING=65.0, PROJECTION_WARNING=65.0."
    - "src/claude_statusbar/styles.py, preview.py, cli.py — out-of-band caller/help defaults aligned to 65/85."
    - "CHANGELOG.md — new entry documenting default-off + 65/85 standardization."
  key_links:
    - "cfg.show_projection/show_forecast (False) → core.py gates in main() (~1393–1422) → neither chip computed; empty projection → window_severity_rgb falls back to current-usage coloring on the 65/85 band."
    - "progress.py band constants → color_for_percent / window_severity_rgb / normalize_thresholds (reused, unchanged logic) → all three bars share the identical band."
    - "predict.py and the show_projection/show_forecast toggles remain — feature is disabled by default, not removed."
---

<objective>
Ship the repo's new defaults: projection (→NN%) and forecast (⚠~ETA) are default-OFF via config only, and all three usage bars (5h/7d/ctx) standardize to a single color band — green <65, yellow 65–84, red ≥85. This is a cohesive defaults change; no feature code is removed and no new coloring logic is written.

Implements locked decisions D-01 (default-off via config), D-02 (four progress.py band constants), D-03 (out-of-band caller/help alignment), D-04 (reuse existing severity helpers only), D-05 (test assertions encode old bands/defaults — update first, TDD), D-06 (docs).

Purpose: A calmer, consistent status bar colored by each segment's own current fill, with both predictive signals still fully available via `cs config set`.
Output: Flipped config defaults, retuned band constants, aligned callers/help/docs, and a green test suite.
</objective>

<execution_context>
@$HOME/.claude-account1/gsd-core/workflows/execute-plan.md
@$HOME/.claude-account1/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@AGENTS.md

# The approved, authoritative plan — implement exactly this
@/Users/khairulazmi/.claude-account1/plans/for-this-repo-default-vivid-zebra.md

# Source under change (current state already confirmed by planner)
@src/claude_statusbar/config.py
@src/claude_statusbar/progress.py
@src/claude_statusbar/styles.py
@src/claude_statusbar/preview.py
@src/claude_statusbar/cli.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Flip projection & forecast to default-off (config only) — D-01, D-05</name>
  <files>tests/test_config_projection.py, tests/test_config_forecast.py, src/claude_statusbar/config.py</files>
  <behavior>
    - StatusbarConfig().show_projection is False (was True).
    - StatusbarConfig().show_forecast is False (was True).
    - load_config on a config file missing both keys resolves both to False (absent key → off).
    - The explicit set_and_load toggle tests (set to "false" then load) continue to pass unchanged.
  </behavior>
  <action>
    RED first — update the default assertions so they encode the new off-by-default behavior:
    - tests/test_config_projection.py line 5: change the default assertion from show_projection is True to show_projection is False (rename the test to test_default_off if it is named test_default_on; keep the set_and_load test intact).
    - tests/test_config_forecast.py line 5 (test_default_on): change show_forecast is True to show_forecast is False (rename to test_default_off is fine).
    Run the two files and confirm they now FAIL against current source.

    GREEN — flip the config defaults per D-01, config only, keeping predict.py and both toggles fully intact:
    - src/claude_statusbar/config.py: the show_forecast dataclass default (~line 91) True to False; refresh its adjacent comment so it reads default-off.
    - the show_projection dataclass default (~line 94) True to False; refresh its adjacent comment so it reads default-off.
    - from_dict/load_config fallbacks (~lines 159–160): change the raw.get("show_forecast", ...) and raw.get("show_projection", ...) default-argument fallbacks from the truthy default to False, so an absent key resolves to off.
    Do NOT touch predict.py, core.py gating, or the show_context default (stays True). Rerun the two files → GREEN.
  </action>
  <verify>
    <automated>uv run --with pytest -m pytest tests/test_config_projection.py tests/test_config_forecast.py -q</automated>
  </verify>
  <done>Both default assertions expect False and pass; config.py dataclass defaults and from_dict fallbacks for show_forecast and show_projection are all False; predict.py and the toggles are unchanged.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Standardize the four band constants to 65/85 + retune band tests — D-02, D-04, D-05</name>
  <files>src/claude_statusbar/progress.py, tests/test_threshold_resolution.py, tests/test_progress.py, tests/test_projection_coloring.py, tests/test_per_segment_colors.py, tests/test_config.py</files>
  <behavior>
    - New band everywhere: green <65, yellow [65,85), red >=85 (inclusive at the lower edge), via the reused _severity_color / color_for_percent / window_severity_rgb / normalize_thresholds helpers — no new coloring logic (D-04).
    - color_for_percent: 20 green, 50 green, 64 green, 65 yellow, 80 yellow, 84 yellow, 85 red.
    - Unset thresholds resolve to warning 65 / critical 85.
    - PROJECTION_WARNING_THRESHOLD == 65.0; PROJECTION_CRITICAL_THRESHOLD stays 85.0.
    - window_severity_rgb fallback (empty "→--" projection, current-usage coloring): 75 → s_warn, 30 → s_ok, 10 → s_ok.
    - set_value cross-field validation still rejects invalid pairs against the new 65/85 defaults.
  </behavior>
  <action>
    RED first — update the assertions that encode the old 30/70 bands and defaults (D-05):
    - tests/test_threshold_resolution.py (~72–75, test_default_thresholds_when_unset): expected warn to 65.0 and crit to 85.0.
    - tests/test_progress.py (~47–60): test_color_warning (input 50) now expects GREEN_FG (was YELLOW_FG); test_color_critical (input 80) now expects YELLOW_FG (was RED_FG); retarget the two boundary tests off the old edges to the new edges — one asserting color_for_percent(65) == YELLOW_FG plus color_for_percent(64) == GREEN_FG, and one asserting color_for_percent(85) == RED_FG plus color_for_percent(84) == YELLOW_FG (rename the boundary tests to match). Leave the input-20 green test and the explicit custom-threshold (40/80) test unchanged. Also refresh any stale ctx-band prose comment in this file to the new band.
    - tests/test_projection_coloring.py: the PROJECTION_WARNING assertion (~71–73) to 65.0, keeping PROJECTION_CRITICAL at 85.0 (rename test_projection_thresholds_are_70_85 accordingly). Fallback block (~77–81): window_severity_rgb(75, "→--", THEME) now expects THEME.s_warn (was s_hot); window_severity_rgb(30, "→--", THEME) now expects THEME.s_ok (was s_warn); the input-10 s_ok case stays. Update the inline comments to the 65/85 band.
    - tests/test_per_segment_colors.py (~22–35): the weekly_pct=50 fixture now colors green, which breaks warn-isolation; bump weekly_pct to 70 so the 7d segment still lands in the new yellow band (assert s_warn in the 7d chunk, s_ok/mute unchanged). Update the docstring wording.
    - tests/test_config.py cross-field validation — rework for the new 65/85 defaults, not just number tweaks:
      • test_set_warning_above_default_critical_rejected: warning=80 is now valid (80 < default critical 85), so use a value >=85 (e.g. 90) that is still rejected; fix the docstring so it describes 65/85 defaults, not 30/70.
      • test_set_critical_below_warning_rejected: the current first step (critical=60) now raises immediately because default warning is 65; rework the sequence to preserve intent — set warning=50 first (50 < 85 OK), then expect critical=40 to raise (50 < 40 invalid).
      • test_thresholds_can_be_widened_in_correct_order (90/80) still passes; refresh only its stale "30 <" comment to reflect the 65 default.
    Run the five files → they FAIL against current constants.

    GREEN — retune only the four usage-band constants at the top of src/claude_statusbar/progress.py per D-02:
    - DEFAULT_WARNING_THRESHOLD (line 14) to 65.0.
    - DEFAULT_CRITICAL_THRESHOLD (line 15) to 85.0.
    - PROJECTION_WARNING_THRESHOLD (line 26) to 65.0.
    - CONTEXT_WARNING_THRESHOLD (line 33) to 65.0.
    Leave PROJECTION_CRITICAL_THRESHOLD (85) and CONTEXT_CRITICAL_THRESHOLD (85) as-is; leave BALANCE_LOW/BALANCE_CRITICAL and _cache_severity untouched. Refresh the surrounding constant comments so they describe the unified 65/85 band. Write NO new severity/coloring code — reuse the existing helpers (D-04). normalize_thresholds' 0 <= warning < critical <= 100 invariant still holds (65 < 85). Rerun the five files → GREEN.
  </action>
  <verify>
    <automated>uv run --with pytest -m pytest tests/test_progress.py tests/test_threshold_resolution.py tests/test_config.py tests/test_projection_coloring.py tests/test_per_segment_colors.py -q</automated>
  </verify>
  <done>progress.py exposes DEFAULT_WARNING=65.0, DEFAULT_CRITICAL=85.0, PROJECTION_WARNING=65.0, CONTEXT_WARNING=65.0 with the two criticals still 85 and BALANCE_*/_cache_severity unchanged; all five retuned test files pass; no new coloring logic was added.</done>
</task>

<task type="auto">
  <name>Task 3: Align out-of-band caller/help defaults + docs — D-03, D-06</name>
  <files>src/claude_statusbar/styles.py, src/claude_statusbar/preview.py, src/claude_statusbar/cli.py, tests/test_context_bar_render.py, tests/test_no_quota_render.py, README.md, CHANGELOG.md</files>
  <action>
    Align the callers so nothing outside the normal render path misreports the band (D-03) — mechanical signature/string swaps, no logic change:
    - src/claude_statusbar/styles.py: the warning_threshold / critical_threshold signature defaults on render_capsule, render_hairline, render_classic (lines 123, 248, 368) to 65.0 / 85.0.
    - src/claude_statusbar/preview.py: the hardcoded warning_threshold / critical_threshold passed into both render(...) call sites (lines 199, 216) to 65.0 / 85.0, so cs preview reflects the new band.
    - src/claude_statusbar/cli.py: the --warning-threshold help text (line 413) default to 65 and the --critical-threshold help text (line 418) default to 85.

    Comment-only test prose refreshes (behavior already passes; wording says the old band) per D-05:
    - tests/test_context_bar_render.py and tests/test_no_quota_render.py: change any "70/85" band prose in comments/docstrings to "65/85". Do not change any assertion values here.

    Docs (D-06):
    - README.md: the 5h/7d threshold line (~111) "30% / 70%" to "65% / 85%"; the context-bar line (~344) "70% / 85%" to "65% / 85%"; the show_projection default (~322) true to false and note show_forecast is now false too; the projection "on by default" blurbs (~67, ~98, ~99) to off-by-default; the headline example strings (~17, ~86) that render →NN% chips — drop the projection chips so the example matches default output.
    - CHANGELOG.md: add a NEW top entry (do not rewrite existing history) noting projection & forecast are now default-off and the usage-bar color band is standardized to 65/85, with the note that both signals remain available via cs config set show_projection|show_forecast on. Leave the pyproject.toml version bump to release time (out of scope here).
  </action>
  <verify>
    <automated>grep -q "warning_threshold=65.0, critical_threshold=85.0" src/claude_statusbar/styles.py && grep -q "warning_threshold=65.0, critical_threshold=85.0" src/claude_statusbar/preview.py && grep -q "default: 65" src/claude_statusbar/cli.py && grep -q "default: 85" src/claude_statusbar/cli.py && uv run --with pytest -m pytest tests/test_context_bar_render.py tests/test_no_quota_render.py -q</automated>
  </verify>
  <done>styles.py and preview.py callers pass 65.0/85.0; cli.py --help shows default 65 / 85; the two comment-refreshed test files still pass; README reflects the 65/85 band, off-by-default projection/forecast, and chip-free example strings; a new CHANGELOG entry is added without rewriting history.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| user config file → render path | `~/.config`/config JSON is user-owned local input; already parsed defensively by load_config (garbage → defaults). This change only alters default values, adds no new parse surface. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-jbf-01 | Tampering | progress.py band constants | low | accept | Values are compile-time literals with the `0 <= warning < critical <= 100` invariant enforced by normalize_thresholds (65 < 85 holds); no external input sets them. |
| T-jbf-02 | Information Disclosure | config default flip | low | accept | Flipping show_projection/show_forecast to False only hides derived UI chips; discloses nothing new. No secrets touched. |
| T-jbf-SC | Tampering | npm/pip/cargo installs | low | accept | No new project dependencies added; render path stays stdlib-only. `uv run --with pytest` pulls pytest transiently for the test run only, not into the shipped package. |
</threat_model>

<verification>
1. Full suite green (nothing removed): `uv run --with pytest -m pytest -q`.
2. Constants landed: `grep -q "DEFAULT_WARNING_THRESHOLD = 65.0" src/claude_statusbar/progress.py && grep -q "DEFAULT_CRITICAL_THRESHOLD = 85.0" src/claude_statusbar/progress.py && grep -q "PROJECTION_WARNING_THRESHOLD = 65.0" src/claude_statusbar/progress.py && grep -q "CONTEXT_WARNING_THRESHOLD = 65.0" src/claude_statusbar/progress.py`.
3. Defaults off: `grep -q "show_forecast: bool = False" src/claude_statusbar/config.py && grep -q "show_projection: bool = False" src/claude_statusbar/config.py`.
4. Feature preserved (not removed): `test -f src/claude_statusbar/predict.py` and `grep -q "show_projection" src/claude_statusbar/config.py` (toggle still present).
5. Optional live check (manual, this editable-installed session): `cs daemon stop && cs daemon start`, then render last_stdin and confirm the bar shows no `→NN%` projection and no `⚠~ETA`, with 5h/7d/ctx colored on the 65/85 band; `cs preview` reflects the new band; `cs config set show_projection on` re-adds the chip and `off` removes it.
</verification>

<success_criteria>
- Default status bar carries no `→NN%` projection chip and no `⚠~ETA` forecast chip; all three usage bars color on the single green<65 / yellow 65–84 / red≥85 band.
- predict.py and the show_projection/show_forecast toggles remain; both signals re-enable via `cs config set ... on`.
- `uv run --with pytest -m pytest -q` passes with no tests removed.
- README and CHANGELOG reflect the new defaults and band.
</success_criteria>

<output>
Create `.planning/quick/260715-jbf-projection-off-and-standardize-threshold/260715-jbf-SUMMARY.md` when done.
</output>
