"""Phase 12: per-account rate-limit store isolation (Nyquist Wave 0 — tests first).

Live incident 2026-07-16: `predict._read_account_id()` hardcodes `~/.claude.json`
and ignores `CLAUDE_CONFIG_DIR`/`transcript_path`, so every logged-in account
resolves to whichever `accountUuid` sits in the default `~/.claude.json` and all
accounts write into ONE shared reconcile/projection store. Anthropic clock-aligns
the 5h window, so two different accounts share the same `resets_at` bucket; the
monotonic-up healing rule then pins that bucket to the cross-account MAX reading
(account2's real 50% renders account1's 100%).

This file authors the WHOLE isolation suite (12 tests) up front, against the
target predict.py API that lands in 12-02 (resolution/keying/threading) and
12-03 (core.py wiring + the e2e regression). Every test here is expected to be
RED (fail or error) against the CURRENT predict.py/core.py — that is the
intended Nyquist Wave 0 outcome, not a bug in this file. Do NOT mark this plan
done on green; `--collect-only` exiting 0 with all 12 node-ids listed is the
verification gate for this plan.

Target API this suite pins (does not exist yet, added in 12-02/12-03):
  - predict.account_id(stdin=None, *, env=None, home=None) — per-session resolver
  - predict._read_keyed_account_id(path) -> Optional[str]
  - predict._account_path(base, aid=_UNSET) — sentinel tri-state (omitted / None / uuid)
  - predict._latest_path(aid=_UNSET) / predict._projection_path(aid=_UNSET)
  - predict.reconcile_account(..., account_uuid=_UNSET)
  - predict.projection(..., account_uuid=_UNSET) — including regime_changed_at(path=...)
  - predict._projection_result_key(u5, r5, u7, r7, account_uuid=_UNSET)
  - core.py resolves `_resolved_account_uuid` once per render and threads it through
    reconcile_account/projection/quota_cache_status.

Fixture idioms copied from tests/test_account.py (_write_claude_json) and
tests/test_core_projection.py (_payload_with_limits, _write_config). The
no-network/subprocess prohibition test reuses tests/test_import_perf.py's
`_list_imports_for` harness directly (tests/ has __init__.py so the cross-test
import works) rather than reinventing an import-graph check.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path

import claude_statusbar.predict as predict


# --- shared fixture helpers -----------------------------------------------
# Copied verbatim in shape from tests/test_account.py's _write_claude_json and
# tests/test_core_projection.py's _payload_with_limits / _write_config.

def _write_claude_json(path: Path, uuid: str = "abc-123",
                       access_token: str | None = None,
                       email: str | None = None) -> None:
    """Write a minimal .claude.json with an oauthAccount block.

    Optional decoy `access_token`/`email` fields let the no-secret-read
    prohibition test assert the keying reader extracts ONLY accountUuid.
    """
    oauth: dict = {"accountUuid": uuid}
    if access_token is not None:
        oauth["accessToken"] = access_token
    if email is not None:
        oauth["emailAddress"] = email
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "someOtherKey": 1,
        "oauthAccount": oauth,
    }), encoding="utf-8")


def _payload_with_limits(session_id, used_5h, reset_5h, used_7d, reset_7d,
                         transcript_path: str = "/n.jsonl"):
    return json.dumps({
        "session_id": session_id,
        "transcript_path": transcript_path,
        "model": {"id": "o", "display_name": "Opus 4.8"},
        "rate_limits": {
            "five_hour": {"used_percentage": used_5h, "resets_at": reset_5h},
            "seven_day": {"used_percentage": used_7d, "resets_at": reset_7d},
        },
    })


def _write_config(tmp_path, **values):
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    base = {
        "show_projection": False,
        "show_forecast": False,
        "show_project_branch": False,
        "show_cache_age": False,
        "show_todos": False,
    }
    base.update(values)
    path = tmp_path / ".claude" / "claude-statusbar.json"
    path.write_text(json.dumps(base), encoding="utf-8")
    return path


# --- Task 1: resolution + keying + store-path unit tests -------------------

def test_account_id_resolves_from_transcript_over_home_json(tmp_path, monkeypatch):
    """R1: transcript_path beats whatever sits in $HOME/.claude.json."""
    home_json = tmp_path / ".claude.json"
    _write_claude_json(home_json, uuid="wrong-home-uuid")  # decoy — must be ignored
    # Legacy hardcoded resolver path — unrelated to the new per-session API,
    # kept patched so it can never accidentally leak the real machine's file.
    monkeypatch.setattr(predict, "_CLAUDE_JSON_PATH", home_json)

    acct1_dir = tmp_path / ".claude-account1"
    _write_claude_json(acct1_dir / ".claude.json",
                       uuid="e1605250-1111-2222-3333-444455556666")
    tp = acct1_dir / "projects" / "-enc-" / "sid.jsonl"
    stdin = {"transcript_path": str(tp)}

    got = predict.account_id(stdin, env={}, home=tmp_path)
    assert got == "e1605250-1111-2222-3333-444455556666"


def test_store_paths_carry_session_uuid(tmp_path, monkeypatch):
    """R4: both _latest_path() and _projection_path() carry the resolved uuid."""
    monkeypatch.setattr(predict, "_LATEST_PATH", tmp_path / "rate_latest.json")
    monkeypatch.setattr(predict, "_PROJECTION_PATH", tmp_path / "rate_projection.json")
    aid = "e1605250-1111-2222-3333-444455556666"

    assert aid[:12] in predict._latest_path(aid).name
    assert aid[:12] in predict._projection_path(aid).name


def test_unresolvable_session_uses_legacy_path(tmp_path, monkeypatch):
    """R5a: empty stdin, no CLAUDE_CONFIG_DIR, no resolvable accountUuid ->
    None, and the store path is the exact legacy unsuffixed path (unchanged)."""
    monkeypatch.setattr(predict, "_LATEST_PATH", tmp_path / "rate_latest.json")

    got = predict.account_id({}, env={}, home=tmp_path)
    assert got is None
    assert predict._latest_path(got) == predict._LATEST_PATH


def test_named_dir_without_own_json_does_not_borrow_home(tmp_path, monkeypatch):
    """R5b (sharpest edge): a named config dir lacking its OWN .claude.json
    must never fall back to $HOME/.claude.json's uuid — that's exactly the
    collision this phase closes."""
    home_json = tmp_path / ".claude.json"
    _write_claude_json(home_json, uuid="home-account-uuid")
    named_dir = tmp_path / ".claude-accountX"  # exists, but NO .claude.json
    named_dir.mkdir()

    got = predict.account_id({}, env={"CLAUDE_CONFIG_DIR": str(named_dir)},
                             home=tmp_path)
    assert got is None  # must NOT be "home-account-uuid"

    monkeypatch.setattr(predict, "_LATEST_PATH", tmp_path / "rate_latest.json")
    assert predict._latest_path(got) == tmp_path / "rate_latest.json"


def test_same_account_two_dirs_shares_store(tmp_path, monkeypatch):
    """Identity edge (no over-isolation): the SAME real uuid in two different
    config dirs resolves to the SAME store filename."""
    monkeypatch.setattr(predict, "_LATEST_PATH", tmp_path / "rate_latest.json")
    uuid = "e1605250-1111-2222-3333-444455556666"

    dir_a = tmp_path / ".claude-account1"
    dir_b = tmp_path / ".claude-account2"
    _write_claude_json(dir_a / ".claude.json", uuid=uuid)
    _write_claude_json(dir_b / ".claude.json", uuid=uuid)
    tp_a = dir_a / "projects" / "-enc-" / "sidA.jsonl"
    tp_b = dir_b / "projects" / "-enc-" / "sidB.jsonl"

    aid_a = predict.account_id({"transcript_path": str(tp_a)}, env={}, home=tmp_path)
    aid_b = predict.account_id({"transcript_path": str(tp_b)}, env={}, home=tmp_path)

    assert aid_a == aid_b == uuid
    assert predict._latest_path(aid_a) == predict._latest_path(aid_b)


def test_account_path_three_way_branch(tmp_path, monkeypatch):
    """Sentinel landmine: _account_path's three branches (omitted / None /
    uuid) must each produce a DIFFERENT path — collapsing any two of them
    either breaks R5b (home-borrow) or breaks every existing zero-arg caller."""
    base = tmp_path / "rate_latest.json"
    monkeypatch.setattr(predict, "account_id", lambda: "legacy-uuid")  # zero-arg legacy resolver

    assert predict._account_path(base) == base.with_name("rate_latest.legacy-uuid.json")
    assert predict._account_path(base, aid=None) == base
    assert predict._account_path(base, aid="new-uuid") == base.with_name("rate_latest.new-uuid.json")


def test_keying_reader_reads_only_account_uuid(tmp_path):
    """Prohibition (no secret): the reader must extract ONLY accountUuid, never
    an adjacent accessToken/emailAddress in the same oauthAccount block."""
    p = tmp_path / ".claude.json"
    _write_claude_json(p, uuid="abc-123",
                       access_token="SECRET-SHOULD-NEVER-BE-TOUCHED",
                       email="a@b.c")

    result = predict._read_keyed_account_id(p)
    assert result == "abc-123"
    assert "SECRET-SHOULD-NEVER-BE-TOUCHED" not in str(result)


# --- Task 2: threading/landmine + prohibition-import + e2e regression ------

def test_projection_threads_account_into_regime_check(tmp_path, monkeypatch):
    """Landmine: projection() calls regime_changed_at() internally (predict.py
    ~1185) with NO path arg today, defaulting to the (wrong, non-per-account)
    legacy _latest_path(). It must receive the per-account reconcile path."""
    monkeypatch.setattr(predict, "_LATEST_PATH", tmp_path / "rate_latest.json")
    monkeypatch.setattr(predict, "_PROJECTION_PATH", tmp_path / "rate_projection.json")
    aid = "e1605250-1111-2222-3333-444455556666"
    captured: dict = {}

    def _fake_regime_changed_at(path=None):
        captured["path"] = path
        return None

    monkeypatch.setattr(predict, "regime_changed_at", _fake_regime_changed_at)

    predict.projection(10.0, 5000.0, 8.0, 9000.0, now=0.0, session_id="s",
                       account_uuid=aid)

    assert captured.get("path") == predict._latest_path(aid)
    assert captured.get("path") != predict._latest_path(None)


def test_projection_result_cache_keys_by_account(monkeypatch):
    """Landmine: the 1s result cache key must differ per account, or account
    B's render within 1s of account A's could receive A's cached (p5, p7)."""
    monkeypatch.setattr(predict, "_PROJECTION_RESULT_CACHE", None)

    key_a = predict._projection_result_key(10.0, 5000.0, 8.0, 9000.0,
                                           account_uuid="acct-a")
    key_b = predict._projection_result_key(10.0, 5000.0, 8.0, 9000.0,
                                           account_uuid="acct-b")

    assert key_a is not None
    assert key_b is not None
    assert key_a != key_b


