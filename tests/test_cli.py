import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.job_search_agent import main


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db = self.root / "jobs.sqlite3"
        self.input_file = self.root / "jobs.json"
        self.input_file.write_text(
            json.dumps(
                {
                    "jobs": [
                        {
                            "source": "company",
                            "source_job_id": "role-100",
                            "url": "https://example.com/jobs/role-100",
                            "company": "示例公司",
                            "title": "解决方案顾问",
                            "location": "深圳",
                            "description": "负责客户需求分析和方案演示。",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["--db", str(self.db), *args])
        return exit_code, output.getvalue()

    def test_ingest_and_review_queues_are_json_serializable(self):
        exit_code, _ = self.run_cli("ingest", "--json", str(self.input_file))
        self.assertEqual(exit_code, 0)

        exit_code, output = self.run_cli("list", "--queue", "review", "--format", "json")
        self.assertEqual(exit_code, 0)
        jobs = json.loads(output)
        self.assertEqual(len(jobs), 1)
        job_id = jobs[0]["id"]

        exit_code, _ = self.run_cli("review", job_id, "--decision", "ready")
        self.assertEqual(exit_code, 0)
        exit_code, output = self.run_cli("list", "--queue", "apply", "--format", "json")
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(json.loads(output)), 1)

    def test_export_writes_json_and_markdown_without_credentials(self):
        self.run_cli("ingest", "--json", str(self.input_file))
        json_file = self.root / "export.json"
        markdown_file = self.root / "export.md"

        exit_code, _ = self.run_cli(
            "export", "--json", str(json_file), "--markdown", str(markdown_file)
        )

        self.assertEqual(exit_code, 0)
        self.assertTrue(json_file.exists())
        self.assertTrue(markdown_file.exists())
        self.assertNotIn("password", json_file.read_text(encoding="utf-8").lower())
        self.assertIn("解决方案顾问", markdown_file.read_text(encoding="utf-8"))

    def test_authorize_and_record_execution_result(self):
        self.run_cli("ingest", "--json", str(self.input_file))
        _, review_output = self.run_cli("list", "--queue", "review", "--format", "json")
        job_id = json.loads(review_output)[0]["id"]
        self.run_cli("review", job_id, "--decision", "ready")

        exit_code, authorization_output = self.run_cli("authorize", job_id)
        self.assertEqual(exit_code, 0)
        authorization = json.loads(authorization_output)
        self.assertEqual(authorization["application_status"], "in_progress")

        _, apply_queue = self.run_cli("list", "--queue", "apply", "--format", "json")
        self.assertEqual(json.loads(apply_queue), [])

        exit_code, result_output = self.run_cli(
            "execution-result",
            job_id,
            "--token",
            authorization["token"],
            "--status",
            "submitted",
            "--evidence-json",
            '{"confirmation_url":"https://example.com/confirmation/100"}',
            "--resume-version",
            "resume-v1",
            "--cover-letter-version",
            "letter-v1",
        )
        self.assertEqual(exit_code, 0)
        result = json.loads(result_output)
        self.assertEqual(result["status"], "submitted_waiting")
        self.assertEqual(result["resume_version"], "resume-v1")
        self.assertEqual(result["cover_letter_version"], "letter-v1")

        _, all_output = self.run_cli("list", "--queue", "all", "--format", "json")
        self.assertEqual(json.loads(all_output)[0]["application_status"], "submitted_waiting")

    def test_profile_can_be_set_and_read_as_json(self):
        exit_code, _ = self.run_cli(
            "profile", "set", "--field", "locations", "--value", '["深圳", "广州"]'
        )
        self.assertEqual(exit_code, 0)
        exit_code, output = self.run_cli("profile", "show")
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output)["locations"], ["深圳", "广州"])

    def test_daily_returns_all_action_queues_in_one_payload(self):
        self.run_cli("ingest", "--json", str(self.input_file))
        _, output = self.run_cli("daily")
        payload = json.loads(output)

        self.assertEqual(set(payload), {"review", "apply", "followup"})
        self.assertEqual(len(payload["review"]), 1)
        self.assertEqual(payload["apply"], [])
        self.assertEqual(payload["followup"], [])

    def test_daily_includes_explainable_fit_assessment_from_local_profile(self):
        self.run_cli(
            "profile", "set", "--field", "target_roles", "--value", '["解决方案顾问"]'
        )
        self.run_cli(
            "profile", "set", "--field", "locations", "--value", '["深圳"]'
        )
        self.run_cli("ingest", "--json", str(self.input_file))

        _, output = self.run_cli("daily")
        assessment = json.loads(output)["review"][0]["fit"]

        self.assertEqual(assessment["verdict"], "strong_match")
        self.assertEqual(assessment["score"], 100.0)
        self.assertIn("role", assessment["matched_dimensions"])

    def test_ingest_can_normalize_a_source_capture(self):
        capture_file = self.root / "boss-capture.json"
        capture_file.write_text(
            json.dumps(
                {
                    "jobs": [
                        {
                            "encryptJobId": "boss-capture-1",
                            "jobName": "解决方案顾问",
                            "brandName": "示例科技",
                            "cityName": "深圳",
                            "postDescription": "负责客户需求分析和方案演示。",
                            "jobUrl": "https://www.zhipin.com/job_detail/boss-capture-1.html",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        exit_code, output = self.run_cli(
            "ingest",
            "--source",
            "boss",
            "--json",
            str(capture_file),
            "--url",
            "https://www.zhipin.com/web/geek/job?query=解决方案顾问",
            "--checked-at",
            "2026-08-04",
        )

        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["ingested"], 1)
        self.assertEqual(payload["warnings"], [])

    def test_ingest_can_normalize_company_html_capture(self):
        html_file = self.root / "company.html"
        html_file.write_text(
            """<script type=\"application/ld+json\">{"@type":"JobPosting","title":"售前顾问","description":"负责企业客户方案。","url":"https://careers.example.com/jobs/7","identifier":{"value":"7"},"hiringOrganization":{"name":"示例公司"},"jobLocation":{"address":{"addressLocality":"广州"}}}</script>""",
            encoding="utf-8",
        )

        exit_code, output = self.run_cli(
            "ingest",
            "--source",
            "company",
            "--html",
            str(html_file),
            "--url",
            "https://careers.example.com/jobs/7",
            "--checked-at",
            "2026-08-04",
        )

        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["ingested"], 1)
        self.assertEqual(payload["warnings"], [])

    def test_material_register_and_list_are_local_version_references(self):
        material_path = self.root / "resume-v1.md"
        material_path.write_text("approved resume", encoding="utf-8")

        exit_code, output = self.run_cli(
            "material", "register", "--kind", "resume", "--version", "resume-v1",
            "--path", str(material_path),
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output)["version"], "resume-v1")
        exit_code, output = self.run_cli("material", "list", "--format", "json")
        self.assertEqual(exit_code, 0)
        records = json.loads(output)
        self.assertEqual(records[0]["kind"], "resume")
        self.assertEqual(records[0]["version"], "resume-v1")

        markdown_file = self.root / "materials-export.md"
        json_file = self.root / "materials-export.json"
        self.run_cli("export", "--json", str(json_file), "--markdown", str(markdown_file))
        markdown = markdown_file.read_text(encoding="utf-8")
        self.assertIn("resume-v1", markdown)
        self.assertNotIn(str(material_path.resolve()), markdown)

    def test_list_supports_management_views_for_saved_checked_and_applied_roles(self):
        self.run_cli("ingest", "--json", str(self.input_file))
        _, review_output = self.run_cli("list", "--queue", "review", "--format", "json")
        job_id = json.loads(review_output)[0]["id"]
        self.run_cli("review", job_id, "--decision", "save", "--reason", "先收藏")

        _, saved_output = self.run_cli("list", "--queue", "saved", "--format", "json")
        self.assertEqual([job["id"] for job in json.loads(saved_output)], [job_id])
        _, checked_output = self.run_cli("list", "--queue", "checked", "--format", "json")
        self.assertEqual([job["id"] for job in json.loads(checked_output)], [job_id])
        _, applied_output = self.run_cli("list", "--queue", "applied", "--format", "json")
        self.assertEqual(json.loads(applied_output), [])

    def test_show_returns_a_traceable_job_record(self):
        self.run_cli("ingest", "--json", str(self.input_file))
        _, review_output = self.run_cli("list", "--queue", "review", "--format", "json")
        job_id = json.loads(review_output)[0]["id"]
        self.run_cli("application", job_id, "--status", "submitted_waiting", "--evidence-json", '{"application_id":"cli-app-1"}')

        exit_code, output = self.run_cli("show", job_id)

        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["job"]["id"], job_id)
        self.assertEqual(payload["applications"][0]["evidence"], {"application_id": "cli-app-1"})
        self.assertTrue(payload["events"])

    def test_importing_the_same_export_twice_does_not_duplicate_application_attempts(self):
        self.run_cli("ingest", "--json", str(self.input_file))
        _, review_output = self.run_cli("list", "--queue", "review", "--format", "json")
        job_id = json.loads(review_output)[0]["id"]
        self.run_cli(
            "application", job_id, "--status", "submitted_waiting",
            "--evidence-json", '{"application_id":"idempotent-1"}',
        )
        export_file = self.root / "round-trip.json"
        self.run_cli("export", "--json", str(export_file), "--markdown", str(self.root / "round-trip.md"))

        self.run_cli("import", "--json", str(export_file))
        self.run_cli("import", "--json", str(export_file))

        _, details_output = self.run_cli("show", job_id)
        details = json.loads(details_output)
        self.assertEqual(len(details["applications"]), 1)

    def test_communication_command_records_draft_without_sending(self):
        self.run_cli("ingest", "--json", str(self.input_file))
        _, review_output = self.run_cli("list", "--queue", "review", "--format", "json")
        job_id = json.loads(review_output)[0]["id"]

        exit_code, output = self.run_cli(
            "communication", "record", job_id,
            "--channel", "boss", "--direction", "draft", "--text", "你好，我会在确认后回复你。",
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output)["direction"], "draft")
        exit_code, output = self.run_cli("communication", "list", job_id, "--format", "json")
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output)[0]["text"], "你好，我会在确认后回复你。")

    def test_export_import_preserves_communication_history_without_duplicates(self):
        self.run_cli("ingest", "--json", str(self.input_file))
        _, review_output = self.run_cli("list", "--queue", "review", "--format", "json")
        job_id = json.loads(review_output)[0]["id"]
        self.run_cli(
            "communication", "record", job_id,
            "--channel", "boss", "--direction", "incoming", "--text", "您好，请问何时方便沟通？",
        )
        export_file = self.root / "communication-export.json"
        markdown_file = self.root / "communication-export.md"
        self.run_cli("export", "--json", str(export_file), "--markdown", str(markdown_file))
        self.assertIn("您好，请问何时方便沟通？", markdown_file.read_text(encoding="utf-8"))

        self.db = self.root / "imported.sqlite3"
        self.run_cli("import", "--json", str(export_file))
        self.run_cli("import", "--json", str(export_file))

        _, jobs_output = self.run_cli("list", "--queue", "all", "--format", "json")
        imported_job_id = json.loads(jobs_output)[0]["id"]
        _, details_output = self.run_cli("show", imported_job_id)
        details = json.loads(details_output)
        self.assertEqual(len(details["communications"]), 1)
        self.assertEqual(details["communications"][0]["direction"], "incoming")

    def test_export_import_preserves_all_job_source_history(self):
        alternate_file = self.root / "alternate-source.json"
        alternate_file.write_text(
            json.dumps(
                {
                    "jobs": [
                        {
                            "source": "boss",
                            "source_job_id": "boss-source-1",
                            "url": "https://www.zhipin.com/job_detail/boss-source-1.html",
                            "company": "示例公司",
                            "title": "解决方案顾问",
                            "location": "深圳",
                            "description": "负责客户需求分析和方案演示。",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.run_cli("ingest", "--json", str(self.input_file))
        self.run_cli("ingest", "--json", str(alternate_file))
        _, jobs_output = self.run_cli("list", "--queue", "all", "--format", "json")
        job_id = json.loads(jobs_output)[0]["id"]
        export_file = self.root / "source-history.json"
        self.run_cli("export", "--json", str(export_file), "--markdown", str(self.root / "source-history.md"))

        self.db = self.root / "source-history-imported.sqlite3"
        self.run_cli("import", "--json", str(export_file))
        self.run_cli("import", "--json", str(export_file))
        _, imported_jobs = self.run_cli("list", "--queue", "all", "--format", "json")
        imported_job_id = json.loads(imported_jobs)[0]["id"]
        _, details_output = self.run_cli("show", imported_job_id)

        details = json.loads(details_output)
        self.assertEqual(len(details["sources"]), 2)

    def test_export_import_preserves_original_event_timestamps_idempotently(self):
        self.run_cli("ingest", "--json", str(self.input_file))
        _, jobs_output = self.run_cli("list", "--queue", "all", "--format", "json")
        job_id = json.loads(jobs_output)[0]["id"]
        export_file = self.root / "event-history.json"
        self.run_cli("export", "--json", str(export_file), "--markdown", str(self.root / "event-history.md"))
        exported = json.loads(export_file.read_text(encoding="utf-8"))
        for event in exported["events"]:
            event["created_at"] = "2020-01-01T00:00:00+00:00"
        export_file.write_text(json.dumps(exported, ensure_ascii=False), encoding="utf-8")
        original_events = {
            (event["type"], event["created_at"])
            for event in exported["events"]
            if event["job_id"] == job_id
        }

        self.db = self.root / "event-history-imported.sqlite3"
        self.run_cli("import", "--json", str(export_file))
        self.run_cli("import", "--json", str(export_file))
        _, imported_jobs = self.run_cli("list", "--queue", "all", "--format", "json")
        imported_job_id = json.loads(imported_jobs)[0]["id"]
        _, details_output = self.run_cli("show", imported_job_id)
        imported_events = {
            (event["type"], event["created_at"])
            for event in json.loads(details_output)["events"]
        }

        self.assertTrue(original_events.issubset(imported_events))

    def test_importing_reviewed_export_twice_does_not_append_review_events(self):
        self.run_cli("ingest", "--json", str(self.input_file))
        _, jobs_output = self.run_cli("list", "--queue", "all", "--format", "json")
        job_id = json.loads(jobs_output)[0]["id"]
        self.run_cli("review", job_id, "--decision", "save", "--reason", "先观察")
        export_file = self.root / "reviewed-history.json"
        self.run_cli("export", "--json", str(export_file), "--markdown", str(self.root / "reviewed-history.md"))

        self.db = self.root / "reviewed-history-imported.sqlite3"
        self.run_cli("import", "--json", str(export_file))
        _, imported_jobs = self.run_cli("list", "--queue", "all", "--format", "json")
        imported_job_id = json.loads(imported_jobs)[0]["id"]
        _, first_details = self.run_cli("show", imported_job_id)
        first_count = len([event for event in json.loads(first_details)["events"] if event["type"] == "reviewed"])

        self.run_cli("import", "--json", str(export_file))
        _, second_details = self.run_cli("show", imported_job_id)
        second_count = len([event for event in json.loads(second_details)["events"] if event["type"] == "reviewed"])

        self.assertEqual(second_count, first_count)


if __name__ == "__main__":
    unittest.main()
