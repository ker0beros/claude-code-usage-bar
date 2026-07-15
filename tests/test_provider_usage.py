"""Search-provider credit bars (show_search_credits): Firecrawl + Tavily
parsing, cache/TTL mechanics, ensure_fresh spawn discipline, and the
render-path (segments()) contract — reads cache only, never spawns, never
opens a socket.
"""
import json
import time

import pytest

from claude_statusbar import provider_usage as pu
from claude_statusbar import _provider_usage_refresh as refresh
from claude_statusbar import progress


def _iso(tmp_path, monkeypatch):
    monkeypatch.setattr(pu, "_cache_root", lambda: tmp_path)


def _stub_responses(monkeypatch, mapping):
    """mapping: dict of url-substring -> json dict (or None for 404/error)."""
    def fake_get(url, key):
        for needle, resp in mapping.items():
            if needle in url:
                return resp
        return None
    monkeypatch.setattr(refresh, "_get_json", fake_get)


# --- provider body parsing (Firecrawl + Tavily) ---

def test_firecrawl_parse_computes_remaining_and_pct(monkeypatch):
    _stub_responses(monkeypatch, {
        "api.firecrawl.dev/v2/team/credit-usage": {
            "data": {"remainingCredits": 820, "planCredits": 1000,
                      "billingPeriodEnd": None}},
    })
    out = refresh._probe_firecrawl("fc-key")
    assert out["remaining"] == 820
    assert out["limit"] == 1000
    assert out["pct"] == pytest.approx(82.0)
    assert out["billing_period_end"] is None


def test_tavily_parse_account_level(monkeypatch):
    _stub_responses(monkeypatch, {
        "api.tavily.com/usage": {"account": {"plan_limit": 1000, "plan_usage": 250}},
    })
    out = refresh._probe_tavily("tv-key")
    assert out["remaining"] == 750
    assert out["limit"] == 1000
    assert out["pct"] == pytest.approx(75.0)


def test_tavily_parse_key_level_fallback(monkeypatch):
    _stub_responses(monkeypatch, {
        "api.tavily.com/usage": {"key": {"limit": 400, "usage": 100}},
    })
    out = refresh._probe_tavily("tv-key")
    assert out["remaining"] == 300
    assert out["limit"] == 400
    assert out["pct"] == pytest.approx(75.0)


def test_tavily_account_present_but_unusable_falls_back_to_key(monkeypatch):
    _stub_responses(monkeypatch, {
        "api.tavily.com/usage": {
            "account": {"plan_limit": 0, "plan_usage": 10},
            "key": {"limit": 200, "usage": 50},
        },
    })
    out = refresh._probe_tavily("tv-key")
    assert out["remaining"] == 150
    assert out["limit"] == 200


# --- omission: missing/zero limit ---

def test_firecrawl_missing_plan_credits_is_unsupported(monkeypatch):
    _stub_responses(monkeypatch, {
        "api.firecrawl.dev/v2/team/credit-usage": {
            "data": {"remainingCredits": 820}},
    })
    assert refresh._probe_firecrawl("fc-key") is None


def test_firecrawl_zero_plan_credits_is_unsupported(monkeypatch):
    _stub_responses(monkeypatch, {
        "api.firecrawl.dev/v2/team/credit-usage": {
            "data": {"remainingCredits": 0, "planCredits": 0}},
    })
    assert refresh._probe_firecrawl("fc-key") is None


def test_tavily_missing_limits_is_unsupported(monkeypatch):
    _stub_responses(monkeypatch, {
        "api.tavily.com/usage": {"account": {}, "key": {}},
    })
    assert refresh._probe_tavily("tv-key") is None


def test_tavily_zero_limit_is_unsupported(monkeypatch):
    _stub_responses(monkeypatch, {
        "api.tavily.com/usage": {"account": {"plan_limit": 0, "plan_usage": 0}},
    })
    assert refresh._probe_tavily("tv-key") is None


# --- prober fail-safe: raise / non-200 / bad JSON / 429 → negative cache, exit 0 ---

def test_main_writes_negative_cache_on_probe_failure(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)

    def _boom(url, key):
        raise OSError("net down")
    monkeypatch.setattr(refresh, "_get_json", _boom)
    monkeypatch.setenv("CS_SEARCH_KEYS", json.dumps({"firecrawl": "fc-key"}))
    rc = refresh.main()
    assert rc == 0
    fp = pu.fingerprint("firecrawl", "fc-key")
    entry = pu.read_cache(fp)
    assert entry["supported"] is False
    assert pu.is_fresh(entry) is True   # negative TTL applies
    assert pu.is_inflight(fp) is False


def test_main_writes_negative_cache_on_non_200(monkeypatch, tmp_path):
    _iso(tmp_path, monkeypatch)
    # _get_json itself returns None for non-200 (mirrors _balance_refresh)
    monkeypatch.setattr(refresh, "_get_json", lambda url, key: None)
    monkeypatch.setenv("CS_SEARCH_KEYS", json.dumps({"tavily": "tv-key"}))
    rc = refresh.main()
    assert rc == 0
    fp = pu.fingerprint("tavily", "tv-key")
    entry = pu.read_cache(fp)
    assert entry["supported"] is False


