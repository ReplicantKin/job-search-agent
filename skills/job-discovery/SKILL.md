---
name: job-discovery
description: Search public China job sources, normalize postings, and import only new or materially changed roles into the local Job Search Agent database.
---

# Job Discovery

Use this skill for a daily job-search run. The plugin is local-first, but live discovery must use public pages and the user's approved browser/search tools.

## Search configuration

Read the local profile before searching. Use these fields when present:

- `target_roles`: role names and close Chinese/English variants;
- `locations`: acceptable cities or regions;
- `exclude_companies` and `exclude_keywords`: hard exclusions;
- `salary_floor`, `work_modes`, `seniority`, and `languages`: preference filters;
- `target_companies` or `company_career_urls`: employer-specific sources.

If there are no target roles or locations, ask for those two inputs before launching a broad search. Treat missing optional preferences as unknown, not as permission to invent them.

## Source pass

For each daily run, make one focused search pass in this order:

1. Search 公司官网和官方 ATS pages for configured target companies and roles.
2. Search official recruiting feeds or public company job pages for roles not covered by the first pass.
3. Search BOSS 直聘, 猎聘, and 前程无忧 using the approved role/location terms.

Use the current visible result page and preserve its exact URL plus the check time. Do not repeat a source URL already present in the local source history unless the user changed a search preference or the page has a meaningful update. Do not use an old aggregator snippet as a fresh posting.

Before showing a role, apply hard exclusions, then the local deduplication rules, then the fit prefilter. A role that is already reviewed, saved, applied, rejected, or otherwise present in the local history should not be shown as a new discovery; show it only when its job description, title, location, employer, or detail URL materially changed.

## Default source order

1. Company career pages and official ATS pages.
2. Official recruiting accounts or public company job feeds.
3. BOSS 直聘, 猎聘, and 前程无忧 public job pages.

Do not treat an inaccessible page, an old search result, or an aggregator snippet as proof that a job is open. Keep the original URL and the date of the source check.

## Import contract

Before importing, create a JSON file with a top-level `jobs` array. Each item must contain:

```json
{
  "source": "company",
  "source_job_id": "optional-id",
  "url": "https://example.com/jobs/role",
  "company": "Company",
  "title": "Role",
  "location": "Shenzhen",
  "description": "Verbatim or faithful job description",
  "work_mode": "hybrid",
  "salary": "optional",
  "posted_at": "optional ISO date",
  "source_checked_at": "2026-08-03"
}
```

Then import it:

```bash
python3 scripts/job_search_agent.py ingest --json /path/to/jobs.json
python3 scripts/job_search_agent.py list --queue review --format json
```

For a browser capture from a supported site, let the local adapter map source fields first:

```bash
python3 scripts/job_search_agent.py ingest --source boss \
  --json /path/to/boss-capture.json \
  --url 'https://www.zhipin.com/web/geek/job?query=ROLE' \
  --checked-at 2026-08-04
```

For a company or ATS detail page containing `JobPosting` JSON-LD, use `--html` instead of `--json`. Inspect and report adapter warnings; do not force incomplete records into the database.

The local core deduplicates by source job ID, canonical URL, and normalized role identity plus JD fingerprint. Do not manually delete prior records to make a job appear new.

## Output discipline

For each candidate, preserve the source, location, current-open evidence, match reason, largest gap, and any uncertainty. Do not invent salary, qualifications, customer resources, quota results, or AI experience.
