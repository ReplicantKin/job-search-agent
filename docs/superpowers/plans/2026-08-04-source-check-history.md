# Source Check History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local, auditable source-page check history so daily job searches avoid rechecking fresh URLs while keeping page-check state separate from job screening and application state.

**Architecture:** Extend the existing SQLite `JobStore` with an append-only `source_checks` table and a small `SourceCheckRecord` model. Reuse `canonical_url()` for identity and existing export/import conventions for privacy-safe persistence. Add a `source-check` CLI command group and update the two discovery skills to check freshness before opening a page and record the result afterward; the adapter and browser layers remain network-free and unchanged.

**Tech Stack:** Python 3.9+, standard-library `sqlite3`, `dataclasses`, `argparse`, existing unittest suite, existing plugin release builder.

## Global Constraints

- Use local SQLite only; do not add a cloud endpoint, telemetry, or background scheduler.
- Do not persist passwords, cookies, browser sessions, resume contents, or raw browser output.
- Normalize source URLs with the existing `src/job_search_agent/dedupe.py:canonical_url` function.
- Accept only HTTPS URLs without embedded credentials or fragments.
- Keep source-check status separate from `screening_status` and `application_status`.
- Run tests before claiming completion and rebuild/validate the public plugin archive.

---

### Task 1: Add the source-check model and validation helpers

**Files:**
- Modify: `src/job_search_agent/models.py`
- Test: `tests/test_source_checks.py`

**Interfaces:**
- Produces `SourceCheckRecord` with fields `id`, `source`, `url`, `checked_at`, `result_count`, `status`, and `warnings`.
- Produces `SOURCE_CHECK_STATUSES = {"ok", "empty", "warning", "unreadable"}` and validation used by the store.

- [ ] **Step 1: Write the failing model test**

```python
def test_source_check_record_has_a_stable_public_shape():
    record = SourceCheckRecord(
        id=1,
        source="company",
        url="https://example.com/careers",
        checked_at="2026-08-04T00:00:00+00:00",
        result_count=0,
        status="empty",
        warnings=("no JobPosting record found",),
    )
    assert record.result_count == 0
    assert record.warnings == ("no JobPosting record found",)
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `PYTHONPATH=src:. .venv/bin/python -m unittest tests.test_source_checks.SourceCheckModelTests.test_source_check_record_has_a_stable_public_shape`

Expected: FAIL because `SourceCheckRecord` is not defined.

- [ ] **Step 3: Implement the dataclass and allowlist**

Add the frozen dataclass and status set to `models.py`. Keep warnings as `tuple[str, ...]` in the model so JSON conversion is explicit at CLI/store boundaries.

- [ ] **Step 4: Run the focused test and confirm it passes**

Run the same focused unittest command.

Expected: PASS.

- [ ] **Step 5: Commit the model change**

```bash
git add src/job_search_agent/models.py tests/test_source_checks.py
git commit -m "feat: model source check history"
```

### Task 2: Persist source-check history in SQLite

**Files:**
- Modify: `src/job_search_agent/store.py`
- Modify: `src/job_search_agent/dedupe.py` only if URL validation needs a focused reusable helper
- Test: `tests/test_source_checks.py`

**Interfaces:**
- `JobStore.record_source_check(source: str, url: str, checked_at: str, result_count: int, status: str, warnings: Sequence[str] = ()) -> SourceCheckRecord`
- `JobStore.latest_source_check(source: str, url: str) -> SourceCheckRecord | None`
- `JobStore.source_check_is_fresh(source: str, url: str, max_age_hours: float = 24, now: datetime | None = None) -> bool`
- `JobStore.list_source_checks(source: str | None = None, limit: int | None = None) -> list[SourceCheckRecord]`

- [ ] **Step 1: Write failing persistence tests**

```python
def test_empty_source_check_is_fresh_and_tracking_parameters_share_identity(self):
    first = self.store.record_source_check(
        "company", "https://example.com/careers?utm_source=search",
        "2026-08-04T00:00:00+00:00", 0, "empty", ["no jobs"],
    )
    latest = self.store.latest_source_check("company", "https://EXAMPLE.com/careers")
    self.assertEqual(latest.id, first.id)
    self.assertTrue(self.store.source_check_is_fresh(
        "company", "https://example.com/careers", now=datetime(2026, 8, 4, 12, tzinfo=timezone.utc)
    ))

