"""Phase 11: opt-in `show_email` account-email chip on the identity line.

Reader: account.resolve_account_email derives the active config dir from the
per-session transcript_path (fallback CLAUDE_CONFIG_DIR, then ~/.claude), reads
oauthAccount.emailAddress from that dir's .claude.json (fallback $HOME/.claude.json).
Config: `show_email` (bool, default True). Render: `👤 <email>` chip on the
identity line, before the version.
"""

from pathlib import Path

import pytest

from claude_statusbar import account, config
from claude_statusbar.identity import IdentityInfo
from claude_statusbar.styles import render, render_identity_line
from claude_statusbar.themes import get_theme


THEME = get_theme("graphite")
EMAIL = "khairul.rashid@silentmode.my"


def _info(name="proj"):
    return IdentityInfo(project_name=name, in_git=True, branch="main",
                        detached=False, worktree_name=None, toplevel="/x")


def _write_claude_json(path: Path, email=EMAIL, uuid="abc-123"):
    """Write a minimal .claude.json with an oauthAccount block."""
    path.write_text(
        '{\n'
        '  "someOtherKey": 1,\n'
        '  "oauthAccount": {\n'
        f'    "accountUuid": "{uuid}",\n'
        f'    "emailAddress": "{email}",\n'
        '    "organizationName": "Acme"\n'
        '  }\n'
        '}\n',
        encoding="utf-8",
    )


def _reset_cache():
    account._EMAIL_CACHE["sig"] = None
    account._EMAIL_CACHE["email"] = None


# --- reader: config-dir resolution --------------------------------------------

def test_config_dir_from_transcript(tmp_path):
    cfg_dir = tmp_path / ".claude-account2"
    tp = cfg_dir / "projects" / "-enc-proj" / "sid.jsonl"
    stdin = {"transcript_path": str(tp)}
    assert account.resolve_config_dir(stdin, env={}, home=tmp_path) == cfg_dir


def test_config_dir_transcript_requires_projects_segment(tmp_path):
    # A path whose parents[1] isn't "projects" is not trusted → env/default.
    tp = tmp_path / ".claude-account2" / "sessions" / "-enc" / "sid.jsonl"
    stdin = {"transcript_path": str(tp)}
    got = account.resolve_config_dir(stdin, env={}, home=tmp_path)
    assert got == tmp_path / ".claude"


def test_config_dir_env_fallback(tmp_path):
    ccd = tmp_path / ".claude-account1"
    got = account.resolve_config_dir(
        {}, env={"CLAUDE_CONFIG_DIR": str(ccd)}, home=tmp_path)
    assert got == ccd


def test_config_dir_default_home(tmp_path):
    got = account.resolve_config_dir({}, env={}, home=tmp_path)
    assert got == tmp_path / ".claude"


def test_transcript_wins_over_env(tmp_path):
    cfg_dir = tmp_path / ".claude-account2"
    tp = cfg_dir / "projects" / "-enc" / "sid.jsonl"
    stdin = {"transcript_path": str(tp)}
    got = account.resolve_config_dir(
        stdin, env={"CLAUDE_CONFIG_DIR": str(tmp_path / ".claude-other")},
        home=tmp_path)
    assert got == cfg_dir


# --- reader: email from .claude.json ------------------------------------------

def test_email_named_account(tmp_path):
    _reset_cache()
    cfg_dir = tmp_path / ".claude-account2"
    cfg_dir.mkdir(parents=True)
    _write_claude_json(cfg_dir / ".claude.json")
    tp = cfg_dir / "projects" / "-enc" / "sid.jsonl"
    got = account.resolve_account_email(
        {"transcript_path": str(tp)}, env={}, home=tmp_path)
    assert got == EMAIL


def test_email_default_account_falls_back_to_home(tmp_path):
    # Default config dir ~/.claude has no per-dir .claude.json; the file lives
    # at $HOME/.claude.json instead.
    _reset_cache()
    (tmp_path / ".claude").mkdir()
    _write_claude_json(tmp_path / ".claude.json", email="default@x.com")
    got = account.resolve_account_email({}, env={}, home=tmp_path)
    assert got == "default@x.com"


def test_email_missing_file_returns_none(tmp_path):
    _reset_cache()
    got = account.resolve_account_email({}, env={}, home=tmp_path)
    assert got is None


