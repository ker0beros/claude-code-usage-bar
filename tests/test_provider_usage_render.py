"""Rendering of search-provider credit bars (show_search_credits): classic
fuel-gauge battery, capsule/hairline severity-colored chips, and the
`cs preview` demo matrix.
"""
from claude_statusbar import progress, styles


_ENTRIES = [
    {"label": "fc", "pct": 82.0, "text": "fc 82%", "remaining": 820, "limit": 1000},
    {"label": "tv", "pct": 18.0, "text": "tv 18%", "remaining": 180, "limit": 1000},
]


# --- classic: battery via format_status_line ---

def test_classic_search_credit_battery_no_quota():
    out = progress.format_status_line(
        msgs_pct=None, tkns_pct=None, reset_time="--", model="qwen-max",
        ctx_pct=0, no_quota=True, use_color=False,
        search_credits=_ENTRIES)
    assert "fc[" in out
    assert "82%" in out
    assert "tv[" in out
    assert "18%" in out


def test_classic_search_credit_battery_quota_mode():
    out = progress.format_status_line(
        msgs_pct=42, tkns_pct=None, reset_time="3h", model="Opus 4.7",
        weekly_pct=18, reset_time_7d="5d",
        use_color=False, search_credits=_ENTRIES)
    assert "fc[" in out and "82%" in out


def test_classic_search_credit_battery_stale_mode():
    out = progress.format_status_line(
        msgs_pct=None, tkns_pct=None, reset_time="--", model="Opus 4.7",
        weekly_pct=None, quota_stale=True, use_color=False,
        search_credits=_ENTRIES)
    assert "fc[" in out and "82%" in out


def test_classic_empty_search_credits_renders_nothing():
    out = progress.format_status_line(
        msgs_pct=None, tkns_pct=None, reset_time="--", model="qwen-max",
        ctx_pct=0, no_quota=True, use_color=False,
        search_credits=[])
    assert "fc" not in out
    assert "tv" not in out


def test_classic_none_search_credits_renders_nothing():
    out = progress.format_status_line(
        msgs_pct=None, tkns_pct=None, reset_time="--", model="qwen-max",
        ctx_pct=0, no_quota=True, use_color=False,
        search_credits=None)
    assert "fc[" not in out


# --- capsule / hairline: severity-colored chips ---

def test_capsule_search_credit_chip():
    out = styles.render_capsule(
        msgs_pct=None, weekly_pct=None, reset_5h="--", reset_7d="",
        model="qwen-max", ctx_pct=0, no_quota=True, use_color=False,
        search_credits=_ENTRIES)
    assert "fc 82%" in out
    assert "tv 18%" in out


def test_hairline_search_credit_chip():
    out = styles.render_hairline(
        msgs_pct=None, weekly_pct=None, reset_5h="--", reset_7d="",
        model="qwen-max", ctx_pct=0, no_quota=True, use_color=False,
        search_credits=_ENTRIES)
    assert "fc 82%" in out
    assert "tv 18%" in out


def test_capsule_empty_search_credits_renders_nothing():
    out = styles.render_capsule(
        msgs_pct=None, weekly_pct=None, reset_5h="--", reset_7d="",
        model="qwen-max", ctx_pct=0, no_quota=True, use_color=False,
        search_credits=[])
    assert "fc" not in out


def test_hairline_empty_search_credits_renders_nothing():
    out = styles.render_hairline(
        msgs_pct=None, weekly_pct=None, reset_5h="--", reset_7d="",
        model="qwen-max", ctx_pct=0, no_quota=True, use_color=False,
        search_credits=[])
    assert "fc" not in out


def test_capsule_fill_color_severity(monkeypatch):
    theme = progress.get_theme("graphite")
    hot_entry = [{"label": "tv", "pct": 5.0, "text": "tv 5%"}]
    out = styles.render_capsule(
        msgs_pct=None, weekly_pct=None, reset_5h="--", reset_7d="",
        model="qwen-max", ctx_pct=0, no_quota=True, use_color=True,
        theme=theme, search_credits=hot_entry)
    hot_rgb = progress._balance_fill_rgb(5.0, theme)
    assert f"\033[48;2;{hot_rgb[0]};{hot_rgb[1]};{hot_rgb[2]}m" in out


# --- cs preview demo matrix ---

def test_preview_shows_demo_search_credit_label(monkeypatch):
    from claude_statusbar import preview as preview_mod
    # Force demo data so the test doesn't depend on a live cache file / env
    # keys, matching the existing test_preview_classic_varies_by_theme
    # precedent.
    monkeypatch.setattr(preview_mod, "_real_data", lambda show_context=False: None)
    rc = preview_mod.run(use_color=False, theme_filter="graphite",
                         style_filter="classic")
    assert rc == 0


def test_preview_output_contains_search_credit_text(monkeypatch, capsys):
    from claude_statusbar import preview as preview_mod
    monkeypatch.setattr(preview_mod, "_real_data", lambda show_context=False: None)
    preview_mod.run(use_color=False, theme_filter="graphite", style_filter="classic")
    out = capsys.readouterr().out
    assert "fc 82%" in out or "fc[" in out
