"""The version is written once and the changelog describes it."""
import importlib.util
import re
from pathlib import Path

import pytest

from pawz import APP_VERSION

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def bump_module():
    spec = importlib.util.spec_from_file_location("bump_version", ROOT / "scripts" / "bump-version.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_version_is_semver_and_in_the_changelog():
    assert re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION)
    assert re.search(rf"^## \[{re.escape(APP_VERSION)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", CHANGELOG, re.MULTILINE)
    assert "## [Unreleased]" in CHANGELOG


def test_pyproject_reads_the_version_from_the_package():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in pyproject
    assert 'version = {attr = "pawz.APP_VERSION"}' in pyproject
    assert not re.search(r'^version = "', pyproject, re.MULTILINE)


def test_bump_dates_unreleased_and_updates_links():
    bump = bump_module()
    text = ("## [Unreleased]\n\n### Added\n- A keyboard.\n\n## [0.1.0] - 2026-11-15\n\n"
            f"[Unreleased]: {bump.REPOSITORY}/compare/v0.1.0...HEAD\n")
    dated = bump.dated_changelog(text, "0.1.0", "0.2.0", "2026-12-01")
    assert dated.startswith("## [Unreleased]\n\n## [0.2.0] - 2026-12-01\n\n### Added\n- A keyboard.\n")
    assert f"[Unreleased]: {bump.REPOSITORY}/compare/v0.2.0...HEAD" in dated
    assert f"[0.2.0]: {bump.REPOSITORY}/compare/v0.1.0...v0.2.0" in dated


def test_bump_refuses_an_empty_unreleased_section():
    bump = bump_module()
    with pytest.raises(SystemExit):
        bump.dated_changelog("## [Unreleased]\n\n## [0.1.0] - 2026-11-15\n", "0.1.0", "0.2.0", "2026-12-01")
