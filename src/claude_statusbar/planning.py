"""Local GSD planning-state reader.

The statusbar must not invoke GSD or hit the network. It only reads the
project-local ``.planning/`` directory to surface the current GSD phase and,
while a phase is executing, per-wave plan progress. This mirrors ``party.py``'s
pure-filesystem contract: no subprocess, no network, and any malformed or
missing file yields ``None`` rather than raising into the render path.

Data model (GSD, confirmed against .planning/ + gsd-core):
- ``.planning/STATE.md`` frontmatter carries ``current_phase``,
  ``current_phase_name``, ``status`` and (nested under ``progress:``)
  ``total_phases``.
- The current phase lives at ``.planning/phases/{NN}-{slug}/`` (``NN`` =
  zero-padded ``current_phase``) and holds ``{NN}-{PP}-PLAN.md`` files whose
  frontmatter carries ``wave: <int>``.
- A plan is DONE iff its sibling ``{NN}-{PP}-SUMMARY.md`` exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, Union


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
_KV_RE = re.compile(r"^\s*([A-Za-z0-9_]+):\s*(.*)$")


def _normalize_state(status: str) -> str:
    """Map a free-form STATE.md ``status`` slug to a normalized token.

    Mirrors gsd-core ``normalizeStateStatus`` (lowercase substring test) because
    the on-disk value is free-form (e.g. ``phase-complete``), not a fixed enum.
    """
    s = (status or "").lower()
    if "execut" in s or "in progress" in s or "in-progress" in s:
        return "executing"
    if "complete" in s or "done" in s:
        return "done"
    if "paus" in s or "stopped" in s:
        return "paused"
    if "discuss" in s:
        return "discussing"
    if "verif" in s:
        return "verifying"
    if "plan" in s:
        return "planning"
    return "idle"


def _to_int(value) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _read_frontmatter(path: Path) -> Optional[Dict[str, str]]:
    """Return the leading ``---``…``---`` block as a flat key→value dict.

    First occurrence of a key wins; values are stripped of surrounding quotes.
    Nested keys (e.g. ``total_phases`` under ``progress:``) are flattened, which
    is fine here because the keys we read are unambiguous. Raises OSError to the
    caller when the file can't be read; returns ``None`` when there is no
    frontmatter block.
    """
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    fm: Dict[str, str] = {}
    for line in m.group(1).splitlines():
        kv = _KV_RE.match(line)
        if kv:
            key, val = kv.group(1), kv.group(2).strip()
            fm.setdefault(key, val.strip('"').strip("'"))
    return fm


@dataclass(frozen=True)
class WaveGroup:
    wave: int
    done: Tuple[bool, ...]      # one flag per plan, ordered by plan id
    state: str                  # "complete" | "active" | "future"


@dataclass(frozen=True)
class PlanningStatus:
    current_phase: int
    total_phases: int
    phase_name: str = ""
    state: str = "idle"         # normalized state token
    waves: Tuple[WaveGroup, ...] = ()
    # Phase numbers > current_phase that are NOT yet complete — the "remaining"
    # phases rendered as the ``[…]`` part 2 of the gsd line. Done phases are
    # excluded even when their number is above current (brownfield out-of-order
    # completion), so this is derived from ROADMAP.md, not from current/total.
    pending_after: Tuple[int, ...] = ()


def _plan_wave(path: Path) -> Optional[int]:
    try:
        fm = _read_frontmatter(path)
    except OSError:
        return None
    if not fm:
        return None
    return _to_int(fm.get("wave"))


def _read_waves(root: Path, current_phase: int) -> Tuple[WaveGroup, ...]:
    """Derive wave groups for the current phase from its PLAN/SUMMARY files.

    A plan is done iff its ``*-SUMMARY.md`` sibling exists. Waves are grouped and
    ordered by number; the *active* wave is the lowest-numbered wave that still
    has a pending plan. Returns ``()`` when the phase has no plans yet.
    """
    padded = f"{current_phase:02d}"
    phase_dir: Optional[Path] = None
    try:
        for d in sorted((root / "phases").iterdir()):
            if d.is_dir() and d.name.startswith(padded + "-"):
                phase_dir = d
                break
    except OSError:
        return ()
    if phase_dir is None:
        return ()

    plan_re = re.compile(rf"^{re.escape(padded)}-(\d+)-PLAN\.md$")
    plans = []  # (plan_id, wave, done)
    try:
        plan_files = sorted(phase_dir.glob(f"{padded}-*-PLAN.md"))
    except OSError:
        return ()
    for pf in plan_files:
        m = plan_re.match(pf.name)
        if not m:
            continue
        plan_id = m.group(1)
        wave = _plan_wave(pf)
        if wave is None:
            wave = 1
        done = pf.with_name(f"{padded}-{plan_id}-SUMMARY.md").exists()
        plans.append((plan_id, wave, done))
    if not plans:
        return ()

    by_wave: Dict[int, list] = {}
    for plan_id, wave, done in sorted(plans, key=lambda p: (p[1], p[0])):
        by_wave.setdefault(wave, []).append(done)

    active_wave: Optional[int] = None
    for wave in sorted(by_wave):
        if not all(by_wave[wave]):
            active_wave = wave
            break

    groups = []
    for wave in sorted(by_wave):
        dones = tuple(by_wave[wave])
        if all(dones):
            state = "complete"
        elif active_wave is not None and wave > active_wave:
            state = "future"
        else:
            state = "active"
        groups.append(WaveGroup(wave=wave, done=dones, state=state))
    return tuple(groups)


# Phase-existence + completion sources in ROADMAP.md, in decreasing done-signal
# strength: the checklist (``- [x] **Phase N: …**``), the progress-table rows
# (``| N. Name | … | Complete | …``), and — for existence only — detail-section
# headers (``### Phase N: …``). A phase counts as done if the checklist or table
# marks it done; a phase seen only as a header carries no done-signal, so it is
# pending by default. Headers matter because large roadmaps often list only the
# early phases in the checklist/table and enumerate the rest as ``### Phase N``
# sections — without this, every not-yet-tabled future phase was invisible to
# the remaining-phases bracket.
_ROADMAP_CHECK_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s*\*\*Phase\s+(\d+)", re.MULTILINE)
_ROADMAP_ROW_RE = re.compile(r"^\|\s*(\d+)\.\s")
_ROADMAP_HEADER_RE = re.compile(r"^\s*#{2,6}\s+Phase\s+(\d+)\b", re.MULTILINE)


def _read_pending_after(root: Path, current_phase: int) -> Tuple[int, ...]:
    """Phase numbers greater than ``current_phase`` that are NOT complete.

    Parsed from ``ROADMAP.md``: phase existence comes from the checklist,
    progress-table rows, AND ``### Phase N`` detail-section headers (so phases
    that appear only as headers are still counted); "done" is the union of the
    checklist ``[x]`` and table ``Complete`` markers. Returns ``()`` on any
    missing-file/parse issue — never raises into the render path. Result is
    sorted ascending and de-duplicated.
    """
    try:
        text = (root / "ROADMAP.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    seen: set = set()
    done: set = set()
    for m in _ROADMAP_CHECK_RE.finditer(text):
        n = _to_int(m.group(2))
        if n is None:
            continue
        seen.add(n)
        if m.group(1).lower() == "x":
            done.add(n)
    for line in text.splitlines():
        m = _ROADMAP_ROW_RE.match(line)
        if not m:
            continue
        n = _to_int(m.group(1))
        if n is None:
            continue
        seen.add(n)
        if "Complete" in line:
            done.add(n)
    # Detail-section headers establish existence only (no done-signal): a phase
    # seen solely as `### Phase N` and never marked complete is pending.
    for m in _ROADMAP_HEADER_RE.finditer(text):
        n = _to_int(m.group(1))
        if n is not None:
            seen.add(n)
    return tuple(sorted(n for n in seen if n > current_phase and n not in done))


def read_planning_status(
    cwd: Union[str, Path],
    *,
    planning_root: Optional[Union[str, Path]] = None,
) -> Optional[PlanningStatus]:
    """Return the local GSD planning status for ``cwd``, or ``None``.

    ``None`` is returned when ``.planning/STATE.md`` is absent or unparseable —
    this is the auto-show gate: no GSD project, no line. ``planning_root``
    overrides the ``.planning`` location (test seam, like party's ``home=``).
    Wave/plan progress is only read when the phase is executing (spec: circles
    appear during execution only).
    """
    root = Path(planning_root) if planning_root is not None else Path(cwd) / ".planning"
    try:
        fm = _read_frontmatter(root / "STATE.md")
    except OSError:
        return None
    if not fm:
        return None

    current_phase = _to_int(fm.get("current_phase"))
    if current_phase is None:
        return None
    total_phases = _to_int(fm.get("total_phases")) or 0
    phase_name = fm.get("current_phase_name", "") or ""
    state = _normalize_state(fm.get("status", ""))

    waves = _read_waves(root, current_phase) if state == "executing" else ()
    pending_after = _read_pending_after(root, current_phase)

    return PlanningStatus(
        current_phase=current_phase,
        total_phases=total_phases,
        phase_name=phase_name,
        state=state,
        waves=waves,
        pending_after=pending_after,
    )
