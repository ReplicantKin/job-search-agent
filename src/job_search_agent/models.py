from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4


SCREENING_STATUSES = {
    "new",
    "reviewed_keep",
    "saved",
    "ready_to_apply",
    "skipped",
    "do_not_recommend",
    "expired",
}

APPLICATION_STATUSES = {
    "not_applied",
    "in_progress",
    "submitted_waiting",
    "hr_contact",
    "rejected",
    "withdrawn",
    "offer",
}

COMMUNICATION_DIRECTIONS = {"incoming", "draft", "sent"}

REVIEW_DECISIONS = {
    "keep": "reviewed_keep",
    "save": "saved",
    "ready": "ready_to_apply",
    "skip": "skipped",
    "do_not_recommend": "do_not_recommend",
}

VERIFIABLE_EVIDENCE_FIELDS = {
    "confirmation_url",
    "application_id",
    "receipt",
    "confirmation_text",
    "screenshot_path",
    "message_url",
    "message_id",
    "channel",
    "user_confirmed",
}


def sanitize_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Keep only small, non-secret evidence fields that the audit model supports."""
    if not isinstance(evidence, dict):
        return {}
    sanitized: dict[str, Any] = {}
    for field in VERIFIABLE_EVIDENCE_FIELDS:
        value = evidence.get(field)
        if field == "user_confirmed":
            if isinstance(value, bool):
                sanitized[field] = value
        elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
            sanitized[field] = value
    return sanitized


def has_verifiable_evidence(evidence: dict[str, Any]) -> bool:
    for field, value in sanitize_evidence(evidence).items():
        if field == "user_confirmed" and value is True:
            return True
        if field != "user_confirmed" and value not in (None, "", False):
            return True
    return False


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class JobInput:
    source: str
    source_job_id: str | None
    url: str
    company: str
    title: str
    location: str
    description: str
    work_mode: str | None = None
    salary: str | None = None
    posted_at: str | None = None
    source_checked_at: str | None = None


@dataclass(frozen=True)
class ReviewDecision:
    decision: Literal["keep", "save", "ready", "skip", "do_not_recommend"]
    reason: str | None = None

    def screening_status(self) -> str:
        return REVIEW_DECISIONS[self.decision]


@dataclass(frozen=True)
class ApplicationResult:
    status: Literal[
        "in_progress",
        "submitted_waiting",
        "hr_contact",
        "rejected",
        "withdrawn",
        "offer",
    ]
    evidence: dict[str, Any]
    resume_version: str | None = None
    cover_letter_version: str | None = None
    reason: str | None = None
    submitted_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", sanitize_evidence(self.evidence))
        if self.status in {"submitted_waiting", "hr_contact", "offer"} and not has_verifiable_evidence(self.evidence):
            raise ValueError(f"{self.status} application requires evidence")
        if self.status == "rejected" and not self.evidence and not self.reason:
            raise ValueError("rejected application requires evidence or a user-confirmed reason")


@dataclass(frozen=True)
class JobRecord:
    id: str
    canonical_key: str
    identity_key: str
    fingerprint: str
    source: str
    source_job_id: str | None
    url: str
    company: str
    title: str
    location: str
    description: str
    work_mode: str | None
    salary: str | None
    posted_at: str | None
    source_checked_at: str | None
    screening_status: str
    application_status: str
    review_reason: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ApplicationRecord:
    id: str
    job_id: str
    status: str
    evidence: dict[str, Any]
    resume_version: str | None
    cover_letter_version: str | None
    reason: str | None
    submitted_at: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class MaterialRecord:
    id: str
    kind: str
    version: str
    path: str
    sha256: str
    size_bytes: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CommunicationRecord:
    id: str
    job_id: str
    channel: str
    direction: str
    text: str
    created_at: str


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
