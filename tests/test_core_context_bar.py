"""Seam-level integration tests for plan 06-03: core.main() must gate the
model's (used/size) suffix and thread show_context=cfg.show_context into the
renderer, in BOTH the official-quota branch and the waiting (session-start)
branch. show_context=off must reproduce today's byte-for-byte behavior.

Drives core.main() end-to-end (real stdin + a real on-disk config file),
mirroring the established pattern in tests/test_no_quota_integration.py, so
these tests exercise the actual wiring rather than a mocked seam.
"""

import io
import json
import sys


def _official_payload(context_used_pct=52):
    """Official rate_limits present + a context_window sized so ctx_pct≈52
    of a 1M window."""
    return json.dumps({
        "session_id": "ctx-official",
        "transcript_path": "/o.jsonl",
        "model": {"id": "o", "display_name": "Opus 4.8"},
        "rate_limits": {
            "five_hour": {"used_percentage": 42, "resets_at": 9999999999},
            "seven_day": {"used_percentage": 18, "resets_at": 9999999999},
        },
        "context_window": {"used_percentage": context_used_pct,
                            "context_window_size": 1_000_000,
                            "total_input_tokens": 520_000},
    })


def _waiting_payload(context_used_pct=52):
    """No rate_limits at all (session just started) but stdin is present and
    carries a context_window — this is the 'waiting' branch (has_official is
    False, _has_stdin is True). No transcript_path so the no-quota heuristic
    stays silent (transcript_has_assistant is False) and no_quota stays
    False, keeping this in the official waiting branch rather than no-quota."""
    return json.dumps({
        "session_id": "ctx-waiting",
        "model": {"id": "o", "display_name": "Opus 4.8"},
        "context_window": {"used_percentage": context_used_pct,
                            "context_window_size": 1_000_000,
                            "total_input_tokens": 520_000},
    })


def _write_config(tmp_path, **values):
    (tmp_path / ".claude").mkdir(parents=True)
    base = {
        "show_project_branch": False,
        "show_cache_age": False,
        "show_todos": False,
        "show_mode": False,
    }
    base.update(values)
    path = tmp_path / ".claude" / "claude-statusbar.json"
    path.write_text(json.dumps(base), encoding="utf-8")
    return path


def _run(tmp_path, monkeypatch, payload, show_context):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("CS_API_MODE", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_USE_BEDROCK", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_USE_VERTEX", raising=False)
    config_path = _write_config(tmp_path, show_context=show_context)
    import claude_statusbar.config as config
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    from claude_statusbar.core import main
    main(use_color=False, _suppress_side_effects=True)


# --- official-quota branch ---------------------------------------------

def test_official_show_context_on_drops_suffix_and_shows_bar(tmp_path, monkeypatch, capsys):
    _run(tmp_path, monkeypatch, _official_payload(), show_context=True)
    out = capsys.readouterr().out
    assert "ctx[" in out
    assert "/1.0M)" not in out  # no (used/size) suffix on the model
    assert "Opus 4.8" in out


def test_official_show_context_off_keeps_suffix_no_bar(tmp_path, monkeypatch, capsys):
    _run(tmp_path, monkeypatch, _official_payload(), show_context=False)
    out = capsys.readouterr().out
    assert "ctx[" not in out
    assert "/1.0M)" in out  # today's (used/size) suffix is unchanged
    assert "Opus 4.8" in out


# --- waiting (session-start) branch -------------------------------------

def test_waiting_show_context_on_drops_suffix_and_shows_bar(tmp_path, monkeypatch, capsys):
    _run(tmp_path, monkeypatch, _waiting_payload(), show_context=True)
    out = capsys.readouterr().out
    assert "ctx[" in out
    assert "/1.0M)" not in out
    assert "Opus 4.8" in out


def test_waiting_show_context_off_keeps_suffix_no_bar(tmp_path, monkeypatch, capsys):
    _run(tmp_path, monkeypatch, _waiting_payload(), show_context=False)
    out = capsys.readouterr().out
    assert "ctx[" not in out
    assert "/1.0M)" in out
    assert "Opus 4.8" in out
