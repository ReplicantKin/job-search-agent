import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.job_search_agent import main


class CredentialCliTests(unittest.TestCase):
    def test_credential_set_reads_secret_prompt_and_delegates_to_local_store(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "jobs.sqlite3"
            output = io.StringIO()
            with patch("scripts.job_search_agent.KeychainCredentialStore") as store_class:
                with patch("scripts.job_search_agent.getpass.getpass", return_value="not-in-args"):
                    with contextlib.redirect_stdout(output):
                        exit_code = main([
                            "--db", str(db), "credential", "set",
                            "--site", "boss", "--username", "jingzhe",
                        ])

            self.assertEqual(exit_code, 0)
            store_class.return_value.set.assert_called_once_with("boss", "jingzhe", "not-in-args")
            self.assertNotIn("not-in-args", output.getvalue())

    def test_non_macos_credential_command_reports_browser_session_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "jobs.sqlite3"
            output = io.StringIO()
            errors = io.StringIO()
            with patch("scripts.job_search_agent.sys.platform", "linux"):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                    exit_code = main([
                        "--db", str(db), "credential", "status", "--site", "boss",
                    ])

            self.assertEqual(exit_code, 2)
            self.assertIn("browser session", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
