"""Validate workspace project versions and exact internal dependency pins."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import tomllib
from typing import Sequence

from packaging.requirements import InvalidRequirement, Requirement


_VERSION_ASSIGNMENT = re.compile(
    r'^__version__\s*=\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)


class WorkspaceVersionError(ValueError):
    """Raised when workspace version metadata is inconsistent."""


def _load_pyproject(path: Path) -> dict:
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream)
    except FileNotFoundError as exc:
        raise WorkspaceVersionError(f"missing pyproject: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise WorkspaceVersionError(f"malformed pyproject {path}: {exc}") from exc


def _source_version(root: Path) -> str:
    candidates = (
        root / "src" / "minions" / "__version__.py",
        root
        / "packages"
        / "minions-core"
        / "src"
        / "minions"
        / "__version__.py",
    )
    for path in candidates:
        if not path.is_file():
            continue
        match = _VERSION_ASSIGNMENT.search(path.read_text(encoding="utf-8"))
        if match is not None:
            return match.group(1)
        raise WorkspaceVersionError(f"cannot parse __version__ assignment: {path}")
    raise WorkspaceVersionError("dynamic root version has no __version__.py owner")


def _project_version(root: Path, path: Path, project: dict) -> str:
    value = project.get("version")
    if isinstance(value, str) and value:
        return value
    if path == root / "pyproject.toml" and "version" in project.get(
        "dynamic", []
    ):
        return _source_version(root)
    raise WorkspaceVersionError(f"project has no concrete version: {path}")


def _internal_requirement_error(
    distribution: str,
    dependency: str,
    version: str,
) -> str | None:
    try:
        requirement = Requirement(dependency)
    except InvalidRequirement as exc:
        return f"{distribution} has invalid dependency {dependency!r}: {exc}"
    name = requirement.name.lower().replace("_", "-")
    if name != "minions" and not name.startswith("minions-"):
        return None
    expected = f"{name}=={version}"
    if (
        str(requirement.specifier) != f"=={version}"
        or requirement.url is not None
        or requirement.marker is not None
    ):
        return (
            f"{distribution} internal dependency {dependency!r} must be "
            f"exactly {expected}"
        )
    return None


def check_workspace_versions(root: Path) -> str:
    """Return the common version or raise on drift/invalid internal pins."""
    root = root.resolve()
    root_path = root / "pyproject.toml"
    root_data = _load_pyproject(root_path)
    root_project = root_data.get("project")
    if not isinstance(root_project, dict):
        raise WorkspaceVersionError(f"missing [project] table: {root_path}")
    version = _project_version(root, root_path, root_project)

    projects: list[tuple[str, Path, dict]] = [
        (str(root_project.get("name", "minions")), root_path, root_project)
    ]
    packages_dir = root / "packages"
    if packages_dir.is_dir():
        for member in sorted(packages_dir.iterdir(), key=lambda item: item.name):
            path = member / "pyproject.toml"
            if not member.is_dir() or not path.is_file():
                continue
            data = _load_pyproject(path)
            project = data.get("project")
            if not isinstance(project, dict):
                raise WorkspaceVersionError(f"missing [project] table: {path}")
            projects.append((str(project.get("name", member.name)), path, project))

    errors: list[str] = []
    for distribution, path, project in projects:
        actual = _project_version(root, path, project)
        if actual != version:
            errors.append(
                f"{distribution} version {actual} does not match minions {version}"
            )
        dependencies = project.get("dependencies", [])
        if not isinstance(dependencies, list):
            errors.append(f"{distribution} dependencies must be an array")
            continue
        for dependency in dependencies:
            if not isinstance(dependency, str):
                errors.append(f"{distribution} has non-string dependency {dependency!r}")
                continue
            error = _internal_requirement_error(distribution, dependency, version)
            if error is not None:
                errors.append(error)

    if errors:
        raise WorkspaceVersionError("\n".join(errors))
    return version


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root (default: current directory)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        version = check_workspace_versions(args.root)
    except WorkspaceVersionError as exc:
        print(f"workspace version error: {exc}", file=sys.stderr)
        return 1
    print(f"workspace versions valid: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
