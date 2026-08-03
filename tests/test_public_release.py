import json
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_public_release import (
    apply_public_metadata,
    main,
    public_release_issues,
    validate_public_url,
)


class PublicReleaseTests(unittest.TestCase):
    def test_current_manifest_reports_missing_real_public_urls(self):
        manifest = json.loads(
            (Path(__file__).resolve().parents[1] / ".codex-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )
        issues = public_release_issues(manifest)
        self.assertEqual(
            issues["missing"],
            [
                "repository",
                "homepage",
                "interface.websiteURL",
                "interface.privacyPolicyURL",
                "interface.termsOfServiceURL",
            ],
        )
        self.assertEqual(issues["invalid"], [])

    def test_write_updates_public_urls_and_preserves_existing_manifest_fields(self):
        manifest = {
            "name": "job-search-agent",
            "version": "0.1.0",
            "author": {"name": "Jinzhe"},
            "interface": {"displayName": "Job Search Agent"},
        }
        updated = apply_public_metadata(
            manifest,
            repository="https://github.com/example/job-search-agent",
            homepage="https://example.com/job-search-agent",
            privacy_url="https://example.com/job-search-agent/privacy",
            terms_url="https://example.com/job-search-agent/terms",
            author_url="https://github.com/example",
        )

        self.assertEqual(updated["name"], "job-search-agent")
        self.assertEqual(updated["repository"], "https://github.com/example/job-search-agent")
        self.assertEqual(updated["homepage"], "https://example.com/job-search-agent")
        self.assertEqual(
            updated["interface"]["privacyPolicyURL"],
            "https://example.com/job-search-agent/privacy",
        )
        self.assertEqual(updated["author"]["url"], "https://github.com/example")
        self.assertEqual(public_release_issues(updated), {"missing": [], "invalid": []})

    def test_write_command_updates_a_temp_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "plugin.json"
            manifest_path.write_text(
                json.dumps({"interface": {"displayName": "Job Search Agent"}}),
                encoding="utf-8",
            )
            exit_code = main(
                [
                    "--manifest",
                    str(manifest_path),
                    "--write",
                    "--repository",
                    "https://github.com/example/job-search-agent",
                    "--homepage",
                    "https://example.com/job-search-agent",
                    "--privacy-url",
                    "https://example.com/privacy",
                    "--terms-url",
                    "https://example.com/terms",
                ]
            )
            self.assertEqual(exit_code, 0)
            saved = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["interface"]["websiteURL"], "https://example.com/job-search-agent")

    def test_public_urls_must_be_https_without_embedded_credentials(self):
        for value in (
            "http://example.com/plugin",
            "https://user:password@example.com/plugin",
            "https://example.com/plugin#section",
        ):
            with self.assertRaises(ValueError):
                validate_public_url(value)


if __name__ == "__main__":
    unittest.main()
