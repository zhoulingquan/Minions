# -*- coding: utf-8 -*-
"""Contracts for the active fourteen-distribution workspace."""
from __future__ import annotations

from pathlib import Path
import importlib
from importlib import metadata
import subprocess
import tomllib

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
VERSION = "0.1.0"
OWNER_PATHS = {
    "minions-core": {
        "core",
        "config",
        "security",
        "envs",
        "observability",
        "utils",
        "constant.py",
        "exceptions.py",
        "schemas.py",
        "__version__.py",
    },
    "minions-runtime": {"runtime", "token_usage", "hooks"},
    "minions-providers": {"providers", "local_models"},
    "minions-tool-calls": {"tool_calls"},
    "minions-drivers": {"drivers"},
    "minions-channels": {"channels"},
    "minions-plugins": {"plugins", "_version_compat.py"},
    "minions-loop": {"loop"},
    "minions-governance": {"governance", "sandbox"},
    "minions-modes": {"modes"},
    "minions-agents": {"agents", "market", "sage"},
    "minions-app": {
        "app",
        "backup",
        "agent_stats",
        "console",
        "docs",
        "tenancy",
        "tunnel",
        "api_action.py",
    },
    "minions-cli": {"cli", "__main__.py"},
}
MEMBER_DISTRIBUTIONS = set(OWNER_PATHS)
INTERNAL_DEPENDENCIES = {
    "minions-core": set(),
    "minions-runtime": {"minions-core"},
    "minions-providers": {"minions-core"},
    "minions-tool-calls": set(),
    "minions-drivers": {"minions-core"},
    "minions-channels": {
        "minions-core",
        "minions-runtime",
        "minions-providers",
    },
    "minions-plugins": {
        "minions-core",
        "minions-runtime",
        "minions-channels",
    },
    "minions-loop": {"minions-core", "minions-runtime"},
    "minions-governance": {"minions-core", "minions-drivers"},
    "minions-modes": {
        "minions-core",
        "minions-runtime",
        "minions-loop",
        "minions-governance",
    },
    "minions-agents": {
        "minions-core",
        "minions-runtime",
        "minions-providers",
        "minions-tool-calls",
        "minions-drivers",
        "minions-plugins",
        "minions-loop",
        "minions-governance",
        "minions-modes",
    },
    "minions-app": {
        "minions-core",
        "minions-runtime",
        "minions-providers",
        "minions-tool-calls",
        "minions-drivers",
        "minions-channels",
        "minions-plugins",
        "minions-governance",
        "minions-loop",
        "minions-modes",
        "minions-agents",
    },
    "minions-cli": {
        "minions-core",
        "minions-runtime",
        "minions-providers",
        "minions-channels",
        "minions-plugins",
        "minions-agents",
        "minions-app",
    },
}
RESOURCE_PATTERNS = {
    "minions-core": {
        "security/tool_guard/rules/**",
        "security/skill_scanner/rules/**",
        "security/skill_scanner/data/**",
    },
    "minions-channels": {"channels/yuanbao/proto/**"},
    "minions-agents": {
        "agents/md_files/**",
        "agents/skills/**",
        "sage/migrations/*.sql",
    },
    "minions-app": {
        "console/**",
        "docs/*.md",
        "tenancy/migrations/*.sql",
    },
}
WORKSPACE_REQUIREMENTS = [
    "-e packages/minions-core",
    "-e packages/minions-tool-calls",
    "-e packages/minions-runtime",
    "-e packages/minions-providers",
    "-e packages/minions-drivers",
    "-e packages/minions-channels",
    "-e packages/minions-plugins",
    "-e packages/minions-governance",
    "-e packages/minions-loop",
    "-e packages/minions-modes",
    "-e packages/minions-agents",
    "-e packages/minions-app",
    "-e packages/minions-cli",
    "-e .[dev,test,full]",
]


def _load_toml(path: Path) -> dict:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _internal_dependencies(project: dict) -> set[str]:
    internal = set()
    for requirement in project.get("dependencies", []):
        if requirement.startswith("minions-"):
            name, separator, version = requirement.partition("==")
            assert separator == "==", requirement
            assert version == VERSION, requirement
            internal.add(name)
    return internal


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
    assert (
        result.returncode == 0
    ), f"git init failed\n{_git_diagnostics(result)}"


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


def test_root_declares_all_workspace_members_and_sources() -> None:
    root = _load_toml(REPO_ROOT / "pyproject.toml")
    assert root["tool"]["uv"]["workspace"]["members"] == ["packages/*"]

    packages_dir = REPO_ROOT / "packages"
    members = {path.name for path in packages_dir.iterdir() if path.is_dir()}
    assert members == MEMBER_DISTRIBUTIONS
    assert root["tool"]["uv"]["sources"] == {
        distribution: {"workspace": True}
        for distribution in MEMBER_DISTRIBUTIONS
    }


def test_component_source_roots_have_exclusive_namespace_ownership() -> None:
    for distribution, expected_paths in OWNER_PATHS.items():
        src_minions = REPO_ROOT / "packages" / distribution / "src" / "minions"
        assert src_minions.is_dir(), distribution
        assert not (src_minions / "__init__.py").exists(), distribution
        actual_paths = {
            child.name
            for child in src_minions.iterdir()
            if child.name != "__pycache__"
        }
        assert actual_paths == expected_paths, distribution


