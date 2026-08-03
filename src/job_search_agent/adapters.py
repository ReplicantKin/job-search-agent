from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .models import JobInput


@dataclass(frozen=True)
class CaptureResult:
    jobs: list[JobInput]
    warnings: list[str]


SOURCE_ALIASES = {
    "boss": "boss",
    "b0ss": "boss",
    "zhipin": "boss",
    "boss直聘": "boss",
    "liepin": "liepin",
    "猎聘": "liepin",
    "51job": "51job",
    "51": "51job",
    "前程无忧": "51job",
    "company": "company",
    "company-career": "company",
    "company-careers": "company",
    "ats": "ats",
    "workday": "workday",
    "greenhouse": "greenhouse",
    "icims": "icims",
}

ATS_HTML_SOURCES = {"company", "ats", "workday", "greenhouse", "icims"}

FIELD_ALIASES = {
    "source_job_id": ("source_job_id", "sourceJobId", "jobId", "jobid", "encryptJobId", "job_id", "identifier", "id"),
    "title": ("title", "jobTitle", "job_title", "jobName", "job_name", "positionName", "position_name"),
    "company": ("company", "companyName", "company_name", "brandName", "compName", "co_name", "hiringOrganization"),
    "location": ("location", "city", "cityName", "workarea_text", "workArea", "address", "jobLocation"),
    "description": ("description", "content", "jobDescription", "jobDesc", "job_detail", "postDescription", "positionDescription"),
    "url": ("url", "absolute_url", "jobUrl", "job_href", "jobHref", "job_link", "link"),
    "work_mode": ("work_mode", "workMode", "workplaceType"),
    "salary": ("salary", "salaryDesc", "salary_text", "providesalary_text", "salaryRange", "baseSalary"),
    "posted_at": ("posted_at", "postedAt", "datePosted", "first_published"),
}

JSON_LD_SCRIPT = re.compile(
    r"<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")


def canonical_source(source: str) -> str:
    normalized = " ".join(source.strip().lower().split())
    return SOURCE_ALIASES.get(normalized, normalized or "unknown")


def parse_capture(
    source: str,
    payload: Any,
    *,
    source_url: str,
    source_checked_at: str,
) -> CaptureResult:
    """Normalize a browser capture without performing network access.

    The browser skill supplies either a structured JSON capture or the HTML of
    a company/ATS detail page. Keeping this function offline makes site access
    and local persistence independently testable.
    """

    normalized_source = canonical_source(source)
    warnings: list[str] = []
    records: list[Mapping[str, Any]] = []

    if isinstance(payload, str):
        text = payload.strip()
        if normalized_source in ATS_HTML_SOURCES and "application/ld+json" in text.lower():
            records.extend(_json_ld_records(text, warnings))
        else:
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError:
                warnings.append("capture is neither valid JSON nor supported JobPosting HTML")
            else:
                records.extend(_json_records(decoded, warnings))
    elif isinstance(payload, Mapping) or isinstance(payload, Sequence):
        records.extend(_json_records(payload, warnings))
    else:
        warnings.append("capture must be JSON, HTML text, or a list of records")

    jobs: list[JobInput] = []
    for index, record in enumerate(records, start=1):
        job, record_warnings = _record_to_job(
            normalized_source,
            record,
            source_url=source_url,
            source_checked_at=source_checked_at,
            index=index,
        )
        warnings.extend(record_warnings)
        if job is not None:
            jobs.append(job)

    return CaptureResult(jobs=jobs, warnings=warnings)


def _json_records(payload: Any, warnings: list[str]) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        if isinstance(payload.get("jobs"), list):
            raw_records = payload["jobs"]
        elif isinstance(payload.get("data"), list):
            raw_records = payload["data"]
        elif payload.get("@type") or payload.get("title") or payload.get("jobName"):
            raw_records = [payload]
        else:
            warnings.append("JSON capture has no jobs array or recognizable job record")
            return []
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        raw_records = payload
    else:
        warnings.append("JSON capture must be an object or array")
        return []

    records = [item for item in raw_records if isinstance(item, Mapping)]
    if len(records) != len(raw_records):
        warnings.append("some capture entries were ignored because they were not objects")
    return records


def _json_ld_records(document: str, warnings: list[str]) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    for chunk in JSON_LD_SCRIPT.findall(document):
        try:
            payload = json.loads(html.unescape(chunk).strip())
        except json.JSONDecodeError:
            warnings.append("invalid JSON-LD block was ignored")
            continue
        candidates: list[Any]
        if isinstance(payload, Mapping) and isinstance(payload.get("@graph"), list):
            candidates = payload["@graph"]
        elif isinstance(payload, list):
            candidates = payload
        else:
            candidates = [payload]
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            types = candidate.get("@type", [])
            if types == "JobPosting" or "JobPosting" in (types if isinstance(types, list) else []):
                records.append(candidate)
    if not records and not warnings:
        warnings.append("no JobPosting JSON-LD record found")
    return records


def _record_to_job(
    source: str,
    record: Mapping[str, Any],
    *,
    source_url: str,
    source_checked_at: str,
    index: int,
) -> tuple[JobInput | None, list[str]]:
    values = {field: _field_value(record, aliases) for field, aliases in FIELD_ALIASES.items()}
    values["source_job_id"] = _text(values["source_job_id"])
    values["url"] = _text(values["url"]) or _text(source_url)
    required = ("company", "title", "location", "description", "url")
    missing = [field for field in required if not _text(values[field])]
    if missing:
        return None, [f"record {index} missing {field}" for field in missing]

    return JobInput(
        source=source,
        source_job_id=_text(values["source_job_id"]) or None,
        url=_text(values["url"]),
        company=_text(values["company"]),
        title=_text(values["title"]),
        location=_text(values["location"]),
        description=_text(values["description"]),
        work_mode=_text(values["work_mode"]) or None,
        salary=_text(values["salary"]) or None,
        posted_at=_text(values["posted_at"]) or None,
        source_checked_at=source_checked_at,
    ), []


def _field_value(record: Mapping[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        if alias in record and record[alias] not in (None, "", []):
            return record[alias]
    return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Mapping):
        for key in ("value", "name", "text", "addressLocality", "addressRegion", "streetAddress"):
            if key in value and value[key] not in (None, ""):
                return _text(value[key])
        if "address" in value:
            return _text(value["address"])
        return ""
    if isinstance(value, list):
        return " / ".join(part for part in (_text(item) for item in value) if part)
    cleaned = html.unescape(str(value))
    cleaned = TAG_RE.sub(" ", cleaned)
    return " ".join(cleaned.split())
