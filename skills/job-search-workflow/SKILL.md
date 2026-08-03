---
name: job-search-workflow
description: Orchestrate a local-first daily job search from public-source discovery through per-role review, materials, authorized application, follow-up, and draft-first recruiter communication.
---

# Job Search Workflow

Use this skill as the entry point when the user asks to find work, run the daily search, review opportunities, or continue an application. Keep the local SQLite store as the source of truth and keep screening status separate from application status.

## Daily workflow

Run the stages in order:

1. Read the user's configured local profile and run `python3 scripts/job_search_agent.py daily`.
2. Use the approved browser/search surface to inspect company career pages, official ATS pages, BOSS 直聘, 猎聘, and 前程无忧. Preserve each checked URL and date, then normalize the captured JSON/HTML with `ingest`.
3. Apply the local fit prefilter and show only new or materially updated roles in the review queue. For every role, state the source evidence, match strengths, largest gap, and uncertainty. A page view or AI score is not a user review decision.
4. Ask the user for an explicit decision on each role: keep, save, ready to apply, skip, or do not recommend. Do not silently mark a role as reviewed.
5. For roles marked ready, prepare the role-specific material package and show the selected resume, cover-letter, and answer versions. Pause for user edits and for salary, availability, location, work authorization, or other sensitive commitments.
6. Present one role at a time with the job URL, company, title, fit summary, material versions, fields that will be filled, and the exact action `投递`. 逐个确认后才能 issue that role's authorization；不得批量投递，也不得把“看起来合适”当作授权。
7. After authorization, use the connected browser session or the approved local credential store. Consume only that role's one-time authorization. Pause for CAPTCHA, MFA, unknown questions, missing material, site errors, or any unsupported commitment.
8. Record `submitted` only with a confirmation URL, application ID, visible confirmation text, screenshot reference, or explicit user confirmation. Otherwise record `paused`, `failed`, or `manual_required` with the actual reason.
9. Show follow-up queues with `list --queue no_reply`, `list --queue hr_contact`, `list --queue rejected`, `list --queue offer`, and `show JOB_ID` when the user needs the evidence trail.

## Recruiter communication

When the user supplies an incoming recruiter message, record it locally as `incoming`, update an existing waiting application to `hr_contact`, and draft a response using the configured display name. Keep the first-contact disclosure that an AI assistant is helping organize the conversation and that the candidate will review important information. Record the response as `draft` until the user approves it. Never monitor a mailbox in the background or send a message without explicit confirmation.

## Boundaries

- Never print, request in chat, or export a saved password.
- Never bypass CAPTCHA, MFA, login controls, site terms, or anti-bot restrictions.
- Never invent experience, salary, customer resources, quotas, certifications, availability, or work authorization.
- Never infer rejection from silence; `submitted_waiting` remains a live follow-up state until evidence changes it.
- If a source cannot be read or normalized, keep its warning and use manual fallback instead of claiming coverage.
