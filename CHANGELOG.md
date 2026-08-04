# Changelog

## 0.1.6

- Treat missing or unknown work-mode data as unknown in fit scoring instead of awarding a preferred hybrid/remote match.
- Preserve the explainable `work-mode: unspecified` gap so users can review the missing evidence before deciding.

## 0.1.5

- Match documented Chinese and English role aliases in the local fit prefilter, including solution architecture, presales, customer success, commercial product, and forward-deployed engineering titles.
- Keep alias matches deterministic and explainable; source evidence and per-role user confirmation remain required.

## 0.1.4

- Add append-only local source-page check history with a 24-hour freshness query.
- Record empty, warning, and unreadable source checks separately from job screening and application state.
- Expose `source-check record`, `source-check status`, and `source-check list` commands and preserve checks through privacy-safe export/import.

## 0.1.3

- Clarify which preferences are natively scored locally and which require live-page evidence or an AI/manual check.

## 0.1.2

- Make the daily discovery workflow read local search preferences, prioritize company and official ATS pages, and avoid rechecking unchanged URLs or resurfacing already handled roles.

## 0.1.1

- Sanitize application evidence and execution events with an explicit allowlist so accidental passwords, tokens, and nested secret fields do not persist or enter exports.
- Add the public submission packet with listing metadata, release notes, and reproducible positive and negative test cases.

## 0.1.0

Initial local-first release candidate.

- Discover and import public job captures from BOSS 直聘, 猎聘, 前程无忧, company career pages, and official ATS sources.
- Normalize supported JSON, Greenhouse API, and `JobPosting` JSON-LD captures with warnings for incomplete records.
- Keep screening status separate from application status and prevent duplicate review/application work.
- Run explainable local fit prefiltering from a user-managed profile.
- Register local resume, cover-letter, answer, and portfolio versions with export-time path redaction.
- Require one explicit authorization per application and verifiable evidence for a successful submission.
- Keep paused, failed, CAPTCHA, MFA, and unknown-field states visible for manual fallback or re-authorization.
- Store opt-in macOS credentials in Keychain; never include them in the job database export or release archive.
- Include a neutral briefcase-and-spark icon and a public metadata preflight helper; real repository and legal URLs remain publisher-supplied.
- Add saved/checked/applied/outcome management queues and a read-only per-job audit view.
- Add local HR communication records for incoming messages, drafts, and user-confirmed sent history; incoming HR messages update waiting applications to `hr_contact`.
- Make export/import preserve source and communication history without duplicating records on repeated imports.
- Give non-macOS users an explicit browser-session/manual-credential fallback instead of attempting an unavailable system command.
- Redact local path fields nested inside application evidence and event exports while retaining public confirmation evidence.
- Declare the tested standard-library runtime floor as Python 3.9.
- Keep internal planning notes out of the public release archive.
- Restore exported event timestamps idempotently during import, so audit history survives backup recovery.
- Add a top-level workflow skill that connects daily discovery, per-role confirmation, authorized application, follow-up, and draft-first HR communication.

Known release boundaries:

- Live site access remains browser-session and site-layout dependent.
- Anti-bot checks, CAPTCHA, MFA, unknown questions, and sensitive commitments require user handling.
- Public directory submission requires a real repository, legal URLs, and publisher-approved visual assets.
