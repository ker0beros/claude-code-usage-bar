# Phase 10: GSD Phase & Wave Indicator — Specification

**Created:** 2026-07-16
**Ambiguity score:** 0.10 (gate: ≤ 0.20)
**Requirements:** 5 locked

## Goal

In any directory containing a GSD `.planning/STATE.md`, the status bar auto-renders a dedicated
`gsd` line showing the current phase as `{current_phase}/{total_phases}` and — while the phase is
executing — per-plan progress as `●`/`○` circles grouped by wave and colored by wave state.

## Background

The Claude Status Bar (this project) renders rate-limit / model / cache / context / cost plus an
optional second line (git branch + AgentParty), but has no awareness of GSD workflow state. The
maintainer builds with GSD (phases → plans grouped into waves) and wants at-a-glance phase/wave
progress while running `gsd-execute-phase`. GSD state lives locally in `.planning/`: `STATE.md`
frontmatter carries `current_phase`, `current_phase_name`, `status`, and `progress.total_phases`;
each phase dir holds `{NN}-{PP}-PLAN.md` files with a `wave:` frontmatter field, and a plan is
done when its sibling `{NN}-{PP}-SUMMARY.md` exists. The closest existing analog is `party.py` /
`render_party_line`, which reads a local cache and renders a `None`-gated line. No GSD reader,
renderer, or line exists today.

## Requirements

1. **GSD state reader**: A pure-filesystem module reads local GSD state and returns a status object
   or `None`.
   - Current: no module reads `.planning/`; the status bar has zero GSD awareness.
   - Target: `planning.read_planning_status(cwd)` parses `.planning/STATE.md` frontmatter and, when
     executing, the current phase's `*-PLAN.md` files (wave) + `*-SUMMARY.md` presence (done);
     returns a frozen `PlanningStatus`, or `None` when `.planning/STATE.md` is absent. No network,
     no subprocess.
   - Acceptance: given a fake `.planning/` tree, the reader returns correct phase numbers, state,
     and per-wave done-flags; returns `None` when `.planning/STATE.md` is missing.

2. **Phase text (Option A)**: The line shows the current phase as `N/total`.
   - Current: no phase display exists.
   - Target: renders `gsd {current_phase}/{progress.total_phases}` (e.g. `gsd 6/9`).
   - Acceptance: with `current_phase: 6`, `progress.total_phases: 9`, the rendered line contains
     `gsd 6/9`.

3. **Wave/plan circles (Option B, executing)**: During execution, one circle per plan in the
   current phase, grouped by wave, colored by wave state.
   - Current: no progress display exists.
   - Target: `●` = plan done, `○` = pending; groups (waves) separated by a space; color = green
     (`theme.s_ok`, completed wave) / yellow (`theme.s_warn`, active wave = lowest wave with a
     pending plan) / grey (`theme.mute`, future wave). Reuses the `●`/`○` glyph idiom from
     `render_party_line`.
   - Acceptance: for a phase with wave 1 = 2 done, wave 2 = 1 pending and status executing, the
     rendered (no-color) line is `gsd 6/9 ●● ○`; colors resolve from the active theme, not
     hardcoded RGB.

4. **Idle/complete form**: When not executing, the line shows phase + a status word, no circles.
   - Current: n/a.
   - Target: `gsd {N}/{total} {word}` where `{word}` is derived from `status` by lowercase
     substring (`complete`/`done` → `done`; `plan`/`discuss`/`verif`/`paus` → that word; else
     `idle`).
   - Acceptance: with `status: phase-complete`, the rendered line is `gsd 6/9 done` and contains no
     `●`/`○`.

5. **Auto-show gate + own line, no regression**: The line auto-appears only in GSD projects, on its
   own dedicated line, and changes nothing elsewhere.
   - Current: n/a.
   - Target: `core.main()` builds `planning_kwargs` only when the reader returns non-`None`
     (wrapped in try/except); the renderer appends the line via `out = out + "\n" + line` after the
     identity/cwd block (line 3 with branch line on, line 2 without). No config field. All three
     styles (classic/capsule/hairline) render it.
   - Acceptance: in a dir with `.planning/`, the `gsd` line appears; in a dir without `.planning/`,
     rendered output is byte-for-byte identical to pre-phase behavior (no line, no stray newline).

## Boundaries

**In scope:**
- New `src/claude_statusbar/planning.py` reader (STATE.md frontmatter + wave/plan derivation).
- `render_planning_line` in `styles.py` + dispatcher pop/append.
- Auto-show gate in `core.py` + the four `render(...)` splat sites.
- Tests: reader, renderer, and core auto-show seam (incl. the no-`.planning/` regression guard).

