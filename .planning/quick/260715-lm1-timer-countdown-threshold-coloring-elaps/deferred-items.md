# Deferred Items — 260715-lm1

Out-of-scope discoveries logged during execution (not fixed — see SCOPE BOUNDARY).

## test_version_sync.py::test_marketplace_and_plugin_versions_match_pyproject

- **Found during:** Task 1 full-suite verification run.
- **Issue:** `.claude-plugin/marketplace.json` `metadata.version` is `3.29.11` but
  `pyproject.toml` version is `3.30.0`. Pre-existing drift unrelated to timer
  coloring — confirmed failing identically on HEAD before this quick task's
  changes (via `git stash` + re-run).
- **Action:** Not fixed — out of scope for this quick task. Needs a release-time
  bump of `.claude-plugin/marketplace.json` to match `pyproject.toml`.