def test_invalid_source_check_does_not_write(self):
    with self.assertRaises(ValueError):
        self.store.record_source_check("company", "http://example.com/careers", "2026-08-04T00:00:00+00:00", 1, "ok")
    self.assertEqual(self.store.list_source_checks(), [])
```

- [ ] **Step 2: Run focused tests and confirm they fail**

Run: `PYTHONPATH=src:. .venv/bin/python -m unittest tests.test_source_checks.SourceCheckStoreTests`

Expected: FAIL because the table and methods are not present.

- [ ] **Step 3: Add the table, conversion helpers, and methods**

Create the table in `_create_schema()` with an index on `(source, url, checked_at)`. Normalize the source with the existing source normalizer, normalize the URL with `canonical_url()`, reject non-HTTPS/credential/fragment URLs, validate status/result count/warning types, and convert SQLite rows to `SourceCheckRecord`.

For freshness, parse the stored ISO timestamp with timezone-aware datetimes, compare against `now` (default UTC now), and return `False` when there is no latest record or the age is negative/greater than `max_age_hours`.

- [ ] **Step 4: Run focused tests and add boundary assertions**

Run: `PYTHONPATH=src:. .venv/bin/python -m unittest tests.test_source_checks -v`

Add assertions for expired records, different sources, unknown status, negative result count, and warnings containing a non-string value. Expected: PASS.

- [ ] **Step 5: Commit persistence**

```bash
git add src/job_search_agent/store.py src/job_search_agent/dedupe.py tests/test_source_checks.py
git commit -m "feat: persist source check history"
```

### Task 3: Add CLI commands and privacy-safe import/export

**Files:**
- Modify: `scripts/job_search_agent.py`
- Modify: `src/job_search_agent/store.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_source_checks.py`

**Interfaces:**
- `source-check record` accepts `--source`, `--url`, `--result-count`, `--status`, repeated `--warning`, and optional `--checked-at`.
- `source-check status` accepts `--source`, `--url`, and `--max-age-hours`, returning JSON with `fresh` and the latest record or `latest: null`.
- `source-check list` accepts optional `--source`, `--limit`, and `--format table|json`.
- `export_json()` adds `source_checks`; `_import_export()` imports them idempotently.

- [ ] **Step 1: Write failing CLI tests**

```python
def test_source_check_record_and_status_are_json_serializable(self):
    code, output = self.run_cli(
        "source-check", "record", "--source", "company",
        "--url", "https://example.com/careers?utm_source=test",
        "--result-count", "0", "--status", "empty", "--warning", "no jobs",
        "--checked-at", "2026-08-04T00:00:00+00:00",
    )
    self.assertEqual(code, 0)
    self.assertEqual(json.loads(output)["url"], "https://example.com/careers")

    code, output = self.run_cli(
        "source-check", "status", "--source", "company",
        "--url", "https://example.com/careers", "--max-age-hours", "24",
    )
    self.assertEqual(code, 0)
    self.assertTrue(json.loads(output)["fresh"])

def test_source_checks_survive_idempotent_export_import(self):
    self.run_cli("source-check", "record", "--source", "company", "--url", "https://example.com/careers", "--result-count", "2", "--status", "ok")
    exported = self.root / "export.json"
    markdown = self.root / "export.md"
    self.assertEqual(self.run_cli("export", "--json", str(exported), "--markdown", str(markdown))[0], 0)
    self.assertEqual(self.run_cli("import", "--json", str(exported))[0], 0)
    self.assertEqual(self.run_cli("source-check", "list", "--format", "json")[1].count("example.com/careers"), 1)
