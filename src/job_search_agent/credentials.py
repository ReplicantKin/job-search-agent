from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Credential:
    site: str
    username: str
    password: str


class InMemoryCredentialStore:
    """Testing store only; never use this implementation for production secrets."""

    def __init__(self):
        self._values: dict[str, Credential] = {}

    def set(self, site: str, username: str, password: str) -> None:
        self._values[site] = Credential(site, username, password)

    def get(self, site: str) -> Credential | None:
        return self._values.get(site)

    def delete(self, site: str) -> None:
        self._values.pop(site, None)


class KeychainCredentialStore:
    """Store opt-in site credentials in the macOS login keychain."""

    def __init__(self, runner: Callable[..., Any] | None = None, service: str = "job-search-agent"):
        self.runner = runner or subprocess.run
        self.service = service

    def _run(self, command: list[str], *, input_text: str | None = None) -> Any:
        result = self.runner(
            command,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "keychain operation failed")
        return result

    def set(self, site: str, username: str, password: str) -> None:
        payload = json.dumps({"username": username, "password": password}, ensure_ascii=False)
        self._run(
            ["security", "add-generic-password", "-a", site, "-s", self.service, "-U", "-w"],
            # With -w and no argv password, macOS security prompts twice.
            # Supplying both responses keeps the secret out of process args.
            input_text=payload + "\n" + payload + "\n",
        )

    def get(self, site: str) -> Credential | None:
        result = self.runner(
            ["security", "find-generic-password", "-a", site, "-s", self.service, "-w"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        payload = json.loads(result.stdout)
        return Credential(site=site, username=payload["username"], password=payload["password"])

    def delete(self, site: str) -> None:
        result = self.runner(
            ["security", "delete-generic-password", "-a", site, "-s", self.service],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode not in (0, 44):
            raise RuntimeError(result.stderr.strip() or "keychain delete failed")
