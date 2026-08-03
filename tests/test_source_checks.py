import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from job_search_agent.models import SourceCheckRecord
from job_search_agent.store import JobStore


class SourceCheckModelTests(unittest.TestCase):
    def test_source_check_record_has_a_stable_public_shape(self):
        record = SourceCheckRecord(
            id=1,
            source="company",
            url="https://example.com/careers",
            checked_at="2026-08-04T00:00:00+00:00",
            result_count=0,
            status="empty",
            warnings=("no JobPosting record found",),
        )

        self.assertEqual(record.result_count, 0)
        self.assertEqual(record.warnings, ("no JobPosting record found",))


class SourceCheckStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = JobStore.open(Path(self.temp_dir.name) / "jobs.sqlite3")

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_empty_source_check_is_fresh_and_tracking_parameters_share_identity(self):
        first = self.store.record_source_check(
            "company",
            "https://example.com/careers?utm_source=search",
            "2026-08-04T00:00:00+00:00",
            0,
            "empty",
            ["no jobs"],
        )

        latest = self.store.latest_source_check("company", "https://EXAMPLE.com/careers")

        self.assertIsNotNone(latest)
        self.assertEqual(latest.id, first.id)
        self.assertTrue(
            self.store.source_check_is_fresh(
                "company",
                "https://example.com/careers",
                now=datetime(2026, 8, 4, 12, tzinfo=timezone.utc),
            )
        )

    def test_invalid_source_check_does_not_write(self):
        with self.assertRaises(ValueError):
            self.store.record_source_check(
                "company",
                "http://example.com/careers",
                "2026-08-04T00:00:00+00:00",
                1,
                "ok",
            )

        self.assertEqual(self.store.list_source_checks(), [])

    def test_source_check_expires_after_the_configured_age(self):
        self.store.record_source_check(
            "company",
            "https://example.com/careers",
            "2026-08-04T00:00:00+00:00",
            2,
            "ok",
        )

        self.assertFalse(
            self.store.source_check_is_fresh(
                "company",
                "https://example.com/careers",
                max_age_hours=24,
                now=datetime(2026, 8, 5, 1, tzinfo=timezone.utc),
            )
        )

    def test_source_check_rejects_invalid_status_count_warning_and_fragment(self):
        invalid_values = (
            {"status": "unknown"},
            {"result_count": -1},
            {"warnings": ["ok", 3]},
            {"url": "https://example.com/careers#results"},
            {"url": "https://example.com/careers#"},
        )

        for overrides in invalid_values:
            values = {
                "source": "company",
                "url": "https://example.com/careers",
                "checked_at": "2026-08-04T00:00:00+00:00",
                "result_count": 1,
                "status": "ok",
                "warnings": (),
            }
            values.update(overrides)
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.store.record_source_check(**values)

        self.assertEqual(self.store.list_source_checks(), [])

    def test_source_check_warning_is_bounded_and_redacts_secrets_and_local_paths(self):
        record = self.store.record_source_check(
            "company",
            "https://example.com/careers",
            "2026-08-04T00:00:00+00:00",
            0,
            "warning",
            [
                "password=do-not-save token=token-value cookie=cookie-value "
                "/Users/jinzhe/private/browser-output " + "x" * 400,
            ],
        )

        warning = record.warnings[0]
        self.assertLessEqual(len(warning), 240)
        self.assertNotIn("do-not-save", warning)
        self.assertNotIn("token-value", warning)
        self.assertNotIn("cookie-value", warning)
        self.assertNotIn("/Users/jinzhe", warning)
        exported = json.dumps(self.store.export_json(), ensure_ascii=False)
        self.assertNotIn("do-not-save", exported)
        self.assertNotIn("token-value", exported)
        self.assertNotIn("cookie-value", exported)


if __name__ == "__main__":
    unittest.main()