def test_predict_module_imports_no_network_or_subprocess():
    """Prohibition: predict.py must stay stdlib-only, no network/subprocess —
    reuses the existing tests/test_import_perf.py harness verbatim.

    Note: bare "urllib" is deliberately excluded from the banned set. `pathlib`
    itself transitively imports `urllib.parse` (a pure string-parsing module,
    no network capability, no `socket`/`subprocess` underneath) on this
    Python version — confirmed by direct measurement: a bare `import json,
    math, os; from datetime import datetime; from pathlib import Path`
    already pulls in `urllib`/`urllib.parse` with zero predict.py code
    involved. Banning the parent package name would false-positive on that
    pre-existing, unrelated stdlib artifact. The actual network-capable
    submodule (`urllib.request`) is what's banned, alongside `socket` and
    `subprocess`.
    """
    from tests.test_import_perf import _list_imports_for

    loaded = _list_imports_for("claude_statusbar.predict")
    banned = {"subprocess", "socket", "urllib.request"}
    leaked = sorted(banned & loaded)
    assert not leaked, f"predict.py must stay network/subprocess-free: {leaked}"


def test_no_destructive_fs_ops_on_existing_stores(tmp_path, monkeypatch):
    """Prohibition (fix-forward only): the new keying path must never delete,
    move, or rename a pre-existing rate_latest*/rate_projection* file. The
    store's OWN atomic-write os.replace on ITS OWN target is fine — only
    scope the assertion to the pre-existing `stale` file specifically."""
    stale = tmp_path / "rate_latest.stale-uuid.json"
    stale.write_text("{}", encoding="utf-8")
    calls = []

    monkeypatch.setattr(os, "unlink", lambda *a, **k: calls.append(("unlink", a)))
    monkeypatch.setattr(os, "replace", lambda *a, **k: calls.append(("replace", a)))
    monkeypatch.setattr(Path, "rename", lambda *a, **k: calls.append(("rename", a)))
    monkeypatch.setattr(predict, "_LATEST_PATH", tmp_path / "rate_latest.json")

    predict.reconcile_account(10.0, 5000.0, 8.0, 9000.0, now=0.0,
                              account_uuid="new-account")

    assert not any(
        stale.name in str(c[1]) for c in calls
    ), f"destructive fs op touched the pre-existing stale store: {calls}"


