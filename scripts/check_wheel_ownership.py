"""Validate disjoint PEP 420 ownership across the fourteen Minions wheels."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from email.parser import Parser
from fnmatch import fnmatch
from pathlib import Path
import sys
from typing import Sequence
import zipfile

from packaging.utils import canonicalize_name


COMPONENT_MODULES = {
    "minions-core": "minions/constant.py",
    "minions-runtime": "minions/runtime/__init__.py",
    "minions-providers": "minions/providers/__init__.py",
    "minions-tool-calls": "minions/tool_calls/__init__.py",
    "minions-drivers": "minions/drivers/__init__.py",
    "minions-channels": "minions/channels/__init__.py",
    "minions-plugins": "minions/plugins/__init__.py",
    "minions-loop": "minions/loop/__init__.py",
    "minions-governance": "minions/governance/__init__.py",
    "minions-modes": "minions/modes/__init__.py",
    "minions-agents": "minions/agents/__init__.py",
    "minions-app": "minions/app/__init__.py",
    "minions-cli": "minions/cli/__init__.py",
}

COMPONENT_RESOURCES = {
    "minions-core": (
        "minions/security/tool_guard/rules/*.yaml",
        "minions/security/skill_scanner/rules/**/*.yaml",
        "minions/security/skill_scanner/data/*.yaml",
    ),
    "minions-channels": ("minions/channels/yuanbao/proto/*.json",),
    "minions-agents": (
        "minions/agents/md_files/**/*.md",
        "minions/agents/skills/**/SKILL.md",
        "minions/sage/migrations/*.sql",
    ),
    "minions-app": (
        "minions/console/**",
        "minions/docs/*.md",
        "minions/tenancy/migrations/*.sql",
    ),
}

EXPECTED_DISTRIBUTIONS = frozenset((*COMPONENT_MODULES, "minions"))


class WheelOwnershipError(ValueError):
    """Raised when wheel contents violate namespace ownership."""


@dataclass(frozen=True)
class WheelContents:
    distribution: str
    path: Path
    files: frozenset[str]


def _wheel_contents(path: Path) -> WheelContents:
    if not path.is_file():
        raise WheelOwnershipError(f"wheel does not exist: {path}")
    try:
        with zipfile.ZipFile(path) as wheel:
            names = tuple(
                name.replace("\\", "/")
                for name in wheel.namelist()
                if name and not name.endswith("/")
            )
            metadata_names = [
                name for name in names if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_names) != 1:
                raise WheelOwnershipError(
                    f"{path} must contain exactly one .dist-info/METADATA"
                )
            metadata = Parser().parsestr(
                wheel.read(metadata_names[0]).decode("utf-8")
            )
    except (OSError, zipfile.BadZipFile, UnicodeError) as exc:
        raise WheelOwnershipError(f"cannot inspect wheel {path}: {exc}") from exc
    raw_name = metadata.get("Name")
    if not raw_name:
        raise WheelOwnershipError(f"wheel metadata has no Name: {path}")
    distribution = str(canonicalize_name(raw_name))
    return WheelContents(distribution, path, frozenset(names))


def _owned_files(contents: WheelContents) -> frozenset[str]:
    return frozenset(
        name for name in contents.files if ".dist-info/" not in name
    )


def check_wheel_ownership(wheels: Sequence[Path]) -> None:
    """Raise when wheel files overlap or required namespace assets are absent."""
    inspected = [_wheel_contents(path.resolve()) for path in wheels]
    by_distribution: dict[str, WheelContents] = {}
    errors: list[str] = []
    for contents in inspected:
        previous = by_distribution.get(contents.distribution)
        if previous is not None:
            errors.append(
                f"duplicate wheel for {contents.distribution}: "
                f"{previous.path} and {contents.path}"
            )
        else:
            by_distribution[contents.distribution] = contents

    actual = frozenset(by_distribution)
    missing = sorted(EXPECTED_DISTRIBUTIONS - actual)
    unexpected = sorted(actual - EXPECTED_DISTRIBUTIONS)
    if missing:
        errors.append(f"missing distributions: {missing}")
    if unexpected:
        errors.append(f"unexpected distributions: {unexpected}")

    ownership: dict[str, str] = {}
    for distribution, contents in sorted(by_distribution.items()):
        for filename in sorted(_owned_files(contents)):
            previous = ownership.get(filename)
            if previous is not None and previous != distribution:
                errors.append(
                    f"overlapping wheel file {filename}: "
                    f"{previous} and {distribution}"
                )
            else:
                ownership[filename] = distribution
            if filename.casefold() == "minions/__init__.py":
                errors.append(
                    f"forbidden PEP 420 namespace initializer {filename} "
                    f"in {distribution}"
                )
            path_parts = tuple(part.casefold() for part in filename.split("/"))
            if (
                "__pycache__" in path_parts
                or filename.casefold().endswith((".pyc", ".pyo"))
            ):
                errors.append(
                    f"generated Python cache {filename} in {distribution}"
                )

    meta = by_distribution.get("minions")
    if meta is not None:
        leaked = sorted(
            filename
            for filename in _owned_files(meta)
            if filename.startswith("minions/")
        )
        for filename in leaked:
            errors.append(f"meta wheel minions contains source file {filename}")

    for distribution, expected_module in COMPONENT_MODULES.items():
        contents = by_distribution.get(distribution)
        if contents is None:
            continue
        files = _owned_files(contents)
        if expected_module not in files:
            errors.append(
                f"{distribution} is missing expected module {expected_module}"
            )
        for pattern in COMPONENT_RESOURCES.get(distribution, ()):
            if not any(fnmatch(filename, pattern) for filename in files):
                errors.append(
                    f"{distribution} is missing required resource {pattern}"
                )

    if errors:
        raise WheelOwnershipError("\n".join(errors))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheels", nargs="+", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        check_wheel_ownership(args.wheels)
    except WheelOwnershipError as exc:
        print(f"wheel ownership error: {exc}", file=sys.stderr)
        return 1
    print(f"wheel ownership valid: {len(args.wheels)} wheels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
