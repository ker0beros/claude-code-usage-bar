"""Tests for the local GSD planning-state reader (planning.py)."""

from pathlib import Path

from claude_statusbar.planning import (
    PlanningStatus,
    WaveGroup,
    _normalize_state,
    _read_pending_after,
    read_planning_status,
)


def _make_planning(root: Path, *, status: str, total_phases: int = 9,
                   current_phase: int = 6, plans=None, phase_slug="ctx"):
    """Build a fake .planning/ tree under `root`.

    `plans` is a list of (plan_id, wave, done) tuples; a done plan also gets a
    sibling SUMMARY.md. Returns the .planning path.
    """
    pl = root / ".planning"
    pl.mkdir(parents=True, exist_ok=True)
    (pl / "STATE.md").write_text(
        "---\n"
        f"current_phase: {current_phase}\n"
        f"current_phase_name: Phase {current_phase}\n"
        f"status: {status}\n"
        "progress:\n"
        f"  total_phases: {total_phases}\n"
        "  completed_phases: 5\n"
        "---\n# Project State\n",
        encoding="utf-8",
    )
    if plans is not None:
        padded = f"{current_phase:02d}"
        ph = pl / "phases" / f"{padded}-{phase_slug}"
        ph.mkdir(parents=True, exist_ok=True)
        for plan_id, wave, done in plans:
            (ph / f"{padded}-{plan_id}-PLAN.md").write_text(
                f"---\nphase: {padded}-{phase_slug}\nplan: {plan_id}\nwave: {wave}\n---\n",
                encoding="utf-8",
            )
            if done:
                (ph / f"{padded}-{plan_id}-SUMMARY.md").write_text(
                    "---\nstatus: complete\n---\n", encoding="utf-8")
    return pl


def test_absent_planning_returns_none(tmp_path):
    assert read_planning_status(str(tmp_path)) is None


def test_malformed_state_missing_phase_returns_none(tmp_path):
    pl = tmp_path / ".planning"
    pl.mkdir()
    (pl / "STATE.md").write_text("---\nstatus: executing\n---\n", encoding="utf-8")
    assert read_planning_status(str(tmp_path)) is None


def test_state_without_frontmatter_returns_none(tmp_path):
    pl = tmp_path / ".planning"
    pl.mkdir()
    (pl / "STATE.md").write_text("no frontmatter here\n", encoding="utf-8")
    assert read_planning_status(str(tmp_path)) is None


def test_reads_phase_and_total(tmp_path):
    _make_planning(tmp_path, status="phase-complete", current_phase=6, total_phases=9)
    ps = read_planning_status(str(tmp_path))
    assert isinstance(ps, PlanningStatus)
    assert ps.current_phase == 6
    assert ps.total_phases == 9
    assert ps.phase_name == "Phase 6"
    assert ps.state == "done"


def test_complete_status_has_no_waves(tmp_path):
    # Even with plans on disk, a non-executing phase reads no wave detail.
    _make_planning(tmp_path, status="phase-complete",
                   plans=[("01", 1, True), ("02", 2, False)])
    ps = read_planning_status(str(tmp_path))
    assert ps.state == "done"
    assert ps.waves == ()


def test_executing_derives_wave_groups(tmp_path):
    _make_planning(tmp_path, status="executing", current_phase=6, total_phases=9,
                   plans=[("01", 1, True), ("02", 1, True), ("03", 2, False)])
    ps = read_planning_status(str(tmp_path))
    assert ps.state == "executing"
    assert ps.waves == (
        WaveGroup(wave=1, done=(True, True), state="complete"),
        WaveGroup(wave=2, done=(False,), state="active"),
    )


def test_active_wave_is_lowest_pending(tmp_path):
    # wave 1 fully done, wave 2 mixed (active), wave 3 untouched (future).
    _make_planning(tmp_path, status="executing",
                   plans=[("01", 1, True), ("02", 2, True), ("03", 2, False),
                          ("04", 3, False)])
    ps = read_planning_status(str(tmp_path))
    states = {wg.wave: wg.state for wg in ps.waves}
    assert states == {1: "complete", 2: "active", 3: "future"}


def test_executing_but_no_plans_yields_empty_waves(tmp_path):
    _make_planning(tmp_path, status="executing", plans=[])
    ps = read_planning_status(str(tmp_path))
    assert ps.state == "executing"
    assert ps.waves == ()


def test_executing_but_no_phase_dir_yields_empty_waves(tmp_path):
    # STATE says executing phase 7, but no phases/07-* dir exists.
    _make_planning(tmp_path, status="executing", current_phase=7)
    ps = read_planning_status(str(tmp_path))
    assert ps.state == "executing"
    assert ps.waves == ()


def test_plan_without_wave_defaults_to_wave_1(tmp_path):
    pl = _make_planning(tmp_path, status="executing", plans=[])
    ph = pl / "phases" / "06-ctx"
    (ph / "06-01-PLAN.md").write_text("---\nphase: 06-ctx\nplan: 01\n---\n",
                                      encoding="utf-8")
    ps = read_planning_status(str(tmp_path))
    assert ps.waves == (WaveGroup(wave=1, done=(False,), state="active"),)


