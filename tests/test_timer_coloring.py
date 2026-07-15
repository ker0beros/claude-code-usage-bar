"""The ⏰ reset-timer countdown colors by ELAPSED% of its own window on a
FIXED 65/85 band — decoupled from the bar's configurable warning/critical
thresholds. 5h is FLIPPED (short countdown = fresh quota = green); 7d is
NORMAL (short countdown = window running out = red).
"""

import inspect

import pytest

from claude_statusbar.progress import (
    RESET,
    TIMER_CRITICAL_THRESHOLD,
    TIMER_WARNING_THRESHOLD,
    _fg,
    format_status_line,
    timer_elapsed_pct,
    timer_severity_rgb,
)
from claude_statusbar.styles import render
from claude_statusbar.themes import get_theme

THEME = get_theme("graphite")


# ── constants ────────────────────────────────────────────────────────────
def test_timer_thresholds_are_65_85():
    assert TIMER_WARNING_THRESHOLD == 65.0
    assert TIMER_CRITICAL_THRESHOLD == 85.0


# ── timer_severity_rgb: boundary checks for both mappings ──────────────────
@pytest.mark.parametrize("elapsed,expected_attr", [
    (64, "s_hot"),
    (65, "s_warn"),
    (84, "s_warn"),
    (85, "s_ok"),
    (86, "s_ok"),
])
def test_timer_severity_rgb_5h_flipped_boundaries(elapsed, expected_attr):
    # flip=True (5h): short countdown is GOOD → green as elapsed grows.
    assert timer_severity_rgb(elapsed, flip=True, theme=THEME) == getattr(THEME, expected_attr)


@pytest.mark.parametrize("elapsed,expected_attr", [
    (64, "s_ok"),
    (65, "s_warn"),
    (84, "s_warn"),
    (85, "s_hot"),
    (86, "s_hot"),
])
def test_timer_severity_rgb_7d_normal_boundaries(elapsed, expected_attr):
    # flip=False (7d): short countdown is BAD → red as elapsed grows.
    assert timer_severity_rgb(elapsed, flip=False, theme=THEME) == getattr(THEME, expected_attr)


def test_timer_severity_rgb_none_elapsed_is_none():
    assert timer_severity_rgb(None, flip=True, theme=THEME) is None
    assert timer_severity_rgb(None, flip=False, theme=THEME) is None


def test_timer_severity_rgb_defaults_theme_when_omitted():
    # theme is optional — falls back to get_theme("graphite").
    assert timer_severity_rgb(90, flip=True) == THEME.s_ok


# ── timer_elapsed_pct: clamp + None cases ───────────────────────────────────
def test_timer_elapsed_pct_negative_remaining_clamps_to_100():
    assert timer_elapsed_pct(-5, 18000) == 100.0


def test_timer_elapsed_pct_remaining_exceeds_window_clamps_to_0():
    assert timer_elapsed_pct(20000, 18000) == 0.0


def test_timer_elapsed_pct_full_window_remaining_is_0():
    assert timer_elapsed_pct(18000, 18000) == 0.0


def test_timer_elapsed_pct_mid_value():
    assert timer_elapsed_pct(6300, 18000) == 65.0


def test_timer_elapsed_pct_none_remaining_is_none():
    assert timer_elapsed_pct(None, 18000) is None


def test_timer_elapsed_pct_zero_window_is_none():
    assert timer_elapsed_pct(100, 0) is None


# ── independence: timer band ignores the bar's configurable thresholds ─────
def test_timer_severity_rgb_signature_has_no_threshold_params():
    sig = inspect.signature(timer_severity_rgb)
    assert "warning_threshold" not in sig.parameters
    assert "critical_threshold" not in sig.parameters


def test_timer_color_ignores_customized_bar_thresholds():
    # Bar band retuned to 70/90; timer elapsed=65 must still land in the
    # timer's OWN 65-85 warn band (yellow), not read against 70/90.
    result = format_status_line(
        msgs_pct=20, tkns_pct=None, reset_time="2h30m", model="Opus",
        warning_threshold=70, critical_threshold=90,
        timer_elapsed_5h=65, use_color=True, theme=THEME,
    )
    expected_timer_segment = f"{_fg(THEME.s_warn)}⏰2h30m{RESET}"
    assert expected_timer_segment in result


