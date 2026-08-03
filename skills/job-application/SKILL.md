---
name: job-application
description: Execute one explicitly authorized job application at a time through the connected browser, recording evidence and pausing on unknown or sensitive conditions.
---

# Job Application

Use this skill only after the user has selected one job and explicitly confirmed the `投递` action in the Codex page.

## Required sequence

1. Load the selected job record and confirm it has no existing application unless the user explicitly authorizes a re-application.
2. Confirm the selected resume and cover-letter versions before opening the application page.
3. Use the connected browser session or the opt-in local credential store; never ask the user to paste a password into the conversation.
4. Fill only fields grounded in the user's approved profile or the selected materials.
5. Pause and return `paused` or `manual_required` for CAPTCHA, MFA, unknown free-text questions, sensitive commitments, missing material, or site errors.
6. Submit only after the one-job authorization is consumed.
7. Return `submitted` only with evidence such as a confirmation URL, application ID, or visible confirmation text; otherwise return the actual paused or failed state.
8. Record the result through `scripts/job_search_agent.py execution-result ...`; include the selected `--resume-version` and `--cover-letter-version` when the result is `submitted`.

Issuing the authorization creates the local `in_progress` attempt. A paused, failed, or manual-required result keeps that attempt visible so the user can decide whether to resume, finish manually, or update it with a later status.

If a saved local login is needed, the user may configure it with `credential set`; the password is entered through a protected prompt and only the site/username status is shown back. Prefer an already authenticated browser session when available.

## Never do

- Never batch-submit without a separate authorization for each job.
- Never invent experience, salary expectations, availability, customer resources, quota results, or work authorization.
- Never bypass CAPTCHA, MFA, login controls, or site restrictions.
- Never mark a silent application as rejected or a failed submission as successful.
