"""Build all Minions component artifacts and the source-free meta package."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence

from check_wheel_ownership import check_wheel_ownership
from check_workspace_versions import check_workspace_versions


COMPONENT_BUILD_ORDER = (
    "minions-core",
    "minions-tool-calls",
    "minions-providers",
    "minions-runtime",
    "minions-drivers",
    "minions-channels",
    "minions-plugins",
    "minions-loop",
    "minions-governance",
    "minions-modes",
    "minions-agents",
    "minions-app",
    "minions-cli",
)


class WorkspaceBuildError(RuntimeError):
    """Raised when workspace structure or artifact output is invalid."""


def build_targets(root: Path) -> tuple[Path, ...]:
    """Return the dependency-ordered component roots followed by meta root."""
    root = root.resolve()
    targets = tuple(root / "packages" / name for name in COMPONENT_BUILD_ORDER)
    missing = [path for path in targets if not (path / "pyproject.toml").is_file()]
    if missing:
        raise WorkspaceBuildError(
            "missing component pyprojects: "
            + ", ".join(str(path) for path in missing)
        )
    if not (root / "pyproject.toml").is_file():
        raise WorkspaceBuildError(f"missing meta pyproject: {root / 'pyproject.toml'}")
    return (*targets, root)


def _prepare_dist(root: Path) -> Path:
    """Create a clean repository-local dist directory after safety checks."""
    dist = (root / "dist").resolve()
    if dist.parent != root.resolve() or dist.name != "dist":
        raise WorkspaceBuildError(f"refusing unsafe dist path: {dist}")
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir()
    return dist


def _clean_generated_build_inputs(target: Path, root: Path) -> None:
    """Remove generated caches that setuptools could copy into artifacts."""
    root = root.resolve()
    target = target.resolve()
    if target != root and target.parent != (root / "packages").resolve():
        raise WorkspaceBuildError(f"refusing unsafe build target: {target}")

    build_dir = target / "build"
    if build_dir.is_dir():
        shutil.rmtree(build_dir)

    source_root = target / "src"
    if source_root.is_dir():
        for cache_dir in sorted(
            source_root.rglob("__pycache__"),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            if cache_dir.is_dir():
                shutil.rmtree(cache_dir)
        for suffix in ("*.pyc", "*.pyo"):
            for cache_file in source_root.rglob(suffix):
                cache_file.unlink()

    egg_info_roots = (target, source_root)
    for egg_info_root in egg_info_roots:
        if not egg_info_root.is_dir():
            continue
        for egg_info in egg_info_root.glob("*.egg-info"):
            if egg_info.is_dir():
                shutil.rmtree(egg_info)


def build_workspace(root: Path) -> tuple[Path, ...]:
    """Build fourteen wheels/sdists, then validate version and ownership."""
    root = root.resolve()
    check_workspace_versions(root)
    targets = build_targets(root)
    dist = _prepare_dist(root)
    for target in targets:
        _clean_generated_build_inputs(target, root)
        command = (
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--sdist",
            "--outdir",
            str(dist),
            str(target),
        )
        try:
            subprocess.run(command, cwd=root, check=True)
        except subprocess.CalledProcessError as exc:
            raise WorkspaceBuildError(
                f"build failed for {target} with exit code {exc.returncode}"
            ) from exc
    wheels = tuple(sorted(dist.glob("*.whl")))
    if len(wheels) != 14:
        raise WorkspaceBuildError(
            f"expected exactly 14 wheels, found {len(wheels)} in {dist}"
        )
    check_wheel_ownership(wheels)
    return wheels


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print validated build order without creating artifacts",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        targets = build_targets(args.root)
        check_workspace_versions(args.root)
        if args.dry_run:
            for index, target in enumerate(targets, start=1):
                print(f"build {index:02d}: {target.as_posix()}")
            return 0
        wheels = build_workspace(args.root)
    except (WorkspaceBuildError, ValueError) as exc:
        print(f"workspace build error: {exc}", file=sys.stderr)
        return 1
    print(f"workspace build valid: {len(wheels)} wheels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
