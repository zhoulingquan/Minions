# -*- coding: utf-8 -*-
"""Capture deterministic static Python public-API compatibility baselines."""
from __future__ import annotations

import argparse
import ast
from enum import Enum, auto
import json
from pathlib import Path
import re
import sys
import tokenize
from typing import Any, Iterable, Sequence

if __package__:
    # pylint: disable-next=relative-beyond-top-level
    from ._architecture_common import (
        ArchitectureError,
        load_architecture_config,
        module_name_for_path,
        validate_source_roots,
    )

    # pylint: disable-next=relative-beyond-top-level
    from .check_architecture import (
        iter_python_files,
        validate_active_source_ownership,
    )

    # pylint: disable-next=relative-beyond-top-level
    from .check_namespace import check_namespace
else:
    from _architecture_common import (  # type: ignore[no-redef]
        ArchitectureError,
        load_architecture_config,
        module_name_for_path,
        validate_source_roots,
    )

    # pylint: disable-next=no-name-in-module
    from check_architecture import (  # type: ignore[no-redef]
        iter_python_files,
        validate_active_source_ownership,
    )
    from check_namespace import check_namespace  # type: ignore[no-redef]


SCHEMA_VERSION = 1
_CONSTANT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
_NO_LITERAL = object()


class _ExecutionScope(Enum):
    MODULE = auto()
    CLASS = auto()
    FUNCTION = auto()


class _AllState(Enum):
    """Resolution of ``__all__`` while a class body is executing."""

    MODULE = auto()
    CLASS_BOUND = auto()
    GLOBAL = auto()
    UNKNOWN = auto()


def _merge_all_states(*states: _AllState) -> _AllState:
    unique = set(states)
    if len(unique) == 1:
        return states[0]
    if _AllState.UNKNOWN in unique:
        return _AllState.UNKNOWN
    if unique == {_AllState.MODULE, _AllState.CLASS_BOUND}:
        return _AllState.UNKNOWN
    if _AllState.GLOBAL in unique:
        return _AllState.GLOBAL
    return _AllState.UNKNOWN


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


