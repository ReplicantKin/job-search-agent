# Source adapter capability matrix

The public plugin separates discovery, capture, tracking, and submission. A source can support one capability without supporting the others.

| Source | Discovery | Capture/import | Auto-fill | Auto-submit | Initial policy |
|---|---|---|---|---|---|
| BOSS 直聘 | public/browser search | structured JSON or browser capture | adapter-dependent | user-authorized only | verify current page and site terms |
| 猎聘 | public/browser search | structured JSON or browser capture | adapter-dependent | user-authorized only | verify current page and site terms |
| 前程无忧 | public/browser search | structured JSON or browser capture | adapter-dependent | user-authorized only | verify current page and site terms |
| Company career page | public page | structured JSON or browser capture | ATS-dependent | user-authorized only | prefer the employer's original page |
| Official ATS | public page | structured JSON or browser capture | platform adapter | user-authorized only | pause for CAPTCHA/MFA/unknown fields |
| Workday / Greenhouse / iCIMS | public detail page when available | JSON-LD, supported public API capture, or browser capture | platform-dependent | user-authorized only | preserve platform URL; cookie/login gates use manual fallback |

The local capture adapter maps common field names from BOSS 直聘, 猎聘, and 前程无忧 JSON captures, supports the public Greenhouse jobs API field shape, and reads `JobPosting` JSON-LD from company/ATS HTML. For example:

```bash
python3 scripts/job_search_agent.py ingest \
  --source greenhouse \
  --json greenhouse-api-capture.json \
  --url 'https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true' \
  --checked-at 2026-08-04
```

The adapter itself performs no network access; the browser/search layer or an explicit user-provided capture supplies the JSON/HTML. A detail-page capture may use the checked page URL when the page does not repeat its canonical URL.

An adapter must report what it actually did. Unsupported or failed execution returns warnings/manual fallback, never a false job record or false submission success.
