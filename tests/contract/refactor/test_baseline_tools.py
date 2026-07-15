# -*- coding: utf-8 -*-
"""Contracts for deterministic static refactor compatibility baselines."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

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
) -> dict[str, object]:
    result = _run_tool(tool, repo, "--json", str(output), config=config)
    assert result.returncode == 0, _output(result)
    return json.loads(output.read_text(encoding="utf-8"))


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
    assert [
        (edge["target_module"], edge["line"])
        for edge in edges
    ] == [
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
    assert next(edge for edge in edges if edge["line"] == 6)[
        "function_scope"
    ] is False
    assert next(edge for edge in edges if edge["line"] == 8)[
        "function_scope"
    ] is True
    assert next(edge for edge in edges if edge["line"] == 10)[
        "type_checking"
    ] is True
    assert next(edge for edge in edges if edge["line"] == 12)[
        "type_checking"
    ] is False
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


def test_public_api_marks_dynamic_all_instead_of_guessing(tmp_path: Path) -> None:
    _fixture_repo(tmp_path, active_packages=["minions"])
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        'names = ["Visible"]\n__all__ = names + ["run"]\ndef run():\n    pass\n',
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
        f"{prefix}value = {{}}\nmatch value:\n    case {pattern}:\n        pass\n",
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
            "    __all__ = [\"function-local\"]\n"
            "class Nested:\n"
            "    __all__ = [\"class-local\"]\n"
            f"result = {comprehension}\n"
        ),
    )

    model = _generate(API_TOOL, tmp_path, tmp_path / "api.json")

    assert model["modules"][0]["all"] == {
        "names": ["literal"],
        "status": "resolved",
    }


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
