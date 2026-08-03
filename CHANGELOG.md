# Changelog

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
