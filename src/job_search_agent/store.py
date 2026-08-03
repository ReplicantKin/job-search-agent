from __future__ import annotations

import json
import hashlib
import secrets
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .dedupe import canonical_job_key, identity_key, job_fingerprint
from .execution import ApplicationAuthorization
from .models import (
    APPLICATION_STATUSES,
    ApplicationRecord,
    ApplicationResult,
    CommunicationRecord,
    COMMUNICATION_DIRECTIONS,
    JobInput,
    JobRecord,
    MaterialRecord,
    ReviewDecision,
    new_id,
    now_iso,
)


def _redact_local_paths(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key.casefold().endswith("_path") or key.casefold() in {"path", "local_path"}:
                redacted[key] = "[local path omitted]"
            else:
                redacted[key] = _redact_local_paths(item)
        return redacted
    if isinstance(value, list):
        return [_redact_local_paths(item) for item in value]
    return value


class JobStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row

    @classmethod
    def open(cls, path: Path) -> "JobStore":
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        store = cls(connection)
        store._create_schema()
        return store

    def close(self) -> None:
        self.connection.close()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                canonical_key TEXT NOT NULL UNIQUE,
                identity_key TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                source TEXT NOT NULL,
                source_job_id TEXT,
                url TEXT NOT NULL,
                company TEXT NOT NULL,
                title TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                work_mode TEXT,
                salary TEXT,
                posted_at TEXT,
                source_checked_at TEXT,
                screening_status TEXT NOT NULL DEFAULT 'new',
                application_status TEXT NOT NULL DEFAULT 'not_applied',
                review_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_queue ON jobs(screening_status, application_status);
            CREATE INDEX IF NOT EXISTS idx_jobs_identity ON jobs(identity_key, fingerprint);

            CREATE TABLE IF NOT EXISTS job_sources (
                job_id TEXT NOT NULL,
                source TEXT NOT NULL,
                source_job_id TEXT,
                url TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_checked_at TEXT NOT NULL,
                PRIMARY KEY(job_id, source, url),
                FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                status TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                resume_version TEXT,
                cover_letter_version TEXT,
                reason TEXT,
                submitted_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id, updated_at);

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS authorizations (
                token TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                expires_at REAL NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                issued_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS profile (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS materials (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                version TEXT NOT NULL,
                path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(kind, version)
            );

            CREATE TABLE IF NOT EXISTS communications (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                direction TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_communications_job ON communications(job_id, created_at);
            """
        )
        self.connection.commit()

    def upsert_job(self, job: JobInput) -> JobRecord:
        canonical = canonical_job_key(
            source=job.source,
            source_job_id=job.source_job_id,
            url=job.url,
            company=job.company,
            title=job.title,
            location=job.location,
        )
        identity = identity_key(company=job.company, title=job.title, location=job.location)
        fingerprint = job_fingerprint(job.description)
        now = now_iso()
        row = self.connection.execute("SELECT * FROM jobs WHERE canonical_key = ?", (canonical,)).fetchone()
        if row is None:
            row = self.connection.execute(
                "SELECT * FROM jobs WHERE identity_key = ? AND fingerprint = ? ORDER BY updated_at DESC LIMIT 1",
                (identity, fingerprint),
            ).fetchone()

        if row is None:
            job_id = new_id("job")
            self.connection.execute(
                """
                INSERT INTO jobs (
                    id, canonical_key, identity_key, fingerprint, source, source_job_id, url,
                    company, title, location, description, work_mode, salary, posted_at,
                    source_checked_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id, canonical, identity, fingerprint, job.source, job.source_job_id,
                    job.url, job.company, job.title, job.location, job.description,
                    job.work_mode, job.salary, job.posted_at, job.source_checked_at or now, now, now,
                ),
            )
            self._add_source(job_id, job, now)
            self._event(job_id, "job_discovered", {"source": job.source, "url": job.url}, now)
        else:
            job_id = row["id"]
            checked_at = job.source_checked_at or row["source_checked_at"] or now
            materially_changed = (
                row["fingerprint"] != fingerprint
                or row["url"] != job.url
                or row["company"] != job.company
                or row["title"] != job.title
                or row["location"] != job.location
            )
            changed = materially_changed or row["source_checked_at"] != checked_at
            next_screening_status = row["screening_status"]
            next_review_reason = row["review_reason"]
            if materially_changed and row["application_status"] == "not_applied":
                next_screening_status = "new"
                next_review_reason = None
            next_updated_at = now if changed else row["updated_at"]
            self.connection.execute(
                """
                UPDATE jobs SET canonical_key = ?, fingerprint = ?, source = ?, source_job_id = ?, url = ?,
                    company = ?, title = ?, location = ?, description = ?, work_mode = ?, salary = ?,
                    posted_at = ?, source_checked_at = ?, screening_status = ?, review_reason = ?, updated_at = ? WHERE id = ?
                """,
                (
                    canonical, fingerprint, job.source, job.source_job_id, job.url, job.company,
                    job.title, job.location, job.description, job.work_mode, job.salary,
                    job.posted_at, checked_at, next_screening_status, next_review_reason, next_updated_at, job_id,
                ),
            )
            self._add_source(job_id, job, now)
            if changed:
                self._event(
                    job_id,
                    "job_updated",
                    {"source": job.source, "url": job.url, "materially_changed": materially_changed},
                    now,
                )

        self.connection.commit()
        return self.get_job(job_id)

    def _add_source(self, job_id: str, job: JobInput, now: str) -> None:
        self.connection.execute(
            """
            INSERT INTO job_sources(job_id, source, source_job_id, url, first_seen_at, last_checked_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id, source, url) DO UPDATE SET
                source_job_id = excluded.source_job_id,
                last_checked_at = excluded.last_checked_at
            """,
            (job_id, job.source, job.source_job_id, job.url, now, job.source_checked_at or now),
        )

    def upsert_job_source(
        self,
        job_id: str,
        source: str,
        source_job_id: str | None,
        url: str,
        first_seen_at: str,
        last_checked_at: str,
    ) -> None:
        self.get_job(job_id)
        if not source.strip() or not url.strip():
            raise ValueError("job source and URL cannot be empty")
        self.connection.execute(
            """
            INSERT INTO job_sources(job_id, source, source_job_id, url, first_seen_at, last_checked_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id, source, url) DO UPDATE SET
                source_job_id = excluded.source_job_id,
                first_seen_at = MIN(job_sources.first_seen_at, excluded.first_seen_at),
                last_checked_at = MAX(job_sources.last_checked_at, excluded.last_checked_at)
            """,
            (job_id, source, source_job_id, url, first_seen_at, last_checked_at),
        )
        self.connection.commit()

    def _event(self, job_id: str, event_type: str, payload: dict[str, Any], created_at: str | None = None) -> None:
        self.connection.execute(
            "INSERT INTO events(job_id, type, payload_json, created_at) VALUES (?, ?, ?, ?)",
            (job_id, event_type, json.dumps(payload, ensure_ascii=False, sort_keys=True), created_at or now_iso()),
        )

    def import_event(
        self,
        job_id: str,
        event_type: str,
        payload: dict[str, Any],
        created_at: str,
    ) -> None:
        """Restore one exported event exactly once without exposing event IDs."""
        self.get_job(job_id)
        if not event_type.strip() or not created_at.strip():
            raise ValueError("event type and timestamp cannot be empty")
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        existing = self.connection.execute(
            """
            SELECT 1 FROM events
            WHERE job_id = ? AND type = ? AND payload_json = ? AND created_at = ?
            LIMIT 1
            """,
            (job_id, event_type, serialized, created_at),
        ).fetchone()
        if existing is None:
            self.connection.execute(
                "INSERT INTO events(job_id, type, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (job_id, event_type, serialized, created_at),
            )
            self.connection.commit()

    def get_job(self, job_id: str) -> JobRecord:
        row = self.connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown job: {job_id}")
        return JobRecord(**dict(row))

    def review_job(self, job_id: str, decision: ReviewDecision) -> JobRecord:
        status = decision.screening_status()
        now = now_iso()
        self.get_job(job_id)
        self.connection.execute(
            "UPDATE jobs SET screening_status = ?, review_reason = ?, updated_at = ? WHERE id = ?",
            (status, decision.reason, now, job_id),
        )
        self._event(job_id, "reviewed", {"decision": decision.decision, "reason": decision.reason}, now)
        self.connection.commit()
        return self.get_job(job_id)

    def record_application(self, job_id: str, result: ApplicationResult, allow_duplicate: bool = False) -> ApplicationRecord:
        if result.status not in APPLICATION_STATUSES - {"not_applied"}:
            raise ValueError(f"invalid application status: {result.status}")
        job = self.get_job(job_id)
        existing = self.connection.execute(
            "SELECT * FROM applications WHERE job_id = ? ORDER BY updated_at DESC LIMIT 1", (job_id,)
        ).fetchone()

        # Follow-up outcomes update the current application attempt. A new
        # in-progress/submitted attempt remains explicitly opt-in so that a
        # re-application cannot overwrite the original history by accident.
        can_update_existing = result.status in {"hr_contact", "rejected", "withdrawn", "offer"}
        can_finish_in_progress = existing is not None and existing["status"] == "in_progress" and result.status == "submitted_waiting"
        if existing is not None and not allow_duplicate and (can_update_existing or can_finish_in_progress):
            now = now_iso()
            submitted_at = result.submitted_at or existing["submitted_at"]
            if submitted_at is None and result.status in {"submitted_waiting", "hr_contact", "offer"}:
                submitted_at = now
            evidence = result.evidence or json.loads(existing["evidence_json"])
            resume_version = result.resume_version or existing["resume_version"]
            cover_letter_version = result.cover_letter_version or existing["cover_letter_version"]
            reason = result.reason if result.reason is not None else existing["reason"]
            self.connection.execute(
                """
                UPDATE applications SET status = ?, evidence_json = ?, resume_version = ?,
                    cover_letter_version = ?, reason = ?, submitted_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    result.status, json.dumps(evidence, ensure_ascii=False, sort_keys=True),
                    resume_version, cover_letter_version, reason,
                    submitted_at, now, existing["id"],
                ),
            )
            self.connection.execute(
                "UPDATE jobs SET application_status = ?, updated_at = ? WHERE id = ?",
                (result.status, now, job_id),
            )
            self._event(
                job_id,
                "application_status_updated",
                {
                    "application_id": existing["id"],
                    "from": existing["status"],
                    "to": result.status,
                    "evidence": evidence,
                    "reason": reason,
                },
                now,
            )
            self.connection.commit()
            return self._get_application(existing["id"])

        if existing is not None and not allow_duplicate:
            raise ValueError(f"application already exists for {job_id}; use explicit override to reapply")

        now = now_iso()
        application_id = new_id("application")
        submitted_at = result.submitted_at or (now if result.status in {"submitted_waiting", "hr_contact", "offer"} else None)
        self.connection.execute(
            """
            INSERT INTO applications(
                id, job_id, status, evidence_json, resume_version, cover_letter_version,
                reason, submitted_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application_id, job_id, result.status, json.dumps(result.evidence, ensure_ascii=False, sort_keys=True),
                result.resume_version, result.cover_letter_version, result.reason, submitted_at, now, now,
            ),
        )
        screening_status = job.screening_status if job.screening_status == "ready_to_apply" else "ready_to_apply"
        self.connection.execute(
            "UPDATE jobs SET screening_status = ?, application_status = ?, updated_at = ? WHERE id = ?",
            (screening_status, result.status, now, job_id),
        )
        self._event(
            job_id,
            "application_recorded",
            {"application_id": application_id, "status": result.status, "evidence": result.evidence},
            now,
        )
        self.connection.commit()
        return self._get_application(application_id)

    def issue_authorization(self, job_id: str, ttl_seconds: int = 900) -> ApplicationAuthorization:
        job = self.get_job(job_id)
        if job.screening_status != "ready_to_apply":
            raise ValueError("job must be marked ready_to_apply before authorization")
        if job.application_status not in {"not_applied", "in_progress"}:
            raise ValueError("job already has a completed application")
        active = self.connection.execute(
            "SELECT token FROM authorizations WHERE job_id = ? AND used = 0 AND expires_at > ? LIMIT 1",
            (job_id, time.time()),
        ).fetchone()
        if active is not None:
            raise ValueError("job already has an active authorization")
        if job.application_status == "not_applied":
            self.record_application(
                job_id,
                ApplicationResult(status="in_progress", evidence={}),
            )
        token = secrets.token_urlsafe(32)
        now = now_iso()
        expires_at = time.time() + ttl_seconds
        self.connection.execute(
            "INSERT INTO authorizations(token, job_id, expires_at, used, issued_at) VALUES (?, ?, ?, 0, ?)",
            (token, job_id, expires_at, now),
        )
        self._event(job_id, "authorization_issued", {"expires_at": expires_at}, now)
        self.connection.commit()
        return ApplicationAuthorization(token=token, job_id=job_id, expires_at=expires_at)

    def consume_authorization(self, token: str, job_id: str) -> bool:
        row = self.connection.execute("SELECT * FROM authorizations WHERE token = ?", (token,)).fetchone()
        if row is None:
            raise ValueError("unknown authorization")
        if row["job_id"] != job_id:
            raise ValueError("authorization is scoped to a different job")
        if row["used"]:
            raise ValueError("authorization has already been used")
        if row["expires_at"] < time.time():
            raise ValueError("authorization has expired")
        now = now_iso()
        self.connection.execute("UPDATE authorizations SET used = 1 WHERE token = ?", (token,))
        self._event(job_id, "authorization_consumed", {}, now)
        self.connection.commit()
        return True

    def record_execution_event(self, job_id: str, status: str, payload: dict[str, Any]) -> None:
        if status not in {"paused", "failed", "manual_required"}:
            raise ValueError(f"execution event cannot use status: {status}")
        self.get_job(job_id)
        self._event(job_id, f"execution_{status}", payload)
        self.connection.commit()

    def set_profile(self, key: str, value: Any) -> None:
        if not key.strip():
            raise ValueError("profile key cannot be empty")
        self.connection.execute(
            """
            INSERT INTO profile(key, value_json, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at
            """,
            (key.strip(), json.dumps(value, ensure_ascii=False, sort_keys=True), now_iso()),
        )
        self.connection.commit()

    def get_profile(self) -> dict[str, Any]:
        rows = self.connection.execute("SELECT key, value_json FROM profile ORDER BY key").fetchall()
        return {row["key"]: json.loads(row["value_json"]) for row in rows}

    def register_material(self, kind: str, version: str, path: Path) -> MaterialRecord:
        allowed_kinds = {"resume", "cover_letter", "answers", "portfolio"}
        clean_kind = kind.strip()
        clean_version = version.strip()
        material_path = path.expanduser().resolve()
        if clean_kind not in allowed_kinds:
            raise ValueError(f"unknown material kind: {clean_kind}")
        if not clean_version:
            raise ValueError("material version cannot be empty")
        if not material_path.is_file():
            raise FileNotFoundError(f"material file not found: {material_path}")
        digest = hashlib.sha256(material_path.read_bytes()).hexdigest()
        size_bytes = material_path.stat().st_size
        now = now_iso()
        existing = self.connection.execute(
            "SELECT id, created_at FROM materials WHERE kind = ? AND version = ?",
            (clean_kind, clean_version),
        ).fetchone()
        material_id = existing["id"] if existing else new_id("material")
        created_at = existing["created_at"] if existing else now
        self.connection.execute(
            """
            INSERT INTO materials(id, kind, version, path, sha256, size_bytes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(kind, version) DO UPDATE SET
                path = excluded.path, sha256 = excluded.sha256, size_bytes = excluded.size_bytes,
                updated_at = excluded.updated_at
            """,
            (material_id, clean_kind, clean_version, str(material_path), digest, size_bytes, created_at, now),
        )
        self.connection.commit()
        return self._get_material(material_id)

    def list_materials(self, kind: str | None = None) -> list[MaterialRecord]:
        if kind is None:
            rows = self.connection.execute("SELECT * FROM materials ORDER BY kind, version").fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM materials WHERE kind = ? ORDER BY version", (kind,)
            ).fetchall()
        return [MaterialRecord(**dict(row)) for row in rows]

    def _get_application(self, application_id: str) -> ApplicationRecord:
        row = self.connection.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown application: {application_id}")
        data = dict(row)
        data["evidence"] = json.loads(data.pop("evidence_json"))
        return ApplicationRecord(**data)

    def list_applications(self, job_id: str) -> list[ApplicationRecord]:
        self.get_job(job_id)
        rows = self.connection.execute(
            "SELECT id FROM applications WHERE job_id = ? ORDER BY created_at, id", (job_id,)
        ).fetchall()
        return [self._get_application(row["id"]) for row in rows]

    def _get_material(self, material_id: str) -> MaterialRecord:
        row = self.connection.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown material: {material_id}")
        return MaterialRecord(**dict(row))

    def _get_communication(self, communication_id: str) -> CommunicationRecord:
        row = self.connection.execute(
            "SELECT * FROM communications WHERE id = ?", (communication_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown communication: {communication_id}")
        return CommunicationRecord(**dict(row))

    def record_communication(
        self,
        job_id: str,
        channel: str,
        direction: str,
        text: str,
        *,
        user_confirmed: bool = False,
    ) -> CommunicationRecord:
        self.get_job(job_id)
        clean_channel = channel.strip()
        clean_text = text.strip()
        if not clean_channel:
            raise ValueError("communication channel cannot be empty")
        if direction not in COMMUNICATION_DIRECTIONS:
            raise ValueError(f"invalid communication direction: {direction}")
        if not clean_text:
            raise ValueError("communication text cannot be empty")
        if direction == "sent" and not user_confirmed:
            raise ValueError("recording a sent message requires explicit user confirmation")
        if direction == "incoming":
            application = self.connection.execute(
                "SELECT status FROM applications WHERE job_id = ? ORDER BY updated_at DESC LIMIT 1",
                (job_id,),
            ).fetchone()
            if application is not None and application["status"] in {"in_progress", "submitted_waiting"}:
                self.record_application(
                    job_id,
                    ApplicationResult(
                        status="hr_contact",
                        evidence={"user_confirmed": True, "channel": clean_channel},
                        reason="HR message recorded locally",
                    ),
                )
        communication_id = new_id("communication")
        now = now_iso()
        self.connection.execute(
            "INSERT INTO communications(id, job_id, channel, direction, text, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (communication_id, job_id, clean_channel, direction, clean_text, now),
        )
        self._event(
            job_id,
            "communication_recorded",
            {"communication_id": communication_id, "channel": clean_channel, "direction": direction},
            now,
        )
        self.connection.commit()
        return self._get_communication(communication_id)

    def list_communications(self, job_id: str) -> list[CommunicationRecord]:
        self.get_job(job_id)
        rows = self.connection.execute(
            "SELECT id FROM communications WHERE job_id = ? ORDER BY rowid", (job_id,)
        ).fetchall()
        return [self._get_communication(row["id"]) for row in rows]

    def list_jobs(self, queue: str = "all") -> list[JobRecord]:
        clauses = {
            "review": ("screening_status = ?", ("new",)),
            "saved": ("screening_status = ?", ("saved",)),
            "checked": (
                "screening_status != ?",
                ("new",),
            ),
            "apply": ("screening_status = ? AND application_status = ?", ("ready_to_apply", "not_applied")),
            "followup": ("application_status IN (?, ?)", ("submitted_waiting", "hr_contact")),
            "applied": ("application_status != ?", ("not_applied",)),
            "no_reply": ("application_status = ?", ("submitted_waiting",)),
            "hr_contact": ("application_status = ?", ("hr_contact",)),
            "rejected": ("application_status = ?", ("rejected",)),
            "offer": ("application_status = ?", ("offer",)),
            "withdrawn": ("application_status = ?", ("withdrawn",)),
            "all": ("1 = 1", ()),
        }
        if queue not in clauses:
            raise ValueError(f"unknown queue: {queue}")
        where, params = clauses[queue]
        rows = self.connection.execute(f"SELECT * FROM jobs WHERE {where} ORDER BY updated_at DESC", params).fetchall()
        return [JobRecord(**dict(row)) for row in rows]

    def events_for(self, job_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT type, payload_json, created_at FROM events WHERE job_id = ? ORDER BY id", (job_id,)).fetchall()
        return [{"type": row["type"], "payload": json.loads(row["payload_json"]), "created_at": row["created_at"]} for row in rows]

    def job_details(self, job_id: str) -> dict[str, Any]:
        """Return one job with source, application, and event history for audit views."""
        job = self.get_job(job_id)
        sources = self.connection.execute(
            "SELECT * FROM job_sources WHERE job_id = ? ORDER BY first_seen_at, url", (job_id,)
        ).fetchall()
        return {
            "job": asdict(job),
            "sources": [dict(row) for row in sources],
            "applications": [asdict(record) for record in self.list_applications(job_id)],
            "communications": [asdict(record) for record in self.list_communications(job_id)],
            "events": self.events_for(job_id),
        }

    def export_json(self) -> dict[str, Any]:
        jobs = [dict(row) for row in self.connection.execute("SELECT * FROM jobs ORDER BY created_at").fetchall()]
        sources = [dict(row) for row in self.connection.execute("SELECT * FROM job_sources ORDER BY first_seen_at").fetchall()]
        applications = []
        for row in self.connection.execute("SELECT * FROM applications ORDER BY created_at").fetchall():
            data = dict(row)
            data["evidence"] = _redact_local_paths(json.loads(data.pop("evidence_json")))
            applications.append(data)
        events = []
        for row in self.connection.execute("SELECT * FROM events ORDER BY id").fetchall():
            data = dict(row)
            data["payload"] = _redact_local_paths(json.loads(data.pop("payload_json")))
            events.append(data)
        materials = []
        for row in self.connection.execute("SELECT * FROM materials ORDER BY kind, version").fetchall():
            data = dict(row)
            data.pop("path", None)
            materials.append(data)
        communications = [
            dict(row)
            for row in self.connection.execute(
                "SELECT * FROM communications ORDER BY created_at, id"
            ).fetchall()
        ]
        return {
            "version": 1,
            "profile": self.get_profile(),
            "jobs": jobs,
            "job_sources": sources,
            "applications": applications,
            "events": events,
            "materials": materials,
            "communications": communications,
        }
