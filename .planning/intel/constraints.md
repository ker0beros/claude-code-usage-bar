# Constraints (from SPECs)

Eight SPEC-classified design documents. Each entry preserves the source design contract.
Precedence: SPEC (rank 2 of ADR > SPEC > PRD > DOC). None are LOCKED.

## Rate-Limit Focused Status Bar Redesign
- source: docs/superpowers/specs/2026-03-25-rate-limit-focused-redesign.md
- type: nfr
- content:
  Target audience Max $100/$200 subscribers (claude.ai login, English-only UI). Replace
  cost / context% / lines-changed with a rate-limit-focused dual progress bar:
  `[████████░░] msgs 82% | [████░░░░░░] tkns 42% | ⏰2h51m | Opus 4.6`.
  Bar width 10 chars (`█`/`░`), two independent dimensions (messages, tokens), each bar
  colored by its own percentage; always ≥1 filled block when >0%.
  Color thresholds: <30% green, 30-70% yellow, >70% red. Filled portion colored by own
  pct; surrounding text (separators, timer, model) uses the higher severity of the two.
  Extreme cases: >100% → `msgs 100%+` full red; data unavailable → empty dimmed bar `--%`;
  reset <10min → normal timer, no special color. Bypass indicator `| ⚠️BYPASS` appended
  when `CLAUDE_SKIP_PERMISSIONS=1` or settings `defaultMode == "bypassPermissions"`.

## Per-segment color management + classic theme adoption
- source: docs/superpowers/specs/2026-05-07-per-segment-color-management-design.md
- type: nfr
- content:
  Fixes (1) color bleed — `format_status_line` derives a single `overall_color = max
  severity` and tints the whole classic line; each metric segment must own its own color,
  no leakage. (2) Classic ignores themes — `progress.py` uses raw 8-color ANSI; classic
  must pull red/green/yellow from `theme.s_ok / s_warn / s_hot` RGB and neutral text from
  `theme.ink / theme.mute`, respecting the active theme.
  All three styles (classic, capsule, hairline) surface 5h, 7d, context, cache
  independently. Numeric segments (5h, 7d, context) share 30/70 thresholds; cache keeps
  its string-age severity. Visual identity unchanged (battery bar, `[ ]`, 🕐/⏰, ` | `).
  Mandatory: new `theme.pill_cost` field on every theme. Out of scope: new thresholds,
  layout/glyph changes, new styles, cache threshold model.

## Project + branch identity segment
- source: docs/superpowers/specs/2026-05-21-project-branch-segment-design.md
- type: nfr
- content:
  Opt-in second status line `⤷ <project> ⎇ <branch>●` (dot only when tree dirty), via
  multi-line statusLine output. Default OFF (`show_project_branch: true` to enable).
  Inline render must stay under ~30ms: no `git` subprocess on synchronous render path;
  branch read directly from `.git/HEAD` (microseconds); dirty from a shared TTL cache
  keyed by `sha1(resolved-toplevel)`, refreshed by background worker (daemon) or detached
  Popen (inline). Outside a git repo collapses to `⤷ <project> (no git)`. Works in all
  three styles, respects theme. `parse_stdin_data()` in core.py gains `workspace.repo.name`,
  `workspace.project_dir`, `workspace.current_dir`, `workspace.git_worktree` (default
  empty/None when absent). Out of scope: ahead/behind, stash, remote URL, commit SHA,
  non-git VCS.

## Rate-limit forecast chip (⚠~ETA)
- source: docs/superpowers/specs/2026-06-02-rate-limit-forecast-design.md
- type: nfr
- content:
  On-bar prediction only (notifications separate/later). For each window (five_hour,
  seven_day), when projected time-to-100% at recent burn rate < time until window resets,
  render `⚠~<duration>` chip right after that window's `⏰<reset>` timer:
  `5h[███27%░░░░]⏰1h28m ⚠~40m | 7d[███61%░░░░]⏰5d18h`.
  Color: `s_hot` (red) when ≤~10min, else `s_warn` (yellow). Silent (no chip) when window
  not projected to exhaust before reset. Battery bar, %, ⏰ timer unchanged; chip additive.
  Config `show_forecast` (bool), DEFAULT ON (silent until at-risk). Classic style first;
  capsule/hairline out of scope unless trivial. Model is an estimate (`~`): assumes
  near-monotonic growth to cap; degrades safely on rolling windows (plateau → rate≤0 → no
  chip; worst case over-conservative early warning, never a false green light). Exact
  window semantics and lookback windows confirmed empirically post-ship.

