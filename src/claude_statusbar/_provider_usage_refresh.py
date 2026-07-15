"""Detached search-provider credit prober — spawned by
``provider_usage.ensure_fresh()``.

Contract:
  env CS_SEARCH_KEYS — JSON object of {provider_name: raw_key, ...} for every
                        provider due for a re-check (forwarded, never
                        persisted to disk — mirrors ``_balance_refresh``'s
                        ``CS_BALANCE_KEY``).

Fully local dispatch: one HTTP call per provider (Firecrawl credit-usage /
Tavily usage). Any per-provider failure (raise, non-200, bad JSON, missing
limit) writes a ``supported: false`` negative-cache entry so the render path
simply omits that provider's bar and the negative TTL backs off from
re-probing for an hour. One provider's failure never blocks another's probe.
This module NEVER raises out to the shell — ``main()`` always returns 0.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

from . import provider_usage

_TIMEOUT_S = 6
_UA = "claude-statusbar-search/1.0"


def _get_json(url: str, key: str) -> dict | None:
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {key}",
                      "Accept": "application/json",
                      "User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            if resp.status != 200:
                return None
            body = resp.read(65536)
        data = json.loads(body.decode("utf-8", "replace"))
        return data if isinstance(data, dict) else None
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None


def _clamp(pct: float) -> float:
    return max(0.0, min(100.0, pct))


def _probe_firecrawl(key: str) -> dict | None:
    data = _get_json("https://api.firecrawl.dev/v2/team/credit-usage", key)
    if not data:
        return None
    inner = data.get("data")
    if not isinstance(inner, dict):
        return None
    remaining = inner.get("remainingCredits")
    limit = inner.get("planCredits")
    if not isinstance(limit, (int, float)) or limit <= 0:
        return None
    if not isinstance(remaining, (int, float)):
        return None
    return {
        "remaining": remaining,
        "limit": limit,
        "pct": _clamp(remaining / limit * 100),
        "billing_period_end": inner.get("billingPeriodEnd"),
    }


def _probe_tavily(key: str) -> dict | None:
    data = _get_json("https://api.tavily.com/usage", key)
    if not data:
        return None

    account = data.get("account")
    if isinstance(account, dict):
        limit = account.get("plan_limit")
        usage = account.get("plan_usage")
        if (isinstance(limit, (int, float)) and limit > 0
                and isinstance(usage, (int, float))):
            remaining = limit - usage
            return {"remaining": remaining, "limit": limit,
                    "pct": _clamp(remaining / limit * 100)}

    key_obj = data.get("key")
    if isinstance(key_obj, dict):
        limit = key_obj.get("limit")
        usage = key_obj.get("usage")
        if (isinstance(limit, (int, float)) and limit > 0
                and isinstance(usage, (int, float))):
            remaining = limit - usage
            return {"remaining": remaining, "limit": limit,
                    "pct": _clamp(remaining / limit * 100)}

    return None


_PROBERS = {
    "firecrawl": _probe_firecrawl,
    "tavily": _probe_tavily,
}


def main() -> int:
    try:
        keys = json.loads(os.environ.get("CS_SEARCH_KEYS", "{}"))
    except (ValueError, json.JSONDecodeError):
        keys = {}
    if not isinstance(keys, dict):
        keys = {}

    for name, key in keys.items():
        if not key:
            continue
        prober = _PROBERS.get(name)
        fp = provider_usage.fingerprint(name, key)
        try:
            result = prober(key) if prober else None
        except Exception:
            result = None
        try:
            if result is None:
                provider_usage.write_cache_atomic(
                    fp, {"ts": time.time(), "supported": False})
            else:
                provider_usage.write_cache_atomic(
                    fp, {"ts": time.time(), "supported": True, **result})
        finally:
            provider_usage.clear_inflight(fp)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Never crash a detached refresh — the bar degrades to "no segment".
        sys.exit(0)
