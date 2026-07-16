---
phase: 12
slug: per-account-rate-limit-store-isolation
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-16
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from 12-RESEARCH.md "## Validation Architecture". Requirement IDs are the SPEC's R1–R5
> (no formal REQ-IDs in REQUIREMENTS.md). Task IDs (`12-NN-MM`) are assigned by the planner; refine
> the Per-Task map once PLAN.md files exist.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`.venv/bin/python -m pytest`) |
| **Config file** | none — default discovery; `tests/__init__.py` present (enables `from tests.test_import_perf import _list_imports_for`) |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_account_rate_isolation.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -q` |
| **Estimated runtime** | quick ~2s · full ~30s (baseline: 1090 passed) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/test_account_rate_isolation.py -q`
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/ -q` (must stay ≥1090 + new, all green)
- **Before `/gsd-verify-work`:** Full suite green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

> Task column TBD until planner assigns `12-NN-MM` IDs. Rows are the requirement→test map from research.

| Req | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| R3 (primary) | Two accounts, identical 5h `resets_at` 1784191800, used 100 vs 50 → each renders own value | integration (core.main e2e) | `pytest tests/test_account_rate_isolation.py::test_two_accounts_share_5h_reset_render_own_values -x` | ❌ W0 | ⬜ pending |
| R1 | `transcript_path` under `.claude-account1/…` resolves account1's uuid over `~/.claude.json` | unit | `pytest …::test_account_id_resolves_from_transcript_over_home_json -x` | ❌ W0 | ⬜ pending |
| R4 | `_latest_path()`/`_projection_path()` both carry the resolved uuid | unit | `pytest …::test_store_paths_carry_session_uuid -x` | ❌ W0 | ⬜ pending |
| R5a | Unresolvable session → legacy unsuffixed path, unchanged | unit | `pytest …::test_unresolvable_session_uses_legacy_path -x` | ❌ W0 | ⬜ pending |
| R5b | Named dir w/o own `.claude.json` → legacy path, NOT `$HOME/.claude.json`'s uuid | unit | `pytest …::test_named_dir_without_own_json_does_not_borrow_home -x` | ❌ W0 | ⬜ pending |
| edge: identity | Same real uuid, two dirs → same store (no over-isolation) | unit | `pytest …::test_same_account_two_dirs_shares_store -x` | ❌ W0 | ⬜ pending |
| prohibition | Only `accountUuid` read; no OAuth token/secret | unit | `pytest …::test_keying_reader_reads_only_account_uuid -x` | ❌ W0 | ⬜ pending |
| prohibition | No `unlink`/`replace`/`rename` of existing store files | unit | `pytest …::test_no_destructive_fs_ops_on_existing_stores -x` | ❌ W0 | ⬜ pending |
| prohibition | `predict.py` imports no `subprocess`/`socket`/`urllib` | unit | `pytest …::test_predict_module_imports_no_network_or_subprocess -x` | ❌ W0 | ⬜ pending |
| landmine | Sentinel 3-way branch (omitted / None / uuid) → distinct paths | unit | `pytest …::test_account_path_three_way_branch -x` | ❌ W0 | ⬜ pending |
| landmine | `regime_changed_at` reads per-account path from `projection()` | unit | `pytest …::test_projection_threads_account_into_regime_check -x` | ❌ W0 | ⬜ pending |
| landmine | `_projection_result_key` differs per account (1s cache no leak) | unit | `pytest …::test_projection_result_cache_keys_by_account -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_account_rate_isolation.py` — new file; all rows above start from zero (naming mirrors `tests/test_account_switch.py`; fixtures mirror `tests/test_account.py` + `tests/test_core_projection.py`)
- [ ] Local helpers `_write_claude_json` / `_payload_with_limits` — copy shape from `tests/test_account.py` / `tests/test_core_projection.py` (no new conftest.py needed)
- [ ] Reuse `tests.test_import_perf._list_imports_for` directly for the no-network/subprocess prohibition test
- [ ] Framework install: none — `.venv` pytest already configured (1090 passing)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| "FAILS pre-fix, PASSES post-fix" proof for the regression test | R3 | Requires reverting `predict.py` to pre-fix state to observe RED | During execution: git-stash only `predict.py` (or checkout pre-fix), run `pytest …::test_two_accounts_share_5h_reset_render_own_values` → confirm RED, restore, confirm GREEN. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