## Rate-limit projection model (→NN% always-on)
- source: docs/superpowers/specs/2026-06-02-rate-limit-projection-learning-design.md
- type: schema
- content:
  Always-visible end-of-window projection `5h →50% | 7d →90%`: expected reset-time
  percentage if usage continues per the best available model. Must work from cold start,
  collect local history immediately, improve with observation, and remain auditable.
  Non-goals: never hide projection for low confidence (always show a number); no
  low/med/learning labels in the main line; rely only on official status-line payload
  (`used_percentage`, `resets_at`, model/context metadata, timestamps); do NOT make the
  ⚠~ETA chip the projection model — explicit coexistence, projection has its own purpose;
  hidden weights OK only if persisted snapshots make error measurable.
  Single delivery: timestamped account-global samples; projection snapshots + reset-outcome
  error logging; 5h blended projection (recent rate + whole-window average + personal
  coarse-bucket baseline); 7d future-bucket integration with learned coarse buckets +
  default priors; wall-clock/sample-based output smoothing; `show_projection` config.
  Accuracy measurement is a first-class requirement (store projection snapshots per window).

## Rate-limit Projection Model — implementation contract
- source: docs/superpowers/plans/2026-06-02-rate-limit-projection-model.md
- type: schema
- content:
  File-level build contract for the projection model. Extend `src/claude_statusbar/
  predict.py` (keep existing `format_eta`, `project_window`, `forecast_chip`,
  `reconcile_account`, `forecast` for ⚠~ETA; add projection store, sample recording,
  coarse buckets, learned rates, smoothing, metrics, `projection(...)`). `config.py` adds
  `show_projection: bool = True` with validation/bool parsing; `cli.py` shows it in
  `cs config show`; `core.main` calls `predict.projection(...)` when official rate-limit
  data exists and config enables it (keep `show_forecast` dedicated to ⚠~ETA);
  `progress.py` adds `projection_5h`/`projection_7d` render slots after each reset timer
  and before the forecast ETA; `styles.py` threads projection strings through
  `render_classic`/`render`. Tech: Python 3.9+ stdlib only; persistence via
  `claude_statusbar.cache.atomic_write_text`; tests via pytest with `PYTHONPATH=src`.

## Burn-Rate Regime Detection
- source: docs/superpowers/specs/2026-07-02-burn-regime-detection-design.html
- type: schema
- content:
  (claude-statusbar v3.19.0) →NN% recent-rate estimate uses 30/60-min lookback; model
  switches (Sonnet↔Fable burn-rate steps) or fleet composition changes make the lookback
  straddle two burn regimes and average out the step, so post-switch predictions chase the
  old regime. Record regime-boundary timestamps in account-global shared store
  `rate_latest.<acct>.json` (key `regime: {changed_at, reason, model}`); truncate the
  rate-estimation lookback at the boundary, relax the min sample span after it to "jump"
  onto the new rate faster, and reset display smoothing once at the boundary (don't smooth
  away the jump). `sessions[sid]` gains a `model` field (from stdin `model.id`, preserved
  when missing). Triggers: model.id change on known session (reason=model-switch); new
  session whose model is not in the active fleet (changed_at ≤ FLEET_ACTIVE_S=900s), reason
  =fleet-join. `_rate_from_samples` cutoff = max(now−lookback, since); min span 300s→
  REGIME_MIN_SPAN_S=120s when truncation active. Explicit non-goals: $ cost rate signal,
  model burn-weight table, Fable-specific 7d bucket, session-departure detection.

## Context window as a bar in quota mode
- source: docs/superpowers/specs/2026-07-15-context-bar-quota-mode-design.md
- type: nfr
- content:
  In quota mode context currently shows only as `(523k/1M)` suffix on the model name plus
  model-name color. Make context follow the bar style in quota mode too. When `ctx_pct is
  not None` and `show_context` on, render context as a bar segment in each style's own idiom
  (classic `ctx[███52%░░░░]`, capsule `⛁ CTX 52% ●` pill, hairline `› ctx █▃▁ 52%`),
  placed between the 7d segment and the model, in quota mode and session-start waiting
  state. Drop the `(used/size)` suffix from the model name and neutralize model color (the
  bar carries context severity; capsule also drops the redundant model `●` dot). Severity
  uses the context band: yellow ≥ CONTEXT_WARNING_THRESHOLD (70), red ≥
  CONTEXT_CRITICAL_THRESHOLD (85). New config `show_context: bool`, DEFAULT True. Reuses
  each style's existing no-quota ctx rendering so quota/no-quota look identical.
