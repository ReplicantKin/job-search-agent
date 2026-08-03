# Job Search Agent

Job Search Agent is a publishable, local-first Codex plugin for discovering public job postings, reviewing fit, tracking job history, preparing application materials, and executing one explicitly authorized application at a time.

## What it does

- Imports structured job postings from public job-search runs.
- Deduplicates postings by source ID, canonical URL, and job fingerprint.
- Separates review state from application state.
- Builds daily review, application, and follow-up queues.
- Provides an explainable local prefilter and AI-assisted strengths/gaps review.
- Prepares role-specific, user-reviewed application materials without inventing facts.
- Records application materials, evidence, and execution events.
- Exports non-secret data as JSON or Markdown.
- Supports an opt-in local credential store for sites that require a saved login.

The first release is designed for China-based job seekers. It includes offline capture adapters for common BOSS 直聘, 猎聘, 前程无忧, company career-page, and official ATS fields; live page access remains browser- and site-layout-dependent.

Generic capture examples are in [`examples/`](examples/). Public release and local marketplace steps are in [`docs/publishing.md`](docs/publishing.md).
The current release scope and known boundaries are recorded in [`CHANGELOG.md`](CHANGELOG.md).

## Local-first privacy

The plugin does not require a cloud account, central database, telemetry, or background upload. Personal profiles, job history, application records, and logs are kept in the user's local data directory. Credentials are handled separately from the job database and are never included in exports.

The browser execution layer must pause for CAPTCHA, MFA, unknown questions, sensitive commitments, or any result that cannot be evidenced. A failed or paused action is never reported as submitted.

## Install for development

This repository contains the plugin root. Validate it with:

```bash
python3 /path/to/plugin-creator/scripts/validate_plugin.py .
```

The runtime CLI is available as `python3 scripts/job_search_agent.py` during development.
The local core requires Python 3.9 or newer and uses only the standard library.

Build a clean release archive with:

```bash
python3 scripts/build_release.py --output dist
```

## Quick start

```bash
python3 scripts/job_search_agent.py init
python3 scripts/job_search_agent.py profile set --field locations --value '["深圳", "广州"]'
python3 scripts/job_search_agent.py profile set --field target_roles --value '["解决方案顾问", "售前产品经理"]'
python3 scripts/job_search_agent.py ingest --json jobs.json
python3 scripts/job_search_agent.py list --queue review
# 查看今日待处理队列
python3 scripts/job_search_agent.py daily
```

Inspect a role's complete source, application, communication, and event history:

```bash
python3 scripts/job_search_agent.py show JOB_ID
```

Browser captures can be normalized before they enter the local database:

```bash
python3 scripts/job_search_agent.py ingest --source boss \
  --json boss-capture.json \
  --url 'https://www.zhipin.com/web/geek/job?query=解决方案顾问' \
  --checked-at 2026-08-04
python3 scripts/job_search_agent.py ingest --source company \
  --html company-job.html \
  --url 'https://careers.example.com/jobs/42' \
  --checked-at 2026-08-04
```

The source adapter accepts common BOSS 直聘、猎聘、前程无忧 capture fields and company/ATS `JobPosting` JSON-LD. Incomplete records are returned as warnings and are not inserted.

After reviewing a role, move it into the application queue:

```bash
python3 scripts/job_search_agent.py review JOB_ID --decision ready --reason "Approved for application"
python3 scripts/job_search_agent.py authorize JOB_ID
```

The Codex browser skill consumes the one-job authorization and records either a submitted result with evidence or a paused/manual-required result. It never treats an unverified action as a successful application.

When a submission succeeds, the execution record can include `--resume-version` and `--cover-letter-version` so the used material versions remain auditable.

If you choose to save a site login locally, the credential store is separate from the job database. On macOS it uses Keychain; credentials are not exported, packaged, or uploaded.
On other platforms, the credential command stops with a browser-session/manual-fallback message; it does not write passwords to a plaintext file.

Review saved and historical roles directly:

```bash
python3 scripts/job_search_agent.py list --queue saved
python3 scripts/job_search_agent.py list --queue checked
python3 scripts/job_search_agent.py list --queue applied
python3 scripts/job_search_agent.py list --queue rejected
```

Set or remove a saved login without putting the password in shell history:

```bash
python3 scripts/job_search_agent.py credential set --site boss --username YOUR_USERNAME
python3 scripts/job_search_agent.py credential status --site boss
python3 scripts/job_search_agent.py credential delete --site boss
```

Register approved material versions locally so an application can reference exactly what was used:

```bash
python3 scripts/job_search_agent.py material register \
  --kind resume --version resume-2026-08-04 --path /path/to/resume.pdf
python3 scripts/job_search_agent.py material list --format json
```

## Data and status model

The local SQLite store separates screening state (`new`, `saved`, `ready_to_apply`, `skipped`, `expired`) from application state (`not_applied`, `in_progress`, `submitted_waiting`, `hr_contact`, `rejected`, `withdrawn`, `offer`).

Do not put resumes, credentials, live job data, or personal configuration into the plugin package or source repository.