def test_two_accounts_share_5h_reset_render_own_values(tmp_path, monkeypatch, capsys):
    """THE regression test (R3): a true core.main() end-to-end reproduction of
    the live 2026-07-16 cross-account collision. Two accounts share an
    IDENTICAL clock-aligned 5h resets_at with different real used_percentage
    (100 vs 50); each render must show its OWN value.

    Deviation from the literal historical epoch in 12-RESEARCH.md/12-SPEC.md
    (1784191800): resets_5h is computed as `time.time() + 3600` instead of a
    hardcoded epoch. reconcile_account()'s `_reset_plausible` guard rejects any
    resets_at more than 60s in the past relative to wall-clock `now` (used to
    reject a poisoned far-future value from permanently winning the monotonic
    merge) — a hardcoded historical literal recedes further into the past
    every day this suite runs and would eventually make the reset implausible,
    silently turning the two reconcile calls into independent passthroughs
    that never share a bucket (a false-negative collision, defeating the
    "FAILS pre-fix" acceptance proof). A wall-clock-relative near-future reset
    keeps the identical-bucket collision deterministic regardless of when the
    suite executes, while preserving the exact defect shape (two accounts,
    one shared clock-aligned 5h bucket, 100 vs 50 real usage).
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_config(tmp_path, show_forecast=False, show_projection=False)
    import claude_statusbar.config as config
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / ".claude" / "claude-statusbar.json")

    # Redirect the shared stores under tmp_path so this test never touches the
    # real machine's cache/config, regardless of which code path (legacy
    # hardcoded resolver pre-fix, or the new per-session resolver post-fix)
    # actually determines the store filename.
    monkeypatch.setattr(predict, "_LATEST_PATH", tmp_path / "cache" / "rate_latest.json")
    monkeypatch.setattr(predict, "_PROJECTION_PATH", tmp_path / "cache" / "rate_projection.json")
    monkeypatch.setattr(predict, "_CLAUDE_JSON_PATH", tmp_path / "does-not-exist-home.json")

    acct1_dir = tmp_path / ".claude-account1"
    acct2_dir = tmp_path / ".claude-account2"
    _write_claude_json(acct1_dir / ".claude.json",
                       uuid="e1605250-1111-2222-3333-444455556666")
    _write_claude_json(acct2_dir / ".claude.json",
                       uuid="c87262ba-1111-2222-3333-444455556666")
    tp1 = acct1_dir / "projects" / "-enc-" / "sid1.jsonl"
    tp2 = acct2_dir / "projects" / "-enc-" / "sid2.jsonl"
    tp1.parent.mkdir(parents=True)
    tp1.touch()
    tp2.parent.mkdir(parents=True)
    tp2.touch()

    now = time.time()
    resets_5h = now + 3600           # IDENTICAL clock-aligned reset — the live collision
    resets_7d_1 = now + 6 * 86400
    resets_7d_2 = now + 4 * 86400

    payload1 = _payload_with_limits("s1", 100.0, resets_5h, 5.0, resets_7d_1,
                                    transcript_path=str(tp1))
    payload2 = _payload_with_limits("s2", 50.0, resets_5h, 3.0, resets_7d_2,
                                    transcript_path=str(tp2))

    from claude_statusbar.core import main

    monkeypatch.setattr(sys, "stdin", io.StringIO(payload1))
    main(use_color=False, _suppress_side_effects=True)
    out1 = capsys.readouterr().out

    monkeypatch.setattr(sys, "stdin", io.StringIO(payload2))
    main(use_color=False, _suppress_side_effects=True)
    out2 = capsys.readouterr().out

    assert "100%" in out1   # account1 sees its own real 100%
    assert "50%" in out2    # account2 sees its own real 50%
    assert "100%" not in out2  # NOT account1's 100% (the live cross-account bug)
