from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Any, Literal

from .models import has_verifiable_evidence


EXECUTION_STATUSES = {"submitted", "paused", "failed", "manual_required"}


@dataclass(frozen=True)
class ApplicationExecutorResult:
    status: Literal["submitted", "paused", "failed", "manual_required"]
    evidence: dict[str, Any]
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in EXECUTION_STATUSES:
            raise ValueError(f"invalid execution status: {self.status}")
        if self.status == "submitted" and not has_verifiable_evidence(self.evidence):
            raise ValueError("submitted execution must include evidence")
        if self.status != "submitted" and not self.reason:
            raise ValueError(f"{self.status} execution must include a reason")


@dataclass
class ApplicationAuthorization:
    token: str
    job_id: str
    expires_at: float
    used: bool = False


class AuthorizationGate:
    def __init__(self):
        self._authorizations: dict[str, ApplicationAuthorization] = {}

    def issue(self, job_id: str, ttl_seconds: int = 900) -> ApplicationAuthorization:
        authorization = ApplicationAuthorization(
            token=secrets.token_urlsafe(32),
            job_id=job_id,
            expires_at=time.time() + ttl_seconds,
        )
        self._authorizations[authorization.token] = authorization
        return authorization

    def consume(self, token: str, job_id: str) -> bool:
        authorization = self._authorizations.get(token)
        if authorization is None:
            raise ValueError("unknown authorization")
        if authorization.job_id != job_id:
            raise ValueError("authorization is scoped to a different job")
        if authorization.used:
            raise ValueError("authorization has already been used")
        if authorization.expires_at < time.time():
            raise ValueError("authorization has expired")
        authorization.used = True
        return True
