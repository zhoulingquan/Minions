"""Validate actual Python import edges against distribution architecture."""
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import sys
import tokenize
from typing import Iterable, Sequence

if __package__:
    from ._architecture_common import (
        ArchitectureConfig,
        ArchitectureError,
        SourceRoot,
        is_init_module,
        is_python_source,
        iter_owned_files,
        load_architecture_config,
        module_name_for_path,
        validate_source_roots,
    )
else:
    from _architecture_common import (  # type: ignore[no-redef]
        ArchitectureConfig,
        ArchitectureError,
        SourceRoot,
        is_init_module,
        is_python_source,
        iter_owned_files,
        load_architecture_config,
        module_name_for_path,
        validate_source_roots,
    )


@dataclass(frozen=True)
class ImportRecord:
    """A resolved import occurrence with scope diagnostics."""

    source_distribution: str
    source_file: Path
    target_module: str
    line: int
    function_scope: bool
    type_checking: bool


@dataclass(frozen=True)
class ImportDiagnostic:
    """An invalid import occurrence with the same scope context as imports."""

    message: str
    source_file: Path
    line: int
    function_scope: bool
    type_checking: bool

    def render(self) -> str:
        function_scope = str(self.function_scope).lower()
        type_checking = str(self.type_checking).lower()
        return (
            f"{self.message}: {self.source_file} line {self.line} "
            f"(function_scope={function_scope}, type_checking={type_checking})"
        )


@dataclass(frozen=True)
class ForbiddenEdge:
    """An import occurrence denied by its source distribution allowlist."""

    record: ImportRecord
    target_distribution: str


@dataclass(frozen=True)
class ArchitectureReport:
    """Complete architecture analysis result."""

    forbidden_edges: tuple[ForbiddenEdge, ...]
    cycles: tuple[tuple[str, ...], ...]
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not (self.forbidden_edges or self.cycles or self.errors)


