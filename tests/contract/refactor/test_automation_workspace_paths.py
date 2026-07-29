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


# --- User-facing docs & config: no monolithic src/ paths ---------------------
#
# After the multi-distribution refactor, no user/operator-facing doc or config
# should reference the removed monolithic ``src/minions`` (or the even older
# ``src/agentscope``) layout, nor ``--cov=src``. Legitimate references use the
# ``packages/<component>/src/minions`` form and are normalized away before the
# check; an explicit allowlist covers the few files that legitimately mention
# the old layout (baseline data, the refactor plan itself, and the synthetic
# fixtures used by these contract tests).

_USER_FACING_TEXT_SUFFIXES = {
    ".bat", ".cfg", ".flake8", ".ini", ".md", ".ps1", ".py", ".sh",
    ".toml", ".ts", ".yaml", ".yml",
}

# Directories whose text files are scanned for legacy monolithic paths.
_USER_FACING_SCAN_DIRS = (
    "console/src",
    "docs",
    "e2e",
    "packages",  # covers bundled docs, md_files, skills, and per-package config
    "tests",
    "website",
)

# Repo-root text files scanned in addition to the directories above.
_USER_FACING_SCAN_ROOT_FILES = (
    "CONTRIBUTING.md",
    "README.md",
    "SECURITY.md",
    ".flake8",
    ".gitignore",
    "pyproject.toml",
)

# Files that may legitimately mention the old layout (relative to REPO_ROOT,
# matched by posix path prefix so a directory covers all of its contents).
_LEGACY_PATH_ALLOWLIST = (
    # Refactor baseline data captures the pre/during-refactor import graph.
    "docs/refactor/import-baseline.json",
    "docs/refactor/public-api-baseline.json",
    # The refactor plan documents the migration from src/minions.
    "docs/superpowers/plans/2026-07-23-minions-multi-distribution-refactor.md",
    # Contract tests build synthetic fixtures that exercise the architecture
    # checker / baseline tools against the old monolithic layout on purpose.
    "tests/contract/refactor/test_architecture_checker.py",
    "tests/contract/refactor/test_baseline_tools.py",
    # This file's own assertions reference the forbidden tokens.
    "tests/contract/refactor/test_automation_workspace_paths.py",
    # Historical comment documenting a long-fixed dual-import scenario.
    "tests/unit/providers/test_provider_class_identity.py",
)

# A ``packages/<component>/src/minions`` reference is the legitimate new form.
_PACKAGES_SRC_MINIONS = re.compile(r"packages/[^/\s'\"]+/src/minions")


def _is_allowlisted(posix_path: str) -> bool:
    return any(
        posix_path == allowed or posix_path.startswith(allowed + "/")
        for allowed in _LEGACY_PATH_ALLOWLIST
    )


def _user_facing_files() -> list[Path]:
    files: list[Path] = []
    for name in _USER_FACING_SCAN_ROOT_FILES:
        path = REPO_ROOT / name
        if path.is_file():
            files.append(path)
    for directory in _USER_FACING_SCAN_DIRS:
        root = REPO_ROOT / directory
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in _USER_FACING_TEXT_SUFFIXES:
                continue
            files.append(path)
    # Deduplicate while preserving order.
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in files:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def test_user_facing_docs_have_no_monolithic_source_paths() -> None:
    violations: list[str] = []
    for path in _user_facing_files():
        posix = path.relative_to(REPO_ROOT).as_posix()
        if _is_allowlisted(posix):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        normalized = text.replace("\\", "/")
        for line_number, line in enumerate(normalized.splitlines(), start=1):
            # Strip legitimate packages/<component>/src/minions references,
            # then look for any remaining bare monolithic path tokens.
            without_component_paths = _PACKAGES_SRC_MINIONS.sub("", line)
            for token in ("src/minions", "src/agentscope", "--cov=src"):
                if token in without_component_paths:
                    violations.append(
                        f"{posix}:{line_number}: {line.strip()}"
                    )
                    break

    assert not violations, (
        "User-facing docs/config must not reference the removed monolithic "
        "src/minions (or src/agentscope / --cov=src) layout; use "
        "packages/<component>/src/minions instead. "
        "If a reference is intentional, add it to "
        "_LEGACY_PATH_ALLOWLIST in test_automation_workspace_paths.py.\n"
        + "\n".join(violations)
    )
