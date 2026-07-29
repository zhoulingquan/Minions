# -*- coding: utf-8 -*-
"""Contracts for deterministic static refactor compatibility baselines."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
IMPORT_TOOL = REPO_ROOT / "scripts" / "refactor" / "analyze_imports.py"
API_TOOL = REPO_ROOT / "scripts" / "refactor" / "capture_public_api.py"
PackageConfig = dict[str, dict[str, list[str]]]


def _write(path: Path, contents: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    return path


def _write_config(
    repo: Path,
    packages: PackageConfig,
    active_packages: list[str],
    *,
    name: str = "architecture.toml",
) -> Path:
    lines: list[str] = []
    for distribution, package in packages.items():
        lines.extend(
            (
                f"[packages.{distribution}]",
                f"imports = {json.dumps(package['imports'])}",
                f"allows = {json.dumps(package['allows'])}",
                "",
            ),
        )
    lines.extend(
        (
            "[workspace]",
            f"active_packages = {json.dumps(active_packages)}",
            "",
        ),
    )
    return _write(repo / name, "\n".join(lines))


def _source_root(repo: Path, distribution: str) -> Path:
    if distribution == "minions":
        source_root = repo / "src" / "minions"
    else:
        source_root = repo / "packages" / distribution / "src" / "minions"
    source_root.mkdir(parents=True, exist_ok=True)
    return source_root


def _fixture_repo(
    repo: Path,
    *,
    active_packages: list[str] | None = None,
    config_name: str = "architecture.toml",
) -> tuple[PackageConfig, Path]:
    packages: PackageConfig = {
        "minions-core": {
            "imports": ["minions.core"],
            "allows": [],
        },
        "minions-runtime": {
            "imports": ["minions.runtime"],
            "allows": ["minions-core"],
        },
        "minions": {
            "imports": ["minions.app"],
            "allows": ["minions-core", "minions-runtime"],
        },
    }
    active = active_packages or ["minions", "minions-core", "minions-runtime"]
    config = _write_config(repo, packages, active, name=config_name)
    for distribution in active:
        _source_root(repo, distribution)
    return packages, config


def _run_tool(
    tool: Path,
    repo: Path,
    *arguments: str,
    config: Path | str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(tool), "--root", str(repo)]
    if config is not None:
        command.extend(("--config", str(config)))
    command.extend(arguments)
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def _generate(
    tool: Path,
    repo: Path,
    output: Path,
    *,
    config: Path | str | None = None,
) -> dict[str, Any]:
    result = _run_tool(tool, repo, "--json", str(output), config=config)
    assert result.returncode == 0, _output(result)
    return json.loads(output.read_text(encoding="utf-8"))


def _capture_all(tmp_path: Path, source: str) -> dict[str, object]:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(_source_root(tmp_path, "minions") / "app.py", source)
    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")
    modules = model["modules"]
    assert isinstance(modules, list)
    return modules[0]["all"]


def test_import_baseline_records_all_internal_call_sites_and_scope(
    tmp_path: Path,
) -> None:
    _fixture_repo(tmp_path, config_name="fixture-architecture.toml")
    _write(
        _source_root(tmp_path, "minions-core") / "core" / "pkg" / "mod.py",
        (
            "from typing import TYPE_CHECKING\n"
            "import minions.runtime.absolute\n"
            "from minions.runtime import first, second\n"
            "from . import local\n"
            "class Holder:\n"
            "    import minions.runtime.class_local\n"
            "def load():\n"
            "    import minions.runtime.call\n"
            "if TYPE_CHECKING:\n"
            "    from minions.runtime import typed\n"
            "if not TYPE_CHECKING:\n"
            "    import minions.runtime.runtime_only\n"
            "import minions.runtime.call\n"
        ),
    )
    output = tmp_path / "imports.json"

    model = _generate(
        IMPORT_TOOL,
        tmp_path,
        output,
        config="fixture-architecture.toml",
    )

    assert model["schema_version"] == 1
    edges = model["edges"]
    assert isinstance(edges, list)
    assert [(edge["target_module"], edge["line"]) for edge in edges] == [
        ("minions.runtime.absolute", 2),
        ("minions.runtime.first", 3),
        ("minions.runtime.second", 3),
        ("minions.core.pkg.local", 4),
        ("minions.runtime.class_local", 6),
        ("minions.runtime.call", 8),
        ("minions.runtime.typed", 10),
        ("minions.runtime.runtime_only", 12),
        ("minions.runtime.call", 13),
    ]
    assert all(
        edge["source_module"] == "minions.core.pkg.mod" for edge in edges
    )
    assert all(edge["source_distribution"] == "minions-core" for edge in edges)
    assert all(
        edge["source_file"]
        == "packages/minions-core/src/minions/core/pkg/mod.py"
        for edge in edges
    )
    assert all(edge["ownership_error"] is None for edge in edges)
    assert [edge["target_distribution"] for edge in edges] == [
        "minions-runtime",
        "minions-runtime",
        "minions-runtime",
        "minions-core",
        "minions-runtime",
        "minions-runtime",
        "minions-runtime",
        "minions-runtime",
        "minions-runtime",
    ]
    assert (
        next(edge for edge in edges if edge["line"] == 6)["function_scope"]
        is False
    )
    assert (
        next(edge for edge in edges if edge["line"] == 8)["function_scope"]
        is True
    )
    assert (
        next(edge for edge in edges if edge["line"] == 10)["type_checking"]
        is True
    )
    assert (
        next(edge for edge in edges if edge["line"] == 12)["type_checking"]
        is False
    )
    encoded = output.read_text(encoding="utf-8")
    assert str(tmp_path) not in encoded
    assert "timestamp" not in encoded.lower()


def test_import_baseline_falls_back_from_inactive_prefix_to_umbrella(
    tmp_path: Path,
) -> None:
    packages, _config = _fixture_repo(
        tmp_path,
        active_packages=["minions", "minions-runtime"],
    )
    packages["minions-runtime"]["allows"] = ["minions-core"]
    _write_config(tmp_path, packages, ["minions", "minions-runtime"])
    _write(
        _source_root(tmp_path, "minions-runtime") / "runtime" / "lazy.py",
        "import minions.core.api\n",
    )

    model = _generate(IMPORT_TOOL, tmp_path, tmp_path / "imports.json")

    assert model["edges"] == [
        {
            "function_scope": False,
            "line": 1,
            "ownership_error": None,
            "source_distribution": "minions-runtime",
            "source_file": (
                "packages/minions-runtime/src/minions/runtime/lazy.py"
            ),
            "source_module": "minions.runtime.lazy",
            "target_distribution": "minions",
            "target_module": "minions.core.api",
            "type_checking": False,
        },
    ]


def test_import_baseline_fails_on_unowned_import_without_active_umbrella(
    tmp_path: Path,
) -> None:
    packages: PackageConfig = {
        "minions-runtime": {
            "imports": ["minions.runtime"],
            "allows": [],
        },
    }
    _write_config(tmp_path, packages, ["minions-runtime"])
    _write(
        _source_root(tmp_path, "minions-runtime") / "runtime" / "runner.py",
        "import minions.unowned.module\n",
    )
    output = tmp_path / "imports.json"

    result = _run_tool(IMPORT_TOOL, tmp_path, "--json", str(output))

    assert result.returncode != 0
    assert not output.exists()
    rendered = _output(result)
    assert "ownership" in rendered.lower()
    assert "minions.unowned.module" in rendered
    assert "runtime/runner.py" in rendered.replace("\\", "/")
    assert "line 1" in rendered.lower()
    assert "Traceback (most recent call last)" not in rendered


def test_public_api_records_exports_declaration_kinds_and_private_exclusions(
    tmp_path: Path,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        (
            '__all__ = ["Visible"] + ["run"] + ["CONST"]\n'
            "class Visible:\n"
            "    pass\n"
            "class _Private:\n"
            "    pass\n"
            "def run():\n"
            "    pass\n"
            "def _hidden():\n"
            "    pass\n"
            "async def stream():\n"
            "    pass\n"
            "async def _hidden_async():\n"
            "    pass\n"
            "CONST = 1\n"
            "HTTP_2_OK: bool = True\n"
            "_PRIVATE_CONST = 2\n"
            "mixedCase = 3\n"
            "class Outer:\n"
            "    NESTED = 4\n"
            "    def nested(self):\n"
            "        pass\n"
        ),
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["schema_version"] == 1
    assert model["modules"] == [
        {
            "all": {
                "names": ["CONST", "Visible", "run"],
                "status": "resolved",
            },
            "declarations": [
                {"kind": "class", "line": 2, "name": "Visible"},
                {"kind": "function", "line": 6, "name": "run"},
                {"kind": "async_function", "line": 10, "name": "stream"},
                {"kind": "constant", "line": 14, "name": "CONST"},
                {"kind": "constant", "line": 15, "name": "HTTP_2_OK"},
                {"kind": "class", "line": 18, "name": "Outer"},
            ],
            "module": "minions.app",
            "source_distribution": "minions",
            "source_file": "src/minions/app.py",
        },
    ]


def test_public_api_marks_dynamic_all_instead_of_guessing(
    tmp_path: Path,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        (
            'names = ["Visible"]\n'
            '__all__ = names + ["run"]\n'
            "def run():\n"
            "    pass\n"
        ),
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    module = model["modules"][0]
    assert module["all"] == {"names": [], "status": "dynamic"}
    assert module["declarations"] == [
        {"kind": "function", "line": 3, "name": "run"},
    ]


@pytest.mark.parametrize(
    "source",
    (
        'FLAG = True\nif FLAG:\n    __all__ = ["conditional"]\n',
        (
            '__all__ = ["literal"]\n'
            'names = ["mutated"]\n'
            "__all__[:] = names\n"
        ),
    ),
)
def test_public_api_marks_conditional_or_subscript_all_as_dynamic(
    tmp_path: Path,
    source: str,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(_source_root(tmp_path, "minions") / "app.py", source)

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": [],
        "status": "dynamic",
    }


@pytest.mark.parametrize(
    "pattern",
    (
        "__all__",
        "[*__all__]",
        "{**__all__}",
    ),
)
@pytest.mark.parametrize("initial_all", (False, True))
def test_public_api_marks_match_capture_string_bindings_as_dynamic(
    tmp_path: Path,
    pattern: str,
    initial_all: bool,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    prefix = '__all__ = ["literal"]\n' if initial_all else ""
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        (
            f"{prefix}value = {{}}\n"
            "match value:\n"
            f"    case {pattern}:\n"
            "        pass\n"
        ),
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": [],
        "status": "dynamic",
    }


@pytest.mark.parametrize("initial_all", (False, True))
def test_public_api_marks_except_handler_string_binding_as_dynamic(
    tmp_path: Path,
    initial_all: bool,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    prefix = '__all__ = ["literal"]\n' if initial_all else ""
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        (
            f"{prefix}try:\n"
            "    pass\n"
            "except Exception as __all__:\n"
            "    pass\n"
        ),
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": [],
        "status": "dynamic",
    }


@pytest.mark.parametrize(
    "binding",
    (
        "import package as __all__\n",
        "from package import value as __all__\n",
        "def __all__():\n    pass\n",
        "class __all__:\n    pass\n",
    ),
)
def test_public_api_keeps_existing_string_binding_guards(
    tmp_path: Path,
    binding: str,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(_source_root(tmp_path, "minions") / "app.py", binding)

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": [],
        "status": "dynamic",
    }


@pytest.mark.parametrize(
    "comprehension",
    (
        "[item for __all__ in values for item in __all__]",
        "{item for __all__ in values for item in __all__}",
        "{item: item for __all__ in values for item in __all__}",
        "(item for __all__ in values for item in __all__)",
    ),
)
def test_public_api_ignores_nested_and_comprehension_local_bindings(
    tmp_path: Path,
    comprehension: str,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        (
            '__all__ = ["literal"]\n'
            "values = []\n"
            "def nested():\n"
            '    __all__ = ["function-local"]\n'
            "class Nested:\n"
            '    __all__ = ["class-local"]\n'
            f"result = {comprehension}\n"
        ),
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": ["literal"],
        "status": "resolved",
    }


@pytest.mark.parametrize("definition_kind", ("def", "async def"))
@pytest.mark.parametrize(
    "effect_site",
    ("decorator", "default", "kwdefault", "annotation", "return"),
)
def test_public_api_scans_function_definition_time_effects(
    tmp_path: Path,
    definition_kind: str,
    effect_site: str,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    decorator = ""
    signature = "()"
    if effect_site == "decorator":
        decorator = '@__all__.append("effect")\n'
    elif effect_site == "default":
        signature = '(value=__all__.append("effect"))'
    elif effect_site == "kwdefault":
        signature = '(*, value=__all__.append("effect"))'
    elif effect_site == "annotation":
        signature = '(value: __all__.append("effect"))'
    elif effect_site == "return":
        signature = '() -> __all__.append("effect")'
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        (
            '__all__ = ["literal"]\n'
            f"{decorator}{definition_kind} target{signature}:\n"
            "    pass\n"
        ),
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": [],
        "status": "dynamic",
    }


@pytest.mark.parametrize("definition_kind", ("def", "async def"))
def test_public_api_ignores_function_body_effects(
    tmp_path: Path,
    definition_kind: str,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        (
            '__all__ = ["literal"]\n'
            f"{definition_kind} target():\n"
            '    __all__.append("body")\n'
        ),
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": ["literal"],
        "status": "resolved",
    }


def test_public_api_scans_lambda_default_but_not_body(tmp_path: Path) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        (
            '__all__ = ["literal"]\n'
            'callback = lambda value=__all__.append("default"): '
            '__all__.append("body")\n'
        ),
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": [],
        "status": "dynamic",
    }


def test_public_api_ignores_lambda_body_effect(tmp_path: Path) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        (
            '__all__ = ["literal"]\n'
            'callback = lambda: __all__.append("body")\n'
        ),
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": ["literal"],
        "status": "resolved",
    }


@pytest.mark.parametrize(
    "definition",
    (
        '@__all__.append("decorator")\nclass Target:\n    pass\n',
        'class Target(__all__.append("base")):\n    pass\n',
        ('class Target(metaclass=__all__.append("keyword")):\n' "    pass\n"),
    ),
)
def test_public_api_scans_class_definition_time_effects(
    tmp_path: Path,
    definition: str,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        f'__all__ = ["literal"]\n{definition}',
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": [],
        "status": "dynamic",
    }


def test_public_api_scans_class_body_before_local_all_binding(
    tmp_path: Path,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        (
            '__all__ = ["literal"]\n'
            "class Target:\n"
            '    __all__.append("module")\n'
            '    __all__ = ["class-local"]\n'
            '    __all__.append("class-local")\n'
        ),
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": [],
        "status": "dynamic",
    }


@pytest.mark.parametrize(
    "class_body",
    (
        '    __all__ = ["class-local"]\n',
        (
            '    __all__ = ["class-local"]\n'
            '    __all__.append("class-local")\n'
        ),
        '    __all__ = ["class-local"]\n    del __all__\n',
    ),
)
def test_public_api_keeps_class_local_all_effects_local(
    tmp_path: Path,
    class_body: str,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        f'__all__ = ["literal"]\nclass Target:\n{class_body}',
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": ["literal"],
        "status": "resolved",
    }


def test_public_api_honors_global_all_in_class_body(tmp_path: Path) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        (
            '__all__ = ["literal"]\n'
            "class Target:\n"
            "    global __all__\n"
            '    __all__.append("module")\n'
        ),
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": [],
        "status": "dynamic",
    }


def test_public_api_ignores_nested_method_body_effect(tmp_path: Path) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        (
            '__all__ = ["literal"]\n'
            "class Target:\n"
            "    def method(self):\n"
            '        __all__.append("method-body")\n'
        ),
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": ["literal"],
        "status": "resolved",
    }


@pytest.mark.parametrize(
    "comprehension",
    (
        '[__all__.append("body") for item in values]',
        '{__all__.append("body") for item in values}',
        '{item: __all__.append("body") for item in values}',
    ),
)
def test_public_api_uses_module_scope_for_eager_class_comprehension_bodies(
    tmp_path: Path,
    comprehension: str,
) -> None:
    captured = _capture_all(
        tmp_path,
        (
            '__all__ = ["literal"]\n'
            "values = []\n"
            "class Target:\n"
            '    __all__ = ["class-local"]\n'
            f"    result = {comprehension}\n"
        ),
    )

    assert captured == {"names": [], "status": "dynamic"}


@pytest.mark.parametrize("kind", ("list", "set", "dict"))
def test_public_api_evaluates_first_comprehension_iterable_in_class(
    tmp_path: Path,
    kind: str,
) -> None:
    expressions = {
        "list": '[item for item in __all__.append("class-local")]',
        "set": '{item for item in __all__.append("class-local")}',
        "dict": '{item: item for item in __all__.append("class-local")}',
    }
    captured = _capture_all(
        tmp_path,
        (
            '__all__ = ["literal"]\n'
            "class Target:\n"
            '    __all__ = ["class-local"]\n'
            f"    result = {expressions[kind]}\n"
        ),
    )

    assert captured == {"names": ["literal"], "status": "resolved"}


@pytest.mark.parametrize(
    "expression",
    (
        '(__all__.append("body") for item in values)',
        '(item for item in values if __all__.append("if"))',
        '(item for item in values for later in __all__.append("later"))',
    ),
)
def test_public_api_ignores_delayed_generator_expression_parts(
    tmp_path: Path,
    expression: str,
) -> None:
    captured = _capture_all(
        tmp_path,
        '__all__ = ["literal"]\nvalues = []\nresult = ' + expression + "\n",
    )

    assert captured == {"names": ["literal"], "status": "resolved"}


def test_public_api_scans_first_generator_iterable_immediately(
    tmp_path: Path,
) -> None:
    captured = _capture_all(
        tmp_path,
        (
            '__all__ = ["literal"]\n'
            'result = (item for item in __all__.append("first"))\n'
        ),
    )

    assert captured == {"names": [], "status": "dynamic"}


def test_public_api_uses_class_scope_for_first_generator_iterable(
    tmp_path: Path,
) -> None:
    captured = _capture_all(
        tmp_path,
        (
            '__all__ = ["literal"]\n'
            "class Target:\n"
            '    __all__ = ["class-local"]\n'
            '    result = (item for item in __all__.append("first"))\n'
        ),
    )

    assert captured == {"names": ["literal"], "status": "resolved"}


@pytest.mark.parametrize(
    ("condition", "expected"),
    (
        ("True", {"names": [], "status": "dynamic"}),
        ("False", {"names": ["literal"], "status": "resolved"}),
        ("condition", {"names": [], "status": "dynamic"}),
    ),
)
def test_public_api_tracks_conditional_class_local_deletion(
    tmp_path: Path,
    condition: str,
    expected: dict[str, object],
) -> None:
    captured = _capture_all(
        tmp_path,
        (
            '__all__ = ["literal"]\n'
            "condition = object()\n"
            "class Target:\n"
            '    __all__ = ["class-local"]\n'
            f"    if {condition}:\n"
            "        del __all__\n"
            '    __all__.append("after-delete")\n'
        ),
    )

    assert captured == expected


@pytest.mark.parametrize(
    "control_flow",
    (
        "    for item in values:\n        del __all__\n",
        (
            "    match value:\n"
            "        case 0:\n"
            "            del __all__\n"
            "        case _:\n"
            "            pass\n"
        ),
        (
            "    try:\n"
            "        operation()\n"
            "        del __all__\n"
            "    except Exception:\n"
            "        pass\n"
        ),
    ),
)
def test_public_api_conservatively_merges_class_control_flow(
    tmp_path: Path,
    control_flow: str,
) -> None:
    captured = _capture_all(
        tmp_path,
        (
            '__all__ = ["literal"]\n'
            "values = []\n"
            "value = object()\n"
            "class Target:\n"
            '    __all__ = ["class-local"]\n'
            f"{control_flow}"
            '    __all__.append("after-control-flow")\n'
        ),
    )

    assert captured == {"names": [], "status": "dynamic"}


def test_public_api_applies_decorator_walrus_before_function_defaults(
    tmp_path: Path,
) -> None:
    captured = _capture_all(
        tmp_path,
        (
            '__all__ = ["literal"]\n'
            "def decorator(function):\n"
            "    return function\n"
            "class Target:\n"
            "    @(__all__ := decorator)\n"
            '    def method(value=__all__.append("class-local")):\n'
            "        pass\n"
            '    __all__.append("still-class-local")\n'
        ),
    )

    assert captured == {"names": ["literal"], "status": "resolved"}


@pytest.mark.parametrize(
    "definition",
    (
        (
            '    @__all__.append("module-decorator")\n'
            "    def method(value=(__all__ := [])):\n"
            "        pass\n"
        ),
        (
            "    def method("
            'value=__all__.append("module-default")):\n'
            "        pass\n"
        ),
    ),
)
def test_public_api_keeps_real_module_effects_before_class_local_binding(
    tmp_path: Path,
    definition: str,
) -> None:
    captured = _capture_all(
        tmp_path,
        '__all__ = ["literal"]\nclass Target:\n' + definition,
    )

    assert captured == {"names": [], "status": "dynamic"}


def test_public_api_evaluates_annassign_value_before_annotation(
    tmp_path: Path,
) -> None:
    captured = _capture_all(
        tmp_path,
        (
            '__all__ = ["literal"]\n'
            "class Target:\n"
            "    field: "
            '__all__.append("class-local") = (__all__ := [])\n'
        ),
    )

    assert captured == {"names": ["literal"], "status": "resolved"}


@pytest.mark.parametrize(
    "definition",
    (
        'value: __all__.append("module-annotation")\n',
        ("class Target:\n" '    value: __all__.append("class-annotation")\n'),
        (
            "def target("
            'value: __all__.append("parameter-annotation")'
            ') -> __all__.append("return-annotation"):\n'
            "    pass\n"
        ),
    ),
)
def test_public_api_skips_postponed_annotations(
    tmp_path: Path,
    definition: str,
) -> None:
    captured = _capture_all(
        tmp_path,
        (
            "from __future__ import annotations\n"
            '__all__ = ["literal"]\n'
            f"{definition}"
        ),
    )

    assert captured == {"names": ["literal"], "status": "resolved"}


@pytest.mark.parametrize(
    "definition",
    (
        'value: object = __all__.append("module-value")\n',
        ('@__all__.append("decorator")\n' "def target():\n" "    pass\n"),
        ('def target(value=__all__.append("default")):\n' "    pass\n"),
    ),
)
def test_public_api_still_scans_eager_fields_with_postponed_annotations(
    tmp_path: Path,
    definition: str,
) -> None:
    captured = _capture_all(
        tmp_path,
        (
            "from __future__ import annotations\n"
            '__all__ = ["literal"]\n'
            f"{definition}"
        ),
    )

    assert captured == {"names": [], "status": "dynamic"}


@pytest.mark.parametrize(
    "definition",
    (
        'value: __all__.append("module-annotation")\n',
        ("class Target:\n" '    value: __all__.append("class-annotation")\n'),
        (
            "def target("
            'value: __all__.append("parameter-annotation")):\n'
            "    pass\n"
        ),
    ),
)
def test_public_api_scans_eager_annotations_without_future_import(
    tmp_path: Path,
    definition: str,
) -> None:
    captured = _capture_all(
        tmp_path,
        '__all__ = ["literal"]\n' + definition,
    )

    assert captured == {"names": [], "status": "dynamic"}


@pytest.mark.parametrize(
    "definition",
    (
        ('def target[T: __all__.append("bound")]():\n' "    pass\n"),
        (
            "def target["
            'T: (__all__.append("first"), __all__.append("second"))'
            "]():\n"
            "    pass\n"
        ),
        ('class Target[T: __all__.append("bound")]:\n' "    pass\n"),
        'type Alias = __all__.append("alias-value")\n',
    ),
)
def test_public_api_skips_lazy_pep695_expressions(
    tmp_path: Path,
    definition: str,
) -> None:
    captured = _capture_all(
        tmp_path,
        '__all__ = ["literal"]\n' + definition,
    )

    assert captured == {"names": ["literal"], "status": "resolved"}


def test_public_api_conservatively_marks_star_import_all_binding(
    tmp_path: Path,
) -> None:
    captured = _capture_all(
        tmp_path,
        '__all__ = ["literal"]\nfrom exports import *\n',
    )

    assert captured == {"names": [], "status": "dynamic"}


def test_public_api_propagates_nested_class_states_to_try_handlers(
    tmp_path: Path,
) -> None:
    captured = _capture_all(
        tmp_path,
        (
            '__all__ = ["literal"]\n'
            "condition = object()\n"
            "class Target:\n"
            '    __all__ = ["class-local"]\n'
            "    try:\n"
            "        if condition:\n"
            "            del __all__\n"
            "            operation()\n"
            '            __all__ = ["rebound"]\n'
            "    except Exception:\n"
            '        __all__.append("possible-module")\n'
        ),
    )

    assert captured == {"names": [], "status": "dynamic"}


@pytest.mark.parametrize(
    "annotation",
    (
        'holder.value: __all__.append("attribute-annotation")\n',
        'holder[0]: __all__.append("subscript-annotation")\n',
    ),
)
def test_public_api_skips_non_simple_annassign_annotations(
    tmp_path: Path,
    annotation: str,
) -> None:
    captured = _capture_all(
        tmp_path,
        '__all__ = ["literal"]\nholder = object()\n' + annotation,
    )

    assert captured == {"names": ["literal"], "status": "resolved"}


@pytest.mark.parametrize(
    ("expression", "expected_names"),
    (
        ('("TupleExport", "Another")', ["Another", "TupleExport"]),
        ('{"SetExport", "Another"}', ["Another", "SetExport"]),
    ),
)
def test_public_api_resolves_tuple_and_set_all_literals(
    tmp_path: Path,
    expression: str,
    expected_names: list[str],
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        f"__all__ = {expression}\n",
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": expected_names,
        "status": "resolved",
    }


def test_public_api_normalizes_package_init_and_case_variant_python_sources(
    tmp_path: Path,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions-core"])
    source_root = _source_root(tmp_path, "minions-core")
    _write(
        source_root / "core" / "pkg" / "__INIT__.PY",
        "def package_api():\n    pass\n",
    )
    _write(
        source_root / "core" / "Caps.PY",
        "CAPS_VALUE = 1\n",
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert [module["module"] for module in model["modules"]] == [
        "minions.core.Caps",
        "minions.core.pkg",
    ]
    assert [module["source_file"] for module in model["modules"]] == [
        "packages/minions-core/src/minions/core/Caps.PY",
        "packages/minions-core/src/minions/core/pkg/__INIT__.PY",
    ]


@pytest.mark.parametrize("tool", (IMPORT_TOOL, API_TOOL))
def test_baseline_tool_reports_syntax_and_config_errors_without_traceback(
    tmp_path: Path,
    tool: Path,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    source = _write(
        _source_root(tmp_path, "minions") / "app.py",
        "def broken(:\n",
    )

    result = _run_tool(tool, tmp_path, "--json", str(tmp_path / "out.json"))

    rendered = _output(result)
    assert result.returncode != 0
    assert "syntax" in rendered.lower()
    assert str(source) in rendered
    assert "line 1" in rendered.lower()
    assert "Traceback (most recent call last)" not in rendered

    broken_config = _write(tmp_path / "broken.toml", "[packages\n")
    result = _run_tool(
        tool,
        tmp_path,
        "--json",
        str(tmp_path / "other.json"),
        config=broken_config,
    )
    rendered = _output(result)
    assert result.returncode != 0
    assert "config" in rendered.lower()
    assert str(broken_config) in rendered
    assert "Traceback (most recent call last)" not in rendered


@pytest.mark.parametrize("tool", (IMPORT_TOOL, API_TOOL))
def test_baseline_output_is_deterministic_and_check_is_non_mutating(
    tmp_path: Path,
    tool: Path,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    source = _write(
        _source_root(tmp_path, "minions") / "app.py",
        "import minions.app\nVALUE = 1\n",
    )
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    _generate(tool, tmp_path, first)
    _generate(tool, tmp_path, second)

    assert first.read_bytes() == second.read_bytes()
    before = first.read_bytes()
    result = _run_tool(tool, tmp_path, "--check", str(first))
    assert result.returncode == 0, _output(result)
    assert first.read_bytes() == before

    source.write_text(
        "import minions.app\nimport minions.extra\nVALUE = 1\nNEW_VALUE = 2\n",
        encoding="utf-8",
    )
    result = _run_tool(tool, tmp_path, "--check", str(first))

    assert result.returncode != 0
    assert "drift" in _output(result).lower()
    assert first.read_bytes() == before


@pytest.mark.parametrize("tool", (IMPORT_TOOL, API_TOOL))
def test_baseline_json_and_check_options_are_mutually_exclusive(
    tmp_path: Path,
    tool: Path,
) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])

    result = _run_tool(
        tool,
        tmp_path,
        "--json",
        str(tmp_path / "write.json"),
        "--check",
        str(tmp_path / "check.json"),
    )

    assert result.returncode != 0
    assert "not allowed with argument" in _output(result).lower()


def test_importing_baseline_tools_has_no_cli_side_effects() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import scripts.refactor.analyze_imports; "
                "import scripts.refactor.capture_public_api"
            ),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, _output(result)
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("tool", "baseline"),
    (
        (IMPORT_TOOL, REPO_ROOT / "docs" / "refactor" / "import-baseline.json"),
        (API_TOOL, REPO_ROOT / "docs" / "refactor" / "public-api-baseline.json"),
    ),
)
def test_committed_baselines_match_source(tool: Path, baseline: Path) -> None:
    """Committed baselines must stay in sync with the current source tree.

    The baselines are regenerated with ``make update-baselines`` (which calls
    ``analyze_imports.py --json`` / ``capture_public_api.py --json``). A drift
    here means an intentional API/import change was made without refreshing the
    baselines -- run ``make update-baselines``, review the diff, then commit.
    """
    result = _run_tool(tool, REPO_ROOT, "--check", str(baseline))
    assert result.returncode == 0, _output(result)
