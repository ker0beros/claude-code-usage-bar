"""Regression: search-credit cache must get a refresh chance from
render_thin's own LIVE process environment on every tick, not only from the
shared daemon's env.

Root cause (see .planning/debug/search-credit-bars-missing.md): the daemon's
os.environ is frozen at its own spawn time (daemon.py's subprocess.Popen
inherits whatever env its parent had at that exact moment and never updates
afterward). Since the daemon serves virtually every statusline render after
warmup, a FIRECRAWL_API_KEY / TAVILY_API_KEY exported or rotated after the
daemon started was previously invisible forever — the bars would render at
best once (a lucky inline-fallback tick) and then go permanently stale.

render_thin.py runs fresh on every `cs render` invocation, so its os.environ
always reflects whatever process spawned it right now. These tests pin down
that render_thin._maybe_refresh_search_credits() is called unconditionally
(fast daemon-cat path AND inline fallback alike) and always uses render_thin's
own live os.environ — never a stale/frozen snapshot.
"""
import json
import os
import time
from pathlib import Path

from claude_statusbar import config, provider_usage, render_thin


def _setup_session_paths(monkeypatch, tmp_path: Path):
    """Common helper: rebase render_thin's cache + sessions root to tmp_path
    (mirrors tests/test_daemon.py's helper of the same name)."""
    monkeypatch.setattr(render_thin, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(render_thin, "_SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(render_thin, "_LEGACY_STDIN_CACHE", tmp_path / "last_stdin.json")
    monkeypatch.setattr(render_thin, "_USER_SETTINGS", tmp_path / "no-such-settings.json")


# ---------------------------------------------------------------------------
# _maybe_refresh_search_credits() unit behavior
# ---------------------------------------------------------------------------
def test_noop_when_toggle_off(monkeypatch):
    monkeypatch.setattr(config, "load_config",
                        lambda *a, **kw: config.StatusbarConfig(show_search_credits=False))
    calls = []
    monkeypatch.setattr(provider_usage, "ensure_fresh", lambda env: calls.append(env))
    render_thin._maybe_refresh_search_credits()
    assert calls == [], "must not touch provider_usage at all when the toggle is off"


def test_calls_ensure_fresh_with_this_process_live_env_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "load_config",
                        lambda *a, **kw: config.StatusbarConfig(show_search_credits=True))
    calls = []
    monkeypatch.setattr(provider_usage, "ensure_fresh", lambda env: calls.append(env))
    monkeypatch.setenv("FIRECRAWL_API_KEY", "live-key-only-in-this-process")

    render_thin._maybe_refresh_search_credits()

    assert len(calls) == 1
    assert calls[0].get("FIRECRAWL_API_KEY") == "live-key-only-in-this-process", (
        "must pass THIS process's os.environ (live), not some other snapshot"
    )


def test_swallows_config_errors(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("config blew up")
    monkeypatch.setattr(config, "load_config", _boom)
    render_thin._maybe_refresh_search_credits()  # must not raise


def test_swallows_ensure_fresh_errors(monkeypatch):
    monkeypatch.setattr(config, "load_config",
                        lambda *a, **kw: config.StatusbarConfig(show_search_credits=True))
    monkeypatch.setattr(provider_usage, "ensure_fresh",
                        lambda env: (_ for _ in ()).throw(RuntimeError("network blew up")))
    render_thin._maybe_refresh_search_credits()  # must not raise


# ---------------------------------------------------------------------------
# render() must call it on BOTH the fast (daemon-cat) and slow (fallback)
# paths — the fast path is the one that previously skipped it entirely,
# since it never touches core.py at all.
# ---------------------------------------------------------------------------
def test_render_fast_path_still_refreshes_search_credits(monkeypatch, tmp_path: Path, capsys):
    """THE key regression test: when the daemon's pre-rendered output is
    fresh, render() takes the fast cat-file path and never imports core.py —
    so core.py's own ensure_fresh(os.environ) call never fires on this tick.
    Without the render_thin-side call, a daemon spawned before a key was
    exported could never discover it. This must still fire every tick."""
    _setup_session_paths(monkeypatch, tmp_path)
    sid = "search-credits-fast"
    sdir = tmp_path / "sessions" / sid
    sdir.mkdir(parents=True)
    (sdir / "rendered.ansi").write_text("FAKE BAR\n", encoding="utf-8")
    (sdir / "rendered.meta.json").write_text(json.dumps({
        "generated_at": time.time(),
        "stale_after_seconds": 5.0,
    }), encoding="utf-8")

    payload = json.dumps({"session_id": sid}).encode()
    monkeypatch.setattr(render_thin, "_consume_stdin", lambda: payload)

    refreshed = []
    monkeypatch.setattr(render_thin, "_maybe_refresh_search_credits",
                        lambda: refreshed.append(True))

    rc = render_thin.render()
    out = capsys.readouterr().out

    assert rc == 0
    assert out == "FAKE BAR\n"
    assert refreshed == [True], (
        "fast (daemon-cat) path must still trigger a live-env search-credit refresh"
    )


def test_render_fallback_path_also_refreshes_search_credits(monkeypatch, tmp_path: Path):
    _setup_session_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(render_thin, "_signal_outdated_daemon", lambda meta: None)
    monkeypatch.setattr(render_thin, "_spawn_daemon_async", lambda: None)
    monkeypatch.setattr(render_thin, "_fallback_inline", lambda: 0)

    refreshed = []
    monkeypatch.setattr(render_thin, "_maybe_refresh_search_credits",
                        lambda: refreshed.append(True))

    rc = render_thin.render()

    assert rc == 0
    assert refreshed == [True]


# ---------------------------------------------------------------------------
# End-to-end (real provider_usage, not mocked): the live process's env sees
# a key a "frozen" snapshot never had.
# ---------------------------------------------------------------------------
def test_live_env_sees_key_that_a_frozen_snapshot_would_miss(monkeypatch, tmp_path: Path):
    """Models the actual bug mechanism directly: a fingerprinted cache entry
    keyed off a key that exists ONLY in THIS process's os.environ (as
    render_thin always has) must be visible via os.environ, while a
    simulated frozen snapshot (standing in for a daemon spawned before the
    key existed) sees nothing for that provider — proving the daemon's
    env-freeze is exactly what silently hides the bar."""
    monkeypatch.setattr(provider_usage, "_cache_root", lambda: tmp_path)

    live_key = "fc-live-key-only-in-this-process"
    monkeypatch.setenv("FIRECRAWL_API_KEY", live_key)
    fp = provider_usage.fingerprint("firecrawl", live_key)
    provider_usage.write_cache_atomic(fp, {
        "ts": time.time(), "supported": True,
        "pct": 55.0, "remaining": 550, "limit": 1000,
    })

    # Simulate the daemon's frozen environment: spawned before the key was
    # ever exported, so it's simply absent — not merely a different value.
    frozen_daemon_env = {"PATH": "/usr/bin"}
    assert provider_usage.segments(frozen_daemon_env) == [], (
        "a frozen env lacking the key must never see the bar (this is the bug)"
    )

    # render_thin, by contrast, always reads its OWN (live) os.environ.
    live_segments = provider_usage.segments(os.environ)
    assert len(live_segments) == 1
    assert live_segments[0]["label"] == "fc"
    assert live_segments[0]["pct"] == 55.0

    # And render_thin's own refresh call, wired through config + the live
    # env, must not error and must leave the already-fresh entry alone (no
    # spurious re-probe/network spawn — cache is fresh so ensure_fresh no-ops).
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "cfg.json")
    (tmp_path / "cfg.json").write_text(
        json.dumps({"show_search_credits": True}), encoding="utf-8")

    before = provider_usage.read_cache(fp)
    render_thin._maybe_refresh_search_credits()
    after = provider_usage.read_cache(fp)
    assert after == before, "already-fresh cache entry must not be touched"
