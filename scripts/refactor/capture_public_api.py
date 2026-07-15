"""Capture deterministic static Python public-API compatibility baselines."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import sys
import tokenize
from typing import Any, Iterable, Sequence

if __package__:
    from ._architecture_common import (
        ArchitectureError,
        load_architecture_config,
        module_name_for_path,
        validate_source_roots,
    )
    from .check_architecture import (
        iter_python_files,
        validate_active_source_ownership,
    )
    from .check_namespace import check_namespace
else:
    from _architecture_common import (  # type: ignore[no-redef]
        ArchitectureError,
        load_architecture_config,
        module_name_for_path,
        validate_source_roots,
    )
    from check_architecture import (  # type: ignore[no-redef]
        iter_python_files,
        validate_active_source_ownership,
    )
    from check_namespace import check_namespace  # type: ignore[no-redef]


SCHEMA_VERSION = 1
_CONSTANT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _parse_python(path: Path) -> tuple[ast.Module | None, str | None]:
    try:
        with tokenize.open(path) as stream:
            source = stream.read()
        return ast.parse(source, filename=str(path)), None
    except SyntaxError as exc:
        line = exc.lineno or 1
        return None, f"Python syntax error: {path} line {line}: {exc.msg}"
    except (OSError, UnicodeError) as exc:
        return None, f"cannot read Python source {path}: {exc}"


def _literal_all(node: ast.AST) -> tuple[str, ...] | None:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: list[str] = []
        for element in node.elts:
            if not isinstance(element, ast.Constant) or not isinstance(
                element.value,
                str,
            ):
                return None
            values.append(element.value)
        return tuple(values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_all(node.left)
        right = _literal_all(node.right)
        if left is not None and right is not None:
            return (*left, *right)
    return None


def _assignment_targets(node: ast.AST) -> Iterable[ast.Name]:
    if isinstance(node, ast.Name):
        yield node
    elif isinstance(node, (ast.List, ast.Tuple)):
        for element in node.elts:
            yield from _assignment_targets(element)


class _ClassGlobalAllFinder(ast.NodeVisitor):
    """Find a class-scope ``global __all__`` without entering child scopes."""

    def __init__(self) -> None:
        self.found = False

    def visit_Global(self, node: ast.Global) -> None:  # noqa: N802
        if "__all__" in node.names:
            self.found = True

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        return

    def visit_AsyncFunctionDef(  # noqa: N802
        self,
        node: ast.AsyncFunctionDef,
    ) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802
        return


class _DynamicAllFinder(ast.NodeVisitor):
    """Find unsupported module-scope bindings or mutations of ``__all__``."""

    def __init__(
        self,
        *,
        module_reads: bool = True,
        module_writes: bool = True,
    ) -> None:
        self.found = False
        self.module_reads = module_reads
        self.module_writes = module_writes

    def _record_string_binding(self, name: str | None) -> None:
        if self.module_writes and name == "__all__":
            self.found = True

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        if (
            self.module_writes
            and node.id == "__all__"
            and isinstance(node.ctx, (ast.Store, ast.Del))
        ):
            self.found = True

    def visit_Subscript(self, node: ast.Subscript) -> None:  # noqa: N802
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "__all__"
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and self.module_reads
        ):
            self.found = True
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "__all__"
            and self.module_reads
        ):
            self.found = True
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self._record_string_binding(
                alias.asname or alias.name.partition(".")[0],
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        for alias in node.names:
            self._record_string_binding(alias.asname or alias.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._record_string_binding(node.name)
        self._visit_function_definition(node)

    def visit_AsyncFunctionDef(  # noqa: N802
        self,
        node: ast.AsyncFunctionDef,
    ) -> None:
        self._record_string_binding(node.name)
        self._visit_function_definition(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self._record_string_binding(node.name)
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)
        self._visit_type_parameters(node)
        self._visit_class_body(node.body)

    def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802
        self._visit_arguments_definition_time(node.args)

    def _visit_function_definition(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        self._visit_arguments_definition_time(node.args)
        if node.returns is not None:
            self.visit(node.returns)
        self._visit_type_parameters(node)

    def _visit_arguments_definition_time(self, arguments: ast.arguments) -> None:
        for default in arguments.defaults:
            self.visit(default)
        for default in arguments.kw_defaults:
            if default is not None:
                self.visit(default)
        annotated = [
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        ]
        if arguments.vararg is not None:
            annotated.append(arguments.vararg)
        if arguments.kwarg is not None:
            annotated.append(arguments.kwarg)
        for argument in annotated:
            if argument.annotation is not None:
                self.visit(argument.annotation)

    def _visit_type_parameters(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    ) -> None:
        for parameter in getattr(node, "type_params", ()):
            self.generic_visit(parameter)

    @staticmethod
    def _class_declares_global_all(body: list[ast.stmt]) -> bool:
        finder = _ClassGlobalAllFinder()
        for statement in body:
            finder.visit(statement)
        return finder.found

    @staticmethod
    def _class_local_all_after(
        statement: ast.stmt,
        shadowed: bool,
    ) -> bool:
        if isinstance(statement, ast.Assign):
            return shadowed or any(
                target.id == "__all__"
                for raw_target in statement.targets
                for target in _assignment_targets(raw_target)
            )
        if isinstance(statement, ast.AnnAssign):
            return shadowed or (
                statement.value is not None
                and isinstance(statement.target, ast.Name)
                and statement.target.id == "__all__"
            )
        if isinstance(statement, ast.AugAssign):
            return shadowed or (
                isinstance(statement.target, ast.Name)
                and statement.target.id == "__all__"
            )
        if isinstance(statement, ast.Delete) and any(
            target.id == "__all__"
            for raw_target in statement.targets
            for target in _assignment_targets(raw_target)
        ):
            return False
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return shadowed or statement.name == "__all__"
        if isinstance(statement, ast.Import):
            return shadowed or any(
                (alias.asname or alias.name.partition(".")[0]) == "__all__"
                for alias in statement.names
            )
        if isinstance(statement, ast.ImportFrom):
            return shadowed or any(
                (alias.asname or alias.name) == "__all__"
                for alias in statement.names
            )
        return shadowed

    def _visit_class_body(self, body: list[ast.stmt]) -> None:
        global_all = self._class_declares_global_all(body)
        shadowed = False
        for statement in body:
            finder = _DynamicAllFinder(
                module_reads=global_all or not shadowed,
                module_writes=global_all,
            )
            finder.visit(statement)
            if finder.found:
                self.found = True
            if not global_all:
                shadowed = self._class_local_all_after(statement, shadowed)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:  # noqa: N802
        self._record_string_binding(node.name)
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:  # noqa: N802
        self._record_string_binding(node.name)
        self.generic_visit(node)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:  # noqa: N802
        self._record_string_binding(node.name)
        self.generic_visit(node)

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:  # noqa: N802
        self._record_string_binding(node.rest)
        self.generic_visit(node)

    def _visit_comprehension_target(self, node: ast.AST) -> None:
        if isinstance(node, ast.Name):
            return
        if isinstance(node, ast.Starred):
            self._visit_comprehension_target(node.value)
            return
        if isinstance(node, (ast.List, ast.Tuple)):
            for element in node.elts:
                self._visit_comprehension_target(element)
            return
        self.visit(node)

    def _visit_comprehension_parts(
        self,
        generators: list[ast.comprehension],
    ) -> None:
        for generator in generators:
            self._visit_comprehension_target(generator.target)
            self.visit(generator.iter)
            for condition in generator.ifs:
                self.visit(condition)

    def visit_ListComp(self, node: ast.ListComp) -> None:  # noqa: N802
        self._visit_comprehension_parts(node.generators)
        self.visit(node.elt)

    def visit_SetComp(self, node: ast.SetComp) -> None:  # noqa: N802
        self._visit_comprehension_parts(node.generators)
        self.visit(node.elt)

    def visit_DictComp(self, node: ast.DictComp) -> None:  # noqa: N802
        self._visit_comprehension_parts(node.generators)
        self.visit(node.key)
        self.visit(node.value)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:  # noqa: N802
        self._visit_comprehension_parts(node.generators)
        self.visit(node.elt)


def _has_dynamic_all(statement: ast.stmt) -> bool:
    finder = _DynamicAllFinder()
    finder.visit(statement)
    return finder.found


def _all_record(tree: ast.Module) -> dict[str, Any]:
    status = "absent"
    names: tuple[str, ...] = ()
    for statement in tree.body:
        value: ast.AST | None = None
        assigns_all = False
        if isinstance(statement, ast.Assign):
            assigns_all = any(
                target.id == "__all__"
                for raw_target in statement.targets
                for target in _assignment_targets(raw_target)
            )
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            assigns_all = (
                isinstance(statement.target, ast.Name)
                and statement.target.id == "__all__"
            )
            value = statement.value
        elif isinstance(statement, (ast.AugAssign, ast.Delete)):
            raw_targets = (
                [statement.target]
                if isinstance(statement, ast.AugAssign)
                else statement.targets
            )
            if any(
                target.id == "__all__"
                for raw_target in raw_targets
                for target in _assignment_targets(raw_target)
            ):
                status = "dynamic"
                names = ()
            elif _has_dynamic_all(statement):
                status = "dynamic"
                names = ()
            continue
        elif (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Attribute)
            and isinstance(statement.value.func.value, ast.Name)
            and statement.value.func.value.id == "__all__"
        ):
            status = "dynamic"
            names = ()
            continue

        if not assigns_all:
            if _has_dynamic_all(statement):
                status = "dynamic"
                names = ()
            continue
        resolved = _literal_all(value) if value is not None else None
        if resolved is None:
            status = "dynamic"
            names = ()
        else:
            status = "resolved"
            names = resolved
    return {"names": sorted(names), "status": status}


def _declarations(tree: ast.Module) -> list[dict[str, Any]]:
    declarations: list[dict[str, Any]] = []
    for statement in tree.body:
        if isinstance(statement, ast.ClassDef):
            if not statement.name.startswith("_"):
                declarations.append(
                    {
                        "kind": "class",
                        "line": statement.lineno,
                        "name": statement.name,
                    },
                )
            continue
        if isinstance(statement, ast.AsyncFunctionDef):
            if not statement.name.startswith("_"):
                declarations.append(
                    {
                        "kind": "async_function",
                        "line": statement.lineno,
                        "name": statement.name,
                    },
                )
            continue
        if isinstance(statement, ast.FunctionDef):
            if not statement.name.startswith("_"):
                declarations.append(
                    {
                        "kind": "function",
                        "line": statement.lineno,
                        "name": statement.name,
                    },
                )
            continue

        raw_targets: list[ast.AST] = []
        if isinstance(statement, ast.Assign):
            raw_targets.extend(statement.targets)
        elif isinstance(statement, ast.AnnAssign):
            raw_targets.append(statement.target)
        for raw_target in raw_targets:
            for target in _assignment_targets(raw_target):
                if _CONSTANT_NAME.fullmatch(target.id):
                    declarations.append(
                        {
                            "kind": "constant",
                            "line": target.lineno,
                            "name": target.id,
                        },
                    )
    return declarations


def capture_public_api(
    root: Path,
    config_path: Path | None = None,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Return public declarations for every active Python module."""
    root = root.resolve()
    check_namespace(root, config_path)
    config = load_architecture_config(root, config_path)
    source_roots = validate_source_roots(root, config)
    validate_active_source_ownership(config, source_roots)
    modules: list[dict[str, Any]] = []
    errors: list[str] = []
    for distribution in sorted(source_roots):
        source_root = source_roots[distribution]
        for path in iter_python_files(source_root):
            tree, error = _parse_python(path)
            if error is not None:
                errors.append(error)
                continue
            assert tree is not None
            modules.append(
                {
                    "all": _all_record(tree),
                    "declarations": _declarations(tree),
                    "module": module_name_for_path(source_root.path, path),
                    "source_distribution": distribution,
                    "source_file": path.relative_to(root).as_posix(),
                },
            )
    modules.sort(key=lambda module: (module["module"], module["source_file"]))
    return {"schema_version": SCHEMA_VERSION, "modules": modules}, tuple(errors)


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
    outputs.add_argument("--json", type=Path, help="write the computed baseline")
    outputs.add_argument("--check", type=Path, help="check an existing baseline")
    return parser


def _serialized(model: dict[str, Any]) -> str:
    return json.dumps(
        model,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _read_baseline(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ArchitectureError(f"baseline file does not exist: {path}") from exc
    except OSError as exc:
        raise ArchitectureError(f"cannot read baseline {path}: {exc}") from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ArchitectureError(f"invalid JSON baseline {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ArchitectureError(f"baseline {path} must contain a JSON object")
    return value


def _write_baseline(path: Path, model: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_serialized(model), encoding="utf-8", newline="\n")
    except OSError as exc:
        raise ArchitectureError(f"cannot write baseline {path}: {exc}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    """Run the static public-API baseline CLI."""
    args = _parser().parse_args(argv)
    try:
        model, errors = capture_public_api(args.root, args.config)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        if args.check is not None:
            existing = _read_baseline(args.check)
            if existing != model:
                print(f"public API baseline drift: {args.check}", file=sys.stderr)
                return 1
            print(f"public API baseline matches: {args.check}")
            return 0
        _write_baseline(args.json, model)
    except ArchitectureError as exc:
        print(f"public API baseline config/ownership error: {exc}", file=sys.stderr)
        return 1

    print(
        f"wrote public API baseline: {args.json} "
        f"({len(model['modules'])} modules)",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
