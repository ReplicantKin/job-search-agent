import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def test_publishable_manifest_and_required_public_files_exist(self):
        manifest_path = ROOT / ".codex-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "job-search-agent")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(manifest["license"], "MIT")
        self.assertEqual(manifest["interface"]["category"], "Productivity")
        self.assertIsInstance(manifest["interface"]["defaultPrompt"], list)
        self.assertTrue((ROOT / "README.md").exists())
        self.assertTrue((ROOT / "LICENSE").exists())
        self.assertTrue((ROOT / "CHANGELOG.md").exists())
        self.assertTrue((ROOT / "PRIVACY.md").exists())
        self.assertTrue((ROOT / "TERMS.md").exists())
        self.assertTrue((ROOT / "docs" / "publishing.md").exists())
        self.assertTrue((ROOT / "docs" / "evaluation.md").exists())
        submission_path = ROOT / "docs" / "public-submission.md"
        self.assertTrue(submission_path.exists())
        submission_text = submission_path.read_text(encoding="utf-8")
        self.assertIn("5 个正向测试用例", submission_text)
        self.assertIn("3 个反向测试用例", submission_text)
        self.assertIn("job-search-agent-0.1.5.zip", submission_text)
        publishing_text = (ROOT / "docs" / "publishing.md").read_text(encoding="utf-8")
        self.assertIn("codex plugin marketplace add ReplicantKin/job-search-agent", publishing_text)
        self.assertIn("job-search-agent@job-search-agent-public", publishing_text)
        self.assertTrue((ROOT / "assets" / "job-search-agent-icon.svg").exists())
        self.assertEqual(manifest["interface"]["composerIcon"], "./assets/job-search-agent-icon.svg")
        self.assertEqual(manifest["interface"]["logo"], "./assets/job-search-agent-icon.svg")
        self.assertTrue((ROOT / "examples" / "boss-capture.sample.json").exists())
        self.assertTrue((ROOT / "examples" / "company-jobposting.sample.html").exists())
        self.assertTrue((ROOT / "examples" / "greenhouse-api.sample.json").exists())
        self.assertTrue((ROOT / "skills" / "job-discovery" / "SKILL.md").exists())
        self.assertTrue((ROOT / "skills" / "job-tracking" / "SKILL.md").exists())
        self.assertTrue((ROOT / "skills" / "application-materials" / "SKILL.md").exists())
        self.assertTrue((ROOT / "skills" / "job-fit" / "SKILL.md").exists())
        self.assertTrue((ROOT / "skills" / "hr-communication" / "SKILL.md").exists())
        workflow_skill = ROOT / "skills" / "job-search-workflow" / "SKILL.md"
        self.assertTrue(workflow_skill.exists())
        workflow_text = workflow_skill.read_text(encoding="utf-8")
        self.assertIn("逐个确认", workflow_text)
        self.assertIn("daily", workflow_text)
        self.assertIn("不得批量投递", workflow_text)
        self.assertIn("target_roles", workflow_text)
        self.assertIn("已检查 URL", workflow_text)
        discovery_text = (ROOT / "skills" / "job-discovery" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("公司官网和官方 ATS", discovery_text)
        self.assertIn("exclude_keywords", discovery_text)

    def test_repo_marketplace_points_at_this_plugin_root(self):
        marketplace_path = ROOT / ".agents" / "plugins" / "marketplace.json"
        self.assertTrue(marketplace_path.exists())
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        self.assertEqual(marketplace["name"], "job-search-agent-public")
        self.assertEqual(len(marketplace["plugins"]), 1)
        entry = marketplace["plugins"][0]
        self.assertEqual(entry["name"], "job-search-agent")
        self.assertEqual(entry["source"], {"source": "local", "path": "./"})
        self.assertEqual(entry["policy"], {"installation": "AVAILABLE", "authentication": "ON_INSTALL"})
        self.assertEqual(entry["category"], "Productivity")

    def test_release_docs_describe_source_check_history(self):
        discovery = (ROOT / "skills" / "job-discovery" / "SKILL.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("source-check status", discovery)
        self.assertIn("source-check record", discovery)
        self.assertIn("source_checks", readme)

    def test_public_package_contains_no_personal_workspace_paths(self):
        forbidden = ("/Users/", "/private/var/", "求职" + "上下文.md", "automation-" + "8")
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts or ".venv" in path.parts or "tests" in path.parts or path.suffix in {".pyc", ".sqlite3"}:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            for value in forbidden:
                self.assertNotIn(value, content, f"personal value leaked into {path}")

    def test_cli_help_is_available_from_a_clean_process(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "job_search_agent.py"), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("ingest", result.stdout)

    def test_release_builder_creates_a_clean_versioned_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_release.py"), "--output", directory],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            archive = Path(directory) / "job-search-agent-0.1.5.zip"
            self.assertTrue(archive.exists())
            with zipfile.ZipFile(archive) as package:
                names = set(package.namelist())
            self.assertIn(".codex-plugin/plugin.json", names)
            self.assertIn("CHANGELOG.md", names)
            self.assertIn("skills/job-fit/SKILL.md", names)
            self.assertIn("examples/boss-capture.sample.json", names)
            self.assertIn("examples/greenhouse-api.sample.json", names)
            self.assertIn("assets/job-search-agent-icon.svg", names)
            self.assertFalse(any(name.startswith("docs/superpowers/") for name in names))
            self.assertFalse(any(name.startswith((".git/", ".venv/", "tests/", "dist/")) for name in names))

    def test_extracted_archive_runs_cli_from_a_clean_install_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "release"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_release.py"), "--output", str(output_dir)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            archive = output_dir / "job-search-agent-0.1.5.zip"
            install_dir = Path(directory) / "installed"
            install_dir.mkdir()
            with zipfile.ZipFile(archive) as package:
                package.extractall(install_dir)

            cli = install_dir / "scripts" / "job_search_agent.py"
            smoke = subprocess.run(
                [sys.executable, str(cli), "--help"],
                cwd=install_dir,
                text=True,
                capture_output=True,
            )
            self.assertEqual(smoke.returncode, 0, smoke.stderr)
            self.assertIn("execution-result", smoke.stdout)


if __name__ == "__main__":
    unittest.main()