**Out of scope:**
- GSD **quick tasks** (`.planning/quick/…`) — they don't move `current_phase`; excluded to keep
  the indicator unambiguous.
- Any **config toggle / opt-out** — the maintainer chose auto-show; a toggle can be added later via
  the 5-site `show_context` pattern if needed.
- **Right-alignment on line 1** — proven infeasible under Claude Code (no terminal width at render
  time); replaced by own-line-always.
- Multi-milestone / cross-project GSD state, ROADMAP parsing, and any GSD command invocation.

## Constraints

- Reader is pure filesystem, no network/subprocess; must not raise into the render path (guarded,
  returns `None`/empty on any error) — a malformed `.planning/` must never break the status line.
- Must stay within the render budget: read only STATE.md frontmatter + the current phase's small
  PLAN.md frontmatters + `SUMMARY.md` existence checks (a handful of small reads).
- Colors sourced from the active theme palette (`theme.s_ok` / `s_warn` / `mute`), never hardcoded.
- No new third-party dependency (no YAML lib) — parse the frontmatter block directly.
- Terminal width is unavailable at render time under Claude Code — no feature may depend on it.

## Acceptance Criteria

- [ ] `read_planning_status(cwd)` returns `None` when `.planning/STATE.md` is absent.
- [ ] Rendered line contains `gsd {current_phase}/{total_phases}`.
- [ ] Executing + mixed waves → `gsd 6/9 ●● ○` (no-color), circles grouped by wave.
- [ ] Circle colors resolve from the active theme (green/yellow/grey by wave state).
- [ ] `status: phase-complete` → `gsd 6/9 done`, no circles.
- [ ] Line renders on its own row (line 3 with branch on / line 2 without) in all three styles.
- [ ] No `.planning/` present → rendered output byte-for-byte unchanged.
- [ ] Full test suite passes including new reader/renderer/seam tests.

## Edge Coverage

**Coverage:** 5/5 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| empty/absent input | R1 | ✅ covered | No `.planning/STATE.md` → reader returns `None` → no line (AC1, AC7) |
| malformed input | R1 | ✅ covered | Unparseable STATE.md / partial frontmatter → reader returns `None`; core gate try/excepts |
| boundary: no plans yet | R3 | ✅ covered | Phase dir has no `*-PLAN.md` → `waves=()` → executing shows `gsd N/total` with no circles |
| state classification | R4 | ✅ covered | Free-form `status` slug classified by lowercase substring (mirrors `normalizeStateStatus`) |
| all-done / project end | R3 | ✅ covered | All plans done in a wave → green `●`; `completed_phases == total_phases` still renders `N/total` |

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT raise into the render path on any malformed/absent `.planning/` file | R1, R5 | resolved | verification: test — reader wrapped in try/except returns `None`; core gate try/excepts |
| MUST NOT alter rendered output when no `.planning/` is present | R5 | resolved | verification: test — byte-for-byte-unchanged regression assertion |
| MUST NOT perform any network call or subprocess / invoke GSD commands | R1 | resolved | verification: judgment — pure filesystem reads only (mirrors `party.py` contract) |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                             |
|--------------------|-------|------|--------|---------------------------------------------------|
| Goal Clarity       | 0.92  | 0.75 | ✓      | Exact format + data source locked                 |
| Boundary Clarity   | 0.90  | 0.70 | ✓      | Explicit out-of-scope (quick tasks, toggle, right-align) |
| Constraint Clarity | 0.85  | 0.65 | ✓      | Pure-fs, no-dep, budget, theme-color              |
| Acceptance Criteria| 0.88  | 0.70 | ✓      | 8 pass/fail criteria                              |
| **Ambiguity**      | 0.10  | ≤0.20| ✓      |                                                   |

## Interview Log

| Round | Perspective     | Question summary              | Decision locked                                    |
|-------|-----------------|-------------------------------|----------------------------------------------------|
| 1     | Researcher      | What to show?                 | Phase + wave + progress                            |
| 1     | Boundary Keeper | Placement?                    | Line 1 right-aligned → **changed to own-line** after width proven infeasible |
| 2     | Simplifier      | Gating / when shown?          | Auto-show, no toggle; phase + status word when idle |
| 2     | Failure Analyst | Fallback when width unknown?  | Own new line (became the sole placement)           |
| 3     | Boundary Keeper | Styles / quick tasks?         | Own circle visual (all styles); phases only        |
| 3     | Seed Closer     | Circle meaning + colors?      | `●`/`○` glyphs; A=phase text, B=wave/plan circles; green/yellow/grey by wave |

---

*Phase: 10-gsd-phase-wave-indicator*
*Spec created: 2026-07-16*
*Next step: implemented directly per approved plan (planning.py reader → renderer → core gate → tests)*
