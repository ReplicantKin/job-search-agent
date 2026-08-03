#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) in sys.path:
    sys.path.remove(str(SRC_ROOT))
sys.path.insert(0, str(SRC_ROOT))

from job_search_agent.execution import ApplicationExecutorResult
from job_search_agent.adapters import parse_capture
from job_search_agent.credentials import KeychainCredentialStore
from job_search_agent.fit import rank_jobs
from job_search_agent.models import ApplicationResult, JobInput, ReviewDecision, now_iso
from job_search_agent.store import JobStore


def default_db_path() -> Path:
    configured = os.environ.get("JOB_SEARCH_AGENT_DATA_DIR")
    if configured:
        root = Path(configured).expanduser()
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "job-search-agent"
    elif sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "job-search-agent"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "job-search-agent"
    return root / "jobs.sqlite3"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="job-search-agent")
    parser.add_argument("--db", type=Path, default=default_db_path())
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init")
    subparsers.add_parser("daily")

    show = subparsers.add_parser("show")
    show.add_argument("job_id")

    ingest = subparsers.add_parser("ingest")
    capture_input = ingest.add_mutually_exclusive_group(required=True)
    capture_input.add_argument("--json", type=Path, dest="json_path")
    capture_input.add_argument("--html", type=Path, dest="html_path")
    ingest.add_argument("--source")
    ingest.add_argument("--url")
    ingest.add_argument("--checked-at", dest="source_checked_at")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument(
        "--queue",
        choices=[
            "review", "saved", "checked", "apply", "followup", "applied",
            "no_reply", "hr_contact", "rejected", "offer", "withdrawn", "all",
        ],
        default="review",
    )
    list_parser.add_argument("--format", choices=["json", "table"], default="table")

    review = subparsers.add_parser("review")
    review.add_argument("job_id")
    review.add_argument("--decision", choices=["keep", "save", "ready", "skip", "do_not_recommend"], required=True)
    review.add_argument("--reason")

    application = subparsers.add_parser("application")
    application.add_argument("job_id")
    application.add_argument("--status", choices=["in_progress", "submitted_waiting", "hr_contact", "rejected", "withdrawn", "offer"], required=True)
    application.add_argument("--evidence-json", default="{}")
    application.add_argument("--resume-version")
    application.add_argument("--cover-letter-version")
    application.add_argument("--reason")
    application.add_argument("--allow-duplicate", action="store_true")

    authorize = subparsers.add_parser("authorize")
    authorize.add_argument("job_id")
    authorize.add_argument("--ttl-seconds", type=int, default=900)

    execution = subparsers.add_parser("execution-result")
    execution.add_argument("job_id")
    execution.add_argument("--token", required=True)
    execution.add_argument("--status", choices=["submitted", "paused", "failed", "manual_required"], required=True)
    execution.add_argument("--evidence-json", default="{}")
    execution.add_argument("--reason")
    execution.add_argument("--resume-version")
    execution.add_argument("--cover-letter-version")

    export = subparsers.add_parser("export")
    export.add_argument("--json", required=True, type=Path, dest="json_path")
    export.add_argument("--markdown", required=True, type=Path, dest="markdown_path")

    importer = subparsers.add_parser("import")
    importer.add_argument("--json", required=True, type=Path, dest="json_path")

    profile = subparsers.add_parser("profile")
    profile_subparsers = profile.add_subparsers(dest="profile_command", required=True)
    profile_set = profile_subparsers.add_parser("set")
    profile_set.add_argument("--field", required=True)
    profile_set.add_argument("--value", required=True)
    profile_subparsers.add_parser("show")

    credential = subparsers.add_parser("credential")
    credential_subparsers = credential.add_subparsers(dest="credential_command", required=True)
    credential_set = credential_subparsers.add_parser("set")
    credential_set.add_argument("--site", required=True)
    credential_set.add_argument("--username", required=True)
    credential_delete = credential_subparsers.add_parser("delete")
    credential_delete.add_argument("--site", required=True)
    credential_status = credential_subparsers.add_parser("status")
    credential_status.add_argument("--site", required=True)

    material = subparsers.add_parser("material")
    material_subparsers = material.add_subparsers(dest="material_command", required=True)
    material_register = material_subparsers.add_parser("register")
    material_register.add_argument("--kind", choices=["resume", "cover_letter", "answers", "portfolio"], required=True)
    material_register.add_argument("--version", required=True)
    material_register.add_argument("--path", required=True, type=Path)
    material_list = material_subparsers.add_parser("list")
    material_list.add_argument("--kind", choices=["resume", "cover_letter", "answers", "portfolio"])
    material_list.add_argument("--format", choices=["json", "table"], default="table")

    communication = subparsers.add_parser("communication")
    communication_subparsers = communication.add_subparsers(dest="communication_command", required=True)
    communication_record = communication_subparsers.add_parser("record")
    communication_record.add_argument("job_id")
    communication_record.add_argument("--channel", required=True)
    communication_record.add_argument("--direction", choices=["incoming", "draft", "sent"], required=True)
    message_input = communication_record.add_mutually_exclusive_group(required=True)
    message_input.add_argument("--text")
    message_input.add_argument("--text-file", type=Path)
    communication_record.add_argument("--user-confirmed", action="store_true")
    communication_list = communication_subparsers.add_parser("list")
    communication_list.add_argument("job_id")
    communication_list.add_argument("--format", choices=["json", "table"], default="table")

    source_check = subparsers.add_parser("source-check")
    source_check_subparsers = source_check.add_subparsers(dest="source_check_command", required=True)
    source_check_record = source_check_subparsers.add_parser("record")
    source_check_record.add_argument("--source", required=True)
    source_check_record.add_argument("--url", required=True)
    source_check_record.add_argument("--result-count", required=True, type=int)
    source_check_record.add_argument(
        "--status",
        required=True,
        choices=["ok", "empty", "warning", "unreadable"],
    )
    source_check_record.add_argument("--warning", action="append", default=[])
    source_check_record.add_argument("--checked-at", default=None)

    source_check_status = source_check_subparsers.add_parser("status")
    source_check_status.add_argument("--source", required=True)
    source_check_status.add_argument("--url", required=True)
    source_check_status.add_argument("--max-age-hours", type=float, default=24)

    source_check_list = source_check_subparsers.add_parser("list")
    source_check_list.add_argument("--source")
    source_check_list.add_argument("--limit", type=int)
    source_check_list.add_argument("--format", choices=["json", "table"], default="table")
    return parser.parse_args(argv)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_capture(path: Path, is_html: bool) -> Any:
    content = path.read_text(encoding="utf-8")
    return content if is_html else json.loads(content)


