"""Search-provider credit segments (``show_search_credits``).

Surfaces remaining API credits for the user's MCP search providers
(Firecrawl, Tavily) as opt-in, per-provider mini fuel-gauge bars — the same
at-a-glance treatment the status line already gives Claude rate limits and
the third-party relay balance.

Fuses two proven in-repo patterns:
  * the sourcing/caching mechanics of ``balance_cache.py`` (fingerprint +
    atomic write + positive/negative TTL + inflight lock), and
  * the opt-in network-signal spawn discipline of ``ip_risk.py``
    (``ensure_fresh`` is the ONLY spawn path; the render path never blocks).

Each provider bar shows ONLY when that provider's env var is present AND its
cache entry is fresh, supported, and carries a computable percentage. The
render path (``segments()``) reads cache files only — it never imports
subprocess/urllib and never opens a socket; the detached
``_provider_usage_refresh`` prober does all HTTP.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ordered provider table: name -> (env var, short label). Order defines
# segment order in segments(). Exactly two entries per CONTEXT "New modules"
# — Exa is explicitly OUT OF SCOPE (no remaining-balance API).
PROVIDERS = (
    ("firecrawl", "FIRECRAWL_API_KEY", "fc"),
    ("tavily", "TAVILY_API_KEY", "tv"),
)

# Credits change slowly; a 5-minute positive TTL keeps the bar fresh without
# hammering the provider at the statusLine's ~1Hz refresh (mirrors
# balance_cache.TTL_SECONDS).
TTL_SECONDS = 300
# A provider that's unsupported (missing/zero limit, or a persistent probe
# failure) won't start working mid-session — back off for an hour before
# re-probing rather than every 5 minutes (mirrors
# balance_cache.NEGATIVE_TTL_SECONDS).
NEGATIVE_TTL_SECONDS = 3600
# A spawned refresh that never writes (network hang killed by timeout) must
# not wedge the inflight gate forever (mirrors balance_cache.INFLIGHT_MAX_AGE_S).
INFLIGHT_MAX_AGE_S = 60


def _cache_root() -> Path:
    return Path(os.path.expanduser("~")) / ".cache" / "claude-statusbar" / "provider_usage"


def fingerprint(name: str, key: str) -> str:
    """Stable per-provider bucket id. The raw key never touches disk."""
    h = hashlib.sha1()
    h.update((name or "").encode("utf-8"))
    h.update(b"\x00")
    h.update((key or "").encode("utf-8"))
    return h.hexdigest()


def cache_path_for(fp: str) -> Path:
    return _cache_root() / f"{fp}.json"


def read_cache(fp: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(cache_path_for(fp).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def is_fresh(entry: Optional[Dict[str, Any]], now: Optional[float] = None) -> bool:
    """Fresh = within the TTL that matches the entry's polarity. A
    ``supported=False`` entry uses the long negative TTL; a real reading uses
    the short positive TTL."""
    if not isinstance(entry, dict):
        return False
    ts = entry.get("ts")
    if not isinstance(ts, (int, float)):
        return False
    ttl = TTL_SECONDS if entry.get("supported") else NEGATIVE_TTL_SECONDS
    return (now if now is not None else time.time()) - ts < ttl


def write_cache_atomic(fp: str, entry: Dict[str, Any]) -> None:
    p = cache_path_for(fp)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=f".{p.name}.",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(entry))
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _inflight_path(fp: str) -> Path:
    return cache_path_for(fp).with_suffix(".inflight")


def is_inflight(fp: str) -> bool:
    try:
        data = json.loads(_inflight_path(fp).read_text(encoding="utf-8"))
        ts = data.get("ts", 0)
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    return (time.time() - ts) < INFLIGHT_MAX_AGE_S


def mark_inflight(fp: str) -> None:
    p = _inflight_path(fp)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"pid": os.getpid(), "ts": time.time()}),
                 encoding="utf-8")


def clear_inflight(fp: str) -> None:
    try:
        _inflight_path(fp).unlink()
    except FileNotFoundError:
        pass


def ensure_fresh(env: Dict[str, str]) -> None:
    """Spawn ONE detached prober for whichever providers are due for a
    re-check and not already inflight. Safe to call from anywhere (render
    path AND the daemon heartbeat) — the inflight marker prevents
    double-spawns. Never raises. This is the ONLY spawn path; ``segments()``
    never spawns.
    """
    try:
        to_probe: Dict[str, str] = {}
        marked: List[str] = []
        for name, env_var, _label in PROVIDERS:
            key = env.get(env_var) if env else None
            if not key:
                continue
            fp = fingerprint(name, key)
            entry = read_cache(fp)
            if is_fresh(entry) or is_inflight(fp):
                continue
            mark_inflight(fp)
            marked.append(fp)
            to_probe[name] = key
        if not to_probe:
            return
        try:
            import subprocess
            import sys
            child_env = dict(os.environ)
            child_env["CS_SEARCH_KEYS"] = json.dumps(to_probe)
            subprocess.Popen(
                [sys.executable, "-m", "claude_statusbar._provider_usage_refresh"],
                env=child_env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True,
            )
        except (OSError, ValueError):
            for fp in marked:
                clear_inflight(fp)
    except Exception:
        pass


def segments(env: Dict[str, str]) -> List[Dict[str, Any]]:
    """Read-only: ordered [{label,pct,text,remaining,limit}] for providers
    whose env key is present AND whose cache entry is fresh, supported, and
    carries a computable pct. Omits everything else — no ``--``, no crash.
    Reads cache files only — never spawns, never imports subprocess/urllib.
    """
    out: List[Dict[str, Any]] = []
    if not env:
        return out
    for name, env_var, label in PROVIDERS:
        key = env.get(env_var)
        if not key:
            continue
        fp = fingerprint(name, key)
        entry = read_cache(fp)
        if not is_fresh(entry) or not entry.get("supported"):
            continue
        pct = entry.get("pct")
        if not isinstance(pct, (int, float)):
            continue
        out.append({
            "label": label,
            "pct": float(pct),
            "text": f"{label} {pct:.0f}%",
            "remaining": entry.get("remaining"),
            "limit": entry.get("limit"),
        })
    return out
