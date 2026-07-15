# -*- coding: utf-8 -*-
"""Contracts for namespace ownership and distribution architecture gates."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
NAMESPACE_CHECKER = REPO_ROOT / "scripts" / "refactor" / "check_namespace.py"
ARCHITECTURE_CHECKER = (
    REPO_ROOT / "scripts" / "refactor" / "check_architecture.py"
)
PackageConfig = dict[str, dict[str, list[str]]]

EXPECTED_PACKAGES: PackageConfig = {
    "minions-core": {
        "imports": ["minions.core"],
        "allows": [],
    },
    "minions-tool-calls": {
        "imports": ["minions.tool_calls"],
        "allows": [],
    },
    "minions-runtime": {
        "imports": ["minions.runtime"],
        "allows": ["minions-core", "minions-tool-calls"],
    },
    "minions-providers": {
        "imports": ["minions.providers", "minions.local_models"],
        "allows": ["minions-core"],
    },
    "minions-drivers": {
        "imports": ["minions.drivers"],
        "allows": ["minions-core"],
    },
    "minions-channels": {
        "imports": ["minions.channels"],
        "allows": ["minions-core"],
    },
    "minions-plugins": {
        "imports": ["minions.plugins"],
        "allows": ["minions-core", "minions-runtime"],
    },
    "minions-governance": {
        "imports": [
            "minions.governance",
            "minions.security",
            "minions.sandbox",
        ],
        "allows": ["minions-core"],
    },
    "minions-loop": {
        "imports": ["minions.loop"],
        "allows": ["minions-core"],
    },
    "minions-agents": {
        "imports": ["minions.agents"],
        "allows": [
            "minions-core",
            "minions-runtime",
            "minions-providers",
            "minions-tool-calls",
            "minions-drivers",
            "minions-plugins",
            "minions-governance",
        ],
    },
    "minions-modes": {
        "imports": ["minions.modes"],
        "allows": [
            "minions-core",
            "minions-runtime",
            "minions-loop",
            "minions-governance",
        ],
    },
    "minions": {
        "imports": [
            "minions.__main__",
            "minions.__version__",
            "minions._version_compat",
            "minions.api_action",
            "minions.bootstrap",
            "minions._compat",
            "minions.app",
            "minions.cli",
            "minions.hooks",
            "minions.backup",
            "minions.market",
            "minions.agent_stats",
            "minions.tenancy",
            "minions.services",
            "minions.tunnel",
            "minions.sage",
            "minions.tokenizer",
            "minions.utils",
            "minions.constant",
            "minions.exceptions",
            "minions.schemas",
            "minions.config",
            "minions.envs",
            "minions.token_usage",
            "minions.observability",
        ],
        "allows": [
            "minions-core",
            "minions-runtime",
            "minions-providers",
            "minions-tool-calls",
            "minions-drivers",
            "minions-channels",
            "minions-plugins",
            "minions-governance",
            "minions-loop",
            "minions-agents",
            "minions-modes",
        ],
    },
}


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


def _base_fixture(
    repo: Path,
    *,
    active_packages: list[str] | None = None,
) -> PackageConfig:
    packages: PackageConfig = {
        "minions-core": {
            "imports": ["minions.core"],
            "allows": [],
        },
        "minions-runtime": {
            "imports": ["minions.runtime"],
            "allows": ["minions-core"],
        },
        "minions-providers": {
            "imports": ["minions.providers"],
            "allows": [],
        },
        "minions": {
            "imports": ["minions.app"],
            "allows": [
                "minions-core",
                "minions-runtime",
                "minions-providers",
            ],
        },
    }
    active = active_packages or ["minions", "minions-core", "minions-runtime"]
    _write_config(repo, packages, active)
    for distribution in active:
        _source_root(repo, distribution)
    return packages


def _run_checker(
    checker: Path,
    repo: Path,
    *,
    config: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(checker), "--root", str(repo)]
    if config is not None:
        command.extend(("--config", str(config)))
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def _assert_success(
    result: subprocess.CompletedProcess[str],
    phrase: str,
) -> None:
    assert result.returncode == 0, _output(result)
    assert phrase in _output(result)


def _assert_failure(
    result: subprocess.CompletedProcess[str],
    *details: str,
) -> None:
    output = _output(result)
    assert result.returncode != 0, output
    for detail in details:
        assert detail.lower() in output.lower(), output


def test_repository_configuration_is_the_fixed_twelve_distribution_model() -> (
    None
):
    with (REPO_ROOT / "architecture.toml").open("rb") as stream:
        actual = tomllib.load(stream)

    assert actual == {
        "packages": EXPECTED_PACKAGES,
        "workspace": {"active_packages": ["minions"]},
    }


@pytest.mark.parametrize(
    ("checker", "phrase"),
    (
        (NAMESPACE_CHECKER, "namespace ownership valid"),
        (ARCHITECTURE_CHECKER, "0 forbidden edges, 0 distribution cycles"),
    ),
)
def test_current_repository_passes_checker_cli(
    checker: Path,
    phrase: str,
) -> None:
    _assert_success(_run_checker(checker, REPO_ROOT), phrase)


def test_importing_checkers_has_no_cli_side_effects() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import scripts.refactor.check_namespace; "
                "import scripts.refactor.check_architecture"
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


@pytest.mark.parametrize("distribution", ("minions", "minions-experimental"))
def test_namespace_checker_rejects_init_in_every_discovered_source_root(
    tmp_path: Path,
    distribution: str,
) -> None:
    packages: PackageConfig = {
        "minions": {"imports": ["minions.app"], "allows": []},
        "minions-experimental": {
            "imports": ["minions.experimental"],
            "allows": [],
        },
    }
    _write_config(tmp_path, packages, ["minions", "minions-experimental"])
    _source_root(tmp_path, "minions")
    source_root = _source_root(tmp_path, "minions-experimental")
    if distribution == "minions":
        source_root = _source_root(tmp_path, "minions")
    init = _write(source_root / "__init__.py")

    result = _run_checker(NAMESPACE_CHECKER, tmp_path)

    _assert_failure(result, "__init__.py", distribution, str(init))


@pytest.mark.parametrize("distribution", ("minions", "minions-core"))
def test_namespace_checker_rejects_case_variant_top_level_init(
    tmp_path: Path,
    distribution: str,
) -> None:
    _base_fixture(tmp_path)
    init = _write(_source_root(tmp_path, distribution) / "__INIT__.PY")

    result = _run_checker(NAMESPACE_CHECKER, tmp_path)

    _assert_failure(result, "__INIT__.PY", distribution, str(init))
    assert str(init) in _output(result)


def test_namespace_checker_rejects_duplicate_module_or_resource_ownership(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    first = _write(
        _source_root(tmp_path, "minions") / "collision.json", "root"
    )
    second = _write(
        _source_root(tmp_path, "minions-core") / "collision.json",
        "member",
    )

    result = _run_checker(NAMESPACE_CHECKER, tmp_path)

    _assert_failure(
        result, "collision.json", str(first), str(second), "duplicate"
    )


def test_namespace_checker_preserves_distinct_unicode_resource_paths(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    _write(_source_root(tmp_path, "minions") / "straße.json")
    _write(_source_root(tmp_path, "minions-core") / "strasse.json")

    result = _run_checker(NAMESPACE_CHECKER, tmp_path)

    _assert_success(result, "namespace ownership valid")


def test_namespace_checker_preserves_distinct_unicode_module_paths(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    _write(_source_root(tmp_path, "minions") / "straße.py")
    _write(_source_root(tmp_path, "minions-core") / "strasse.py")

    result = _run_checker(NAMESPACE_CHECKER, tmp_path)

    _assert_success(result, "namespace ownership valid")


def test_namespace_checker_normalizes_module_identity_across_source_roots(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    module_file = _write(_source_root(tmp_path, "minions") / "foo.py")
    package_init = _write(
        _source_root(tmp_path, "minions-core") / "foo" / "__init__.py"
    )

    result = _run_checker(NAMESPACE_CHECKER, tmp_path)

    _assert_failure(
        result,
        "duplicate module ownership",
        "minions.foo",
        str(module_file),
        str(package_init),
    )


def test_namespace_checker_treats_uppercase_py_as_python_module(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    module_file = _write(_source_root(tmp_path, "minions") / "Foo.PY")
    package_init = _write(
        _source_root(tmp_path, "minions-core") / "foo" / "__init__.py"
    )

    result = _run_checker(NAMESPACE_CHECKER, tmp_path)

    _assert_failure(
        result,
        "duplicate module ownership",
        "minions.foo",
        str(module_file),
        str(package_init),
    )


def test_namespace_checker_normalizes_case_variant_init_identity(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    module_file = _write(_source_root(tmp_path, "minions") / "pkg.py")
    package_init = _write(
        _source_root(tmp_path, "minions-core") / "pkg" / "__INIT__.PY"
    )

    result = _run_checker(NAMESPACE_CHECKER, tmp_path)

    _assert_failure(
        result,
        "duplicate module ownership",
        "minions.pkg",
        str(module_file),
        str(package_init),
    )


def test_namespace_checker_rejects_source_root_for_inactive_package(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    inactive_root = _source_root(tmp_path, "minions-providers")

    result = _run_checker(NAMESPACE_CHECKER, tmp_path)

    _assert_failure(
        result, "minions-providers", str(inactive_root), "inactive"
    )


def test_namespace_checker_rejects_missing_source_root_for_active_package(
    tmp_path: Path,
) -> None:
    packages = _base_fixture(tmp_path)
    packages["minions-providers"]["allows"] = ["minions-core"]
    config = _write_config(
        tmp_path,
        packages,
        ["minions", "minions-core", "minions-runtime", "minions-providers"],
        name="custom-architecture.toml",
    )

    result = _run_checker(NAMESPACE_CHECKER, tmp_path, config=config)

    _assert_failure(result, "minions-providers", "missing", "src")


def test_namespace_checker_rejects_unknown_active_package(
    tmp_path: Path,
) -> None:
    packages = _base_fixture(tmp_path)
    config = _write_config(
        tmp_path,
        packages,
        ["minions", "not-configured"],
        name="unknown-active.toml",
    )

    result = _run_checker(NAMESPACE_CHECKER, tmp_path, config=config)

    _assert_failure(result, "not-configured", "active", "unknown")


def test_checkers_reject_duplicate_import_prefix_ownership(
    tmp_path: Path,
) -> None:
    packages = _base_fixture(tmp_path)
    packages["minions-runtime"]["imports"] = ["minions.core"]
    config = _write_config(
        tmp_path,
        packages,
        ["minions", "minions-core", "minions-runtime"],
        name="duplicate-prefix.toml",
    )

    for checker in (NAMESPACE_CHECKER, ARCHITECTURE_CHECKER):
        result = _run_checker(checker, tmp_path, config=config)
        _assert_failure(
            result,
            "minions.core",
            "minions-core",
            "minions-runtime",
            "duplicate",
        )


def test_checkers_reject_case_equivalent_import_prefix_ownership(
    tmp_path: Path,
) -> None:
    packages = _base_fixture(tmp_path)
    packages["minions-runtime"]["imports"] = ["minions.Core"]
    config = _write_config(
        tmp_path,
        packages,
        ["minions", "minions-core", "minions-runtime"],
        name="case-equivalent-prefix.toml",
    )

    for checker in (NAMESPACE_CHECKER, ARCHITECTURE_CHECKER):
        result = _run_checker(checker, tmp_path, config=config)
        _assert_failure(
            result,
            "duplicate",
            "minions.core",
            "minions-core",
            "minions.Core",
            "minions-runtime",
        )


def test_checkers_reject_same_owner_case_equivalent_import_prefixes(
    tmp_path: Path,
) -> None:
    packages = _base_fixture(tmp_path)
    packages["minions-core"]["imports"] = ["minions.core", "minions.Core"]
    config = _write_config(
        tmp_path,
        packages,
        ["minions", "minions-core", "minions-runtime"],
        name="same-owner-case-equivalent-prefix.toml",
    )

    for checker in (NAMESPACE_CHECKER, ARCHITECTURE_CHECKER):
        result = _run_checker(checker, tmp_path, config=config)
        _assert_failure(
            result,
            "duplicate",
            "minions.core",
            "minions.Core",
            "minions-core",
        )


def test_checkers_reject_overlapping_import_prefix_ownership(
    tmp_path: Path,
) -> None:
    packages = _base_fixture(tmp_path)
    packages["minions-providers"]["imports"] = ["minions.core.detail"]
    config = _write_config(
        tmp_path,
        packages,
        ["minions", "minions-core", "minions-runtime"],
        name="overlapping-prefix.toml",
    )

    for checker in (NAMESPACE_CHECKER, ARCHITECTURE_CHECKER):
        result = _run_checker(checker, tmp_path, config=config)
        _assert_failure(
            result,
            "overlapping",
            "minions.core",
            "minions-core",
            "minions.core.detail",
            "minions-providers",
        )


def test_checkers_reject_case_equivalent_boundary_overlap(
    tmp_path: Path,
) -> None:
    packages = _base_fixture(tmp_path)
    packages["minions-providers"]["imports"] = ["minions.Core.detail"]
    config = _write_config(
        tmp_path,
        packages,
        ["minions", "minions-core", "minions-runtime"],
        name="case-equivalent-overlap.toml",
    )

    for checker in (NAMESPACE_CHECKER, ARCHITECTURE_CHECKER):
        result = _run_checker(checker, tmp_path, config=config)
        _assert_failure(
            result,
            "overlapping",
            "minions.core",
            "minions-core",
            "minions.Core.detail",
            "minions-providers",
        )


def test_checkers_allow_same_owner_parent_child_import_prefixes(
    tmp_path: Path,
) -> None:
    packages = _base_fixture(
        tmp_path,
        active_packages=["minions", "minions-core"],
    )
    packages["minions-core"]["imports"] = [
        "minions.core",
        "minions.core.detail",
    ]
    config = _write_config(
        tmp_path,
        packages,
        ["minions", "minions-core"],
        name="same-owner-parent-child.toml",
    )

    for checker, phrase in (
        (NAMESPACE_CHECKER, "namespace ownership valid"),
        (ARCHITECTURE_CHECKER, "0 forbidden edges, 0 distribution cycles"),
    ):
        result = _run_checker(checker, tmp_path, config=config)
        _assert_success(result, phrase)


def test_checkers_keep_unicode_import_prefixes_distinct(
    tmp_path: Path,
) -> None:
    packages = _base_fixture(tmp_path)
    packages["minions-core"]["imports"] = ["minions.straße"]
    packages["minions-runtime"]["imports"] = ["minions.strasse"]
    config = _write_config(
        tmp_path,
        packages,
        ["minions", "minions-core", "minions-runtime"],
        name="unicode-distinct-prefixes.toml",
    )

    for checker, phrase in (
        (NAMESPACE_CHECKER, "namespace ownership valid"),
        (ARCHITECTURE_CHECKER, "0 forbidden edges, 0 distribution cycles"),
    ):
        result = _run_checker(checker, tmp_path, config=config)
        _assert_success(result, phrase)


@pytest.mark.parametrize("checker", (NAMESPACE_CHECKER, ARCHITECTURE_CHECKER))
def test_checkers_reject_package_root_that_shadows_umbrella(
    tmp_path: Path,
    checker: Path,
) -> None:
    _base_fixture(tmp_path)
    umbrella = _source_root(tmp_path, "minions")
    shadow = tmp_path / "packages" / "minions" / "src" / "minions"
    shadow.mkdir(parents=True)

    result = _run_checker(checker, tmp_path)

    _assert_failure(
        result,
        "duplicate",
        "minions",
        str(umbrella),
        str(shadow),
    )


def test_architecture_checker_rejects_unknown_allow_target(
    tmp_path: Path,
) -> None:
    packages = _base_fixture(tmp_path)
    packages["minions-runtime"]["allows"] = ["minions-missing"]
    config = _write_config(
        tmp_path,
        packages,
        ["minions", "minions-core", "minions-runtime"],
        name="unknown-allow.toml",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path, config=config)

    _assert_failure(result, "minions-runtime", "minions-missing", "unknown")


def test_architecture_checker_accepts_allowed_absolute_import(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    _write(_source_root(tmp_path, "minions-core") / "core" / "api.py")
    _write(
        _source_root(tmp_path, "minions-runtime") / "runtime" / "runner.py",
        "from minions.core import api\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_success(result, "0 forbidden edges, 0 distribution cycles")


def test_architecture_checker_rejects_noncanonical_configured_source_prefix(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path, active_packages=["minions", "minions-core"])
    _write(_source_root(tmp_path, "minions-core") / "core" / "api.py")
    source = _write(_source_root(tmp_path, "minions") / "Core" / "orphan.py")

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(
        result,
        "non-canonical configured source prefix",
        "minions.Core.orphan",
        "minions.core",
        "minions-core",
        str(source),
    )


def test_architecture_checker_rejects_noncanonical_configured_import_prefix(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path, active_packages=["minions", "minions-core"])
    _write(_source_root(tmp_path, "minions-core") / "core" / "api.py")
    source = _write(
        _source_root(tmp_path, "minions") / "app.py",
        "import minions.Core.api\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(
        result,
        "non-canonical configured-prefix internal import",
        "minions.Core.api",
        "minions.core",
        str(source),
        "line 1",
    )


def test_architecture_checker_accepts_canonical_configured_prefixes(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path, active_packages=["minions", "minions-core"])
    _write(_source_root(tmp_path, "minions-core") / "core" / "api.py")
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        "import minions.core.api\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_success(result, "0 forbidden edges, 0 distribution cycles")


def test_architecture_checker_keeps_unicode_configured_prefixes_distinct(
    tmp_path: Path,
) -> None:
    packages = _base_fixture(
        tmp_path,
        active_packages=["minions", "minions-core"],
    )
    packages["minions-core"]["imports"] = ["minions.straße"]
    _write_config(tmp_path, packages, ["minions", "minions-core"])
    _write(_source_root(tmp_path, "minions-core") / "straße" / "api.py")
    _write(
        _source_root(tmp_path, "minions") / "strasse" / "consumer.py",
        "import minions.strasse.api\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_success(result, "0 forbidden edges, 0 distribution cycles")


def test_architecture_checker_rejects_forbidden_absolute_import(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    source = _write(
        _source_root(tmp_path, "minions-core") / "core" / "api.py",
        "import minions.runtime.runner\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(
        result,
        str(source),
        "line 1",
        "minions-core",
        "minions-runtime",
        "function_scope=false",
        "type_checking=false",
    )


def test_architecture_checker_scans_uppercase_py_source(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    source = _write(
        _source_root(tmp_path, "minions-core") / "core" / "bypass.PY",
        "import minions.runtime.runner\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(
        result,
        str(source),
        "line 1",
        "minions-core",
        "minions-runtime",
    )


def test_architecture_checker_rejects_noncanonical_internal_import(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    source = _write(
        _source_root(tmp_path, "minions-core") / "core" / "casing.py",
        "import Minions.runtime.runner\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(
        result,
        str(source),
        "line 1",
        "Minions.runtime.runner",
        "non-canonical internal import",
        "lowercase minions",
    )


def test_architecture_checker_resolves_relative_import(tmp_path: Path) -> None:
    _base_fixture(tmp_path)
    source = _write(
        _source_root(tmp_path, "minions-core") / "core" / "feature.py",
        "from ..runtime import runner\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(
        result,
        str(source),
        "minions.runtime.runner",
        "minions-core",
        "minions-runtime",
    )


def test_case_variant_init_uses_package_relative_import_base(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    source = _write(
        _source_root(tmp_path, "minions-core")
        / "core"
        / "pkg"
        / "__INIT__.PY",
        "from ...runtime import runner\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(
        result,
        str(source),
        "line 1",
        "minions.runtime.runner",
        "minions-core",
        "minions-runtime",
    )


def test_out_of_bounds_relative_import_retains_function_scope(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    source = _write(
        _source_root(tmp_path, "minions-core") / "core" / "invalid_level.py",
        "def load():\n    from ...outside import value\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(
        result,
        "relative import ownership error",
        str(source),
        "line 2",
        "function_scope=true",
        "type_checking=false",
    )


def test_out_of_bounds_relative_import_retains_type_checking_scope(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    source = _write(
        _source_root(tmp_path, "minions-core") / "core" / "invalid_type.py",
        (
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from ...outside import value\n"
        ),
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(
        result,
        "relative import ownership error",
        str(source),
        "line 4",
        "function_scope=false",
        "type_checking=true",
    )


def test_architecture_checker_scans_function_local_import(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    source = _write(
        _source_root(tmp_path, "minions-core") / "core" / "lazy.py",
        "def load_runtime():\n    import minions.runtime.runner\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(
        result,
        str(source),
        "line 2",
        "minions-runtime",
        "function_scope=true",
        "type_checking=false",
    )


def test_architecture_checker_scans_class_body_import(tmp_path: Path) -> None:
    _base_fixture(tmp_path)
    source = _write(
        _source_root(tmp_path, "minions-core") / "core" / "declaration.py",
        "class Declaration:\n    import minions.runtime.runner\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(result, str(source), "line 2", "minions-runtime")


def test_architecture_checker_scans_type_checking_import(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    source = _write(
        _source_root(tmp_path, "minions-core") / "core" / "types.py",
        (
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from minions.runtime import runner\n"
        ),
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(
        result,
        str(source),
        "line 4",
        "minions-runtime",
        "function_scope=false",
        "type_checking=true",
    )


def test_architecture_checker_does_not_flag_negated_type_checking_guard(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    source = _write(
        _source_root(tmp_path, "minions-core") / "core" / "runtime_only.py",
        (
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if not TYPE_CHECKING:\n"
            "    import minions.runtime.runner\n"
        ),
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(
        result,
        str(source),
        "line 4",
        "minions-runtime",
        "function_scope=false",
        "type_checking=false",
    )


def test_inactive_prefix_resolves_to_umbrella_instead_of_being_ignored(
    tmp_path: Path,
) -> None:
    packages = _base_fixture(
        tmp_path, active_packages=["minions", "minions-runtime"]
    )
    packages["minions-runtime"]["allows"] = ["minions-core"]
    _write_config(tmp_path, packages, ["minions", "minions-runtime"])
    source = _write(
        _source_root(tmp_path, "minions-runtime") / "runtime" / "lazy.py",
        "def load_core():\n    import minions.core.api\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(
        result,
        str(source),
        "minions-runtime",
        "minions",
        "minions.core.api",
        "function_scope=true",
    )


def test_unconfigured_internal_import_falls_back_to_active_umbrella(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path, active_packages=["minions"])
    _write(
        _source_root(tmp_path, "minions") / "app.py",
        "from minions._bootstrap_paths import get_path\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_success(result, "0 forbidden edges, 0 distribution cycles")


def test_unconfigured_internal_import_without_active_umbrella_is_an_error(
    tmp_path: Path,
) -> None:
    packages: PackageConfig = {
        "minions-core": {
            "imports": ["minions.core"],
            "allows": [],
        },
    }
    _write_config(tmp_path, packages, ["minions-core"])
    source = _write(
        _source_root(tmp_path, "minions-core") / "core" / "api.py",
        "import minions.unowned.module\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(
        result,
        str(source),
        "line 1",
        "minions.unowned.module",
        "ownership",
        "function_scope=false",
        "type_checking=false",
    )


def test_architecture_checker_reports_readable_actual_distribution_cycle(
    tmp_path: Path,
) -> None:
    packages = _base_fixture(tmp_path)
    packages["minions-core"]["allows"] = ["minions-runtime"]
    config = _write_config(
        tmp_path,
        packages,
        ["minions", "minions-core", "minions-runtime"],
        name="cycle.toml",
    )
    _write(
        _source_root(tmp_path, "minions-core") / "core" / "api.py",
        "import minions.runtime.runner\n",
    )
    _write(
        _source_root(tmp_path, "minions-runtime") / "runtime" / "runner.py",
        "import minions.core.api\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path, config=config)

    _assert_failure(
        result,
        "cycle",
        "minions-core -> minions-runtime -> minions-core",
    )


def test_architecture_checker_reports_python_syntax_error(
    tmp_path: Path,
) -> None:
    _base_fixture(tmp_path)
    source = _write(
        _source_root(tmp_path, "minions-core") / "core" / "broken.py",
        "def broken(:\n",
    )

    result = _run_checker(ARCHITECTURE_CHECKER, tmp_path)

    _assert_failure(result, str(source), "syntax", "line 1")
    assert "Traceback (most recent call last)" not in _output(result)


@pytest.mark.parametrize("checker", (NAMESPACE_CHECKER, ARCHITECTURE_CHECKER))
def test_checkers_report_malformed_config_without_traceback(
    tmp_path: Path,
    checker: Path,
) -> None:
    config = _write(tmp_path / "broken.toml", "[packages\n")

    result = _run_checker(checker, tmp_path, config=config)

    _assert_failure(result, str(config), "config")
    assert "Traceback (most recent call last)" not in _output(result)
