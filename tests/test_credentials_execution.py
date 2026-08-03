import unittest

from job_search_agent.credentials import InMemoryCredentialStore, KeychainCredentialStore
from job_search_agent.execution import (
    ApplicationAuthorization,
    ApplicationExecutorResult,
    AuthorizationGate,
)


class CredentialTests(unittest.TestCase):
    def test_local_credential_store_round_trip_and_delete(self):
        store = InMemoryCredentialStore()
        store.set("boss", "jingzhe", "secret")

        self.assertEqual(store.get("boss").username, "jingzhe")
        self.assertEqual(store.get("boss").password, "secret")
        store.delete("boss")
        self.assertIsNone(store.get("boss"))

    def test_keychain_does_not_put_password_in_command_arguments(self):
        calls = []

        def fake_runner(command, **kwargs):
            calls.append((command, kwargs))
            return type("Completed", (), {"returncode": 0, "stdout": '{"username":"jingzhe","password":"secret"}\n', "stderr": ""})()

        store = KeychainCredentialStore(runner=fake_runner)
        store.set("boss", "jingzhe", "secret")

        command, kwargs = calls[0]
        self.assertNotIn("secret", command)
        self.assertIn("secret", kwargs["input"])

    def test_keychain_supplies_password_to_both_security_prompts(self):
        calls = []

        def fake_runner(command, **kwargs):
            calls.append((command, kwargs))
            return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        store = KeychainCredentialStore(runner=fake_runner)
        store.set("boss", "jingzhe", "secret")

        _, kwargs = calls[0]
        self.assertEqual(
            kwargs["input"],
            '{"username": "jingzhe", "password": "secret"}\n'
            '{"username": "jingzhe", "password": "secret"}\n',
        )


class ExecutionTests(unittest.TestCase):
    def test_submitted_result_requires_evidence(self):
        with self.assertRaises(ValueError):
            ApplicationExecutorResult(status="submitted", evidence={})
        with self.assertRaises(ValueError):
            ApplicationExecutorResult(status="submitted", evidence={"note": "可能提交了"})

        result = ApplicationExecutorResult(
            status="submitted",
            evidence={"confirmation_url": "https://example.com/confirmation/1"},
        )
        self.assertEqual(result.status, "submitted")

    def test_paused_result_requires_reason(self):
        with self.assertRaises(ValueError):
            ApplicationExecutorResult(status="paused", evidence={}, reason=None)

        result = ApplicationExecutorResult(status="paused", evidence={}, reason="CAPTCHA required")
        self.assertEqual(result.reason, "CAPTCHA required")

    def test_authorization_is_scoped_to_one_job_and_one_use(self):
        gate = AuthorizationGate()
        authorization = gate.issue("job_1")
        self.assertIsInstance(authorization, ApplicationAuthorization)
        self.assertTrue(gate.consume(authorization.token, "job_1"))

        with self.assertRaises(ValueError):
            gate.consume(authorization.token, "job_1")

        other = gate.issue("job_2")
        with self.assertRaises(ValueError):
            gate.consume(other.token, "job_1")


if __name__ == "__main__":
    unittest.main()