# ── signal separation: timer color can differ from the bar color ───────────
def test_timer_color_differs_from_bar_color_when_signals_disagree():
    # Low 5h usage (5%) → bar fill/label reads s_ok (green).
    # elapsed 30 (<65, flipped) → timer text reads s_hot (red).
    result = format_status_line(
        msgs_pct=5, tkns_pct=None, reset_time="4h00m", model="Opus",
        timer_elapsed_5h=30, use_color=True, theme=THEME,
    )
    from claude_statusbar.progress import colorize
    assert colorize("5h", _fg(THEME.s_ok), True) in result
    assert f"{_fg(THEME.s_hot)}⏰4h00m{RESET}" in result


def test_timer_color_differs_from_bar_color_7d():
    # Low 7d usage (5%) → bar fill/label reads s_ok (green).
    # elapsed 90 (>=85, normal) → timer text reads s_hot (red): window almost over.
    result = format_status_line(
        msgs_pct=None, tkns_pct=None, reset_time="--", model="Opus",
        weekly_pct=5, reset_time_7d="1h00m",
        timer_elapsed_7d=90, use_color=True, theme=THEME,
    )
    from claude_statusbar.progress import colorize
    assert colorize("7d", _fg(THEME.s_ok), True) in result
    assert f"{_fg(THEME.s_hot)}⏰1h00m{RESET}" in result


# ── edge cases: never crash, fall back to prior coloring ────────────────────
def test_format_status_line_none_elapsed_falls_back_to_bar_color():
    result = format_status_line(
        msgs_pct=50, tkns_pct=None, reset_time="1h00m", model="Opus",
        use_color=True, theme=THEME,
    )
    # 50% is below warn(65) → bar reads s_ok; with no elapsed% given the
    # timer text falls back to the SAME color_5h — the unchanged prior
    # behavior (timer == bar when there's nothing to band on).
    assert f"{_fg(THEME.s_ok)}⏰1h00m{RESET}" in result


def test_format_status_line_none_elapsed_matches_omitted_kwargs():
    # Passing timer_elapsed_5h/7d=None explicitly must be identical to not
    # passing them at all (both hit the same default).
    kwargs = dict(msgs_pct=42, tkns_pct=None, reset_time="3h00m", model="Opus",
                  weekly_pct=10, reset_time_7d="2d00h", use_color=True, theme=THEME)
    explicit = format_status_line(timer_elapsed_5h=None, timer_elapsed_7d=None, **kwargs)
    omitted = format_status_line(**kwargs)
    assert explicit == omitted


@pytest.mark.parametrize("style", ["classic", "capsule", "hairline"])
def test_render_no_elapsed_never_crashes(style):
    out = render(
        style, msgs_pct=42, weekly_pct=10, reset_5h="3h00m", reset_7d="2d00h",
        model="Opus", use_color=True, theme=THEME,
    )
    assert out  # non-empty, no exception


@pytest.mark.parametrize("style", ["classic", "capsule", "hairline"])
def test_render_none_elapsed_matches_omitted_kwargs(style):
    kwargs = dict(msgs_pct=42, weekly_pct=10, reset_5h="3h00m", reset_7d="2d00h",
                  model="Opus", use_color=True, theme=THEME)
    explicit = render(style, timer_elapsed_5h=None, timer_elapsed_7d=None, **kwargs)
    omitted = render(style, **kwargs)
    assert explicit == omitted


@pytest.mark.parametrize("style", ["classic", "capsule", "hairline"])
def test_render_absent_reset_never_crashes(style):
    # resets_at absent → reset text is "--" / "" and elapsed is undefined —
    # must never raise regardless of style.
    out = render(
        style, msgs_pct=None, weekly_pct=None, reset_5h="--", reset_7d="",
        model="Opus", use_color=True, theme=THEME,
        timer_elapsed_5h=None, timer_elapsed_7d=None,
    )
    assert out
