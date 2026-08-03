#!/usr/bin/env python3
"""Fill and validate the public metadata of a Job Search Agent manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PACKAGE_ROOT / ".codex-plugin" / "plugin.json"


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest must contain a JSON object")
    return payload


def validate_public_url(value: str) -> str:
    """Return a normalized public URL or raise ValueError."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("URL must be a non-empty string")
    candidate = value.strip()
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError(f"URL must be an absolute https:// URL without credentials: {candidate}")
    if parsed.fragment:
        raise ValueError(f"URL must not contain a fragment: {candidate}")
    return candidate


def public_release_issues(manifest: dict[str, Any]) -> dict[str, list[str]]:
    """Return missing and malformed public-release metadata without changing the manifest."""
    missing: list[str] = []
    invalid: list[str] = []
    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        interface = {}

    values = {
        "repository": manifest.get("repository"),
        "homepage": manifest.get("homepage"),
        "interface.websiteURL": interface.get("websiteURL"),
        "interface.privacyPolicyURL": interface.get("privacyPolicyURL"),
        "interface.termsOfServiceURL": interface.get("termsOfServiceURL"),
    }
    for field, value in values.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
            continue
        try:
            validate_public_url(value)
        except ValueError:
            invalid.append(field)
    return {"missing": missing, "invalid": invalid}


def apply_public_metadata(
    manifest: dict[str, Any],
    *,
    repository: str,
    homepage: str,
    privacy_url: str,
    terms_url: str,
    author_url: str | None = None,
) -> dict[str, Any]:
    """Apply publisher-supplied URLs while preserving unrelated manifest fields."""
    urls = {
        "repository": validate_public_url(repository),
        "homepage": validate_public_url(homepage),
        "interface.websiteURL": validate_public_url(homepage),
        "interface.privacyPolicyURL": validate_public_url(privacy_url),
        "interface.termsOfServiceURL": validate_public_url(terms_url),
    }
    interface = manifest.setdefault("interface", {})
    if not isinstance(interface, dict):
        raise ValueError("manifest interface must be an object")
    manifest["repository"] = urls["repository"]
    manifest["homepage"] = urls["homepage"]
    interface["websiteURL"] = urls["interface.websiteURL"]
    interface["privacyPolicyURL"] = urls["interface.privacyPolicyURL"]
    interface["termsOfServiceURL"] = urls["interface.termsOfServiceURL"]
    if author_url is not None:
        author = manifest.setdefault("author", {})
        if not isinstance(author, dict):
            raise ValueError("manifest author must be an object")
        author["url"] = validate_public_url(author_url)
    return manifest


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate or fill real public URLs in .codex-plugin/plugin.json"
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report missing or malformed URLs")
    mode.add_argument("--write", action="store_true", help="write publisher-supplied URLs")
    parser.add_argument("--repository", help="public source repository URL")
    parser.add_argument("--homepage", help="public plugin documentation or website URL")
    parser.add_argument("--privacy-url", help="public privacy policy URL")
    parser.add_argument("--terms-url", help="public terms of service URL")
    parser.add_argument("--author-url", help="optional author or team profile URL")
    args = parser.parse_args(argv)

    try:
        manifest_path = args.manifest.expanduser().resolve()
        manifest = load_manifest(manifest_path)
        if args.check:
            issues = public_release_issues(manifest)
            print(json.dumps({"ok": not any(issues.values()), **issues}, ensure_ascii=False, indent=2))
            return 0 if not any(issues.values()) else 2

        required_args = {
            "--repository": args.repository,
            "--homepage": args.homepage,
            "--privacy-url": args.privacy_url,
            "--terms-url": args.terms_url,
        }
        missing_args = [name for name, value in required_args.items() if not value]
        if missing_args:
            parser.error("--write requires " + ", ".join(missing_args))
        updated = apply_public_metadata(
            manifest,
            repository=args.repository,
            homepage=args.homepage,
            privacy_url=args.privacy_url,
            terms_url=args.terms_url,
            author_url=args.author_url,
        )
        write_manifest(manifest_path, updated)
        print(manifest_path)
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.exit(2, f"prepare_public_release: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
