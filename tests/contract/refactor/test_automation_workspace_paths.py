# -*- coding: utf-8 -*-
"""Contracts keeping automation on the physical multi-distribution workspace."""
from __future__ import annotations

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[3]
TEXT_SUFFIXES = {".bat", ".md", ".ps1", ".py", ".sh", ".yaml", ".yml"}


def _automation_files() -> tuple[Path, ...]:
    files: list[Path] = [REPO_ROOT / "Makefile"]
    for directory in (".github", "deploy", "scripts"):
        root = REPO_ROOT / directory
        files.extend(
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in TEXT_SUFFIXES
            and "scripts/refactor" not in path.as_posix()
        )
    return tuple(sorted(files))


def test_automation_has_no_monolithic_source_paths() -> None:
    violations: list[str] = []
    for path in _automation_files():
        text = path.read_text(encoding="utf-8")
        normalized = text.replace("\\", "/")
        for line_number, line in enumerate(normalized.splitlines(), start=1):
            without_component_paths = re.sub(
                r"packages/[^/\s'\"]+/src/minions",
                "",
                line,
            )
            if "src/minions" in without_component_paths:
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}"
                )

    assert not violations, "\n".join(violations)


def test_ci_uses_workspace_installs_and_package_coverage() -> None:
    violations: list[str] = []
    for path in (REPO_ROOT / ".github").rglob("*.yml"):
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if "pip install -e \".[" in line or "--cov=src" in line:
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}"
                )

    assert not violations, "\n".join(violations)


def test_source_installers_install_workspace_requirements() -> None:
    for relative in (
        "scripts/install.sh",
        "scripts/install.ps1",
        "scripts/install.bat",
    ):
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "requirements-workspace-install.txt" in text, relative
        assert "--no-sources" in text, relative

    install_requirements = (
        REPO_ROOT / "requirements-workspace-install.txt"
    ).read_text(encoding="utf-8")
    assert "-e " not in install_requirements
    assert install_requirements.count("packages/minions-") == 13


def test_wheel_builders_delegate_to_workspace_builder() -> None:
    for relative in ("scripts/wheel_build.sh", "scripts/wheel_build.ps1"):
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "scripts/build_workspace.py" in text, relative
        assert "packages/minions-app/src/minions" in text.replace("\\", "/"), relative


def test_dockerfile_installs_workspace() -> None:
    text = (REPO_ROOT / "deploy" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY packages" in text
    assert "COPY requirements-workspace.txt" in text
    assert "requirements-workspace-install.txt" in text
    assert "--no-sources" in text
    assert "packages/minions-app/src/minions/console" in text
    assert "packages/minions-app/src/minions/docs" in text
    ignored = {
        line.strip()
        for line in (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    }
    assert "uv.lock" not in ignored


def test_release_builds_and_publishes_components_before_meta() -> None:
    text = (REPO_ROOT / ".github" / "workflows" / "publish-pypi.yml").read_text(
        encoding="utf-8"
    )
    assert "scripts/build_workspace.py" in text
    assert "twine check" in text
    component_step = text.index("Publish component distributions")
    meta_step = text.index("Publish meta distribution")
    assert component_step < meta_step


def test_release_verification_uses_cross_platform_wheel_installer() -> None:
    text = (REPO_ROOT / ".github" / "workflows" / "release-verify.yml").read_text(
        encoding="utf-8"
    )
    assert "scripts/install_built_wheels.py --venv .verify-venv" in text
    assert "dist/*.whl" not in text


def test_desktop_packaging_consumes_complete_local_workspace() -> None:
    common = (REPO_ROOT / "scripts" / "pack" / "build_common.py").read_text(
        encoding="utf-8"
    )
    assert "collect_workspace_wheels" in common
    assert "minions[full]" in common
    for relative in ("scripts/pack/build_macos.sh", "scripts/pack/build_win.ps1"):
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "wheel_build" in text, relative
        assert "already has wheel" not in text, relative


def test_main_ci_paths_include_workspace_inputs() -> None:
    text = (REPO_ROOT / ".github" / "workflows" / "tests.yml").read_text(
        encoding="utf-8"
    )
    for expected in (
        "packages/**",
        "requirements-workspace.txt",
        "uv.lock",
        "architecture.toml",
        "scripts/check_architecture.py",
    ):
        assert expected in text
