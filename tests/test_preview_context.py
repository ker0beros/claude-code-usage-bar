"""Tests for `cs preview` mirroring core.py's show_context gating (plan 06-03).

preview.py builds the model (used/size) suffix independently of core.py, so
it must gate that suffix the same way and additionally compute ctx_pct
(which it doesn't pass today) so the ctx bar actually renders.
"""

import io
from contextlib import redirect_stdout

import pytest

from claude_statusbar import preview


@pytest.fixture(autouse=True)
def _force_demo_data(monkeypatch, tmp_path):
    """Point CACHED_STDIN at a path that doesn't exist so _real_data() always
    returns None and these tests exercise the deterministic demo data — the
    dev machine running this suite may have a real ~/.cache/.../last_stdin.json
    with unrelated numbers."""
    monkeypatch.setattr(preview, "CACHED_STDIN", tmp_path / "no-such-file.json")


def _run(show_context=None, theme_filter=None, style_filter=None):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = preview.run(use_color=False, show_context=show_context,
                          theme_filter=theme_filter, style_filter=style_filter)
    return rc, buf.getvalue()


def test_preview_context_on_shows_ctx_bar_no_suffix():
    rc, out = _run(show_context=True, style_filter="classic", theme_filter="graphite")
    assert rc == 0
    assert "ctx[" in out
    # No (used/size) suffix fragment on the model
    assert "k/1.0M)" not in out
    assert "520.0k/" not in out


def test_preview_context_off_keeps_suffix_no_bar():
    rc, out = _run(show_context=False, style_filter="classic", theme_filter="graphite")
    assert rc == 0
    assert "ctx[" not in out
    assert "520.0k/1.0M)" in out  # (used/size) suffix present on the model


def test_preview_defaults_to_config(monkeypatch):
    """No show_context arg → resolved from load_config()."""
    from claude_statusbar import config as _config

    def _fake_load_config(*args, **kwargs):
        return _config.StatusbarConfig(show_context=True)

    monkeypatch.setattr(preview, "load_config", _fake_load_config, raising=False)
    # preview.py resolves via `from .config import load_config` inside run(),
    # so patch the source module too (covers either import style).
    monkeypatch.setattr(_config, "load_config", _fake_load_config)

    rc, out = _run(style_filter="classic", theme_filter="graphite")
    assert rc == 0
    assert "ctx[" in out
