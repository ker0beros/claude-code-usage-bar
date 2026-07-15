import sys

from claude_statusbar import cli
from claude_statusbar.config import StatusbarConfig, load_config, set_value


def test_default_off():
    assert StatusbarConfig().show_search_credits is False


def test_set_and_load(tmp_path):
    p = tmp_path / "cfg.json"
    set_value("show_search_credits", "on", p)
    assert load_config(p).show_search_credits is True
    set_value("show_search_credits", "off", p)
    assert load_config(p).show_search_credits is False


def test_config_show_lists_show_search_credits(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cs", "config", "show"])
    rc = cli.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "show_search_credits" in out
