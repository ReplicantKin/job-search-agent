from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_TRACKING_PARAMETERS = {"ref", "source", "src", "utm_campaign", "utm_medium", "utm_source", "utm_term"}


def normalize_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = normalized.casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_source(source: str) -> str:
    value = normalize_text(source)
    if "boss" in value or "直聘" in value:
        return "boss"
    if "猎聘" in value or "liepin" in value:
        return "liepin"
    if "前程" in value or "51job" in value or "无忧" in value:
        return "51job"
    if "greenhouse" in value:
        return "greenhouse"
    if "workday" in value:
        return "workday"
    if "company" in value or "官网" in value:
        return "company"
    return re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value).strip("-") or "unknown"


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [pair for pair in parse_qsl(parts.query, keep_blank_values=True) if pair[0].casefold() not in _TRACKING_PARAMETERS]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), path, urlencode(query), ""))


def canonical_job_key(
    *,
    source: str,
    source_job_id: str | None,
    url: str,
    company: str,
    title: str,
    location: str,
) -> str:
    normalized_source = normalize_source(source)
    if source_job_id and normalize_text(source_job_id):
        return f"source:{normalized_source}:id:{normalize_text(source_job_id)}"
    if url.strip():
        return f"url:{canonical_url(url)}"
    identity = "|".join(map(normalize_text, (company, title, location)))
    return f"identity:{normalized_source}:{identity}"


def identity_key(*, company: str, title: str, location: str) -> str:
    return "|".join(map(normalize_text, (company, title, location)))


def job_fingerprint(description: str) -> str:
    compact = re.sub(r"\s+", "", unicodedata.normalize("NFKC", description or "").casefold())
    return hashlib.sha256(compact.encode("utf-8")).hexdigest()