def test_email_missing_field_returns_none(tmp_path):
    _reset_cache()
    (tmp_path / ".claude.json").write_text(
        '{"oauthAccount": {"accountUuid": "x"}}', encoding="utf-8")
    got = account.resolve_account_email({}, env={}, home=tmp_path)
    assert got is None


def test_email_no_oauth_account_returns_none(tmp_path):
    # API-key users have no oauthAccount block and no emailAddress anywhere.
    _reset_cache()
    (tmp_path / ".claude.json").write_text(
        '{"projects": {}, "numStartups": 3}', encoding="utf-8")
    got = account.resolve_account_email({}, env={}, home=tmp_path)
    assert got is None


def test_email_anchored_after_oauth_account(tmp_path):
    # A decoy emailAddress BEFORE oauthAccount must not shadow the real one.
    _reset_cache()
    (tmp_path / ".claude.json").write_text(
        '{"emailAddress": "decoy@x.com",'
        ' "oauthAccount": {"emailAddress": "real@x.com"}}',
        encoding="utf-8")
    got = account.resolve_account_email({}, env={}, home=tmp_path)
    assert got == "real@x.com"


def test_email_memoized_and_refreshes(tmp_path):
    _reset_cache()
    p = tmp_path / ".claude.json"
    _write_claude_json(p, email="one@x.com")
    assert account.resolve_account_email({}, env={}, home=tmp_path) == "one@x.com"
    # Rewrite with a new email + bump mtime so the (mtime,size) sig changes.
    import os
    _write_claude_json(p, email="two@example.org")
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    assert account.resolve_account_email({}, env={}, home=tmp_path) == "two@example.org"


def test_resolve_never_raises_on_garbage(tmp_path):
    _reset_cache()
    # transcript_path is a non-path type; must not raise.
    got = account.resolve_account_email(
        {"transcript_path": 12345}, env={}, home=tmp_path)
    assert got is None


# --- config -------------------------------------------------------------------

def test_show_email_defaults_on():
    assert config.StatusbarConfig().show_email is True


def test_show_email_roundtrip(tmp_path):
    p = tmp_path / "cfg.json"
    config.save_config(config.StatusbarConfig(show_email=True), p)
    assert config.load_config(p).show_email is True


def test_set_value_show_email(tmp_path):
    p = tmp_path / "cfg.json"
    assert config.set_value("show_email", "on", p).show_email is True
    assert config.set_value("show_email", "off", p).show_email is False


def test_show_email_keys_registered():
    assert "show_email" in config.VALID_KEYS
    assert "show_email" in config._BOOL_KEYS


# --- identity-line rendering --------------------------------------------------

def test_email_chip_on_identity_line_nocolor():
    s = render_identity_line(_info(), theme=THEME, dirty=False,
                             email_text=EMAIL, use_color=False)
    assert f"· 👤 {EMAIL}" in s


def test_email_chip_before_version_nocolor():
    s = render_identity_line(_info(), theme=THEME, dirty=False,
                             email_text=EMAIL, version_text="9.9.9",
                             use_color=False)
    assert s.index("👤") < s.index("· v9.9.9")


def test_email_chip_color_contains_email():
    s = render_identity_line(_info(), theme=THEME, dirty=False,
                             email_text=EMAIL, use_color=True)
    assert EMAIL in s and "👤" in s


def test_no_email_text_no_chip():
    s = render_identity_line(_info(), theme=THEME, dirty=False, use_color=False)
    assert "👤" not in s


# --- full render plumbing -----------------------------------------------------

_BASE = dict(msgs_pct=10, weekly_pct=5, reset_5h="1h00m", reset_7d="2d00h",
             model="Test", lang_body="", use_color=False, theme=THEME)


def test_render_passes_email_to_identity_line():
    out = render("classic", **_BASE,
                 show_project_branch=True, identity=_info(),
                 identity_dirty=False, email_text=EMAIL)
    assert any("⤷" in ln and f"👤 {EMAIL}" in ln for ln in out.split("\n"))


def test_render_email_absorbed_when_identity_off():
    # email rides the identity line; with the identity line off it's dropped,
    # never leaked into the primary bar.
    out = render("classic", **_BASE, email_text=EMAIL)
    assert "👤" not in out


def test_render_without_email_unchanged():
    base = render("classic", **_BASE, show_project_branch=True,
                  identity=_info(), identity_dirty=False)
    assert "👤" not in base
