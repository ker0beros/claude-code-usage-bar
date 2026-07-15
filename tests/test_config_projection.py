from claude_statusbar.config import StatusbarConfig, load_config, set_value


def test_projection_default_off():
    assert StatusbarConfig().show_projection is False


def test_projection_set_and_load(tmp_path):
    p = tmp_path / "cfg.json"
    set_value("show_projection", "false", p)
    assert load_config(p).show_projection is False
