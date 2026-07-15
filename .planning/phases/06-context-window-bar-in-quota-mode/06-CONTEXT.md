# Phase 6: Context Window Bar in Quota Mode - Context

**Gathered:** 2026-07-15
**Status:** Ready for planning
**Source:** PRD Express Path (docs/superpowers/specs/2026-07-15-context-bar-quota-mode-design.md)

<domain>
## Phase Boundary

Bring the existing **no-quota** context bar into **quota mode**. Today, when official
5h/7d quota data is present (the common case), the context window is shown only as a
`(523k/1M)` suffix on the model name plus the model-name color. In no-quota mode the
tool already renders context as a real bar (`ctx[███52%░░░░]` classic, `⛁ CTX 52%`
capsule, `› ctx █▃▁ 52%` hairline). This phase makes context render as a bar/segment in
quota mode **and** the session-start "waiting" state, across all three styles, gated by a
new `show_context` toggle (default on).

**In scope:** classic / capsule / hairline renderers, the two quota-mode render branches
in `core.py` (official-quota + waiting), a `show_context` config field, and `preview.py`.

**Out of scope:** JSON output for quota mode; the "keep token count" / "after model"
layout variants; the `cs-with-gsd` wrapper / GSD status-bar merge.
</domain>

<decisions>
## Implementation Decisions

### Layout (LOCKED)
- In quota mode, context renders as a bar/segment placed **between the 7d segment and the
  model**, in each style's own idiom.
- The `(used/size)` suffix is **dropped** from the model name when the bar is shown (the
  bar is the context readout now — same reasoning no-quota mode already uses).
- The **model name goes neutral** (theme ink) when the bar is shown; the bar carries the
  context severity. In capsule, the redundant model `●` context dot is also dropped.

### Severity band (LOCKED)
- Context severity uses the **context band**: yellow ≥ `CONTEXT_WARNING_THRESHOLD` (70),
  red ≥ `CONTEXT_CRITICAL_THRESHOLD` (85). NOT the 5h/7d comfort band. This matches the
  existing model-name coloring and the no-quota ctx bar. Reuse the constants in
  `progress.py`.

### Per-style segment (LOCKED — reuse existing no-quota rendering)
- classic: `ctx[███52%░░░░]` via `_build_dimension("ctx", …)` with `fill_rgb` on the
  context band.
- capsule: a `⛁ CTX 52% ●` pill (the same pill the no-quota branch builds), inserted
  after the 7D pill.
- hairline: a `› ctx █▃▁ 52%` segment (the same `mini3` segment), inserted after the 7d
  segment.
- Quota and no-quota modes must render the ctx segment **identically** per style.

### Control toggle (LOCKED)
- New boolean config field `show_context`, **default `True`**.
- ON → draw the ctx bar, drop the model `(k/M)` suffix, neutral model color.
- OFF → today's behavior byte-for-byte (suffix on model, model tinted by context band, no
  bar).
- Persisted/toggled via `cs config set show_context on|off`.

### Suffix source (LOCKED)
- The `(used/size)` suffix is currently appended in **core.py** (official-quota branch
  ~`core.py:1387`, waiting branch ~`core.py:1472`). When `show_context` is on, core must
  **not** append it (still strip any `(… context)` descriptor). The renderers receive a
  `show_context` flag and `ctx_pct` and draw the bar. This preserves opt-out and keeps
  existing tests/preview (which pass `ctx_pct` expecting NO bar) working when off.

### Claude's Discretion
- Exact kwarg name threaded into renderers (`show_context` recommended) and its default in
  the renderer signatures (default `False` so existing callers/tests are unchanged; core
  passes `show_context=cfg.show_context`).
- Whether to also thread `show_context` through the no-quota branch for uniformity (it has
  no suffix to drop; behavior unchanged either way).
- Whether to touch the classic `quota_stale` sub-branch (edge case) — optional, keep scope
  tight unless trivial.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design spec (authoritative)
- `docs/superpowers/specs/2026-07-15-context-bar-quota-mode-design.md` — the approved
  design: layout, toggle, per-style behavior, testing, edge cases.

### Source to modify
- `src/claude_statusbar/config.py` — `StatusbarConfig` dataclass, `from_dict` parse,
  `VALID_KEYS`, `_BOOL_KEYS`, `config show` display.
- `src/claude_statusbar/core.py` — official-quota branch (~1380–1387) and waiting branch
  (~1469–1472): stop appending suffix when `show_context`, pass `show_context` to
  `_render_style`. No-quota branch already draws the bar.
- `src/claude_statusbar/progress.py` — `format_status_line` (classic), `_build_dimension`,
  `CONTEXT_WARNING_THRESHOLD` / `CONTEXT_CRITICAL_THRESHOLD`.
- `src/claude_statusbar/styles.py` — `render_classic`, `render_capsule`, `render_hairline`.
- `src/claude_statusbar/preview.py` — thread `show_context`; gate the model-suffix build.

### Tests (mirror existing)
- `tests/test_no_quota_render.py`, `tests/test_styles.py`, `tests/test_progress.py` —
  patterns for asserting per-style ctx rendering.

### Codebase map
- `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONVENTIONS.md`,
  `.planning/codebase/TESTING.md` — render pipeline, style/theme separation, test layout.
</canonical_refs>

<specifics>
## Specific Ideas

Reference before/after (classic, tokyo-night):

```
BEFORE : 5h[███42%░░░░]⏰3h28m | 7d[██░18%░░░░]⏰5d12h | Opus 4.7(523k/1M)
AFTER  : 5h[███42%░░░░]⏰3h28m | 7d[██░18%░░░░]⏰5d12h | ctx[███52%░░░░] | Opus 4.7
```

Success Criteria (CTX-01/02/03):
1. **CTX-01** — In quota mode, context renders as a bar segment in each style's idiom (not
   just a suffix on the model name).
2. **CTX-02** — Context severity shows yellow at ≥70% and red at ≥85%.
3. **CTX-03** — The `show_context` toggle (default on) controls it; quota and no-quota
   modes render context identically. With the toggle OFF, output is unchanged from today.
</specifics>

<deferred>
## Deferred Ideas

- JSON output for quota mode (context is currently in no-quota JSON only) — unchanged.
- Alternative layouts: "keep token count next to bar" and "context after the model."
- `cs-with-gsd` wrapper / GSD status-bar merge — tracked separately.
</deferred>

---

*Phase: 06-context-window-bar-in-quota-mode*
*Context gathered: 2026-07-15 via PRD Express Path*
