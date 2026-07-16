"""Tests for the GSD indicator renderer + core auto-show wiring."""

import io
import json
import sys

from claude_statusbar.planning import PlanningStatus, WaveGroup
from claude_statusbar.styles import render, render_planning_line
from claude_statusbar.themes import get_theme

THEME = get_theme("graphite")


def _executing():
    return PlanningStatus(
        current_phase=6, total_phases=9, phase_name="Ctx", state="executing",
        waves=(WaveGroup(wave=1, done=(True, True), state="complete"),
               WaveGroup(wave=2, done=(False,), state="active")),
    )


# --- renderer ------------------------------------------------------------

def test_render_none_is_empty():
    assert render_planning_line(None, theme=THEME, use_color=False) == ""


def test_render_executing_circles_no_color():
    out = render_planning_line(_executing(), theme=THEME, use_color=False)
    assert out == "gsd 6/9 ●● ○"


def test_render_done_shows_word_no_circles():
    ps = PlanningStatus(current_phase=6, total_phases=9, state="done")
    out = render_planning_line(ps, theme=THEME, use_color=False)
    assert out == "gsd 6/9 done"
    assert "●" not in out and "○" not in out


def test_render_idle_shows_idle_word():
    ps = PlanningStatus(current_phase=2, total_phases=9, state="idle")
    assert render_planning_line(ps, theme=THEME, use_color=False) == "gsd 2/9 idle"


def test_render_executing_without_waves_is_phase_only():
    ps = PlanningStatus(current_phase=7, total_phases=9, state="executing", waves=())
    assert render_planning_line(ps, theme=THEME, use_color=False) == "gsd 7/9"


def test_render_colors_per_wave_state():
    out = render_planning_line(_executing(), theme=THEME, use_color=True)
    green = "\033[38;2;{};{};{}m".format(*THEME.s_ok)
    yellow = "\033[38;2;{};{};{}m".format(*THEME.s_warn)
    assert green + "●●" in out       # complete wave → green
    assert yellow + "○" in out       # active wave → yellow


# --- dispatcher ----------------------------------------------------------

_BASE = dict(msgs_pct=10, weekly_pct=20, model="Opus 4.8",
             reset_5h="4h", reset_7d="6d", use_color=False, theme=THEME)


def test_dispatcher_appends_planning_line():
    out = render("classic", planning=_executing(), **_BASE)
    lines = out.split("\n")
    assert lines[-1] == "gsd 6/9 ●● ○"


def test_dispatcher_no_planning_appends_nothing():
    out = render("classic", **_BASE)
    assert "gsd" not in out


def test_dispatcher_planning_line_in_all_styles():
    for style in ("classic", "capsule", "hairline"):
        out = render(style, planning=_executing(), **_BASE)
        assert "gsd 6/9 ●● ○" in out


# --- core auto-show seam -------------------------------------------------

def _make_state(root, status="executing"):
    pl = root / ".planning"
    ph = pl / "phases" / "06-ctx"
    ph.mkdir(parents=True)
    (pl / "STATE.md").write_text(
        "---\ncurrent_phase: 6\ncurrent_phase_name: Ctx\n"
        f"status: {status}\nprogress:\n  total_phases: 9\n---\n",
        encoding="utf-8")
    # wave 1: two plans done (●●); wave 2: one plan pending (○)
    (ph / "06-01-PLAN.md").write_text("---\nplan: 01\nwave: 1\n---\n", encoding="utf-8")
    (ph / "06-01-SUMMARY.md").write_text("---\nstatus: complete\n---\n", encoding="utf-8")
    (ph / "06-02-PLAN.md").write_text("---\nplan: 02\nwave: 1\n---\n", encoding="utf-8")
    (ph / "06-02-SUMMARY.md").write_text("---\nstatus: complete\n---\n", encoding="utf-8")
    (ph / "06-03-PLAN.md").write_text("---\nplan: 03\nwave: 2\n---\n", encoding="utf-8")


def _payload(cwd):
    return json.dumps({
        "session_id": "gsd-seam",
        "model": {"id": "o", "display_name": "Opus 4.8"},
        "workspace": {"current_dir": str(cwd)},
        "rate_limits": {
            "five_hour": {"used_percentage": 27, "resets_at": None},
            "seven_day": {"used_percentage": 40, "resets_at": None},
        },
    })


def _run(tmp_path, monkeypatch, cwd):
    monkeypatch.setenv("HOME", str(tmp_path))
    for var in ("ANTHROPIC_BASE_URL", "CS_API_MODE",
                "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"):
        monkeypatch.delenv(var, raising=False)
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    cfg = tmp_path / ".claude" / "claude-statusbar.json"
    cfg.write_text(json.dumps({
        "show_project_branch": False, "show_cwd": False,
        "show_party": False, "show_mode": False,
    }), encoding="utf-8")
    import claude_statusbar.config as config
    monkeypatch.setattr(config, "CONFIG_PATH", cfg)
    monkeypatch.setattr(sys, "stdin", io.StringIO(_payload(cwd)))
    from claude_statusbar.core import main
    main(use_color=False, _suppress_side_effects=True)


def test_core_autoshows_when_planning_present(tmp_path, monkeypatch, capsys):
    project = tmp_path / "proj"
    project.mkdir()
    _make_state(project, status="executing")
    _run(tmp_path, monkeypatch, project)
    out = capsys.readouterr().out
    assert "gsd 6/9 ●● ○" in out


def test_core_done_status_renders_word(tmp_path, monkeypatch, capsys):
    project = tmp_path / "proj"
    project.mkdir()
    _make_state(project, status="phase-complete")
    _run(tmp_path, monkeypatch, project)
    out = capsys.readouterr().out
    assert "gsd 6/9 done" in out


def test_core_unchanged_when_no_planning(tmp_path, monkeypatch, capsys):
    # A cwd with no .planning/ must not emit a gsd line at all.
    project = tmp_path / "bare"
    project.mkdir()
    _run(tmp_path, monkeypatch, project)
    out = capsys.readouterr().out
    assert "gsd" not in out
