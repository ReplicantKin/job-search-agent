import json
import sqlite3
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

    def test_source_check_warning_uses_a_safe_format_allowlist(self):
        record = self.store.record_source_check(
            "company",
            "https://example.com/careers",
            "2026-08-04T00:00:00+00:00",
            0,
            "warning",
            [
                "refresh_token=keep-out",
                '{"password":"keep-out"}',
                "raw response body: <div>keep-out</div>",
                "/tmp/keep-out",
            ],
        )

        self.assertEqual(
            record.warnings,
            (
                "[warning omitted: unsupported warning format]",
                "[warning omitted: unsupported warning format]",
                "[warning omitted: unsupported warning format]",
                "[warning omitted: unsupported warning format]",
            ),
        )

    def test_opening_a_legacy_database_scrubs_existing_source_warnings(self):
        legacy_path = Path(self.temp_dir.name) / "legacy.sqlite3"
        connection = sqlite3.connect(legacy_path)
        connection.execute(
            """
            CREATE TABLE source_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                url TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                result_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                warnings_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO source_checks(source, url, checked_at, result_count, status, warnings_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "company",
                "https://example.com/careers",
                "2026-08-04T00:00:00+00:00",
                0,
                "warning",
                json.dumps(["password=legacy-secret", "raw browser output: <html>legacy</html>"]),
            ),
        )
        connection.commit()
        connection.close()

        legacy_store = JobStore.open(legacy_path)
        try:
            self.assertEqual(
                legacy_store.list_source_checks()[0].warnings,
                (
                    "[warning omitted: unsupported warning format]",
                    "[warning omitted: unsupported warning format]",
                ),
            )
        finally:
            legacy_store.close()

        connection = sqlite3.connect(legacy_path)
        raw_warnings = connection.execute("SELECT warnings_json FROM source_checks").fetchone()[0]
        connection.close()
        self.assertNotIn("legacy-secret", raw_warnings)

    def test_opening_a_legacy_database_handles_malformed_warning_arrays(self):
        legacy_path = Path(self.temp_dir.name) / "malformed-legacy.sqlite3"
        connection = sqlite3.connect(legacy_path)
        connection.execute(
            """
            CREATE TABLE source_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                url TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                result_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                warnings_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO source_checks(source, url, checked_at, result_count, status, warnings_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "company",
                "https://example.com/careers",
                "2026-08-04T00:00:00+00:00",
                0,
                "warning",
                json.dumps(["valid", 3]),
            ),
        )
        connection.commit()
        connection.close()

        legacy_store = JobStore.open(legacy_path)
        try:
            self.assertEqual(
                legacy_store.list_source_checks()[0].warnings,
                ("[warning omitted: unsupported warning format]",),
            )
        finally:
            legacy_store.close()


if __name__ == "__main__":
    unittest.main()
