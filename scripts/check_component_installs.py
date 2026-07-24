"""Verify each component in an isolated dependency-closure environment."""
from __future__ import annotations

import argparse
from email.parser import Parser
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Sequence
import venv
import zipfile

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from install_built_wheels import collect_workspace_wheels, venv_python


COMPONENT_IMPORTS = {
    "minions-core": (
        "minions.core",
        "minions.config",
        "minions.security",
        "minions.envs",
        "minions.observability",
        "minions.utils",
        "minions.constant",
        "minions.exceptions",
        "minions.schemas",
    ),
    "minions-runtime": (
        "minions.runtime",
        "minions.token_usage",
        "minions.hooks",
    ),
    "minions-providers": ("minions.providers", "minions.local_models"),
    "minions-tool-calls": ("minions.tool_calls",),
    "minions-drivers": ("minions.drivers",),
    "minions-channels": ("minions.channels",),
    "minions-plugins": ("minions.plugins", "minions._version_compat"),
    "minions-loop": ("minions.loop",),
    "minions-governance": ("minions.governance", "minions.sandbox"),
    "minions-modes": ("minions.modes",),
    "minions-agents": ("minions.agents", "minions.market", "minions.sage"),
    "minions-app": (
        "minions.app",
        "minions.backup",
        "minions.agent_stats",
        "minions.tenancy",
        "minions.tunnel",
        "minions.api_action",
    ),
    "minions-cli": ("minions.cli", "minions.__main__"),
}

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


class ComponentInstallError(RuntimeError):
    """Raised when a component dependency closure is incomplete."""


def _wheel_metadata(path: Path) -> tuple[str, tuple[str, ...]]:
    with zipfile.ZipFile(path) as wheel:
        metadata_names = [
            name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ComponentInstallError(
                f"{path} must contain exactly one METADATA file",
            )
        metadata = Parser().parsestr(
            wheel.read(metadata_names[0]).decode("utf-8"),
        )
    name = canonicalize_name(metadata.get("Name", ""))
    return str(name), tuple(metadata.get_all("Requires-Dist", []))


def _wheel_map(wheels: Sequence[Path]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in wheels:
        name, _requirements = _wheel_metadata(path)
        result[name] = path
    return result


def validate_internal_dependencies(
    wheel: Path,
    component: str,
) -> None:
    """Require the locked direct internal dependency set at version 0.1.0."""
    _name, raw_requirements = _wheel_metadata(wheel)
    actual: set[str] = set()
    errors: list[str] = []
    for raw in raw_requirements:
        requirement = Requirement(raw)
        name = canonicalize_name(requirement.name)
        if not str(name).startswith("minions-"):
            continue
        expected_pin = f"{name}==0.1.0"
        if (
            str(requirement.specifier) != "==0.1.0"
            or requirement.url is not None
            or requirement.marker is not None
        ):
            errors.append(f"{raw!r} must be exactly {expected_pin}")
        actual.add(str(name))
    expected = INTERNAL_DEPENDENCIES[component]
    for missing in sorted(expected - actual):
        errors.append(f"{component} is missing {missing}==0.1.0")
    for extra in sorted(actual - expected):
        errors.append(f"{component} has unexpected internal dependency {extra}")
    if errors:
        raise ComponentInstallError("\n".join(errors))


def _check_component(component: str, wheel: Path, dist: Path) -> None:
    validate_internal_dependencies(wheel, component)
    with tempfile.TemporaryDirectory(prefix=f"{component}-install-") as temp:
        environment = Path(temp) / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        python = venv_python(environment)
        subprocess.run(
            (
                str(python),
                "-m",
                "pip",
                "install",
                "--find-links",
                str(dist.resolve()),
                str(wheel.resolve()),
            ),
            check=True,
        )
        subprocess.run((str(python), "-m", "pip", "check"), check=True)
        modules = COMPONENT_IMPORTS[component]
        statements = [f"import {module}" for module in modules]
        if component == "minions-core":
            statements.extend(
                (
                    "import importlib.util",
                    "assert importlib.util.find_spec('agentscope') is None",
                ),
            )
        subprocess.run(
            (str(python), "-c", "; ".join(statements)),
            check=True,
        )


def check_component_installs(
    dist: Path,
    components: Sequence[str],
) -> None:
    wheels = collect_workspace_wheels(dist)
    by_name = _wheel_map(wheels)
    for component in components:
        wheel = by_name.get(component)
        if wheel is None:
            raise ComponentInstallError(f"missing wheel for {component}")
        _check_component(component, wheel, dist)
        print(f"component install valid: {component}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path)
    parser.add_argument(
        "--component",
        choices=tuple(COMPONENT_IMPORTS),
        help="check one component (default: all thirteen)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    components = (
        (args.component,) if args.component else tuple(COMPONENT_IMPORTS)
    )
    try:
        check_component_installs(args.dist, components)
    except (
        ComponentInstallError,
        OSError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"component install error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
