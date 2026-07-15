from claude_statusbar.config import StatusbarConfig, load_config, set_value


def test_default_on():
    assert StatusbarConfig().show_context is True

def test_set_and_load(tmp_path):
    p = tmp_path / "cfg.json"
    set_value("show_context", "off", p)
    assert load_config(p).show_context is False
    set_value("show_context", "on", p)
    assert load_config(p).show_context is True
