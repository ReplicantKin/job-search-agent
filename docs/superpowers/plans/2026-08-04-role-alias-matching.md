# Role Alias Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach the local fit prefilter to match common Chinese and English titles within the same configured role family, then publish the behavior as Job Search Agent `0.1.5`.

**Architecture:** Keep matching deterministic and local. Add a private alias-family table and helper in `src/job_search_agent/fit.py`; `evaluate_fit` uses it only after the existing literal title match path. Preserve the existing `FitAssessment` shape, database schema, browser behavior, credentials boundary, and review/application gates.

**Tech Stack:** Python 3.9+, standard library, `unittest`, local SQLite core, Codex plugin manifest and release scripts.

## Global Constraints

- No network call or remote model is added to fit evaluation.
- Alias matching is a positive prefilter signal only; it never changes exclusions or user confirmation requirements.
- Unknown titles and unrelated role families remain unmatched.
- Credentials, resumes, live job data, and personal configuration remain outside the public package.
- Release version is `0.1.5` in every versioned artifact and release test expectation.

### Task 1: Add failing role-alias tests

**Files:**
- Modify: `tests/test_fit.py` after `test_matching_role_location_and_keywords_get_an_explainable_score`

**Interfaces:**
- Consumes: existing `job()` fixture and `evaluate_fit`.
- Produces: executable expectations for Chinese-to-English aliases, English-to-Chinese aliases, unrelated-family rejection, and exclusion preservation.

- [ ] **Step 1: Write the failing tests**

Add these methods to `FitTests`:

```python
    def test_chinese_role_target_matches_english_solution_architect_title(self):
        assessment = evaluate_fit(
            job(title="AI Solution Architect"),
            {"target_roles": ["解决方案架构师"]},
        )

        self.assertEqual(assessment.verdict, "strong_match")
        self.assertIn("role", assessment.matched_dimensions)
        self.assertTrue(any("alias" in strength.lower() for strength in assessment.strengths))

    def test_english_role_target_matches_chinese_customer_success_title(self):
        assessment = evaluate_fit(
            job(title="高级客户成功经理"),
            {"target_roles": ["customer success"]},
        )

        self.assertEqual(assessment.verdict, "strong_match")
        self.assertIn("role", assessment.matched_dimensions)

    def test_unrelated_role_families_do_not_match_through_shared_words(self):
        assessment = evaluate_fit(
            job(title="AI 产品经理"),
            {"target_roles": ["解决方案架构师"]},
        )

        self.assertEqual(assessment.verdict, "weak_match")
        self.assertNotIn("role", assessment.matched_dimensions)

    def test_alias_match_does_not_override_excluded_company(self):
        assessment = evaluate_fit(
            job(company="明确排除公司", title="AI Solution Architect"),
            {
                "target_roles": ["解决方案架构师"],
                "exclude_companies": ["明确排除公司"],
            },
        )

        self.assertEqual(assessment.verdict, "excluded")
        self.assertEqual(assessment.score, 0)
```

- [ ] **Step 2: Run the focused tests to verify they fail for the missing behavior**

Run:

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_fit
```

Expected: the two cross-language tests fail because the current literal matcher does not recognize the aliases; the existing tests continue to pass.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_fit.py
git commit -m "test: specify role alias matching"
```

### Task 2: Implement deterministic role-family matching

**Files:**
- Modify: `src/job_search_agent/fit.py` near the existing weights and `_contains` helpers
- Test: `tests/test_fit.py`

**Interfaces:**
- Consumes: normalized job title and profile `target_roles` values.
- Produces: private `_role_matches(title, target) -> tuple[bool, bool]`, where the second value indicates whether the positive match came from an alias rather than the literal path.

- [ ] **Step 1: Implement the minimum alias vocabulary**

Add a private tuple of role families and a helper that whitespace-normalizes and case-folds text. The helper must first return `(True, False)` for an existing literal match, then return `(True, True)` only when the target and title each contain an alias from the same family, otherwise `(False, False)`.

Use these families exactly:

```python
ROLE_ALIAS_FAMILIES = (
    ("solutions architecture", ("解决方案架构师", "solution architect", "solutions architect", "cloud solution architect", "ai solution architect")),
    ("solutions consulting", ("解决方案顾问", "solutions consultant", "solution consultant")),
    ("presales", ("售前", "presales", "pre-sales", "sales engineer", "technical sales")),
    ("customer success", ("客户成功", "customer success", "customer success manager")),
    ("commercial product", ("产品商业化", "product commercialization", "commercial product")),
    ("forward deployed engineering", ("fde", "forward deployed engineer", "forward-deployed engineer")),
)
```

Use boundary-aware matching for the short alias `FDE` so it does not match arbitrary words containing those letters. Longer aliases may use the existing normalized substring behavior because they are role phrases.

- [ ] **Step 2: Wire the helper into `evaluate_fit`**