```

- [ ] **Step 2: Run focused CLI tests and confirm they fail**

Run: `PYTHONPATH=src:. .venv/bin/python -m unittest tests.test_cli.CliTests.test_source_check_record_and_status_are_json_serializable tests.test_cli.CliTests.test_source_checks_survive_idempotent_export_import`

Expected: FAIL because the parser has no `source-check` command and exports have no `source_checks` key.

- [ ] **Step 3: Implement parser dispatch and serialization**

Add the nested argparse group, call `JobStore` methods, serialize tuple warnings as JSON arrays, and keep the existing stdout/error-code conventions. Export and import source checks without adding any credential or local-path fields.

- [ ] **Step 4: Run focused tests and add invalid-input CLI checks**

Run: `PYTHONPATH=src:. .venv/bin/python -m unittest tests.test_cli -v`

Confirm invalid HTTP input exits with code 2 and writes no source check.

- [ ] **Step 5: Commit CLI and persistence format**

```bash
git add scripts/job_search_agent.py src/job_search_agent/store.py tests/test_cli.py tests/test_source_checks.py
git commit -m "feat: expose source check history CLI"
```

### Task 4: Connect skills and documentation to source history

**Files:**
- Modify: `skills/job-discovery/SKILL.md`
- Modify: `skills/job-search-workflow/SKILL.md`
- Modify: `README.md`
- Modify: `docs/source-adapters.md`
- Modify: `tests/test_release.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Skills invoke `source-check status` before a source pass and `source-check record` after the page has actually been inspected.
- Documentation states that source freshness never proves a role is still open.

- [ ] **Step 1: Write failing release/documentation assertions**

```python
def test_release_docs_describe_source_check_history(self):
    discovery = (ROOT / "skills" / "job-discovery" / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    self.assertIn("source-check status", discovery)
    self.assertIn("source-check record", discovery)
    self.assertIn("source_checks", readme)
```

- [ ] **Step 2: Run the focused assertion and confirm it fails**

Run: `PYTHONPATH=src:. .venv/bin/python -m unittest tests.test_release.ReleaseTests.test_release_docs_describe_source_check_history`

Expected: FAIL because the new instructions are not present.

- [ ] **Step 3: Update skill order and public docs**

Add exact command examples, clarify the 24-hour default, state that empty and warning pages are recorded, and preserve the rule that old source history is not proof of current availability. Update the changelog with the feature and keep the public package free of runtime data.

- [ ] **Step 4: Run documentation tests**

Run: `PYTHONPATH=src:. .venv/bin/python -m unittest tests.test_release -v`

Expected: PASS.

- [ ] **Step 5: Commit skills and docs**

```bash
git add README.md CHANGELOG.md docs/source-adapters.md skills/job-discovery/SKILL.md skills/job-search-workflow/SKILL.md tests/test_release.py
git commit -m "docs: integrate source check history into daily search"
```

### Task 5: Full verification and public artifact refresh

**Files:**
- Modify: `.codex-plugin/plugin.json` only if the release version changes
- Modify: `pyproject.toml` and `src/job_search_agent/__init__.py` only if the release version changes
- Create/replace: `dist/job-search-agent-0.1.4.zip`

- [ ] **Step 1: Run the complete unit suite**

Run: `PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests`

Expected: all existing and new tests pass.

- [ ] **Step 2: Run the official plugin validator and public preflight**

Run:

```bash
python3 <plugin-creator-root>/scripts/validate_plugin.py .
PYTHONPATH=src:. .venv/bin/python scripts/prepare_public_release.py --check
```

Expected: `Plugin validation passed` and JSON with empty `missing` and `invalid` arrays.

- [ ] **Step 3: Build and inspect the release archive**

Run: `PYTHONPATH=src:. .venv/bin/python scripts/build_release.py --output dist`

Inspect the archive to confirm it contains the source-check code, skills, tests-independent public docs, and no `.sqlite3`, `.venv`, personal paths, or `docs/superpowers` files.

- [ ] **Step 4: Run installed-copy smoke tests**

Extract the new archive to a temporary directory, invoke its CLI from `/tmp`, record a source check, query status, and run `--help`. Expected: all commands return zero and the source record is fresh.

- [ ] **Step 5: Commit and publish the local release state**

```bash
git add .
git commit -m "release: add source check history"
git tag v0.1.4
git push origin main --tags
```

After the push, reinstall from the public GitHub marketplace and verify `codex plugin list --json` reports the new version and `enabled: true`.