def test_main_never_raises_on_bad_env_json(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    monkeypatch.setenv("CS_SEARCH_KEYS", "{not json")
    rc = refresh.main()
    assert rc == 0


def test_main_clears_inflight_even_on_failure(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    fp = pu.fingerprint("firecrawl", "fc-key")
    pu.mark_inflight(fp)
    monkeypatch.setattr(refresh, "_get_json",
                        lambda url, key: (_ for _ in ()).throw(ValueError("boom")))
    monkeypatch.setenv("CS_SEARCH_KEYS", json.dumps({"firecrawl": "fc-key"}))
    refresh.main()
    assert pu.is_inflight(fp) is False


def test_main_one_provider_failure_does_not_block_another(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)

    def fake_get(url, key):
        if "firecrawl" in url:
            raise OSError("down")
        if "tavily" in url:
            return {"account": {"plan_limit": 100, "plan_usage": 10}}
        return None
    monkeypatch.setattr(refresh, "_get_json", fake_get)
    monkeypatch.setenv("CS_SEARCH_KEYS", json.dumps(
        {"firecrawl": "fc-key", "tavily": "tv-key"}))
    rc = refresh.main()
    assert rc == 0
    fc_entry = pu.read_cache(pu.fingerprint("firecrawl", "fc-key"))
    tv_entry = pu.read_cache(pu.fingerprint("tavily", "tv-key"))
    assert fc_entry["supported"] is False
    assert tv_entry["supported"] is True
    assert tv_entry["remaining"] == 90


# --- write_cache_atomic writes correct pct entries ---

def test_write_cache_and_is_fresh_positive_ttl(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    fp = pu.fingerprint("firecrawl", "fc-key")
    pu.write_cache_atomic(fp, {"ts": time.time(), "supported": True,
                               "remaining": 820, "limit": 1000, "pct": 82.0})
    entry = pu.read_cache(fp)
    assert entry["pct"] == 82.0
    assert pu.is_fresh(entry) is True


def test_negative_cache_uses_long_ttl(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    fp = pu.fingerprint("tavily", "tv-key")
    now = time.time()
    pu.write_cache_atomic(fp, {"ts": now - pu.TTL_SECONDS - 5, "supported": False})
    entry = pu.read_cache(fp)
    # stale for the positive TTL, but fresh under the negative TTL
    assert pu.is_fresh(entry, now=now) is True


def test_positive_entry_stale_after_positive_ttl(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    fp = pu.fingerprint("firecrawl", "fc-key")
    now = time.time()
    pu.write_cache_atomic(fp, {"ts": now - pu.TTL_SECONDS - 5, "supported": True,
                               "pct": 50.0})
    entry = pu.read_cache(fp)
    assert pu.is_fresh(entry, now=now) is False


# --- fill-color thresholds via progress._balance_fill_rgb (25/10 remaining) ---

def test_fill_color_thresholds_match_balance_semantics():
    theme = progress.get_theme("graphite")
    assert progress._balance_fill_rgb(99.0, theme) == theme.s_ok
    assert progress._balance_fill_rgb(20.0, theme) == theme.s_warn
    assert progress._balance_fill_rgb(5.0, theme) == theme.s_hot


# --- segments(): PROVIDERS order, only fresh+supported+computable ---

def test_segments_includes_only_fresh_supported_computable(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    env = {"FIRECRAWL_API_KEY": "fc-key", "TAVILY_API_KEY": "tv-key"}
    fc_fp = pu.fingerprint("firecrawl", "fc-key")
    tv_fp = pu.fingerprint("tavily", "tv-key")
    pu.write_cache_atomic(fc_fp, {"ts": time.time(), "supported": True,
                                  "remaining": 820, "limit": 1000, "pct": 82.0})
    pu.write_cache_atomic(tv_fp, {"ts": time.time(), "supported": False})
    segs = pu.segments(env)
    assert len(segs) == 1
    assert segs[0]["label"] == "fc"
    assert segs[0]["pct"] == 82.0
    assert segs[0]["text"] == "fc 82%"


def test_segments_preserves_providers_order(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    env = {"FIRECRAWL_API_KEY": "fc-key", "TAVILY_API_KEY": "tv-key"}
    fc_fp = pu.fingerprint("firecrawl", "fc-key")
    tv_fp = pu.fingerprint("tavily", "tv-key")
    pu.write_cache_atomic(tv_fp, {"ts": time.time(), "supported": True,
                                  "remaining": 750, "limit": 1000, "pct": 75.0})
    pu.write_cache_atomic(fc_fp, {"ts": time.time(), "supported": True,
                                  "remaining": 820, "limit": 1000, "pct": 82.0})
    segs = pu.segments(env)
    assert [s["label"] for s in segs] == ["fc", "tv"]


def test_segments_omits_when_key_absent(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    fc_fp = pu.fingerprint("firecrawl", "fc-key")
    pu.write_cache_atomic(fc_fp, {"ts": time.time(), "supported": True,
                                  "remaining": 820, "limit": 1000, "pct": 82.0})
    # key not present in env -> omitted even though cache is fresh+supported
    assert pu.segments({}) == []


def test_segments_omits_stale_entry(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    env = {"FIRECRAWL_API_KEY": "fc-key"}
    fp = pu.fingerprint("firecrawl", "fc-key")
    pu.write_cache_atomic(fp, {"ts": time.time() - pu.TTL_SECONDS - 5,
                               "supported": True, "pct": 82.0})
    assert pu.segments(env) == []


# --- fingerprint: raw key never appears in a written cache file ---

def test_fingerprint_matches_sha1_scheme():
    import hashlib
    expected = hashlib.sha1(b"firecrawl" + b"\x00" + b"secret-key-123").hexdigest()
    assert pu.fingerprint("firecrawl", "secret-key-123") == expected


def test_written_cache_file_never_contains_raw_key(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    raw_key = "sk-super-secret-firecrawl-key-999"
    fp = pu.fingerprint("firecrawl", raw_key)
    pu.write_cache_atomic(fp, {"ts": time.time(), "supported": True,
                               "remaining": 820, "limit": 1000, "pct": 82.0})
    raw_bytes = pu.cache_path_for(fp).read_bytes()
    assert raw_key.encode("utf-8") not in raw_bytes


def test_prober_output_never_persists_raw_key(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    raw_key = "sk-super-secret-tavily-key-777"
    _stub_responses(monkeypatch, {
        "api.tavily.com/usage": {"account": {"plan_limit": 1000, "plan_usage": 250}},
    })
    monkeypatch.setenv("CS_SEARCH_KEYS", json.dumps({"tavily": raw_key}))
    refresh.main()
    fp = pu.fingerprint("tavily", raw_key)
    raw_bytes = pu.cache_path_for(fp).read_bytes()
    assert raw_key.encode("utf-8") not in raw_bytes


# --- pct clamping ---

def test_pct_clamped_to_0_100(monkeypatch):
    _stub_responses(monkeypatch, {
        "api.firecrawl.dev/v2/team/credit-usage": {
            "data": {"remainingCredits": 1500, "planCredits": 1000}},  # overshoot
    })
    out = refresh._probe_firecrawl("fc-key")
    assert out["pct"] == 100.0


def test_pct_clamped_negative_remaining(monkeypatch):
    _stub_responses(monkeypatch, {
        "api.tavily.com/usage": {"account": {"plan_limit": 100, "plan_usage": 150}},
    })
    out = refresh._probe_tavily("tv-key")
    assert out["pct"] == 0.0


# --- ensure_fresh spawn discipline ---

def test_ensure_fresh_spawns_when_stale_and_not_inflight(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    spawned = []

    class _P:
        def __init__(self, *a, **k):
            spawned.append(k.get("env", {}).get("CS_SEARCH_KEYS"))
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", _P)
    pu.ensure_fresh({"FIRECRAWL_API_KEY": "fc-key"})
    assert spawned
    keys = json.loads(spawned[0])
    assert keys == {"firecrawl": "fc-key"}


def test_ensure_fresh_noop_when_fresh(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    fp = pu.fingerprint("firecrawl", "fc-key")
    pu.write_cache_atomic(fp, {"ts": time.time(), "supported": True, "pct": 50.0})
    spawned = []
    import subprocess
    monkeypatch.setattr(subprocess, "Popen",
                        lambda *a, **k: spawned.append("popen"))
    pu.ensure_fresh({"FIRECRAWL_API_KEY": "fc-key"})
    assert not spawned


def test_ensure_fresh_noop_when_inflight(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    fp = pu.fingerprint("firecrawl", "fc-key")
    pu.mark_inflight(fp)
    spawned = []
    import subprocess
    monkeypatch.setattr(subprocess, "Popen",
                        lambda *a, **k: spawned.append("popen"))
    pu.ensure_fresh({"FIRECRAWL_API_KEY": "fc-key"})
    assert not spawned


def test_ensure_fresh_noop_when_no_keys_present(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    spawned = []
    import subprocess
    monkeypatch.setattr(subprocess, "Popen",
                        lambda *a, **k: spawned.append("popen"))
    pu.ensure_fresh({})
    assert not spawned


def test_ensure_fresh_never_raises_on_popen_oserror(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    import subprocess

    def _boom(*a, **k):
        raise OSError("no python found")
    monkeypatch.setattr(subprocess, "Popen", _boom)
    pu.ensure_fresh({"FIRECRAWL_API_KEY": "fc-key"})  # must not raise
    fp = pu.fingerprint("firecrawl", "fc-key")
    assert pu.is_inflight(fp) is False   # cleared after the failed spawn
