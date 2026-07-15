# Quick Task 260715-lm1: Timer countdown threshold coloring — Context

**Gathered:** 2026-07-15
**Status:** Ready for planning
**Origin:** Decisions locked via `/gsd-discuss-phase` conversation (three gray areas resolved: metric basis, band shape, config coupling).

<domain>
## Task Boundary

Give the reset-timer countdowns (`⏰{reset_time}`) their **own** threshold-based color, driven by **time**, decoupled from the usage bar's color. Today (`progress.py` ~600 for 5h, ~617 for 7d) the timer text just inherits the bar's usage-severity color (`color_5h` / `color_7d`). This task makes the timer color a separate signal.

**In scope:** the color of the `⏰` countdown text only, across every style that renders it (classic/capsule/hairline) plus `cs preview`.
**Out of scope:** the bar fill/label coloring (unchanged), and the existing 5h countdown emoji ✨/⚡/🎉 (unchanged).
</domain>

<decisions>
## Implementation Decisions

### 1. Time metric basis (LOCKED)
- The timer color is computed from **elapsed % of the window** (not absolute time, not usage%).
- `elapsed_pct = (window_s − remaining_s) / window_s * 100`, where `remaining_s = resets_at − now`. **Clamp to [0, 100]**.
- Window lengths: 5h → `FIVE_HOUR_S` (5*3600); 7d → `SEVEN_DAY_S` (7*86400) (constants in `core.py` ~139–140).
- Equivalences: `elapsed ≥ 85%` ⟺ `remaining ≤ 15%`; `elapsed ≥ 65%` ⟺ `remaining ≤ 35%`.

### 2. Band shape & values (LOCKED)
- Full **three-color** band (green / yellow / red) — both ends light up; the color slides as the countdown shrinks.
- Cut points are the bar's **65 / 85** applied to elapsed%.
- **Color-to-band mapping differs per window** (this is the polarity flip):

  | Window | elapsed <65% | elapsed 65–85% | elapsed ≥85% |
  |---|---|---|---|
  | **5h** (FLIPPED) | 🔴 red | 🟡 yellow | 🟢 green |
  | **7d** (NORMAL)  | 🟢 green | 🟡 yellow | 🔴 red |

- Rationale: a short 5h countdown is GOOD (fresh quota imminent → green as `elapsed→100`); a short 7d countdown is BAD (→ red as `elapsed→100`). So within one dimension the timer color may now differ from the bar color.
- Concrete landing points:
  - **5h** (300 min): `>1h45m left` → red · `45m–1h45m` → yellow · `<45m left` → green.
  - **7d** (168h): `>2.45d left` → green · `1.05d–2.45d` → yellow · `<1.05d left` → red.

### 3. Config coupling (LOCKED — important)
- The timer uses **FIXED `65` / `85` constants** for ITS band. It must **NEVER** read the bar's configurable `warning_threshold` / `critical_threshold`.
- If the bar band is ever retuned (e.g. to 70/90), the timer **stays at 65/85**. This is what makes the timer threshold genuinely *separate* from the bar even though the numbers match today.
- Define the timer's cutoffs as their own module-level constants (do not alias the bar's threshold params/constants).

### Claude's Discretion
- Exact helper name/shape — recommended a single shared helper, e.g. `timer_severity_color(elapsed_pct, *, flip: bool, theme, use_color)` (or returning an rgb), reused by classic + capsule + hairline + preview. Mirror the Phase 6 pattern (one shared helper, byte-identical across styles) rather than parallel copies.
- Whether to thread `remaining_s` / `resets_at` / `window_s` vs a precomputed `elapsed_pct` (or the resolved color) into `format_status_line` and the style renderers — pick the cleanest threading that keeps preview and live in sync.
- Fallback color choice for the ill-defined cases below (recommended: keep the current/prior color, i.e. no behavior change).

### Edge cases (must handle, never crash)
- `resets_at` absent → `reset_time` is `"--"` / `""` → no elapsed% → keep the **current fallback color** (prior behavior), do not crash.
- Custom `reset_hour` mode (`calculate_reset_time`, fixed clock hour, not a rolling window) → elapsed% is ill-defined → fall back to prior/mute color.
- `elapsed > 100%` or negative `remaining_s` (stale / rollover) → clamp to [0, 100] before banding.
</decisions>

<specifics>
## Specific Ideas / Anchors

- `src/claude_statusbar/progress.py` → `format_status_line`: 5h timer colored at ~line 600 (`dim_5h += colorize(f"⏰{reset_time}{countdown_emoji}", color_5h, use_color)`), 7d at ~line 617 (`... reset_time_7d ..., color_7d`). Keep the bar fill/label on `color_5h`/`color_7d`; only the timer text gets the new color.
- Data source: `core.py` computes `resets_at` (~1325), `resets_at_7d` (~1326), `minutes_to_reset` (5h only, ~1342). No 7d remaining is currently passed to the renderer — thread both windows' remaining-time (or precomputed elapsed%/color) into `format_status_line`.
- Other styles: `src/claude_statusbar/styles.py` (capsule/hairline) and `preview.py` (`cs preview`) must render the timer color identically to classic for the same elapsed% — single shared helper.
- Precedent: quick task `260715-jbf` (the 65/85 bar-band standardization) — same class/scope, focused coloring change with atomic commit + tests.

## Tests (required)
- Band boundaries at `elapsed = 64 / 65 / 84 / 85 / 86` for **both** the flipped (5h) and normal (7d) mappings.
- Independence: timer color stays at fixed 65/85 even when the bar's `warning_threshold` / `critical_threshold` are customized.
- Edge cases: absent `resets_at`, custom `reset_hour`, and clamp of out-of-range elapsed all keep a sane (non-crashing) fallback color.
</specifics>

<canonical_refs>
## Canonical References

- `.planning/quick/260715-jbf-projection-off-and-standardize-threshold/` — precedent quick task (65/85 bar standardization); the four band constants + severity helpers in `progress.py` it introduced are the reuse target for the fixed-cutoff coloring logic.
- No external specs/ADRs — requirements fully captured in the decisions above.
</canonical_refs>
