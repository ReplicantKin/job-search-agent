import json
import tempfile
import unittest
from pathlib import Path

from job_search_agent.models import ApplicationResult, JobInput, ReviewDecision
from job_search_agent.store import JobStore


class JobStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "jobs.sqlite3"
        self.store = JobStore.open(self.db_path)

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_upsert_creates_job_with_separate_status_axes(self):
        job = self.store.upsert_job(
            JobInput(
                source="boss",
                source_job_id="boss-123",
                url="https://www.zhipin.com/job_detail/boss-123.html",
                company="示例科技",
                title="解决方案顾问",
                location="深圳",
                description="负责客户需求分析与方案演示。",
            )
        )

        self.assertEqual(job.screening_status, "new")
        self.assertEqual(job.application_status, "not_applied")
        self.assertEqual(job.company, "示例科技")

    def test_review_decision_does_not_change_application_status(self):
        job = self.store.upsert_job(
            JobInput(
                source="company",
                source_job_id="role-1",
                url="https://example.com/jobs/role-1",
                company="示例公司",
                title="售前产品经理",
                location="广州",
                description="面向企业客户推进产品解决方案。",
            )
        )

        reviewed = self.store.review_job(
            job.id,
            ReviewDecision(decision="save", reason="方向匹配，先观察")
        )

        self.assertEqual(reviewed.screening_status, "saved")
        self.assertEqual(reviewed.application_status, "not_applied")
        events = self.store.events_for(job.id)
        self.assertEqual(events[-1]["type"], "reviewed")

    def test_reviewed_job_returns_to_review_only_when_job_content_changes(self):
        job = self.store.upsert_job(
            JobInput(
                source="company",
                source_job_id="role-reviewed-again",
                url="https://example.com/jobs/role-reviewed-again",
                company="示例公司",
                title="售前产品经理",
                location="广州",
                description="面向企业客户推进产品解决方案。",
            )
        )
        self.store.review_job(job.id, ReviewDecision(decision="save", reason="先观察"))

        unchanged = self.store.upsert_job(
            JobInput(
                source="company",
                source_job_id="role-reviewed-again",
                url="https://example.com/jobs/role-reviewed-again",
                company="示例公司",
                title="售前产品经理",
                location="广州",
                description="面向企业客户推进产品解决方案。",
            )
        )
        self.assertEqual(unchanged.screening_status, "saved")
        self.assertEqual(self.store.list_jobs("review"), [])

        refreshed = self.store.upsert_job(
            JobInput(
                source="company",
                source_job_id="role-reviewed-again",
                url="https://example.com/jobs/role-reviewed-again",
                company="示例公司",
                title="售前产品经理",
                location="广州",
                description="面向企业客户推进产品解决方案，新增职责说明。",
            )
        )

        self.assertEqual(refreshed.screening_status, "new")
        self.assertEqual(len(self.store.list_jobs("review")), 1)

    def test_same_source_job_id_merges_when_detail_url_changes(self):
        first = self.store.upsert_job(
            JobInput(
                source="BOSS 直聘", source_job_id="stable-id", url="https://example.com/jobs/old",
                company="示例公司", title="售前顾问", location="深圳", description="旧版职责。",
            )
        )

        refreshed = self.store.upsert_job(
            JobInput(
                source="boss", source_job_id="stable-id", url="https://example.com/jobs/new",
                company="示例公司", title="售前顾问", location="深圳", description="新版职责。",
            )
        )

        self.assertEqual(refreshed.id, first.id)
        self.assertEqual(refreshed.url, "https://example.com/jobs/new")
        self.assertEqual(refreshed.description, "新版职责。")
        self.assertEqual(len(self.store.list_jobs("all")), 1)
        self.assertEqual(self.store.events_for(first.id)[-1]["type"], "job_updated")

    def test_submitted_application_is_recorded_with_evidence(self):
        job = self.store.upsert_job(
            JobInput(
                source="company",
                source_job_id="role-2",
                url="https://example.com/jobs/role-2",
                company="示例公司",
                title="客户成功经理",
                location="上海",
                description="负责客户成功和产品落地。",
            )
        )

        result = self.store.record_application(
            job.id,
            ApplicationResult(
                status="submitted_waiting",
                evidence={"confirmation_url": "https://example.com/thanks/123"},
                resume_version="resume-v1",
                cover_letter_version="letter-v1",
            ),
        )

        self.assertEqual(result.status, "submitted_waiting")
        refreshed = self.store.get_job(job.id)
        self.assertEqual(refreshed.application_status, "submitted_waiting")
        self.assertEqual(refreshed.screening_status, "ready_to_apply")

    def test_duplicate_application_is_rejected_without_explicit_override(self):
        job = self.store.upsert_job(
            JobInput(
                source="company",
                source_job_id="role-3",
                url="https://example.com/jobs/role-3",
                company="示例公司",
                title="产品商业化经理",
                location="深圳",
                description="推进企业产品商业化。",
            )
        )
        self.store.record_application(
            job.id,
            ApplicationResult(status="submitted_waiting", evidence={"receipt": "abc"}),
        )

        with self.assertRaises(ValueError):
            self.store.record_application(
                job.id,
                ApplicationResult(status="in_progress", evidence={}),
            )

    def test_followup_status_updates_existing_application_without_new_attempt(self):
        job = self.store.upsert_job(
            JobInput(
                source="company",
                source_job_id="role-followup",
                url="https://example.com/jobs/role-followup",
                company="示例公司",
                title="解决方案顾问",
                location="深圳",
                description="帮助客户完成方案落地。",
            )
        )
        submitted = self.store.record_application(
            job.id,
            ApplicationResult(
                status="submitted_waiting",
                evidence={"confirmation_url": "https://example.com/thanks/followup"},
                resume_version="resume-v1",
                cover_letter_version="letter-v1",
            ),
        )

        updated = self.store.record_application(
            job.id,
            ApplicationResult(
                status="hr_contact",
                evidence={"message_url": "https://example.com/messages/1"},
            ),
        )

        self.assertEqual(updated.id, submitted.id)
        self.assertEqual(updated.status, "hr_contact")
        self.assertEqual(updated.resume_version, "resume-v1")
        self.assertEqual(updated.cover_letter_version, "letter-v1")
        self.assertEqual(self.store.get_job(job.id).application_status, "hr_contact")
        application_events = [event for event in self.store.events_for(job.id) if event["type"].startswith("application")]
        self.assertEqual([event["type"] for event in application_events], ["application_recorded", "application_status_updated"])

    def test_in_progress_can_transition_to_submitted_waiting_without_duplicate_attempt(self):
        job = self.store.upsert_job(
            JobInput(
                source="company",
                source_job_id="role-progress",
                url="https://example.com/jobs/role-progress",
                company="示例公司",
                title="售前产品经理",
                location="广州",
                description="推进企业产品方案。",
            )
        )
        started = self.store.record_application(
            job.id,
            ApplicationResult(status="in_progress", evidence={}),
        )

        submitted = self.store.record_application(
            job.id,
            ApplicationResult(
                status="submitted_waiting",
                evidence={"application_id": "app-1"},
            ),
        )

        self.assertEqual(submitted.id, started.id)
        self.assertEqual(submitted.status, "submitted_waiting")

    def test_export_contains_jobs_and_events_but_no_credentials(self):
        self.store.upsert_job(
            JobInput(
                source="boss",
                source_job_id="role-4",
                url="https://example.com/jobs/role-4",
                company="示例公司",
                title="解决方案顾问",
                location="深圳",
                description="帮助客户完成方案落地。",
            )
        )
        exported = self.store.export_json()
        serialized = json.dumps(exported, ensure_ascii=False)

        self.assertIn("jobs", exported)
        self.assertIn("events", exported)
        self.assertNotIn("password", serialized.lower())
        self.assertNotIn("credential", serialized.lower())

    def test_export_redacts_local_paths_inside_application_evidence(self):
        job = self.store.upsert_job(
            JobInput(
                source="company", source_job_id="evidence-path", url="https://example.com/evidence-path",
                company="示例公司", title="解决方案顾问", location="深圳", description="客户方案。",
            )
        )
        local_screenshot = str(Path(self.temp_dir.name) / "private" / "confirmation.png")
        self.store.record_application(
            job.id,
            ApplicationResult(
                status="submitted_waiting",
                evidence={
                    "confirmation_url": "https://example.com/confirmation/1",
                    "screenshot_path": local_screenshot,
                },
            ),
        )

        exported = self.store.export_json()
        serialized = json.dumps(exported, ensure_ascii=False)

        self.assertIn("https://example.com/confirmation/1", serialized)
        self.assertNotIn(local_screenshot, serialized)
        self.assertIn("[local path omitted]", serialized)

    def test_authorization_is_persisted_and_consumed_once(self):
        job = self.store.upsert_job(
            JobInput(
                source="company",
                source_job_id="role-5",
                url="https://example.com/jobs/role-5",
                company="示例公司",
                title="解决方案顾问",
                location="深圳",
                description="帮助客户完成方案落地。",
            )
        )
        self.store.review_job(job.id, ReviewDecision(decision="ready"))
        authorization = self.store.issue_authorization(job.id)

        self.assertTrue(self.store.consume_authorization(authorization.token, job.id))
        with self.assertRaises(ValueError):
            self.store.consume_authorization(authorization.token, job.id)

    def test_authorization_starts_an_application_and_paused_work_can_resume(self):
        job = self.store.upsert_job(
            JobInput(
                source="company",
                source_job_id="role-resume",
                url="https://example.com/jobs/role-resume",
                company="示例公司",
                title="解决方案顾问",
                location="深圳",
                description="帮助客户完成方案落地。",
            )
        )
        self.store.review_job(job.id, ReviewDecision(decision="ready"))

        first = self.store.issue_authorization(job.id)
        self.assertEqual(self.store.get_job(job.id).application_status, "in_progress")
        self.store.consume_authorization(first.token, job.id)
        self.store.record_execution_event(job.id, "paused", {"reason": "CAPTCHA required"})

        second = self.store.issue_authorization(job.id)
        self.assertNotEqual(first.token, second.token)
        self.assertEqual(self.store.get_job(job.id).application_status, "in_progress")

    def test_active_job_authorization_cannot_be_issued_twice_before_consumption(self):
        job = self.store.upsert_job(
            JobInput(
                source="company", source_job_id="auth-active", url="https://example.com/auth-active",
                company="示例公司", title="解决方案顾问", location="深圳", description="客户方案。",
            )
        )
        self.store.review_job(job.id, ReviewDecision("ready"))
        self.store.issue_authorization(job.id)

        with self.assertRaises(ValueError):
            self.store.issue_authorization(job.id)

    def test_paused_execution_is_recorded_without_claiming_submission(self):
        job = self.store.upsert_job(
            JobInput(
                source="company",
                source_job_id="role-6",
                url="https://example.com/jobs/role-6",
                company="示例公司",
                title="客户成功经理",
                location="上海",
                description="负责客户成功和产品落地。",
            )
        )
        self.store.record_execution_event(job.id, "paused", {"reason": "CAPTCHA required"})

        self.assertEqual(self.store.get_job(job.id).application_status, "not_applied")
        self.assertEqual(self.store.events_for(job.id)[-1]["type"], "execution_paused")

    def test_submitted_waiting_application_requires_evidence(self):
        with self.assertRaises(ValueError):
            ApplicationResult(status="submitted_waiting", evidence={})
        with self.assertRaises(ValueError):
            ApplicationResult(status="submitted_waiting", evidence={"note": "可能提交了"})

    def test_profile_is_local_and_included_in_non_secret_export(self):
        self.store.set_profile("locations", ["深圳", "广州"])
        self.store.set_profile("exclude_companies", ["示例黑名单"])

        self.assertEqual(self.store.get_profile()["locations"], ["深圳", "广州"])
        exported = self.store.export_json()
        self.assertEqual(exported["profile"]["exclude_companies"], ["示例黑名单"])

    def test_material_versions_are_registered_and_export_without_local_paths(self):
        material_path = Path(self.temp_dir.name) / "resume-v1.md"
        material_path.write_text("approved resume content", encoding="utf-8")

        material = self.store.register_material("resume", "resume-v1", material_path)

        self.assertEqual(material.kind, "resume")
        self.assertEqual(material.version, "resume-v1")
        self.assertEqual(material.path, str(material_path.resolve()))
        exported = self.store.export_json()
        self.assertEqual(exported["materials"][0]["version"], "resume-v1")
        self.assertNotIn(str(material_path.resolve()), json.dumps(exported, ensure_ascii=False))

    def test_management_queues_expose_saved_checked_applied_and_outcome_statuses(self):
        saved = self.store.upsert_job(
            JobInput(
                source="company", source_job_id="queue-saved", url="https://example.com/saved",
                company="示例公司", title="售前顾问", location="深圳", description="客户方案。",
            )
        )
        checked = self.store.upsert_job(
            JobInput(
                source="company", source_job_id="queue-checked", url="https://example.com/checked",
                company="示例公司", title="解决方案顾问", location="深圳", description="客户方案。",
            )
        )
        rejected = self.store.upsert_job(
            JobInput(
                source="company", source_job_id="queue-rejected", url="https://example.com/rejected",
                company="示例公司", title="客户成功经理", location="上海", description="客户成功。",
            )
        )
        waiting = self.store.upsert_job(
            JobInput(
                source="company", source_job_id="queue-waiting", url="https://example.com/waiting",
                company="示例公司", title="产品经理", location="广州", description="产品规划。",
            )
        )
        self.store.review_job(saved.id, ReviewDecision("save"))
        self.store.review_job(checked.id, ReviewDecision("keep"))
        self.store.record_application(
            rejected.id,
            ApplicationResult(status="rejected", evidence={"user_confirmed": True}, reason="招聘方明确拒绝"),
        )
        self.store.record_application(
            waiting.id,
            ApplicationResult(status="submitted_waiting", evidence={"application_id": "waiting-1"}),
        )

        self.assertEqual([job.id for job in self.store.list_jobs("saved")], [saved.id])
        self.assertEqual({job.id for job in self.store.list_jobs("checked")}, {saved.id, checked.id, rejected.id, waiting.id})
        self.assertEqual({job.id for job in self.store.list_jobs("applied")}, {rejected.id, waiting.id})
        self.assertEqual([job.id for job in self.store.list_jobs("rejected")], [rejected.id])
        self.assertEqual([job.id for job in self.store.list_jobs("no_reply")], [waiting.id])

    def test_job_details_include_sources_applications_and_events(self):
        job = self.store.upsert_job(
            JobInput(
                source="company", source_job_id="details-1", url="https://example.com/details-1",
                company="示例公司", title="解决方案顾问", location="深圳", description="客户方案。",
            )
        )
        self.store.record_application(
            job.id,
            ApplicationResult(status="submitted_waiting", evidence={"application_id": "details-app-1"}),
        )

        details = self.store.job_details(job.id)

        self.assertEqual(details["job"]["id"], job.id)
        self.assertEqual(details["sources"][0]["url"], "https://example.com/details-1")
        self.assertEqual(details["applications"][0]["evidence"], {"application_id": "details-app-1"})
        self.assertEqual(details["events"][0]["type"], "job_discovered")

    def test_communication_records_keep_incoming_and_draft_separate(self):
        job = self.store.upsert_job(
            JobInput(
                source="company", source_job_id="message-1", url="https://example.com/message-1",
                company="示例公司", title="解决方案顾问", location="深圳", description="客户方案。",
            )
        )

        incoming = self.store.record_communication(job.id, "boss", "incoming", "您好，请问何时方便沟通？")
        draft = self.store.record_communication(job.id, "boss", "draft", "你好，我会在确认后回复你。")

        self.assertEqual([record.direction for record in self.store.list_communications(job.id)], ["incoming", "draft"])
        self.assertEqual(self.store.job_details(job.id)["communications"][0]["id"], incoming.id)
        self.assertEqual(self.store.job_details(job.id)["communications"][1]["id"], draft.id)

        with self.assertRaises(ValueError):
            self.store.record_communication(job.id, "boss", "sent", "已发送", user_confirmed=False)

        sent = self.store.record_communication(job.id, "boss", "sent", "已发送", user_confirmed=True)
        self.assertEqual(sent.direction, "sent")

    def test_incoming_hr_message_updates_waiting_application_but_draft_does_not(self):
        job = self.store.upsert_job(
            JobInput(
                source="company", source_job_id="message-status-1", url="https://example.com/message-status-1",
                company="示例公司", title="解决方案顾问", location="深圳", description="客户方案。",
            )
        )
        self.store.record_application(
            job.id,
            ApplicationResult(status="submitted_waiting", evidence={"application_id": "message-status-app"}),
        )

        self.store.record_communication(job.id, "boss", "draft", "等待用户确认")
        self.assertEqual(self.store.get_job(job.id).application_status, "submitted_waiting")
        self.store.record_communication(job.id, "boss", "incoming", "招聘方来信")
        self.assertEqual(self.store.get_job(job.id).application_status, "hr_contact")


if __name__ == "__main__":
    unittest.main()
