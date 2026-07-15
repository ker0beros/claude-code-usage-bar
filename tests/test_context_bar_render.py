"""Render tests for the quota-mode context bar (`show_context`).

In quota mode (official 5h/7d data present), context has always been shown
only as a `(used/size)` suffix on the model name plus a tint. This adds a
real bar/pill/mini-bar segment — one per style — placed between the 7d
segment and the model, gated by `show_context` (renderer default False so
existing callers/tests are unaffected). The segment must render
byte-identically (ANSI stripped) to the existing no-quota ctx segment for the
same style and ctx_pct, and it colors on the CONTEXT_WARNING_THRESHOLD (70) /
CONTEXT_CRITICAL_THRESHOLD (85) band, not the 5h/7d comfort band.
"""

from claude_statusbar import progress, styles


def _extract_segment(text, marker, sep):
    """Split `text` on `sep` and return the first chunk containing `marker`."""
    for part in text.split(sep):
        if marker in part:
            return part
    return None


# --- classic (progress.format_status_line) ---


def test_classic_quota_ctx_bar_between_7d_and_model():
    out = progress.format_status_line(
        msgs_pct=42, tkns_pct=None, reset_time="1h", model="Opus 4.8",
        weekly_pct=18, reset_time_7d="", ctx_pct=52,
        show_context=True, use_color=False,
    )
    assert "5h[" in out
    assert "7d[" in out
    assert "ctx[" in out
    assert "52%" in out
    assert "Opus 4.8" in out
    assert out.index("7d[") < out.index("ctx[") < out.index("Opus 4.8")


def test_classic_quota_ctx_off_unchanged():
    """Default (show_context=False) is unchanged: no ctx bar, 5h/7d intact."""
    out = progress.format_status_line(
        msgs_pct=42, tkns_pct=None, reset_time="1h", model="Opus 4.8",
        weekly_pct=18, reset_time_7d="", ctx_pct=52, use_color=False,
    )
    assert "ctx[" not in out
    assert "5h[" in out
    assert "7d[" in out


def test_classic_quota_ctx_severity_band():
    """Context bar colors on 65/85 (context band), same as the 5h/7d comfort band."""
    theme = progress.get_theme("graphite")
    ok = progress._fg(theme.s_ok)
    warn = progress._fg(theme.s_warn)
    hot = progress._fg(theme.s_hot)

    def _line(ctx_pct):
        return progress.format_status_line(
            msgs_pct=10, tkns_pct=None, reset_time="1h", model="Opus 4.8",
            weekly_pct=10, reset_time_7d="", ctx_pct=ctx_pct,
            show_context=True, use_color=True, theme=theme,
        )

    assert f"{ok}ctx" in _line(50)     # calm below 65
    assert f"{warn}ctx" in _line(75)   # warn >= 65
    assert f"{hot}ctx" in _line(90)    # crit >= 85


def test_classic_quota_ctx_none_no_bar_model_neutral():
    """show_context=True with ctx_pct=None: no ctx bar, model neutral (today's behavior)."""
    theme = progress.get_theme("graphite")
    ink = progress._fg(theme.ink)
    out = progress.format_status_line(
        msgs_pct=42, tkns_pct=None, reset_time="1h", model="Opus 4.8",
        weekly_pct=18, reset_time_7d="", ctx_pct=None,
        show_context=True, use_color=True, theme=theme,
    )
    assert "ctx[" not in out
    assert f"{ink}Opus 4.8" in out


# --- capsule (styles.render_capsule) ---


def test_capsule_quota_ctx_pill_after_7d():
    out = styles.render_capsule(
        msgs_pct=42, weekly_pct=18, reset_5h="1h", reset_7d="2d",
        model="Opus 4.8", ctx_pct=52, show_context=True, use_color=False,
    )
    assert "CTX" in out
    assert "52%" in out
    assert "5H" in out
    assert "7D" in out
    assert "Opus 4.8" in out
    assert out.index("7D") < out.index("CTX") < out.index("Opus 4.8")


def test_capsule_quota_ctx_off_unchanged():
    out = styles.render_capsule(
        msgs_pct=42, weekly_pct=18, reset_5h="1h", reset_7d="2d",
        model="Opus 4.8", ctx_pct=52, use_color=False,
    )
    assert "CTX" not in out
    assert "5H" in out and "7D" in out


# --- hairline (styles.render_hairline) ---


def test_hairline_quota_ctx_segment_after_7d():
    out = styles.render_hairline(
        msgs_pct=42, weekly_pct=18, reset_5h="1h", reset_7d="2d",
        model="Opus 4.8", ctx_pct=52, show_context=True, use_color=False,
    )
    assert "ctx" in out
    assert "52%" in out
    assert "5h" in out
    assert "7d" in out
    assert "Opus 4.8" in out
    assert out.index("7d") < out.index("ctx") < out.index("Opus 4.8")


def test_hairline_quota_ctx_off_unchanged():
    out = styles.render_hairline(
        msgs_pct=42, weekly_pct=18, reset_5h="1h", reset_7d="2d",
        model="Opus 4.8", ctx_pct=52, use_color=False,
    )
    assert "› ctx" not in out
    assert "5h" in out and "7d" in out


# --- quota/no-quota parity across all three styles ---


def test_quota_ctx_matches_no_quota_per_style():
    theme = progress.get_theme("graphite")

    quota_classic = progress.format_status_line(
        msgs_pct=42, tkns_pct=None, reset_time="1h", model="Opus 4.8",
        weekly_pct=18, reset_time_7d="", ctx_pct=52,
        show_context=True, use_color=False, theme=theme,
    )
    no_quota_classic = progress.format_status_line(
        msgs_pct=None, tkns_pct=None, reset_time="--", model="Opus 4.8",
        weekly_pct=None, ctx_pct=52, no_quota=True, use_color=False, theme=theme,
    )
    assert (_extract_segment(quota_classic, "ctx[", " | ")
            == _extract_segment(no_quota_classic, "ctx[", " | "))

    quota_capsule = styles.render_capsule(
        msgs_pct=42, weekly_pct=18, reset_5h="1h", reset_7d="2d",
        model="Opus 4.8", ctx_pct=52, show_context=True, use_color=False, theme=theme,
    )
    no_quota_capsule = styles.render_capsule(
        msgs_pct=None, weekly_pct=None, reset_5h="--", reset_7d="",
        model="Opus 4.8", ctx_pct=52, no_quota=True, use_color=False, theme=theme,
    )
    assert (_extract_segment(quota_capsule, "CTX", " ╱ ")
            == _extract_segment(no_quota_capsule, "CTX", " ╱ "))

    quota_hairline = styles.render_hairline(
        msgs_pct=42, weekly_pct=18, reset_5h="1h", reset_7d="2d",
        model="Opus 4.8", ctx_pct=52, show_context=True, use_color=False, theme=theme,
    )
    no_quota_hairline = styles.render_hairline(
        msgs_pct=None, weekly_pct=None, reset_5h="--", reset_7d="",
        model="Opus 4.8", ctx_pct=52, no_quota=True, use_color=False, theme=theme,
    )
    assert (_extract_segment(quota_hairline, "ctx", " ┊ ")
            == _extract_segment(no_quota_hairline, "ctx", " ┊ "))
