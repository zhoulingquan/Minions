# -*- coding: utf-8 -*-
"""Contracts for the inactive twelve-project uv workspace scaffold."""
from __future__ import annotations

from pathlib import Path
import re
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[3]
MEMBER_DISTRIBUTIONS = {
    "minions-core",
    "minions-runtime",
    "minions-providers",
    "minions-tool-calls",
    "minions-drivers",
    "minions-channels",
    "minions-plugins",
    "minions-governance",
    "minions-loop",
    "minions-agents",
    "minions-modes",
}


def _load_toml(path: Path) -> dict:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _umbrella_version() -> str:
    source = (REPO_ROOT / "src" / "minions" / "__version__.py").read_text(
        encoding="utf-8",
    )
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', source, re.M)
    assert match is not None
    return match.group(1)


def test_root_declares_all_workspace_members() -> None:
    root = _load_toml(REPO_ROOT / "pyproject.toml")
    assert root["tool"]["uv"]["workspace"]["members"] == ["packages/*"]

    packages_dir = REPO_ROOT / "packages"
    members = {path.name for path in packages_dir.iterdir() if path.is_dir()}
    assert members == MEMBER_DISTRIBUTIONS


def test_inactive_members_have_exact_non_buildable_scaffolds() -> None:
    version = _umbrella_version()
    packages_dir = REPO_ROOT / "packages"

    for distribution in MEMBER_DISTRIBUTIONS:
        member_dir = packages_dir / distribution
        assert {path.name for path in member_dir.iterdir()} == {
            "pyproject.toml",
        }
        assert _load_toml(member_dir / "pyproject.toml") == {
            "project": {
                "name": distribution,
                "version": version,
                "requires-python": ">=3.11,<3.14",
                "dependencies": [],
            },
            "tool": {"uv": {"package": False}},
        }
        assert not (member_dir / "src" / "minions").exists()


def test_umbrella_declares_workspace_tooling_and_fastapi() -> None:
    root = _load_toml(REPO_ROOT / "pyproject.toml")
    assert "fastapi>=0.110,<1" in root["project"]["dependencies"]

    test_dependencies = root["project"]["optional-dependencies"]["test"]
    assert "import-linter>=2.3,<3" in test_dependencies
    assert "build>=1.2,<2" in test_dependencies
    assert "twine>=6,<7" in test_dependencies


def test_import_linter_starts_with_only_the_root_package() -> None:
    assert (REPO_ROOT / ".importlinter").read_text(encoding="utf-8") == (
        "[importlinter]\nroot_package = minions\n"
    )


def test_lockfile_is_present_and_not_ignored() -> None:
    assert (REPO_ROOT / "uv.lock").is_file()
    ignore_rules = {
        line.strip()
        for line in (REPO_ROOT / ".gitignore").read_text(
            encoding="utf-8",
        ).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "uv.lock" not in ignore_rules