Replace the current role condition with a loop over `targets` that records the first literal or alias match. Keep the existing score weight and `matched_dimensions` value. For a literal match, preserve the current strength style; for an alias match, emit a strength containing `alias`, the configured target, and the observed title. Preserve the existing gap when no target matches.

- [ ] **Step 3: Run the focused tests to verify they pass**

Run:

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_fit
```

Expected: all focused tests pass.

- [ ] **Step 4: Run the full suite**

Run:

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
```

Expected: all baseline and new tests pass with no test failures.

- [ ] **Step 5: Commit the implementation**

```bash
git add src/job_search_agent/fit.py tests/test_fit.py
git commit -m "feat: match multilingual role aliases"
```

### Task 3: Update public release metadata and documentation

**Files:**
- Modify: `.codex-plugin/plugin.json`
- Modify: `pyproject.toml`
- Modify: `src/job_search_agent/__init__.py`
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `docs/publishing.md`
- Modify: `docs/public-submission.md`
- Modify: `tests/test_release.py`

**Interfaces:**
- Consumes: the role-family behavior from Task 2.
- Produces: consistent `0.1.5` metadata and public documentation explaining deterministic multilingual role matching.

- [ ] **Step 1: Bump every versioned artifact to `0.1.5`**

Update the three runtime/manifest version fields and the fixed archive names/URLs in release docs and tests from `0.1.4` to `0.1.5`. Do not change historical changelog entries.

- [ ] **Step 2: Document the behavior and boundary**

Add a short `0.1.5` changelog entry and a README sentence saying that the local prefilter recognizes the documented Chinese/English role aliases, while final review still requires source evidence and user confirmation.

- [ ] **Step 3: Run release tests and inspect version consistency**

Run:

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_release
rg -n "0\.1\.4|0\.1\.5" . --glob '!docs/superpowers/**' --glob '!dist/**'
```

Expected: release tests pass; remaining `0.1.4` references are historical-only if any.

- [ ] **Step 4: Commit release metadata**

```bash
git add .codex-plugin/plugin.json pyproject.toml src/job_search_agent/__init__.py CHANGELOG.md README.md docs/publishing.md docs/public-submission.md tests/test_release.py
git commit -m "release: prepare job search agent 0.1.5"
```

### Task 4: Verify, publish, and reinstall

**Files:**
- Build: `dist/job-search-agent-0.1.5.zip`
- Verify: public GitHub release `v0.1.5`

**Interfaces:**
- Consumes: the completed branch and release metadata.
- Produces: a validated public archive, GitHub release, and enabled local plugin at `0.1.5`.

- [ ] **Step 1: Run the full verification set**

Run the full tests, official plugin validator, public preflight, release builder, archive privacy scan, and extracted CLI smoke test. The archive must contain no SQLite database, virtual environment, personal path, or superpowers design/plan documents.

- [ ] **Step 2: Review the branch diff and commit any verification-only corrections**

Run `git diff main...HEAD --check` and `git status --short`. Keep the worktree clean except for intentional release output.

- [ ] **Step 3: Merge, tag, and push**

After verification, fast-forward merge the feature branch into `main`, create annotated tag `v0.1.5`, and push `main` and the tag to `ReplicantKin/job-search-agent`.

- [ ] **Step 4: Create and verify the GitHub release**

Create a non-draft, non-prerelease `v0.1.5` release with the archive asset, then verify its SHA-256 digest and release URL.

- [ ] **Step 5: Refresh the public marketplace and reinstall**

Upgrade the public GitHub marketplace and reinstall `job-search-agent@job-search-agent-public`. Verify `codex plugin list --json` reports version `0.1.5`, installed, and enabled; run the extracted installed copy's `--help` smoke test.

### Task 5: Import high-confidence public roles into the local review queue

**Files:**
- Modify: the user's local Job Search Agent SQLite database only

**Interfaces:**
- Consumes: official Microsoft, Dun & Bradstreet, and HSBC source pages already inspected in the current task.
- Produces: local job records with source URLs and current source-check timestamps; no application authorization or message sending.

- [ ] **Step 1: Create a temporary capture with concise faithful summaries**

Include only the role title, company, location, current source URL, and a concise description based on the official page. Mark the Microsoft landing-page role with its listing-page URL and preserve the source date in `source_checked_at`; do not import Qoder until its Shenzhen/杭州 detail mismatch is resolved.

- [ ] **Step 2: Record source checks and ingest the capture**

Record each official source check, then ingest the jobs using the release CLI. Do not set screening decisions or application statuses automatically.

- [ ] **Step 3: Inspect the ranked review queue**

Run `daily` and verify the three roles appear once, have explainable fit results, and remain in `new`/review state. Confirm no credential, application, or HR communication record was created.

- [ ] **Step 4: Report the queue with uncertainty labels**

Show the user the resulting roles, source evidence, match strengths, biggest gaps, and the Qoder mismatch as not imported.
