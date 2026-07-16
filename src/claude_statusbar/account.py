"""Logged-in Claude account email resolution for the identity-line chip.

Pure filesystem, no network/subprocess. Derives the *active session's* config
dir from the statusLine stdin payload's ``transcript_path`` — which is rooted at
``<CONFIG_DIR>/projects/<enc>/<session>.jsonl`` — so it reads the right account
even under the shared daemon, whose ``os.environ`` is frozen at spawn time and
does not reflect a per-session ``CLAUDE_CONFIG_DIR``. Falls back to the
``CLAUDE_CONFIG_DIR`` env (stamped into ``_cs_env`` by render_thin) and finally
to ``~/.claude``.

The email lives at ``oauthAccount.emailAddress`` in that dir's ``.claude.json``
(``<CONFIG_DIR>/.claude.json`` for a named account, ``$HOME/.claude.json`` for
the default ``~/.claude``). It's read via an anchored regex scan memoized on
(path, mtime_ns, size) — mirroring ``predict._read_account_id`` — so steady-state
renders pay only a ``stat()`` on a 60–160KB file. Any error yields ``None`` so
this never raises into the render path. Only ``emailAddress`` is ever read; no
OAuth token or other secret is parsed, and the email is never written to disk.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

# Anchor on the oauthAccount object so an unrelated future "emailAddress" key
# elsewhere in the file can't shadow the login identity (same discipline as
# predict._read_account_id's accountUuid anchor).
_ANCHOR = b'"oauthAccount"'
_EMAIL_RE = re.compile(rb'"emailAddress"\s*:\s*"([^"]{3,254})"')

# Memoized last read, keyed by (path, mtime_ns, size). One entry is enough: a
# given window reads a single .claude.json every tick.
_EMAIL_CACHE: Dict[str, Any] = {"sig": None, "email": None}


def _config_dir_from_transcript(transcript_path: str) -> Optional[Path]:
    """Config dir implied by a transcript path, or ``None``.

    ``transcript_path`` is ``<CONFIG_DIR>/projects/<enc>/<session>.jsonl``, so
    ``parents[2]`` is the config dir — but only trust it when ``parents[1]`` is
    literally ``projects`` (guards against unexpected shapes).
    """
    if not transcript_path:
        return None
    p = Path(transcript_path)
    parents = p.parents
    if len(parents) < 3:
        return None
    if parents[1].name != "projects":
        return None
    return parents[2]


def resolve_config_dir(
    stdin: Mapping[str, Any],
    *,
    env: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
) -> Path:
    """Active config dir for this session.

    Priority: ``transcript_path`` (per-session, daemon-safe) → ``CLAUDE_CONFIG_DIR``
    env → ``~/.claude``. Always returns a Path (the default is never ``None``).
    """
    env = os.environ if env is None else env
    home = Path(os.path.expanduser("~")) if home is None else home

    from_transcript = _config_dir_from_transcript(
        str(stdin.get("transcript_path") or ""))
    if from_transcript is not None:
        return from_transcript

    ccd = env.get("CLAUDE_CONFIG_DIR")
    if ccd:
        return Path(ccd)

    return home / ".claude"


def _claude_json_path(config_dir: Path, home: Path) -> Optional[Path]:
    """Locate the ``.claude.json`` for ``config_dir``.

    Named accounts keep it at ``<CONFIG_DIR>/.claude.json``; the default
    ``~/.claude`` keeps it at ``$HOME/.claude.json``. Prefer the per-dir file,
    fall back to the HOME-level one; ``None`` when neither exists.
    """
    per_dir = config_dir / ".claude.json"
    if per_dir.is_file():
        return per_dir
    home_level = home / ".claude.json"
    if home_level.is_file():
        return home_level
    return None


def _read_email(path: Path) -> Optional[str]:
    """``oauthAccount.emailAddress`` from ``path``, memoized on (mtime, size)."""
    try:
        st = path.stat()
    except OSError:
        return None
    sig = f"{path}\0{st.st_mtime_ns}\0{st.st_size}"
    if _EMAIL_CACHE["sig"] == sig:
        return _EMAIL_CACHE["email"]
    try:
        data = path.read_bytes()
    except OSError:
        return None
    anchor = data.find(_ANCHOR)
    m = _EMAIL_RE.search(data[anchor:] if anchor >= 0 else data)
    email: Optional[str] = None
    if m:
        candidate = m.group(1).decode("utf-8", errors="replace")
        # Cheap sanity gate: a real address has an "@" with text on both sides.
        if "@" in candidate and not candidate.startswith("@") \
                and not candidate.endswith("@"):
            email = candidate
    _EMAIL_CACHE["sig"] = sig
    _EMAIL_CACHE["email"] = email
    return email


def resolve_account_email(
    stdin: Mapping[str, Any],
    *,
    env: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
) -> Optional[str]:
    """Email of the account this session is logged into, or ``None``.

    Never raises: any resolution/IO/parse failure yields ``None`` so the render
    path can call it unguarded-in-spirit (core still try/excepts for defense).
    """
    try:
        home = Path(os.path.expanduser("~")) if home is None else home
        config_dir = resolve_config_dir(stdin, env=env, home=home)
        path = _claude_json_path(config_dir, home)
        if path is None:
            return None
        return _read_email(path)
    except Exception:
        return None