class _ImportCollector(ast.NodeVisitor):
    def __init__(
        self,
        distribution: str,
        path: Path,
        module_name: str,
        *,
        package_module: bool,
    ) -> None:
        self.distribution = distribution
        self.path = path
        self.module_name = module_name
        self.current_package = (
            module_name if package_module else module_name.rpartition(".")[0]
        )
        self.function_depth = 0
        self.type_checking_depth = 0
        self.records: list[ImportRecord] = []
        self.errors: list[ImportDiagnostic] = []

    def _record(self, module: str, line: int) -> None:
        self.records.append(
            ImportRecord(
                source_distribution=self.distribution,
                source_file=self.path,
                target_module=module,
                line=line,
                function_scope=self.function_depth > 0,
                type_checking=self.type_checking_depth > 0,
            ),
        )

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self._record(alias.name, node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        base = self._resolve_from_base(node)
        if base is None:
            return
        for alias in node.names:
            if alias.name == "*":
                target = base
            else:
                target = f"{base}.{alias.name}" if base else alias.name
            self._record(target, node.lineno)

    def _resolve_from_base(self, node: ast.ImportFrom) -> str | None:
        if node.level == 0:
            return node.module or ""

        package_parts = self.current_package.split(".")
        ascents = node.level - 1
        if not self.current_package or ascents >= len(package_parts):
            self.errors.append(
                ImportDiagnostic(
                    message=(
                        "relative import ownership error: traverses beyond "
                        f"package {self.current_package!r}"
                    ),
                    source_file=self.path,
                    line=node.lineno,
                    function_scope=self.function_depth > 0,
                    type_checking=self.type_checking_depth > 0,
                ),
            )
            return None
        base_parts = package_parts[: len(package_parts) - ascents]
        if node.module:
            base_parts.extend(node.module.split("."))
        return ".".join(base_parts)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self.function_depth += 1
        self.generic_visit(node)
        self.function_depth -= 1

    def visit_AsyncFunctionDef(  # noqa: N802
        self,
        node: ast.AsyncFunctionDef,
    ) -> None:
        self.function_depth += 1
        self.generic_visit(node)
        self.function_depth -= 1

    def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802
        self.function_depth += 1
        self.generic_visit(node)
        self.function_depth -= 1

    def visit_If(self, node: ast.If) -> None:  # noqa: N802
        self.visit(node.test)
        guarded = _is_type_checking_guard(node.test)
        if guarded:
            self.type_checking_depth += 1
        for statement in node.body:
            self.visit(statement)
        if guarded:
            self.type_checking_depth -= 1
        for statement in node.orelse:
            self.visit(statement)


def _is_type_checking_guard(node: ast.AST) -> bool:
    return (isinstance(node, ast.Name) and node.id == "TYPE_CHECKING") or (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.attr == "TYPE_CHECKING"
    )


def _python_files(source_root: SourceRoot) -> Iterable[Path]:
    for path, _relative in iter_owned_files(source_root.path):
        if is_python_source(path):
            yield path


def _scan_file(
    source_root: SourceRoot, path: Path
) -> tuple[list[ImportRecord], list[str]]:
    try:
        with tokenize.open(path) as stream:
            source = stream.read()
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        line = exc.lineno or 1
        return [], [f"Python syntax error: {path} line {line}: {exc.msg}"]
    except (OSError, UnicodeError) as exc:
        return [], [f"cannot read Python source {path}: {exc}"]

    module_name = module_name_for_path(source_root.path, path)
    collector = _ImportCollector(
        source_root.distribution,
        path,
        module_name,
        package_module=is_init_module(path),
    )
    collector.visit(tree)
    return collector.records, [error.render() for error in collector.errors]


def _validate_active_source_ownership(
    config: ArchitectureConfig,
    source_roots: dict[str, SourceRoot],
) -> None:
    for distribution, source_root in source_roots.items():
        for path in _python_files(source_root):
            module = module_name_for_path(source_root.path, path)
            configured = config.configured_owner(module)
            if configured is None:
                configured_distribution = None
            else:
                configured_distribution = configured.distribution
                if not configured.uses_canonical_prefix:
                    raise ArchitectureError(
                        f"non-canonical configured source prefix: module {module} "
                        f"in {path} matches configured prefix {configured.prefix} "
                        f"for package "
                        f"{configured_distribution}; use canonical prefix "
                        f"{configured.prefix}",
                    )
            if distribution == "minions":
                if (
                    configured_distribution is not None
                    and configured_distribution != "minions"
                    and configured_distribution in config.active_packages
                ):
                    raise ArchitectureError(
                        f"configured ownership for {module} belongs to active package "
                        f"{configured_distribution}, but source remains in umbrella "
                        f"file {path}",
                    )
                continue
            if configured_distribution != distribution:
                owner = configured_distribution or "no configured package"
                raise ArchitectureError(
                    f"configured ownership for active package {distribution} is "
                    f"inconsistent: module {module} in {path} belongs to {owner}",
                )


def _target_distribution(
    config: ArchitectureConfig,
    record: ImportRecord,
) -> tuple[str | None, str | None]:
    target = record.target_module
    top_level = target.partition(".")[0]
    if top_level.casefold() == "minions" and top_level != "minions":
        return None, (
            f"non-canonical internal import: {record.source_file} line "
            f"{record.line} imports {target}; use lowercase minions as the "
            f"top-level package ({_scope_flags(record)})"
        )
    if target != "minions" and not target.startswith("minions."):
        return None, None

    configured = config.configured_owner(target)
    if configured is not None:
        prefix = configured.prefix
        distribution = configured.distribution
        if not configured.uses_canonical_prefix:
            return None, (
                f"non-canonical configured-prefix internal import: "
                f"{record.source_file} line {record.line} imports {target}; "
                f"use canonical configured prefix {prefix} "
                f"({_scope_flags(record)})"
            )
        if distribution in config.active_packages:
            return distribution, None
        if "minions" in config.active_packages:
            return "minions", None
        return None, (
            f"import ownership error: {record.source_file} line {record.line} "
            f"imports {target}, whose prefix {prefix} belongs to inactive package "
            f"{distribution}, and umbrella minions is not active "
            f"({_scope_flags(record)})"
        )

    if "minions" in config.active_packages:
        return "minions", None
    return None, (
        f"import ownership error: {record.source_file} line {record.line} imports "
        f"unconfigured internal module {target}, and umbrella minions is not active "
        f"({_scope_flags(record)})"
    )


def _strong_components(graph: dict[str, set[str]]) -> list[set[str]]:
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[set[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in sorted(graph[node]):
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])

        if lowlinks[node] != indices[node]:
            return
        component: set[str] = set()
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.add(member)
            if member == node:
                break
        components.append(component)

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return components


def _readable_cycle(
    graph: dict[str, set[str]],
    component: set[str],
) -> tuple[str, ...]:
    start = min(component)

    for neighbor in sorted(graph[start] & component):
        parents: dict[str, str | None] = {neighbor: None}
        stack = [neighbor]
        while stack:
            node = stack.pop()
            if start in graph[node]:
                path = [node]
                while True:
                    parent = parents[path[-1]]
                    if parent is None:
                        break
                    path.append(parent)
                path.reverse()
                return tuple((start, *path, start))
            for target in sorted(graph[node] & component, reverse=True):
                if target != start and target not in parents:
                    parents[target] = node
                    stack.append(target)

    # A multi-node strongly connected component always contains such a path.
    raise ArchitectureError(f"could not render distribution cycle {component}")


def _distribution_cycles(
    graph: dict[str, set[str]],
) -> tuple[tuple[str, ...], ...]:
    cyclic = [
        component
        for component in _strong_components(graph)
        if len(component) > 1
    ]
    return tuple(
        sorted((_readable_cycle(graph, component) for component in cyclic)),
    )


def check_architecture(
    root: Path,
    config_path: Path | None = None,
) -> ArchitectureReport:
    """Analyze active source roots and return all import-edge diagnostics."""
    root = root.resolve()
    config = load_architecture_config(root, config_path)
    source_roots = validate_source_roots(root, config)
    _validate_active_source_ownership(config, source_roots)

    records: list[ImportRecord] = []
    errors: list[str] = []
    for distribution in sorted(source_roots):
        source_root = source_roots[distribution]
        for path in _python_files(source_root):
            file_records, file_errors = _scan_file(source_root, path)
            records.extend(file_records)
            errors.extend(file_errors)

    graph = {distribution: set() for distribution in config.active_packages}
    forbidden: list[ForbiddenEdge] = []
    for record in records:
        target_distribution, ownership_error = _target_distribution(
            config, record
        )
        if ownership_error is not None:
            errors.append(ownership_error)
            continue
        if (
            target_distribution is None
            or target_distribution == record.source_distribution
        ):
            continue
        graph[record.source_distribution].add(target_distribution)
        rule = config.packages[record.source_distribution]
        if target_distribution not in rule.allows:
            forbidden.append(ForbiddenEdge(record, target_distribution))

    forbidden.sort(
        key=lambda edge: (
            str(edge.record.source_file),
            edge.record.line,
            edge.record.target_module,
        ),
    )
    return ArchitectureReport(
        forbidden_edges=tuple(forbidden),
        cycles=_distribution_cycles(graph),
        errors=tuple(errors),
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


def _scope_flags(record: ImportRecord) -> str:
    function_scope = str(record.function_scope).lower()
    type_checking = str(record.type_checking).lower()
    return f"function_scope={function_scope}, type_checking={type_checking}"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the architecture gate CLI."""
    args = _parser().parse_args(argv)
    try:
        report = check_architecture(args.root, args.config)
    except ArchitectureError as exc:
        print(f"architecture config/ownership error: {exc}", file=sys.stderr)
        return 1

    if report.valid:
        print("0 forbidden edges, 0 distribution cycles")
        return 0

    for error in report.errors:
        print(error, file=sys.stderr)
    for edge in report.forbidden_edges:
        record = edge.record
        print(
            f"forbidden edge: {record.source_distribution} -> "
            f"{edge.target_distribution}; import {record.target_module} at "
            f"{record.source_file} line {record.line} "
            f"({_scope_flags(record)})",
            file=sys.stderr,
        )
    for cycle in report.cycles:
        print(f"distribution cycle: {' -> '.join(cycle)}", file=sys.stderr)
    print(
        f"{len(report.forbidden_edges)} forbidden edges, "
        f"{len(report.cycles)} distribution cycles",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
