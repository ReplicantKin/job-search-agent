#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
INCLUDED_PATHS = (
    ".codex-plugin",
    "LICENSE",
    "CHANGELOG.md",
    "README.md",
    "TERMS.md",
    "PRIVACY.md",
    "assets",
    "pyproject.toml",
    "docs",
    "examples",
    "scripts",
    "skills",
    "src",
)


def build_release(output_dir: Path) -> Path:
    manifest = json.loads((PACKAGE_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    archive_path = output_dir / f"{manifest['name']}-{manifest['version']}.zip"
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative_root in INCLUDED_PATHS:
            source = PACKAGE_ROOT / relative_root
            if source.is_file():
                _write_file(archive, source, relative_root)
                continue
            for path in sorted(source.rglob("*")):
                if path.is_file() and _is_publishable(path):
                    _write_file(archive, path, path.relative_to(PACKAGE_ROOT))
    return archive_path


def _is_publishable(path: Path) -> bool:
    return (
        "__pycache__" not in path.parts
        and "superpowers" not in path.parts
        and path.suffix != ".pyc"
    )


def _write_file(archive: zipfile.ZipFile, path: Path, relative_path: str | Path) -> None:
    archive.write(path, Path(relative_path).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a clean Job Search Agent plugin archive")
    parser.add_argument("--output", type=Path, default=PACKAGE_ROOT / "dist")
    args = parser.parse_args()
    archive = build_release(args.output.expanduser().resolve())
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
