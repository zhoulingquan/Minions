"""Validate PEP 420 namespace ownership across workspace source roots."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

if __package__:
    from ._architecture_common import (
        ArchitectureError,
        iter_owned_files,
        load_architecture_config,
        module_name_for_path,
        validate_source_roots,
    )
else:
    from _architecture_common import (  # type: ignore[no-redef]
        ArchitectureError,
        iter_owned_files,
        load_architecture_config,
        module_name_for_path,
        validate_source_roots,
    )


def check_namespace(root: Path, config_path: Path | None = None) -> None:
    """Raise ``ArchitectureError`` when namespace ownership is invalid."""
    root = root.resolve()
    config = load_architecture_config(root, config_path)
    source_roots = validate_source_roots(root, config)

    for source_root in source_roots.values():
        init = source_root.path / "__init__.py"
        if init.is_file():
            raise ArchitectureError(
                f"package {source_root.distribution} has forbidden top-level "
                f"namespace initializer {init}",
            )

    ownership: dict[tuple[str, str], tuple[str, Path]] = {}
    for source_root in source_roots.values():
        for path, relative in iter_owned_files(source_root.path):
            keys = [("resource", relative.as_posix().casefold())]
            if path.suffix == ".py":
                module = module_name_for_path(source_root.path, path)
                keys.append(("module", module.casefold()))
            for kind, identity in keys:
                previous = ownership.get((kind, identity))
                if previous is None:
                    ownership[(kind, identity)] = (
                        source_root.distribution,
                        path,
                    )
                    continue
                previous_distribution, previous_path = previous
                if previous_distribution == source_root.distribution:
                    continue
                raise ArchitectureError(
                    f"duplicate {kind} ownership for {identity}: "
                    f"{previous_distribution} provides {previous_path}; "
                    f"{source_root.distribution} provides {path}",
                )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root (default: current directory)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="architecture config path (default: ROOT/architecture.toml)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the namespace gate CLI."""
    args = _parser().parse_args(argv)
    try:
        check_namespace(args.root, args.config)
    except ArchitectureError as exc:
        print(f"namespace ownership error: {exc}", file=sys.stderr)
        return 1
    print("namespace ownership valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
