---
name: job-fit
description: Analyze job fit using the user's local preferences and approved experience, with transparent strengths, gaps, and uncertainty.
---

# Job Fit

Use this skill after discovery and before asking the user to review a role. The local `daily` command provides an explainable prefilter score; Codex may add a richer reading of the current job description.

For each candidate, report:

- fit verdict: strong match, possible match, weak match, or excluded;
- evidence-backed strengths tied to the user's approved profile or resume;
- largest gaps and whether each gap is confirmed, unknown, or only inferred;
- location, work mode, salary, seniority, language, and start-date concerns;
- a clear recommendation: review, save, or do not recommend.

Never treat keyword overlap as proof of experience. Do not invent customer resources, quota results, certifications, AI experience, salary, or work authorization. A fit analysis does not count as the user's screening decision; only an explicit `review` command moves a job out of the new-review queue.