class _ImportTimeAllAnalyzer:
    """Interpret import-time ``__all__`` effects without importing modules."""

    def __init__(self, tree: ast.Module) -> None:
        self.tree = tree
        self.status = "absent"
        self.names: tuple[str, ...] = ()
        self._class_state_observers: list[list[_AllState]] = []
        self.postponed_annotations = any(
            isinstance(statement, ast.ImportFrom)
            and statement.module == "__future__"
            and any(alias.name == "annotations" for alias in statement.names)
            for statement in tree.body
        )

    def record(self) -> dict[str, Any]:
        state = _AllState.GLOBAL
        for statement in self.tree.body:
            state = self._execute_statement(
                statement,
                _ExecutionScope.MODULE,
                state,
                top_level=True,
            )
        return {"names": sorted(self.names), "status": self.status}

    def _mark_dynamic(self) -> None:
        self.status = "dynamic"
        self.names = ()

    def _set_literal(self, names: tuple[str, ...]) -> None:
        self.status = "resolved"
        self.names = names

    @staticmethod
    def _reads_module(scope: _ExecutionScope, state: _AllState) -> bool:
        if scope in (_ExecutionScope.MODULE, _ExecutionScope.FUNCTION):
            return True
        return state in (
            _AllState.MODULE,
            _AllState.GLOBAL,
            _AllState.UNKNOWN,
        )

    def _observe_class_states(
        self,
        scope: _ExecutionScope,
        *states: _AllState,
    ) -> None:
        if scope is not _ExecutionScope.CLASS:
            return
        for observer in self._class_state_observers:
            observer.extend(states)

    def _bind_name(
        self,
        name: str | None,
        scope: _ExecutionScope,
        state: _AllState,
        *,
        module_literal: object = _NO_LITERAL,
    ) -> _AllState:
        if name != "__all__":
            return state
        if scope is _ExecutionScope.MODULE:
            if module_literal is _NO_LITERAL:
                self._mark_dynamic()
            else:
                assert isinstance(module_literal, tuple)
                self._set_literal(module_literal)
            return state
        if scope is _ExecutionScope.FUNCTION:
            return state
        if state is _AllState.GLOBAL:
            self._mark_dynamic()
            self._observe_class_states(scope, state)
            return state
        bound = _AllState.CLASS_BOUND
        self._observe_class_states(scope, state, bound)
        return bound

    def _bind_target(
        self,
        target: ast.AST,
        scope: _ExecutionScope,
        state: _AllState,
        *,
        module_literal: object = _NO_LITERAL,
    ) -> _AllState:
        if isinstance(target, ast.Name):
            return self._bind_name(
                target.id,
                scope,
                state,
                module_literal=module_literal,
            )
        if isinstance(target, ast.Starred):
            return self._bind_target(target.value, scope, state)
        if isinstance(target, (ast.List, ast.Tuple)):
            for element in target.elts:
                state = self._bind_target(element, scope, state)
            return state
        if isinstance(target, ast.Attribute):
            hits_module = (
                isinstance(target.value, ast.Name)
                and target.value.id == "__all__"
                and self._reads_module(scope, state)
            )
            state = self._scan_expression(target.value, scope, state)
            if hits_module:
                self._mark_dynamic()
            return state
        if isinstance(target, ast.Subscript):
            hits_module = (
                isinstance(target.value, ast.Name)
                and target.value.id == "__all__"
                and self._reads_module(scope, state)
            )
            state = self._scan_expression(target.value, scope, state)
            state = self._scan_expression(target.slice, scope, state)
            if hits_module:
                self._mark_dynamic()
        return state

    def _delete_target(
        self,
        target: ast.AST,
        scope: _ExecutionScope,
        state: _AllState,
    ) -> _AllState:
        if not isinstance(target, ast.Name):
            return self._bind_target(target, scope, state)
        if target.id != "__all__":
            return state
        if scope is _ExecutionScope.MODULE or state is _AllState.GLOBAL:
            self._mark_dynamic()
            return state
        if scope is _ExecutionScope.FUNCTION:
            return state
        unbound = _AllState.MODULE
        self._observe_class_states(scope, state, unbound)
        return unbound

    def _execute_statements(
        self,
        statements: list[ast.stmt],
        scope: _ExecutionScope,
        state: _AllState,
    ) -> _AllState:
        for statement in statements:
            state = self._execute_statement(statement, scope, state)
        return state

    def _execute_statement(
        self,
        statement: ast.stmt,
        scope: _ExecutionScope,
        state: _AllState,
        *,
        top_level: bool = False,
    ) -> _AllState:
        if isinstance(statement, ast.Expr):
            return self._scan_expression(statement.value, scope, state)
        if isinstance(statement, ast.Assign):
            state = self._scan_expression(statement.value, scope, state)
            literal = _literal_all(statement.value)
            for target in statement.targets:
                module_literal: object = _NO_LITERAL
                if (
                    top_level
                    and scope is _ExecutionScope.MODULE
                    and isinstance(target, ast.Name)
                    and target.id == "__all__"
                    and literal is not None
                ):
                    module_literal = literal
                state = self._bind_target(
                    target,
                    scope,
                    state,
                    module_literal=module_literal,
                )
            return state
        if isinstance(statement, ast.AnnAssign):
            if statement.value is not None:
                state = self._scan_expression(statement.value, scope, state)
                literal = _literal_all(statement.value)
                module_literal = (
                    literal
                    if top_level
                    and scope is _ExecutionScope.MODULE
                    and isinstance(statement.target, ast.Name)
                    and statement.target.id == "__all__"
                    and literal is not None
                    else _NO_LITERAL
                )
                state = self._bind_target(
                    statement.target,
                    scope,
                    state,
                    module_literal=module_literal,
                )
            if statement.simple and not self.postponed_annotations:
                state = self._scan_expression(
                    statement.annotation,
                    scope,
                    state,
                )
            return state
        if isinstance(statement, ast.AugAssign):
            hits_module = (
                isinstance(statement.target, ast.Name)
                and statement.target.id == "__all__"
                and self._reads_module(scope, state)
            )
            state = self._scan_expression(statement.target, scope, state)
            state = self._scan_expression(statement.value, scope, state)
            if hits_module:
                self._mark_dynamic()
            return self._bind_target(statement.target, scope, state)
        if isinstance(statement, ast.Delete):
            for target in statement.targets:
                state = self._delete_target(target, scope, state)
            return state
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return self._execute_function_definition(statement, scope, state)
        if isinstance(statement, ast.ClassDef):
            return self._execute_class_definition(statement, scope, state)
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                state = self._bind_name(
                    alias.asname or alias.name.partition(".")[0],
                    scope,
                    state,
                )
            return state
        if isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                if alias.name == "*" and scope is _ExecutionScope.MODULE:
                    self._mark_dynamic()
                    continue
                state = self._bind_name(
                    alias.asname or alias.name,
                    scope,
                    state,
                )
            return state
        type_alias = getattr(ast, "TypeAlias", ())
        if type_alias and isinstance(statement, type_alias):
            return self._bind_target(statement.name, scope, state)
        if isinstance(statement, ast.If):
            return self._execute_if(statement, scope, state)
        if isinstance(statement, (ast.For, ast.AsyncFor)):
            return self._execute_for(statement, scope, state)
        if isinstance(statement, ast.While):
            return self._execute_while(statement, scope, state)
        if isinstance(statement, ast.Try) or (
            hasattr(ast, "TryStar") and isinstance(statement, ast.TryStar)
        ):
            return self._execute_try(statement, scope, state)
        if isinstance(statement, ast.Match):
            return self._execute_match(statement, scope, state)
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            return self._execute_with(statement, scope, state)
        if isinstance(statement, (ast.Pass, ast.Global, ast.Nonlocal)):
            return state
        return self._scan_node_children(statement, scope, state)

    @staticmethod
    def _constant_truth(node: ast.AST) -> bool | None:
        if isinstance(node, ast.Constant):
            return bool(node.value)
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)) and not node.elts:
            return False
        if isinstance(node, ast.Dict) and not node.keys:
            return False
        return None

    def _execute_if(
        self,
        node: ast.If,
        scope: _ExecutionScope,
        state: _AllState,
    ) -> _AllState:
        state = self._scan_expression(node.test, scope, state)
        truth = self._constant_truth(node.test)
        if truth is True:
            return self._execute_statements(node.body, scope, state)
        if truth is False:
            return self._execute_statements(node.orelse, scope, state)
        body_state = self._execute_statements(node.body, scope, state)
        else_state = self._execute_statements(node.orelse, scope, state)
        return _merge_all_states(body_state, else_state)

    def _execute_for(
        self,
        node: ast.For | ast.AsyncFor,
        scope: _ExecutionScope,
        state: _AllState,
    ) -> _AllState:
        state = self._scan_expression(node.iter, scope, state)
        iteration_state = self._bind_target(node.target, scope, state)
        iteration_state = self._execute_statements(
            node.body,
            scope,
            iteration_state,
        )
        exit_state = _merge_all_states(state, iteration_state)
        orelse_state = self._execute_statements(node.orelse, scope, exit_state)
        return _merge_all_states(exit_state, orelse_state)

    def _execute_while(
        self,
        node: ast.While,
        scope: _ExecutionScope,
        state: _AllState,
    ) -> _AllState:
        state = self._scan_expression(node.test, scope, state)
        truth = self._constant_truth(node.test)
        if truth is False:
            return self._execute_statements(node.orelse, scope, state)
        body_state = self._execute_statements(node.body, scope, state)
        exit_state = _merge_all_states(state, body_state)
        orelse_state = self._execute_statements(node.orelse, scope, exit_state)
        return _merge_all_states(exit_state, orelse_state)

    def _execute_try(
        self,
        node: ast.Try | ast.TryStar,
        scope: _ExecutionScope,
        state: _AllState,
    ) -> _AllState:
        checkpoints = [state]
        body_state = state
        observed_states: list[_AllState] = []
        self._class_state_observers.append(observed_states)
        try:
            for statement in node.body:
                body_state = self._execute_statement(
                    statement,
                    scope,
                    body_state,
                )
                checkpoints.append(body_state)
        finally:
            self._class_state_observers.pop()
        normal_state = self._execute_statements(node.orelse, scope, body_state)
        outgoing = [normal_state]
        exception_state = _merge_all_states(*checkpoints, *observed_states)
        for handler in node.handlers:
            handler_state = exception_state
            if handler.type is not None:
                handler_state = self._scan_expression(
                    handler.type,
                    scope,
                    handler_state,
                )
            handler_state = self._bind_name(handler.name, scope, handler_state)
            handler_state = self._execute_statements(
                handler.body,
                scope,
                handler_state,
            )
            if handler.name == "__all__":
                handler_state = self._delete_target(
                    ast.Name(id="__all__", ctx=ast.Del()),
                    scope,
                    handler_state,
                )
            outgoing.append(handler_state)
        merged = _merge_all_states(*outgoing)
        return self._execute_statements(node.finalbody, scope, merged)

    def _execute_match(
        self,
        node: ast.Match,
        scope: _ExecutionScope,
        state: _AllState,
    ) -> _AllState:
        state = self._scan_expression(node.subject, scope, state)
        outgoing = [state]
        for case in node.cases:
            case_state = self._scan_pattern(case.pattern, scope, state)
            if case.guard is not None:
                case_state = self._scan_expression(
                    case.guard,
                    scope,
                    case_state,
                )
            outgoing.append(
                self._execute_statements(case.body, scope, case_state),
            )
        return _merge_all_states(*outgoing)

    def _scan_pattern(
        self,
        pattern: ast.pattern,
        scope: _ExecutionScope,
        state: _AllState,
    ) -> _AllState:
        if isinstance(pattern, ast.MatchValue):
            return self._scan_expression(pattern.value, scope, state)
        if isinstance(pattern, ast.MatchSingleton):
            return state
        if isinstance(pattern, ast.MatchSequence):
            for child in pattern.patterns:
                state = self._scan_pattern(child, scope, state)
            return state
        if isinstance(pattern, ast.MatchMapping):
            for key in pattern.keys:
                state = self._scan_expression(key, scope, state)
            for child in pattern.patterns:
                state = self._scan_pattern(child, scope, state)
            return self._bind_name(pattern.rest, scope, state)
        if isinstance(pattern, ast.MatchClass):
            state = self._scan_expression(pattern.cls, scope, state)
            for child in (*pattern.patterns, *pattern.kwd_patterns):
                state = self._scan_pattern(child, scope, state)
            return state
        if isinstance(pattern, ast.MatchStar):
            return self._bind_name(pattern.name, scope, state)
        if isinstance(pattern, ast.MatchAs):
            if pattern.pattern is not None:
                state = self._scan_pattern(pattern.pattern, scope, state)
            return self._bind_name(pattern.name, scope, state)
        if isinstance(pattern, ast.MatchOr):
            return _merge_all_states(
                *(
                    self._scan_pattern(child, scope, state)
                    for child in pattern.patterns
                ),
            )
        return state

    def _execute_with(
        self,
        node: ast.With | ast.AsyncWith,
        scope: _ExecutionScope,
        state: _AllState,
    ) -> _AllState:
        for item in node.items:
            state = self._scan_expression(item.context_expr, scope, state)
            if item.optional_vars is not None:
                state = self._bind_target(item.optional_vars, scope, state)
        return self._execute_statements(node.body, scope, state)

    def _execute_function_definition(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        scope: _ExecutionScope,
        state: _AllState,
    ) -> _AllState:
        for decorator in node.decorator_list:
            state = self._scan_expression(decorator, scope, state)
        state = self._scan_argument_defaults(node.args, scope, state)
        if not self.postponed_annotations:
            state = self._scan_argument_annotations(node.args, scope, state)
            if node.returns is not None:
                state = self._scan_expression(node.returns, scope, state)
        return self._bind_name(node.name, scope, state)

    def _execute_class_definition(
        self,
        node: ast.ClassDef,
        scope: _ExecutionScope,
        state: _AllState,
    ) -> _AllState:
        for decorator in node.decorator_list:
            state = self._scan_expression(decorator, scope, state)
        for base in node.bases:
            state = self._scan_expression(base, scope, state)
        for keyword in node.keywords:
            state = self._scan_expression(keyword.value, scope, state)
        finder = _ClassGlobalAllFinder()
        for statement in node.body:
            finder.visit(statement)
        class_state = _AllState.GLOBAL if finder.found else _AllState.MODULE
        outer_observers = self._class_state_observers
        self._class_state_observers = []
        try:
            self._execute_statements(
                node.body,
                _ExecutionScope.CLASS,
                class_state,
            )
        finally:
            self._class_state_observers = outer_observers
        return self._bind_name(node.name, scope, state)

    def _scan_argument_defaults(
        self,
        arguments: ast.arguments,
        scope: _ExecutionScope,
        state: _AllState,
    ) -> _AllState:
        for default in arguments.defaults:
            state = self._scan_expression(default, scope, state)
        for default in arguments.kw_defaults:
            if default is not None:
                state = self._scan_expression(default, scope, state)
        return state

    def _scan_argument_annotations(
        self,
        arguments: ast.arguments,
        scope: _ExecutionScope,
        state: _AllState,
    ) -> _AllState:
        annotated = [*arguments.posonlyargs, *arguments.args]
        if arguments.vararg is not None:
            annotated.append(arguments.vararg)
        annotated.extend(arguments.kwonlyargs)
        if arguments.kwarg is not None:
            annotated.append(arguments.kwarg)
        for argument in annotated:
            if argument.annotation is not None:
                state = self._scan_expression(
                    argument.annotation,
                    scope,
                    state,
                )
        return state

    def _scan_expression(
        self,
        node: ast.AST,
        scope: _ExecutionScope,
        state: _AllState,
        *,
        named_scope: _ExecutionScope | None = None,
    ) -> _AllState:
        if isinstance(node, (ast.Constant, ast.Name)):
            return state
        if isinstance(node, ast.NamedExpr):
            state = self._scan_expression(
                node.value,
                scope,
                state,
                named_scope=named_scope,
            )
            return self._bind_target(
                node.target,
                named_scope or scope,
                state,
            )
        if isinstance(node, ast.Call):
            hits_module = (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "__all__"
                and self._reads_module(scope, state)
            )
            state = self._scan_expression(
                node.func,
                scope,
                state,
                named_scope=named_scope,
            )
            for argument in node.args:
                state = self._scan_expression(
                    argument,
                    scope,
                    state,
                    named_scope=named_scope,
                )
            for keyword in node.keywords:
                state = self._scan_expression(
                    keyword.value,
                    scope,
                    state,
                    named_scope=named_scope,
                )
            if hits_module:
                self._mark_dynamic()
            return state
        if isinstance(node, ast.BoolOp):
            return self._scan_bool_operation(
                node,
                scope,
                state,
                named_scope=named_scope,
            )
        if isinstance(node, ast.IfExp):
            state = self._scan_expression(
                node.test,
                scope,
                state,
                named_scope=named_scope,
            )
            truth = self._constant_truth(node.test)
            if truth is True:
                return self._scan_expression(
                    node.body,
                    scope,
                    state,
                    named_scope=named_scope,
                )
            if truth is False:
                return self._scan_expression(
                    node.orelse,
                    scope,
                    state,
                    named_scope=named_scope,
                )
            return _merge_all_states(
                self._scan_expression(
                    node.body,
                    scope,
                    state,
                    named_scope=named_scope,
                ),
                self._scan_expression(
                    node.orelse,
                    scope,
                    state,
                    named_scope=named_scope,
                ),
            )
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if key is not None:
                    state = self._scan_expression(
                        key,
                        scope,
                        state,
                        named_scope=named_scope,
                    )
                state = self._scan_expression(
                    value,
                    scope,
                    state,
                    named_scope=named_scope,
                )
            return state
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            for element in node.elts:
                state = self._scan_expression(
                    element,
                    scope,
                    state,
                    named_scope=named_scope,
                )
            return state
        if isinstance(node, ast.GeneratorExp):
            return self._scan_expression(
                node.generators[0].iter,
                scope,
                state,
                named_scope=named_scope,
            )
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
            return self._scan_eager_comprehension(
                node,
                scope,
                state,
                named_scope=named_scope,
            )
        if isinstance(node, ast.Lambda):
            return self._scan_argument_defaults(node.args, scope, state)
        return self._scan_node_children(
            node,
            scope,
            state,
            named_scope=named_scope,
        )

    def _scan_bool_operation(
        self,
        node: ast.BoolOp,
        scope: _ExecutionScope,
        state: _AllState,
        *,
        named_scope: _ExecutionScope | None,
    ) -> _AllState:
        state = self._scan_expression(
            node.values[0],
            scope,
            state,
            named_scope=named_scope,
        )
        previous = node.values[0]
        for value in node.values[1:]:
            truth = self._constant_truth(previous)
            executes = (
                truth is True
                if isinstance(node.op, ast.And)
                else truth is False
            )
            skips = (
                truth is False
                if isinstance(node.op, ast.And)
                else truth is True
            )
            if skips:
                return state
            next_state = self._scan_expression(
                value,
                scope,
                state,
                named_scope=named_scope,
            )
            state = (
                next_state
                if executes
                else _merge_all_states(state, next_state)
            )
            previous = value
        return state

    def _scan_eager_comprehension(
        self,
        node: ast.ListComp | ast.SetComp | ast.DictComp,
        scope: _ExecutionScope,
        state: _AllState,
        *,
        named_scope: _ExecutionScope | None,
    ) -> _AllState:
        state = self._scan_expression(
            node.generators[0].iter,
            scope,
            state,
            named_scope=named_scope,
        )
        hidden_state = state
        binding_scope = named_scope or scope
        for index, generator in enumerate(node.generators):
            if index:
                hidden_state = self._scan_expression(
                    generator.iter,
                    _ExecutionScope.FUNCTION,
                    hidden_state,
                    named_scope=binding_scope,
                )
            for condition in generator.ifs:
                hidden_state = self._scan_expression(
                    condition,
                    _ExecutionScope.FUNCTION,
                    hidden_state,
                    named_scope=binding_scope,
                )
        if isinstance(node, ast.DictComp):
            hidden_state = self._scan_expression(
                node.key,
                _ExecutionScope.FUNCTION,
                hidden_state,
                named_scope=binding_scope,
            )
            hidden_state = self._scan_expression(
                node.value,
                _ExecutionScope.FUNCTION,
                hidden_state,
                named_scope=binding_scope,
            )
        else:
            hidden_state = self._scan_expression(
                node.elt,
                _ExecutionScope.FUNCTION,
                hidden_state,
                named_scope=binding_scope,
            )
        return _merge_all_states(state, hidden_state)

    def _scan_node_children(
        self,
        node: ast.AST,
        scope: _ExecutionScope,
        state: _AllState,
        *,
        named_scope: _ExecutionScope | None = None,
    ) -> _AllState:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                state = self._scan_expression(
                    child,
                    scope,
                    state,
                    named_scope=named_scope,
                )
            elif isinstance(child, ast.stmt):
                state = self._execute_statement(child, scope, state)
        return state


def _all_record(tree: ast.Module) -> dict[str, Any]:
    return _ImportTimeAllAnalyzer(tree).record()


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
    return {"schema_version": SCHEMA_VERSION, "modules": modules}, tuple(
        errors,
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
                print(
                    f"public API baseline drift: {args.check}",
                    file=sys.stderr,
                )
                return 1
            print(f"public API baseline matches: {args.check}")
            return 0
        _write_baseline(args.json, model)
    except ArchitectureError as exc:
        print(
            f"public API baseline config/ownership error: {exc}",
            file=sys.stderr,
        )
        return 1

    print(
        f"wrote public API baseline: {args.json} "
        f"({len(model['modules'])} modules)",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
