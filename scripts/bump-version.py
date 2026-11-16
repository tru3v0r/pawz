"""Release a new pawz version: set APP_VERSION and date the changelog's Unreleased section.

    python scripts/bump-version.py 0.2.0

The version is written in one place, ``APP_VERSION`` in ``src/pawz/__init__.py``;
``pyproject.toml`` reads it from there. The script refuses a version that is not
higher than the current one, or an empty Unreleased section. It neither commits nor
tags: it prints the commands to do so.
"""
from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "src" / "pawz" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"
REPOSITORY = "https://github.com/tru3v0r/pawz"
VERSION_LINE = re.compile(r'^APP_VERSION = "(\d+\.\d+\.\d+)"', re.MULTILINE)
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def parse(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def current_version() -> str:
    match = VERSION_LINE.search(INIT.read_text(encoding="utf-8"))
    if not match:
        sys.exit(f"APP_VERSION not found in {INIT}")
    return match.group(1)


def dated_changelog(text: str, old: str, new: str, today: str) -> str:
    """The changelog with Unreleased become ``new``, a fresh empty Unreleased above it,
    and the comparison links at the bottom updated."""
    heading = "## [Unreleased]\n"
    start = text.find(heading)
    if start < 0:
        sys.exit("CHANGELOG.md has no '## [Unreleased]' section")
    body_start = start + len(heading)
    following = text.find("\n## [", body_start)
    body = text[body_start:following if following >= 0 else len(text)]
    if not body.strip():
        sys.exit("The Unreleased section of CHANGELOG.md is empty: describe the changes first")
    text = text[:start] + f"{heading}\n## [{new}] - {today}\n" + text[body_start:]
    old_link = f"[Unreleased]: {REPOSITORY}/compare/v{old}...HEAD"
    if old_link not in text:
        sys.exit(f"CHANGELOG.md lacks the link line: {old_link}")
    return text.replace(old_link, f"[Unreleased]: {REPOSITORY}/compare/v{new}...HEAD\n"
                                  f"[{new}]: {REPOSITORY}/compare/v{old}...v{new}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="the new version, MAJOR.MINOR.PATCH")
    new = parser.parse_args().version
    if not SEMVER.match(new):
        sys.exit(f"{new!r} is not MAJOR.MINOR.PATCH")
    old = current_version()
    if parse(new) <= parse(old):
        sys.exit(f"{new} is not higher than the current version, {old}")
    changelog = dated_changelog(CHANGELOG.read_text(encoding="utf-8"), old, new,
                                datetime.date.today().isoformat())
    INIT.write_text(VERSION_LINE.sub(f'APP_VERSION = "{new}"', INIT.read_text(encoding="utf-8"), count=1),
                    encoding="utf-8")
    CHANGELOG.write_text(changelog, encoding="utf-8")
    print(f"pawz {old} -> {new}. Check CHANGELOG.md, build, then:")
    print(f'  git commit -am "Release {new}"')
    print(f'  git tag -a v{new} -m "pawz {new}"')
    print(f"  git push && git push origin v{new}")


if __name__ == "__main__":
    main()