def test_planning_root_override(tmp_path):
    root = tmp_path / "custom-planning"
    _make_planning(tmp_path, status="executing")  # creates tmp_path/.planning
    # point at a bespoke root that has no STATE.md
    assert read_planning_status(str(tmp_path), planning_root=root) is None


# --- pending_after (part 2: remaining-phases bracket) --------------------

def _write_roadmap(pl: Path, text: str):
    (pl / "ROADMAP.md").write_text(text, encoding="utf-8")


def test_pending_after_from_checklist(tmp_path):
    """Forward march: done phases excluded, only phases > current + pending."""
    pl = _make_planning(tmp_path, status="planning", current_phase=3)
    _write_roadmap(pl,
        "- [x] **Phase 1: A** - done\n"
        "- [x] **Phase 2: B** - done\n"
        "- [ ] **Phase 3: C** - current\n"
        "- [ ] **Phase 4: D** - pending\n"
        "- [ ] **Phase 5: E** - pending\n")
    ps = read_planning_status(str(tmp_path))
    assert ps.pending_after == (4, 5)


def test_pending_after_excludes_done_above_current(tmp_path):
    """Brownfield: phases numbered above current but already complete are OUT."""
    pl = _make_planning(tmp_path, status="planning", current_phase=9,
                        total_phases=12)
    _write_roadmap(pl,
        "".join(f"- [x] **Phase {i}: P{i}** - delivered\n" for i in range(1, 9))
        + "- [ ] **Phase 9: Hardening** - planned\n\n"
        + "| Phase | Milestone | Plans | Status | Completed |\n|--|--|--|--|--|\n"
        + "".join(f"| {i}. P{i} | v | d | Complete | date |\n"
                 for i in (10, 11, 12))
        + "| 9. Hardening | H | 0 | Not started | - |\n")
    ps = read_planning_status(str(tmp_path))
    assert ps.pending_after == ()          # 10,11,12 done → excluded; 9 is current


def test_pending_after_ignores_phases_below_current(tmp_path):
    pl = _make_planning(tmp_path, status="planning", current_phase=4)
    _write_roadmap(pl,
        "- [ ] **Phase 2: B** - pending but below current\n"
        "- [ ] **Phase 4: D** - current\n"
        "- [ ] **Phase 6: F** - pending\n")
    ps = read_planning_status(str(tmp_path))
    assert ps.pending_after == (6,)        # phase 2 pending but < current → excluded


def test_pending_after_empty_without_roadmap(tmp_path):
    _make_planning(tmp_path, status="planning", current_phase=3)  # no ROADMAP.md
    ps = read_planning_status(str(tmp_path))
    assert ps.pending_after == ()


def test_pending_after_reads_section_headers(tmp_path):
    """central-flutter shape: early phases in checklist/table, later phases only
    as ``### Phase N`` headers — the header phases still count as pending."""
    pl = _make_planning(tmp_path, status="verifying", current_phase=23,
                        total_phases=35)
    _write_roadmap(pl,
        "- [x] **Phase 1: A** - done\n"
        "- [ ] **Phase 3: C** - pending early\n\n"
        "| Phase | Status |\n|--|--|\n"
        "| 1. A | Complete |\n"
        "| 13. M | Complete |\n\n"
        + "".join(f"### Phase {i}: Section {i}\nprose\n\n" for i in range(23, 36)))
    ps = read_planning_status(str(tmp_path))
    assert ps.pending_after == tuple(range(24, 36))   # 24..35 header-only → pending


def test_pending_after_header_phase_marked_complete_excluded(tmp_path):
    """A header phase above current that IS marked complete (table) is excluded."""
    pl = _make_planning(tmp_path, status="planning", current_phase=5)
    _write_roadmap(pl,
        "### Phase 6: Done section\n\n"
        "### Phase 7: Todo section\n\n"
        "| 6. Done | Complete |\n")
    ps = read_planning_status(str(tmp_path))
    assert ps.pending_after == (7,)          # 6 complete via table, 7 header-only


def test_read_pending_after_table_only(tmp_path):
    """A phase present only in the progress table is still classified."""
    pl = tmp_path / ".planning"
    pl.mkdir(parents=True)
    _write_roadmap(pl,
        "| Phase | Status |\n|--|--|\n"
        "| 5. Done | Complete |\n"
        "| 6. Todo | Not started |\n"
        "| 7. Todo | Not started |\n")
    assert _read_pending_after(pl, current_phase=4) == (6, 7)   # 5 complete → out


def test_normalize_state_variants():
    assert _normalize_state("executing") == "executing"
    assert _normalize_state("Executing Phase 6") == "executing"
    assert _normalize_state("ready to execute") == "executing"
    assert _normalize_state("phase-complete") == "done"
    assert _normalize_state("Complete ✓") == "done"
    assert _normalize_state("paused") == "paused"
    assert _normalize_state("ready to plan") == "planning"
    assert _normalize_state("discussing") == "discussing"
    assert _normalize_state("verifying") == "verifying"
    assert _normalize_state("") == "idle"
    assert _normalize_state("something-weird") == "idle"