def test_component_projects_are_active_setuptools_namespace_packages() -> None:
    for distribution in MEMBER_DISTRIBUTIONS:
        member_dir = REPO_ROOT / "packages" / distribution
        project = _load_toml(member_dir / "pyproject.toml")

        assert (member_dir / "LICENSE").is_file(), distribution
        assert project["build-system"] == {
            "requires": ["setuptools>=77", "wheel"],
            "build-backend": "setuptools.build_meta",
        }
        assert project["project"]["name"] == distribution
        assert project["project"]["version"] == VERSION
        assert project["project"]["requires-python"] == ">=3.11,<3.14"
        assert project["project"]["license"] == "Apache-2.0"
        assert (
            project.get("tool", {}).get("uv", {}).get("package") is not False
        )

        setuptools = project["tool"]["setuptools"]
        assert setuptools["include-package-data"] is True
        package_find = setuptools["packages"]["find"]
        assert package_find["where"] == ["src"]
        assert package_find["namespaces"] is True
        assert "minions" in package_find["include"]
        assert "minions*" not in package_find["include"]


def test_internal_dependencies_use_exact_workspace_version_pins() -> None:
    for distribution, expected in INTERNAL_DEPENDENCIES.items():
        project = _load_toml(
            REPO_ROOT / "packages" / distribution / "pyproject.toml",
        )["project"]
        assert _internal_dependencies(project) == expected, distribution


def test_resources_are_owned_and_declared_by_their_component() -> None:
    required_files = {
        "minions-core": [
            "security/tool_guard/rules/dangerous_shell_commands.yaml",
            "security/skill_scanner/data/default_policy.yaml",
        ],
        "minions-channels": [
            "channels/yuanbao/proto/biz.json",
            "channels/yuanbao/proto/conn.json",
        ],
        "minions-agents": [
            "agents/md_files/en/BOOTSTRAP.md",
            "agents/skills/__init__.py",
            "sage/migrations/0001_sage_core.sql",
        ],
        "minions-app": ["tenancy/migrations/0001_control_plane.sql"],
    }
    for distribution, expected_patterns in RESOURCE_PATTERNS.items():
        member_dir = REPO_ROOT / "packages" / distribution
        project = _load_toml(member_dir / "pyproject.toml")
        patterns = set(
            project["tool"]["setuptools"]["package-data"]["minions"],
        )
        assert patterns == expected_patterns, distribution
        for relative_path in required_files[distribution]:
            assert (
                member_dir / "src" / "minions" / relative_path
            ).is_file(), (distribution, relative_path)


def test_root_is_a_source_free_exact_pinned_meta_distribution() -> None:
    root = _load_toml(REPO_ROOT / "pyproject.toml")
    project = root["project"]

    assert project["name"] == "minions"
    assert project["version"] == VERSION
    assert "dynamic" not in project
    assert root["tool"]["setuptools"]["packages"] == []
    assert set(project["dependencies"]) == {
        f"{distribution}=={VERSION}" for distribution in MEMBER_DISTRIBUTIONS
    }
    assert not (REPO_ROOT / "src").exists()
    assert not (REPO_ROOT / "setup.py").exists()


def test_workspace_requirements_install_every_component_then_meta() -> None:
    requirements = (
        (REPO_ROOT / "requirements-workspace.txt")
        .read_text(
            encoding="utf-8",
        )
        .splitlines()
    )
    assert requirements == WORKSPACE_REQUIREMENTS


def test_umbrella_forwards_tooling_and_component_extras() -> None:
    root = _load_toml(REPO_ROOT / "pyproject.toml")
    test_dependencies = root["project"]["optional-dependencies"]["test"]
    assert "import-linter>=2.13,<3" in test_dependencies
    assert "build>=1.2,<2" in test_dependencies
    assert "twine>=6,<7" in test_dependencies
    assert root["project"]["scripts"]["minions"] == "minions.cli.main:cli"


def test_source_version_prefers_meta_then_falls_back_to_core(
    monkeypatch,
) -> None:
    version_module = importlib.import_module("minions.__version__")
    calls: list[str] = []

    def meta_version(distribution: str) -> str:
        calls.append(distribution)
        if distribution == "minions":
            return "0.1.0-meta"
        raise AssertionError(distribution)

    with monkeypatch.context() as patch:
        patch.setattr(metadata, "version", meta_version)
        assert importlib.reload(version_module).__version__ == "0.1.0-meta"
        assert calls == ["minions"]

    calls.clear()

    def core_fallback(distribution: str) -> str:
        calls.append(distribution)
        if distribution == "minions-core":
            return "0.1.0-core"
        raise metadata.PackageNotFoundError(distribution)

    with monkeypatch.context() as patch:
        patch.setattr(metadata, "version", core_fallback)
        assert importlib.reload(version_module).__version__ == "0.1.0-core"
        assert calls == ["minions", "minions-core"]

    assert importlib.reload(version_module).__version__ == "0.1.0"


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
