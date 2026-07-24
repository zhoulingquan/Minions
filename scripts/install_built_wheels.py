"""Install the complete local Minions wheel set into an existing venv."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Sequence

from check_wheel_ownership import check_wheel_ownership


class BuiltWheelInstallError(RuntimeError):
    """Raised when local wheel installation cannot be performed safely."""


def collect_workspace_wheels(dist: Path) -> tuple[Path, ...]:
    """Return exactly fourteen validated wheel paths from ``dist``."""
    dist = dist.resolve()
    wheels = tuple(sorted(path.resolve() for path in dist.glob("*.whl")))
    if len(wheels) != 14:
        raise BuiltWheelInstallError(
            f"expected exactly 14 wheels in {dist}, found {len(wheels)}",
        )
    check_wheel_ownership(wheels)
    return wheels


def venv_python(venv: Path) -> Path:
    """Return the cross-platform Python executable for an existing venv."""
    venv = venv.resolve()
    candidates = (
        venv / "Scripts" / "python.exe",
        venv / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise BuiltWheelInstallError(f"venv Python does not exist: {venv}")


def install_built_wheels(venv: Path, dist: Path) -> tuple[Path, ...]:
    """Install all local wheels in one pip invocation."""
    wheels = collect_workspace_wheels(dist)
    python = venv_python(venv)
    command = (
        str(python),
        "-m",
        "pip",
        "install",
        *(str(path) for path in wheels),
    )
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise BuiltWheelInstallError(
            f"wheel installation failed with exit code {exc.returncode}",
        ) from exc
    return wheels


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv", required=True, type=Path)
    parser.add_argument(
        "--dist",
        type=Path,
        default=Path("dist"),
        help="wheel directory (default: ./dist)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        wheels = install_built_wheels(args.venv, args.dist)
    except (BuiltWheelInstallError, ValueError) as exc:
        print(f"built wheel install error: {exc}", file=sys.stderr)
        return 1
    print(f"installed local workspace wheels: {len(wheels)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
