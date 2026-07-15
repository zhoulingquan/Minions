# -*- coding: utf-8 -*-
"""Contracts for the inactive twelve-project uv workspace scaffold."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import tomllib

import pytest


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


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _git_diagnostics(result: subprocess.CompletedProcess[str]) -> str:
    return (
        f"exit code: {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _init_git(repo_root: Path) -> None:
    result = _run_git(repo_root, "init", "--quiet")
    assert result.returncode == 0, (
        f"git init failed\n{_git_diagnostics(result)}"
    )


def _assert_tracked_and_not_ignored(repo_root: Path, path: Path) -> None:
    relative_path = path.relative_to(repo_root).as_posix()
    ignored = _run_git(
        repo_root,
        "check-ignore",
        "--no-index",
        "-v",
        "--",
        relative_path,
    )
    assert ignored.returncode == 1, (
        f"git check-ignore --no-index reported {relative_path!r} as ignored "
        "or failed to inspect it\n"
        f"{_git_diagnostics(ignored)}"
    )

    tracked = _run_git(
        repo_root,
        "ls-files",
        "--error-unmatch",
        "--",
        relative_path,
    )
    assert tracked.returncode == 0, (
        f"git ls-files --error-unmatch did not find tracked "
        f"{relative_path!r}\n{_git_diagnostics(tracked)}"
    )


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
    lockfile = REPO_ROOT / "uv.lock"
    assert lockfile.is_file()
    _assert_tracked_and_not_ignored(REPO_ROOT, lockfile)


def test_lockfile_contract_detects_wildcard_ignore_rule(
    tmp_path: Path,
) -> None:
    _init_git(tmp_path)
    (tmp_path / ".gitignore").write_text("*.lock\n", encoding="utf-8")
    lockfile = tmp_path / "uv.lock"
    lockfile.touch()

    with pytest.raises(AssertionError) as exc_info:
        _assert_tracked_and_not_ignored(tmp_path, lockfile)

    message = str(exc_info.value)
    assert "git check-ignore --no-index" in message
    assert "*.lock" in message
    assert "uv.lock" in message


def test_lockfile_contract_detects_untracked_file(tmp_path: Path) -> None:
    _init_git(tmp_path)
    lockfile = tmp_path / "uv.lock"
    lockfile.touch()

    with pytest.raises(AssertionError) as exc_info:
        _assert_tracked_and_not_ignored(tmp_path, lockfile)

    message = str(exc_info.value)
    assert "git ls-files --error-unmatch" in message
    assert "uv.lock" in message
    assert "stderr:" in message
