# Context (from DOCs)

Eight DOC-classified documents: four implementation plans (each pairing with a SPEC) and
four marketing / launch / upstream-request materials. Lowest precedence (DOC, rank 4).

## Implementation plan — rate-limit focused redesign
- source: docs/superpowers/plans/2026-03-25-rate-limit-redesign.md
- Task-by-task plan to replace the status bar with a dual-progress-bar, rate-limit-focused
  format for Max subscribers. Touches status bar, progress-bar rendering, cache layer,
  claude-monitor, statusline, CLI. Build guide for the SPEC
  `specs/2026-03-25-rate-limit-focused-redesign.md`.

## Implementation plan — per-segment color management + classic theme adoption
- source: docs/superpowers/plans/2026-05-07-per-segment-color-management.md
- Task-by-task plan for per-segment severity coloring and classic-style theme adoption in
  the renderer. Touches progress.py, themes.py, styles.py, core.py, preview.py. Build guide
  for the SPEC `specs/2026-05-07-per-segment-color-management-design.md`.

## Implementation plan — project + branch identity segment
- source: docs/superpowers/plans/2026-05-21-project-branch-segment.md
- Task-by-task plan for the opt-in second-line project/branch identity segment with cached
  dirty status. Touches statusbar, git cache, stdin workspace fields, daemon refresh. Build
  guide for the SPEC `specs/2026-05-21-project-branch-segment-design.md`.

## Implementation plan — rate-limit forecast chip
- source: docs/superpowers/plans/2026-06-02-rate-limit-forecast.md
- Task-by-task plan for the opt-in on-bar forecast chip projecting rate-limit exhaustion via
  a new predict.py module (burn rate, core.main, renderer, rate_history.json). Delegates the
  contract to the SPEC `specs/2026-06-02-rate-limit-forecast-design.md`. (classifier
  confidence: medium)

## Marketing — launch kit
- source: docs/launch-kit.md
- Copy-paste marketing materials (X, Reddit, HN, ProductHunt, blog) and launch checklist for
  promoting claude-statusbar. References hero GIF/SVG and build scripts (docs/images/hero.gif,
  hero.svg, scripts/hero.tape, scripts/build-hero-gif.sh).

## Marketing — HN prepared answers
- source: docs/hn-prepared-answers.md
- Copy-paste reply templates for likely Show HN comments (ccusage comparison, daemon mode,
  privacy/network egress, Windows support).

## Distribution — Anthropic plugin directory submission
- source: docs/anthropic-marketplace-submission.md
- Pre-filled form answers for submitting the claude-statusbar plugin to Anthropic's official
  plugin directory (statusLine plugin). References docs/images/*.svg.

## Upstream feature request — focused subagent statusLine field
- source: docs/upstream-fr-statusline-focused-agent.md
- Draft upstream FR asking Claude Code to add a `focused_agent` field to the statusLine
  payload so status reflects the focused subagent pane (per-agent model/context data).
  Contains a proposed JSON payload snippet but no acceptance criteria. (classifier
  confidence: medium; weak SPEC hint from the example schema)
