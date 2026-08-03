---
name: application-materials
description: Prepare job-specific resumes, cover letters, and application answers from the user's approved local profile without inventing facts.
---

# Application Materials

Use this skill after a role is selected for application and before browser execution begins.

## Required inputs

- The selected local job record and its current source URL.
- The user's approved profile, resume facts, portfolio links, and constraints.
- The desired language and the material version name.

If an input is missing, ask the user or mark the field as unresolved. Never fill a gap with a plausible invention.

## Produce

Prepare a reviewable package containing:

1. A tailored resume outline or approved resume version reference.
2. A concise cover letter or first-contact note when the channel supports one.
3. A question-answer sheet for common application fields, with each answer traced to an approved fact.
4. A short fit summary: strongest evidence, largest gap, and questions to verify before submission.

Keep the original source facts, generated draft, user edits, and final approved version separate. Record only the selected version names on the application record; do not put full credentials or unrelated private files into the job database.

After the user approves a file, register its local version reference:

```bash
python3 scripts/job_search_agent.py material register \
  --kind resume --version resume-2026-08-04 --path /path/to/resume.pdf
python3 scripts/job_search_agent.py material list --format json
```

The local store records a SHA-256 summary and path for execution-time use. JSON/Markdown exports include the version and summary but omit the local path and material contents.

## Review gate

Before an application is authorized, show the user the final material package and pause for:

- salary expectations, start date, relocation, working-hours, or work-authorization commitments;
- claims about customers, revenue, quotas, certifications, or confidential employers;
- any question not answerable from the approved profile;
- any mismatch between the job page and the imported job record.

After approval, the job-application skill may use the selected versions while filling one job only.