def _job_inputs(data: Any) -> list[JobInput]:
    items = data.get("jobs", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("input JSON must be a list or an object with a jobs array")
    fields = {
        "source", "source_job_id", "url", "company", "title", "location", "description",
        "work_mode", "salary", "posted_at", "source_checked_at",
    }
    return [JobInput(**{key: item.get(key) for key in fields if key in item}) for item in items]


def _print_jobs(jobs: list[Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps([asdict(job) for job in jobs], ensure_ascii=False, indent=2))
        return
    if not jobs:
        print("No jobs in this queue.")
        return
    print("ID\tCompany\tTitle\tLocation\tScreening\tApplication")
    for job in jobs:
        print("\t".join([
            job.id, job.company, job.title, job.location,
            job.screening_status, job.application_status,
        ]))


def _ranked_job_payload(jobs: list[Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {**asdict(job), "fit": asdict(assessment)}
        for job, assessment in rank_jobs(jobs, profile)
    ]


def _markdown_export(data: dict[str, Any]) -> str:
    lines = ["# Job Search Agent Export", "", f"Jobs: {len(data['jobs'])}", ""]
    applications_by_job: dict[str, list[dict[str, Any]]] = {}
    for application in data.get("applications", []):
        applications_by_job.setdefault(application["job_id"], []).append(application)
    communications_by_job: dict[str, list[dict[str, Any]]] = {}
    for communication in data.get("communications", []):
        communications_by_job.setdefault(communication["job_id"], []).append(communication)
    for job in data["jobs"]:
        lines.extend([
            f"## {job['company']} — {job['title']}",
            f"- ID: `{job['id']}`",
            f"- Location: {job['location']}",
            f"- Source: {job['source']}",
            f"- URL: {job['url']}",
            f"- Screening: `{job['screening_status']}`",
            f"- Application: `{job['application_status']}`",
        ])
        for application in applications_by_job.get(job["id"], []):
            lines.append(f"- Application record: `{application['status']}`")
            if application.get("resume_version"):
                lines.append(f"- Resume version: `{application['resume_version']}`")
            if application.get("cover_letter_version"):
                lines.append(f"- Cover-letter version: `{application['cover_letter_version']}`")
        for communication in communications_by_job.get(job["id"], []):
            text = " ".join(str(communication.get("text", "")).split())
            lines.append(
                f"- Communication ({communication['direction']} via {communication['channel']}): {text}"
            )
        lines.append("")
    if data.get("materials"):
        lines.extend(["## Registered Materials", ""])
        for material in data["materials"]:
            lines.append(f"- {material['kind']}: `{material['version']}` (SHA-256 `{material['sha256']}`)")
        lines.append("")
    return "\n".join(lines)


def _import_export(store: JobStore, data: dict[str, Any]) -> int:
    for key, value in data.get("profile", {}).items():
        store.set_profile(key, value)
    id_map: dict[str, str] = {}
    for raw in data.get("jobs", []):
        job = store.upsert_job(JobInput(
            source=raw["source"], source_job_id=raw.get("source_job_id"), url=raw["url"],
            company=raw["company"], title=raw["title"], location=raw["location"],
            description=raw.get("description", ""), work_mode=raw.get("work_mode"),
            salary=raw.get("salary"), posted_at=raw.get("posted_at"),
            source_checked_at=raw.get("source_checked_at"),
        ))
        id_map[raw["id"]] = job.id
        screening = raw.get("screening_status")
        reverse = {"reviewed_keep": "keep", "saved": "save", "ready_to_apply": "ready", "skipped": "skip", "do_not_recommend": "do_not_recommend"}
        if screening in reverse:
            current = store.get_job(job.id)
            if current.screening_status != screening or current.review_reason != raw.get("review_reason"):
                store.review_job(job.id, ReviewDecision(reverse[screening], raw.get("review_reason")))
    for raw in data.get("source_checks", []):
        store.import_source_check(
            raw["source"],
            raw["url"],
            raw["checked_at"],
            raw["result_count"],
            raw["status"],
            raw.get("warnings", []),
        )
    for raw in data.get("applications", []):
        new_job_id = id_map.get(raw["job_id"])
        if new_job_id is None:
            continue
        evidence = raw.get("evidence", {})
        candidate = (
            raw["status"],
            json.dumps(evidence, ensure_ascii=False, sort_keys=True),
            raw.get("resume_version"),
            raw.get("cover_letter_version"),
            raw.get("reason"),
            raw.get("submitted_at"),
        )
        existing = {
            (
                record.status,
                json.dumps(record.evidence, ensure_ascii=False, sort_keys=True),
                record.resume_version,
                record.cover_letter_version,
                record.reason,
                record.submitted_at,
            )
            for record in store.list_applications(new_job_id)
        }
        if candidate in existing:
            continue
        store.record_application(
            new_job_id,
            ApplicationResult(
                status=raw["status"], evidence=evidence,
                resume_version=raw.get("resume_version"), cover_letter_version=raw.get("cover_letter_version"),
                reason=raw.get("reason"), submitted_at=raw.get("submitted_at"),
            ),
            allow_duplicate=True,
        )
    for raw in data.get("job_sources", []):
        new_job_id = id_map.get(raw["job_id"])
        if new_job_id is None:
            continue
        store.upsert_job_source(
            new_job_id,
            raw["source"],
            raw.get("source_job_id"),
            raw["url"],
            raw.get("first_seen_at") or now_iso(),
            raw.get("last_checked_at") or raw.get("first_seen_at") or now_iso(),
        )
    for raw in data.get("communications", []):
        new_job_id = id_map.get(raw["job_id"])
        if new_job_id is None:
            continue
        candidate = (raw.get("channel"), raw.get("direction"), raw.get("text"))
        existing = {
            (record.channel, record.direction, record.text)
            for record in store.list_communications(new_job_id)
        }
        if candidate in existing:
            continue
        store.record_communication(
            new_job_id,
            raw.get("channel", "unknown"),
            raw["direction"],
            raw.get("text", ""),
            user_confirmed=raw.get("direction") == "sent",
        )
    for raw in data.get("events", []):
        new_job_id = id_map.get(raw["job_id"])
        if new_job_id is None:
            continue
        store.import_event(
            new_job_id,
            raw["type"],
            raw.get("payload", {}),
            raw["created_at"],
        )
    return len(id_map)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    store = JobStore.open(args.db)
    try:
        if args.command == "init":
            print(args.db)
        elif args.command == "daily":
            profile = store.get_profile()
            print(json.dumps({
                "review": _ranked_job_payload(store.list_jobs("review"), profile),
                "apply": _ranked_job_payload(store.list_jobs("apply"), profile),
                "followup": _ranked_job_payload(store.list_jobs("followup"), profile),
            }, ensure_ascii=False, indent=2))
        elif args.command == "show":
            print(json.dumps(store.job_details(args.job_id), ensure_ascii=False, indent=2))
        elif args.command == "ingest":
            payload = _load_capture(args.json_path or args.html_path, args.html_path is not None)
            warnings: list[str] = []
            if args.source:
                if not args.url:
                    raise ValueError("--url is required when --source is used")
                capture = parse_capture(
                    args.source,
                    payload,
                    source_url=args.url,
                    source_checked_at=args.source_checked_at or now_iso(),
                )
                jobs = capture.jobs
                warnings = capture.warnings
            else:
                jobs = _job_inputs(payload)
            records = [store.upsert_job(job) for job in jobs]
            print(json.dumps({
                "ingested": len(records),
                "job_ids": [job.id for job in records],
                "warnings": warnings,
            }, ensure_ascii=False))
        elif args.command == "source-check":
            if args.source_check_command == "record":
                record = store.record_source_check(
                    args.source,
                    args.url,
                    args.checked_at or now_iso(),
                    args.result_count,
                    args.status,
                    args.warning,
                )
                print(json.dumps(asdict(record), ensure_ascii=False))
            elif args.source_check_command == "status":
                normalized_url = store.normalize_source_check_url(args.url)
                latest = store.latest_source_check(args.source, args.url)
                print(json.dumps({
                    "source": args.source,
                    "url": latest.url if latest is not None else normalized_url,
                    "fresh": store.source_check_is_fresh(
                        args.source,
                        args.url,
                        max_age_hours=args.max_age_hours,
                    ),
                    "latest": asdict(latest) if latest is not None else None,
                }, ensure_ascii=False))
            else:
                records = store.list_source_checks(args.source, args.limit)
                if args.format == "json":
                    print(json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2))
                else:
                    if not records:
                        print("No source checks recorded.")
                    else:
                        print("ID\tSource\tURL\tChecked At\tCount\tStatus")
                        for record in records:
                            print("\t".join([
                                str(record.id), record.source, record.url,
                                record.checked_at, str(record.result_count), record.status,
                            ]))
        elif args.command == "list":
            _print_jobs(store.list_jobs(args.queue), args.format)
        elif args.command == "review":
            record = store.review_job(args.job_id, ReviewDecision(args.decision, args.reason))
            print(json.dumps(asdict(record), ensure_ascii=False))
        elif args.command == "application":
            evidence = json.loads(args.evidence_json)
            record = store.record_application(
                args.job_id,
                ApplicationResult(
                    status=args.status, evidence=evidence, resume_version=args.resume_version,
                    cover_letter_version=args.cover_letter_version, reason=args.reason,
                ),
                allow_duplicate=args.allow_duplicate,
            )
            print(json.dumps(asdict(record), ensure_ascii=False))
        elif args.command == "authorize":
            authorization = store.issue_authorization(args.job_id, ttl_seconds=args.ttl_seconds)
            print(json.dumps({
                "token": authorization.token,
                "job_id": authorization.job_id,
                "expires_at": authorization.expires_at,
                "application_status": store.get_job(args.job_id).application_status,
            }, ensure_ascii=False))
        elif args.command == "execution-result":
            evidence = json.loads(args.evidence_json)
            executor_result = ApplicationExecutorResult(status=args.status, evidence=evidence, reason=args.reason)
            store.consume_authorization(args.token, args.job_id)
            if executor_result.status == "submitted":
                record = store.record_application(
                    args.job_id,
                    ApplicationResult(
                        status="submitted_waiting",
                        evidence=executor_result.evidence,
                        resume_version=args.resume_version,
                        cover_letter_version=args.cover_letter_version,
                    ),
                )
                print(json.dumps(asdict(record), ensure_ascii=False))
            else:
                store.record_execution_event(
                    args.job_id,
                    executor_result.status,
                    {"reason": executor_result.reason, "evidence": executor_result.evidence},
                )
                print(json.dumps({"job_id": args.job_id, "status": executor_result.status, "reason": executor_result.reason}, ensure_ascii=False))
        elif args.command == "export":
            data = store.export_json()
            args.json_path.parent.mkdir(parents=True, exist_ok=True)
            args.markdown_path.parent.mkdir(parents=True, exist_ok=True)
            args.json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            args.markdown_path.write_text(_markdown_export(data), encoding="utf-8")
            print(json.dumps({"jobs": len(data["jobs"]), "json": str(args.json_path), "markdown": str(args.markdown_path)}, ensure_ascii=False))
        elif args.command == "import":
            count = _import_export(store, _load_json(args.json_path))
            print(json.dumps({"imported": count}, ensure_ascii=False))
        elif args.command == "profile":
            if args.profile_command == "show":
                print(json.dumps(store.get_profile(), ensure_ascii=False, indent=2))
            else:
                try:
                    value = json.loads(args.value)
                except json.JSONDecodeError:
                    value = args.value
                store.set_profile(args.field, value)
                print(json.dumps({args.field: value}, ensure_ascii=False))
        elif args.command == "credential":
            if sys.platform != "darwin":
                raise RuntimeError(
                    "local Keychain credentials are only available on macOS; use a browser session or manual fallback"
                )
            credential_store = KeychainCredentialStore()
            if args.credential_command == "set":
                password = getpass.getpass(f"Password for {args.site}: ")
                if not password:
                    raise ValueError("credential password cannot be empty")
                credential_store.set(args.site, args.username, password)
                print(json.dumps({"site": args.site, "stored": True}, ensure_ascii=False))
            elif args.credential_command == "delete":
                credential_store.delete(args.site)
                print(json.dumps({"site": args.site, "deleted": True}, ensure_ascii=False))
            else:
                credential = credential_store.get(args.site)
                print(json.dumps({
                    "site": args.site,
                    "configured": credential is not None,
                    "username": credential.username if credential else None,
                }, ensure_ascii=False))
        elif args.command == "material":
            if args.material_command == "register":
                record = store.register_material(args.kind, args.version, args.path)
                print(json.dumps(asdict(record), ensure_ascii=False))
            else:
                records = store.list_materials(args.kind)
                if args.format == "json":
                    print(json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2))
                else:
                    if not records:
                        print("No materials registered.")
                    else:
                        print("Kind\tVersion\tSHA256\tPath")
                        for record in records:
                            print("\t".join([record.kind, record.version, record.sha256, record.path]))
        elif args.command == "communication":
            if args.communication_command == "record":
                text = args.text
                if args.text_file is not None:
                    text = args.text_file.read_text(encoding="utf-8")
                record = store.record_communication(
                    args.job_id,
                    args.channel,
                    args.direction,
                    text or "",
                    user_confirmed=args.user_confirmed,
                )
                print(json.dumps(asdict(record), ensure_ascii=False))
            else:
                records = store.list_communications(args.job_id)
                if args.format == "json":
                    print(json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2))
                else:
                    if not records:
                        print("No communications recorded.")
                    else:
                        print("ID\tChannel\tDirection\tText")
                        for record in records:
                            print("\t".join([record.id, record.channel, record.direction, record.text]))
        return 0
    except (KeyError, ValueError, json.JSONDecodeError, FileNotFoundError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
