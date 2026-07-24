# -*- coding: utf-8 -*-
"""Capture deterministic static internal-import compatibility baselines."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__:
    # pylint: disable-next=relative-beyond-top-level
    from ._architecture_common import ArchitectureError, module_name_for_path

    # pylint: disable-next=relative-beyond-top-level
    from .check_architecture import (
        resolve_target_distribution,
        scan_import_records,
    )

    # pylint: disable-next=relative-beyond-top-level
    from .check_namespace import check_namespace
else:
    from _architecture_common import (  # type: ignore[no-redef]
        ArchitectureError,
        module_name_for_path,
    )

    # pylint: disable-next=no-name-in-module
    from check_architecture import (  # type: ignore[no-redef]
        resolve_target_distribution,
        scan_import_records,
    )
    from check_namespace import check_namespace  # type: ignore[no-redef]


SCHEMA_VERSION = 1


def analyze_imports(
    root: Path,
    config_path: Path | None = None,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Return the complete static import model and actionable diagnostics."""
    root = root.resolve()
    check_namespace(root, config_path)
    config, source_roots, records, scan_errors = scan_import_records(
        root,
        config_path,
    )
    edges: list[dict[str, Any]] = []
    errors = list(scan_errors)
    for record in records:
        target_distribution, ownership_error = resolve_target_distribution(
            config,
            record,
        )
        if target_distribution is None and ownership_error is None:
            continue
        if ownership_error is not None:
            errors.append(ownership_error)
        source_root = source_roots[record.source_distribution]
        edges.append(
            {
                "function_scope": record.function_scope,
                "line": record.line,
                "ownership_error": ownership_error,
                "source_distribution": record.source_distribution,
                "source_file": record.source_file.relative_to(root).as_posix(),
                "source_module": module_name_for_path(
                    source_root.path,
                    record.source_file,
                ),
                "target_distribution": target_distribution,
                "target_module": record.target_module,
                "type_checking": record.type_checking,
            },
        )
    edges.sort(
        key=lambda edge: (
            edge["source_file"],
            edge["line"],
            edge["target_module"],
            edge["function_scope"],
            edge["type_checking"],
        ),
    )
    return {"schema_version": SCHEMA_VERSION, "edges": edges}, tuple(errors)


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
    outputs = parser.add_mutually_exclusive_group(required=True)
    outputs.add_argument(
        "--json",
        type=Path,
        help="write the computed baseline",
    )
    outputs.add_argument(
        "--check",
        type=Path,
        help="check an existing baseline",
    )
    return parser


def _serialized(model: dict[str, Any]) -> str:
    return (
        json.dumps(
            model,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _read_baseline(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ArchitectureError(
            f"baseline file does not exist: {path}",
        ) from exc
    except OSError as exc:
        raise ArchitectureError(f"cannot read baseline {path}: {exc}") from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ArchitectureError(
            f"invalid JSON baseline {path}: {exc}",
        ) from exc
    if not isinstance(value, dict):
        raise ArchitectureError(f"baseline {path} must contain a JSON object")
    return value


def _write_baseline(path: Path, model: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_serialized(model), encoding="utf-8", newline="\n")
    except OSError as exc:
        raise ArchitectureError(
            f"cannot write baseline {path}: {exc}",
        ) from exc


def main(argv: Sequence[str] | None = None) -> int:
    """Run the static import-baseline CLI."""
    args = _parser().parse_args(argv)
    try:
        model, errors = analyze_imports(args.root, args.config)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        if args.check is not None:
            existing = _read_baseline(args.check)
            if existing != model:
                print(f"import baseline drift: {args.check}", file=sys.stderr)
                return 1
            print(f"import baseline matches: {args.check}")
            return 0
        _write_baseline(args.json, model)
    except ArchitectureError as exc:
        print(
            f"import baseline config/ownership error: {exc}",
            file=sys.stderr,
        )
        return 1

    print(f"wrote import baseline: {args.json} ({len(model['edges'])} edges)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
