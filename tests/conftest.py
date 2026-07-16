import pytest


@pytest.fixture(autouse=True)
def _isolate_rate_latest(tmp_path, monkeypatch):
    """Keep every test off the real ~/.cache/claude-statusbar/rate_latest.json.

    predict.reconcile_account (reached via forecast() and core.main's render
    path) reads+writes that shared account-global store. Without isolation tests
    would pollute the developer's real cache and leak state into each other.
    Each test gets its own throwaway path."""
    # Hermetic env: never let the developer's real multi-account CLAUDE_CONFIG_DIR
    # leak into tests. Phase 12 made core.main() resolve the per-session account
    # from _effective_env (os.environ), so a test that drives core.main() without
    # isolating this var would read the real ~/.claude-account*/.claude.json.
    # Tests that WANT a config dir set it explicitly (monkeypatch.setenv or the
    # env= param), which runs after this autouse fixture.
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    try:
        import claude_statusbar.predict as predict
        monkeypatch.setattr(predict, "_LATEST_PATH", tmp_path / "rate_latest.json")
        monkeypatch.setattr(predict, "_PROJECTION_PATH", tmp_path / "rate_projection.json")
        # Stores are account-keyed (suffix from ~/.claude.json); pin the
        # ZERO-ARG (legacy) resolution to "unknown" so tests get the exact
        # paths they monkeypatch, independent of the developer's real login.
        # Account-switch tests override this stub locally. Per-session calls
        # (predict.account_id(stdin, env=, home=) — Phase 12) are NOT pinned:
        # they pass through to the real resolver so tests exercising that
        # per-session resolution logic see genuine behavior, not a stub.
        _real_account_id = predict.account_id

        def _pinned_account_id(stdin=None, **kwargs):
            if stdin is None:
                return None
            return _real_account_id(stdin, **kwargs)

        monkeypatch.setattr(predict, "account_id", _pinned_account_id)
    except Exception:
        pass
