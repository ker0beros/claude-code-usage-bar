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

--- Follow-up bug: flash-then-vanish (see .planning/debug/search-bars-flash-vanish.md) ---

The refresh above only fixed the CACHE. It did NOT fix the DISPLAY: a fresh
cache is useless if provider_usage.segments() is called from inside the
shared daemon (core.main() runs in the daemon's own process — see
daemon.py's _render_payload), because segments() locates a provider's cache
entry via fingerprint(name, key) and the daemon's os.environ still lacks the
raw key. Symptom: a brand-new session's first tick has no per-session daemon
output yet, so it renders inline (render_thin's own live env) and the bars
flash correctly — then the long-lived, iTerm2-restart-persisting daemon
renders that session on its next tick using its OWN keyless env, permanently
overwriting the good render with an empty one. Fix: render_thin stamps a
non-secret per-provider fingerprint (a one-way hash — never the raw key,
see provider_usage.fingerprint()) into the per-session payload under
`_cs_search_fps`; provider_usage.segments() accepts this as a fallback
lookup key (`session_fps=`) when the raw key is absent from `env`, so the
daemon can still locate the cache entry the render_thin process already
refreshed. The tests below pin down: (a) the fingerprint stamp is computed
correctly and never leaks the raw key, (b) the stamp is only added when the
feature is enabled, and (c) segments()/core.main() actually render the bar
when given a keyless env + the session-stamped fingerprint — the direct
regression guard for this bug.
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


# ---------------------------------------------------------------------------
# provider_usage.session_fingerprints() — the non-secret stamp
# ---------------------------------------------------------------------------
def test_session_fingerprints_matches_fingerprint_and_never_leaks_raw_key(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-super-secret-123")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    fps = provider_usage.session_fingerprints(os.environ)

    assert fps == {"firecrawl": provider_usage.fingerprint(
        "firecrawl", "fc-super-secret-123")}
    assert "tavily" not in fps
    assert "fc-super-secret-123" not in json.dumps(fps), (
        "the stamped map must be the one-way hash, never the raw key"
    )


def test_session_fingerprints_empty_when_no_keys_present():
    assert provider_usage.session_fingerprints({"PATH": "/usr/bin"}) == {}


# ---------------------------------------------------------------------------
# render_thin._inject_session_env() stamps `_cs_search_fps`
# ---------------------------------------------------------------------------
def test_inject_session_env_stamps_search_fingerprint_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "load_config",
                        lambda *a, **kw: config.StatusbarConfig(show_search_credits=True))
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-live-key-999")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    payload = json.dumps({"session_id": "s"}).encode()
    out = render_thin._inject_session_env(payload)
    stamped = json.loads(out.decode("utf-8"))

    assert stamped["_cs_search_fps"] == {
        "firecrawl": provider_usage.fingerprint("firecrawl", "fc-live-key-999")
    }
    assert "fc-live-key-999" not in out.decode("utf-8"), (
        "the raw key must never be written into the persisted stdin payload"
    )


def test_inject_session_env_omits_search_fps_when_toggle_off(monkeypatch):
    monkeypatch.setattr(config, "load_config",
                        lambda *a, **kw: config.StatusbarConfig(show_search_credits=False))
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-live-key-999")

    payload = json.dumps({"session_id": "s"}).encode()
    out = render_thin._inject_session_env(payload)
    stamped = json.loads(out.decode("utf-8"))

    assert "_cs_search_fps" not in stamped


def test_inject_session_env_omits_search_fps_when_no_keys_present(monkeypatch):
    monkeypatch.setattr(config, "load_config",
                        lambda *a, **kw: config.StatusbarConfig(show_search_credits=True))
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    payload = json.dumps({"session_id": "s"}).encode()
    out = render_thin._inject_session_env(payload)
    stamped = json.loads(out.decode("utf-8"))

    assert "_cs_search_fps" not in stamped


# ---------------------------------------------------------------------------
# THE key regression: segments() must find the bar via a session-stamped
# fingerprint even when the calling env (standing in for the daemon's frozen
# os.environ) has no keys at all. Without this, a fresh cache is invisible to
# the daemon-rendered output, and the bars "flash then vanish for good."
# ---------------------------------------------------------------------------
def test_segments_frozen_env_with_session_fps_still_shows_bar(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_usage, "_cache_root", lambda: tmp_path)

    live_key = "fc-only-ever-in-render-thins-live-env"
    fp = provider_usage.fingerprint("firecrawl", live_key)
    provider_usage.write_cache_atomic(fp, {
        "ts": time.time(), "supported": True,
        "pct": 42.0, "remaining": 420, "limit": 1000,
    })

    # Simulate the daemon's frozen environment: no FIRECRAWL_API_KEY at all.
    frozen_daemon_env = {"PATH": "/usr/bin"}
    assert provider_usage.segments(frozen_daemon_env) == [], (
        "sanity: without the session stamp, a keyless env still sees nothing"
    )

    # render_thin computed this fingerprint from its own live env and
    # stamped it into the per-session payload (`_cs_search_fps`).
    session_fps = {"firecrawl": fp}
    segs = provider_usage.segments(frozen_daemon_env, session_fps=session_fps)

    assert len(segs) == 1
    assert segs[0]["label"] == "fc"
    assert segs[0]["pct"] == 42.0


def test_segments_session_fps_ignored_when_cache_stale(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_usage, "_cache_root", lambda: tmp_path)
    fp = provider_usage.fingerprint("firecrawl", "some-key")
    provider_usage.write_cache_atomic(fp, {
        "ts": time.time() - provider_usage.TTL_SECONDS - 5,
        "supported": True, "pct": 42.0,
    })
    segs = provider_usage.segments({}, session_fps={"firecrawl": fp})
    assert segs == [], "a stale cache entry must not render even via the session stamp"


def test_segments_raw_key_in_env_still_wins_over_session_fps(tmp_path, monkeypatch):
    """If both are available, the raw key (more authoritative — this process's
    own live env) takes precedence; the session stamp is purely a fallback."""
    monkeypatch.setattr(provider_usage, "_cache_root", lambda: tmp_path)
    real_key = "fc-real-current-key"
    fp = provider_usage.fingerprint("firecrawl", real_key)
    provider_usage.write_cache_atomic(fp, {
        "ts": time.time(), "supported": True, "pct": 77.0,
    })
    env = {"FIRECRAWL_API_KEY": real_key}
    # A bogus/stale stamp for a DIFFERENT (e.g. rotated-away) key must be ignored.
    stale_fps = {"firecrawl": provider_usage.fingerprint("firecrawl", "old-rotated-key")}
    segs = provider_usage.segments(env, session_fps=stale_fps)
    assert len(segs) == 1
    assert segs[0]["pct"] == 77.0


# ---------------------------------------------------------------------------
# End-to-end through core.main(): the actual daemon-render scenario. os.environ
# lacks the key (simulating the frozen daemon); stdin carries render_thin's
# `_cs_search_fps` stamp. The bar must still render.
# ---------------------------------------------------------------------------
def test_core_main_renders_bar_from_session_stamp_when_os_environ_is_keyless(
    tmp_path, monkeypatch, capsys
):
    import io
    import sys

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    live_key = "fc-key-only-render-thin-ever-saw"
    fp = provider_usage.fingerprint("firecrawl", live_key)
    provider_usage.write_cache_atomic(fp, {
        "ts": time.time(), "supported": True,
        "pct": 91.0, "remaining": 910, "limit": 1000,
    })

    (tmp_path / ".claude").mkdir(parents=True)
    cfg = tmp_path / ".claude" / "claude-statusbar.json"
    cfg.write_text(json.dumps({
        "show_project_branch": False, "show_cache_age": False,
        "show_todos": False, "show_mode": False, "show_context": False,
        "show_search_credits": True,
    }), encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", cfg)

    # Payload models exactly what render_thin persists for the daemon to
    # consume: NO raw key anywhere, only the non-secret fingerprint stamp.
    payload = json.dumps({
        "session_id": "s", "transcript_path": "/n.jsonl",
        "model": {"id": "o", "display_name": "Opus 4.8"},
        "rate_limits": {
            "five_hour": {"used_percentage": 42, "resets_at": 9999999999},
            "seven_day": {"used_percentage": 18, "resets_at": 9999999999},
        },
        "_cs_env": {"ANTHROPIC_BASE_URL": "", "CS_API_MODE": "auto"},
        "_cs_search_fps": {"firecrawl": fp},
    })
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))

    from claude_statusbar.core import main
    main(use_color=False, _suppress_side_effects=True)
    out = capsys.readouterr().out
    assert "fc[" in out and "91%" in out, (
        "this is the actual daemon-render scenario: os.environ has no key, "
        "only the session-stamped fingerprint — the bar must still render "
        f"(got: {out!r})"
    )
