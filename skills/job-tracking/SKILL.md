---
name: job-tracking
description: Manage local job review, application, follow-up, deduplication, and export queues in Job Search Agent.
---

# Job Tracking

Use the local CLI as the source of truth for job state. Screening state and application state are separate.

## Daily queues

To retrieve all three queues in one response:

```bash
python3 scripts/job_search_agent.py daily
```

The daily JSON payload includes the local fit prefilter (`score`, `verdict`, matched dimensions, strengths, and gaps). Treat it as triage evidence, not as the user's final screening decision.

Or inspect one queue at a time:

```bash
python3 scripts/job_search_agent.py list --queue review
python3 scripts/job_search_agent.py list --queue saved
python3 scripts/job_search_agent.py list --queue checked
python3 scripts/job_search_agent.py list --queue apply
python3 scripts/job_search_agent.py list --queue followup
python3 scripts/job_search_agent.py list --queue applied
python3 scripts/job_search_agent.py list --queue rejected
python3 scripts/job_search_agent.py show JOB_ID
```

- `review`: new roles the user has not explicitly handled.
- `saved`: roles the user has checked and kept for later.
- `checked`: every role that has left the new-review queue, including skipped and do-not-recommend roles.
- `apply`: roles the user marked ready to apply and that have no prior application.
- `followup`: submitted applications waiting for a reply or in HR contact.
- `applied`: every role with an application attempt, including in-progress, waiting, rejected, withdrawn, and offer states.
- `no_reply`, `hr_contact`, `rejected`, `offer`, and `withdrawn`: focused application-status views.

Use `show JOB_ID` when the user needs the source URLs, all application attempts, evidence, and the chronological event history for one role. This is the audit view behind a clear status; it does not change any state.

Issuing a per-job authorization starts an `in_progress` application attempt. If the browser pauses for CAPTCHA, MFA, an unknown field, or a site error, the attempt remains `in_progress` and may be resumed with a new explicit authorization; it is never silently converted to `submitted_waiting`.

An unchanged source refresh does not re-open a reviewed role. A material JD, title, company, location, or detail-URL change re-enters the review queue when the role has not been applied to, and creates a `job_updated` event.

## User decisions

```bash
python3 scripts/job_search_agent.py review JOB_ID --decision save --reason "Worth keeping"
python3 scripts/job_search_agent.py review JOB_ID --decision ready --reason "Approved for application"
python3 scripts/job_search_agent.py review JOB_ID --decision skip --reason "Location mismatch"
python3 scripts/job_search_agent.py review JOB_ID --decision do_not_recommend --reason "User exclusion"
```

Only an explicit user decision marks a role as reviewed. An AI analysis or a page view alone is not enough.

## Application outcomes

Record a result only when there is evidence or a user-confirmed status:

```bash
python3 scripts/job_search_agent.py application JOB_ID \
  --status submitted_waiting \
  --evidence-json '{"confirmation_url":"https://example.com/confirmation"}' \
  --resume-version resume-v1
```

The CLI blocks a second application for the same job by default. Re-application requires an explicit `--allow-duplicate` and should only be used for a materially changed requisition.

After an application exists, recording `hr_contact`, `rejected`, `withdrawn`, or `offer` updates that current attempt and appends an event; it does not create a second application.

Export records without secrets:

```bash
python3 scripts/job_search_agent.py export --json export.json --markdown export.md
```

Exported application evidence keeps public confirmation URLs and IDs but replaces local screenshot or file paths with `[local path omitted]`.
