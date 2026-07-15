# Context window as a bar in quota mode

- **Date:** 2026-07-15
- **Status:** Approved (design)
- **Scope:** `src/claude_statusbar` — styles, core render dispatch, config, preview

## Motivation

In no-quota mode (third-party relay / Bedrock / Vertex) the status line already
promotes the context window to its own battery bar — `ctx[███52%░░░░]` (classic),
`⛁ CTX 52%` (capsule), `› ctx █▃▁ 52%` (hairline).

In the normal **quota mode** (official 5h/7d data, the common case), context is
shown only as:

- a `(523k/1M)` suffix appended to the model name, and
- the color of the model name (context severity band).

There is no context *bar*. The request: make the context readout **follow the bar
style** in quota mode too, so it matches 5h/7d and the no-quota ctx bar.

## Behavior

When context data is available (`ctx_pct is not None`) and `show_context` is on,
render context as a bar/segment in each style's own idiom, in **quota mode** and
the session-start **waiting** state:

- Placed **between the 7d segment and the model**.
- The `(used/size)` suffix is **dropped** from the model name (the bar is now the
  context readout — same reasoning no-quota mode uses).
- The **model name goes neutral** (the bar carries context severity now). In
  capsule, the redundant model `●` context dot is also dropped.

Severity uses the **context band**: yellow ≥ `CONTEXT_WARNING_THRESHOLD` (70),
red ≥ `CONTEXT_CRITICAL_THRESHOLD` (85) — the same band the model name uses today
and the same the no-quota ctx bar uses. Not the 5h/7d comfort band.

Each style reuses its existing no-quota ctx rendering, so the ctx segment looks
identical in quota and no-quota modes.

### Before / after (classic, tokyo-night)

```
BEFORE : 5h[███42%░░░░]⏰3h28m | 7d[██░18%░░░░]⏰5d12h | Opus 4.7(523k/1M)
AFTER  : 5h[███42%░░░░]⏰3h28m | 7d[██░18%░░░░]⏰5d12h | ctx[███52%░░░░] | Opus 4.7
```

### Per-style segment

| Style    | Quota-mode ctx segment (new) | Reused from |
|----------|------------------------------|-------------|
| classic  | `ctx[███52%░░░░]`            | `_build_dimension("ctx", …)` |
| capsule  | `⛁ CTX 52% ●` pill           | no-quota CTX pill |
| hairline | `› ctx █▃▁ 52%` segment      | no-quota `mini3` segment |

## Control — `show_context` toggle

New boolean config field `show_context`, **default `True`**.

- **ON** → draw the ctx bar, drop the model `(k/M)` suffix, neutral model color.
- **OFF** → today's behavior exactly (suffix on model, model tinted by context
  band, no bar).

Default-on changes the default line for all users on upgrade (the `(280k/1M)`
suffix becomes a `ctx[…]` bar). This is intended and confirmed. Opt out with
`cs config set show_context off`.

## Implementation surface

1. **`config.py`**
   - Add `show_context: bool = True` to `StatusbarConfig`.
   - Parse in `from_dict`: `show_context=_to_bool(raw.get("show_context", True))`.
   - Add `"show_context"` to the persist list and `_BOOL_KEYS`.
   - Show it in `config show` output.

2. **`core.py`**
   - Official-quota branch (`~1380–1387`): when `cfg.show_context`, do **not**
     append `(used/size)` to the model; still strip any `(… context)` descriptor.
     Pass `show_context=cfg.show_context` into `_render_style`.
   - Waiting branch (`~1469–1472`): same treatment.
   - No-quota branch: already draws the bar; pass `show_context` through for
     uniformity (it has no suffix to drop, behavior unchanged).

3. **`progress.py` / `styles.py`**
   - `format_status_line` (classic): accept `show_context: bool = False`; when set
     and `ctx_pct is not None`, append a ctx dimension (context band, `fill_rgb`)
     after `dim_7d`, and force `model_color = ink`.
   - `render_capsule`: accept + thread `show_context`; insert the CTX pill after
     the 7D pill; set `model_sev = ""`.
   - `render_hairline`: accept + thread `show_context`; insert the ctx segment
     after the 7d segment; force neutral model ink.
   - `render_classic`: thread `show_context` into `format_status_line`.

4. **`preview.py`**
   - Thread `show_context` into the `render(...)` calls so `cs preview` reflects
     it. Gate the model-suffix build (`_real_data`) so preview mirrors core: no
     suffix when `show_context` is on.

## Testing

Extend `test_styles.py` / `test_progress.py`, mirroring `test_no_quota_render.py`:

- With `show_context=True` + a `ctx_pct`: each style's output contains its ctx
  segment (`ctx[`, `CTX`, `› ctx`) and the model has **no** `(k/M)` suffix.
- With `show_context=False`: output is unchanged from today (suffix present, no
  ctx segment) — guards backward compatibility.
- `--no-color`: `_strip` path still yields a readable ctx segment.

## Edge cases

- `ctx_pct is None` (session start before any context is reported): no bar, model
  neutral — same as today.
- No-quota mode: unchanged (already a bar).
- `show_weekly=False` (capsule/hairline): ctx inserts after 5h (there is no 7d
  segment) — falls out naturally from appending after the 7d block.

## Non-goals (this pass)

- JSON output for quota mode stays as-is (context already in no-quota JSON only).
- The "keep token count next to bar" and "after model" layouts (grouped/
  drop-suffix was chosen).
- The `cs-with-gsd` wrapper / GSD status bar merge — tracked separately.
