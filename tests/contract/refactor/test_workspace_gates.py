# -*- coding: utf-8 -*-
"""Contracts for workspace version and build gates."""
from __future__ import annotations

from pathlib import Path
import runpy
import subprocess
import sys
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[3]
VERSION_CHECKER = REPO_ROOT / "scripts" / "check_workspace_versions.py"
WHEEL_CHECKER = REPO_ROOT / "scripts" / "check_wheel_ownership.py"
BUILD_WORKSPACE = REPO_ROOT / "scripts" / "build_workspace.py"
INSTALL_WHEELS = REPO_ROOT / "scripts" / "install_built_wheels.py"
CHECK_COMPONENT_INSTALLS = (
    REPO_ROOT / "scripts" / "check_component_installs.py"
)
ARCHITECTURE_ENTRYPOINT = REPO_ROOT / "scripts" / "check_architecture.py"

COMPONENT_MODULES = {
    "minions-core": "minions/constant.py",
    "minions-runtime": "minions/runtime/__init__.py",
    "minions-providers": "minions/providers/__init__.py",
    "minions-tool-calls": "minions/tool_calls/__init__.py",
    "minions-drivers": "minions/drivers/__init__.py",
    "minions-channels": "minions/channels/__init__.py",
    "minions-plugins": "minions/plugins/__init__.py",
    "minions-loop": "minions/loop/__init__.py",
    "minions-governance": "minions/governance/__init__.py",
    "minions-modes": "minions/modes/__init__.py",
    "minions-agents": "minions/agents/__init__.py",
    "minions-app": "minions/app/__init__.py",
    "minions-cli": "minions/cli/__init__.py",
}

COMPONENT_RESOURCES = {
    "minions-core": (
        "minions/security/tool_guard/rules/dangerous.yaml",
        "minions/security/skill_scanner/rules/signatures/rule.yaml",
        "minions/security/skill_scanner/data/default_policy.yaml",
    ),
    "minions-channels": ("minions/channels/yuanbao/proto/conn.json",),
    "minions-agents": (
        "minions/agents/md_files/en/SOUL.md",
        "minions/agents/skills/cron-en/SKILL.md",
        "minions/sage/migrations/0001_sage_core.sql",
    ),
    "minions-app": (
        "minions/console/index.html",
        "minions/docs/guide.md",
        "minions/tenancy/migrations/0001_control_plane.sql",
    ),
}


def _run_version_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERSION_CHECKER), "--root", str(root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_project(
    root: Path,
    distribution: str,
    version: str,
    dependencies: tuple[str, ...] = (),
) -> None:
    if distribution == "minions":
        path = root / "pyproject.toml"
    else:
        path = root / "packages" / distribution / "pyproject.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    dependency_lines = ", ".join(repr(item) for item in dependencies)
    path.write_text(
        "\n".join(
            (
                "[project]",
                f'name = "{distribution}"',
                f'version = "{version}"',
                f"dependencies = [{dependency_lines}]",
                "",
            ),
        ),
        encoding="utf-8",
    )


def _write_wheel(
    directory: Path,
    distribution: str,
    files: tuple[str, ...],
) -> Path:
    normalized = distribution.replace("-", "_")
    path = directory / f"{normalized}-0.1.0-py3-none-any.whl"
    dist_info = f"{normalized}-0.1.0.dist-info"
    with zipfile.ZipFile(path, "w") as wheel:
        wheel.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.1\nName: {distribution}\nVersion: 0.1.0\n",
        )
        wheel.writestr(f"{dist_info}/WHEEL", "Wheel-Version: 1.0\n")
        for filename in files:
            wheel.writestr(filename, "fixture\n")
    return path


def _complete_wheel_set(directory: Path) -> list[Path]:
    wheels = [
        _write_wheel(
            directory,
            distribution,
            (module, *COMPONENT_RESOURCES.get(distribution, ())),
        )
        for distribution, module in COMPONENT_MODULES.items()
    ]
    wheels.append(_write_wheel(directory, "minions", ()))
    return wheels


def _run_wheel_checker(wheels: list[Path]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WHEEL_CHECKER), *(str(path) for path in wheels)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_repository_workspace_versions_are_aligned() -> None:
    result = _run_version_checker(REPO_ROOT)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "workspace versions valid: 0.1.0" in result.stdout


def test_workspace_version_checker_rejects_component_drift(
    tmp_path: Path,
) -> None:
    _write_project(tmp_path, "minions", "0.1.0")
    _write_project(tmp_path, "minions-core", "0.2.0")

    result = _run_version_checker(tmp_path)

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "minions-core" in output
    assert "0.2.0" in output
    assert "0.1.0" in output


def test_workspace_version_checker_requires_exact_internal_pins(
    tmp_path: Path,
) -> None:
    _write_project(tmp_path, "minions", "0.1.0")
    _write_project(tmp_path, "minions-core", "0.1.0")
    _write_project(
        tmp_path,
        "minions-runtime",
        "0.1.0",
        dependencies=("minions-core>=0.1.0",),
    )

    result = _run_version_checker(tmp_path)

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "minions-runtime" in output
    assert "minions-core>=0.1.0" in output
    assert "minions-core==0.1.0" in output


def test_wheel_ownership_checker_accepts_complete_disjoint_set(
    tmp_path: Path,
) -> None:
    result = _run_wheel_checker(_complete_wheel_set(tmp_path))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "wheel ownership valid: 14 wheels" in result.stdout


def test_wheel_ownership_checker_rejects_overlapping_namespace_file(
    tmp_path: Path,
) -> None:
    wheels = _complete_wheel_set(tmp_path)
    runtime = next(path for path in wheels if path.name.startswith("minions_runtime"))
    with zipfile.ZipFile(runtime, "a") as wheel:
        wheel.writestr("minions/constant.py", "overlap\n")

    result = _run_wheel_checker(wheels)

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "minions/constant.py" in output
    assert "minions-core" in output
    assert "minions-runtime" in output


def test_wheel_ownership_checker_rejects_namespace_initializer(
    tmp_path: Path,
) -> None:
    wheels = _complete_wheel_set(tmp_path)
    core = next(path for path in wheels if path.name.startswith("minions_core"))
    with zipfile.ZipFile(core, "a") as wheel:
        wheel.writestr("minions/__init__.py", "")

    result = _run_wheel_checker(wheels)

    assert result.returncode != 0
    assert "minions/__init__.py" in result.stdout + result.stderr


def test_wheel_ownership_checker_rejects_generated_python_cache(
    tmp_path: Path,
) -> None:
    wheels = _complete_wheel_set(tmp_path)
    agents = next(path for path in wheels if path.name.startswith("minions_agents"))
    with zipfile.ZipFile(agents, "a") as wheel:
        wheel.writestr(
            "minions/agents/skills/example/__pycache__/helper.cpython-312.pyc",
            b"generated cache",
        )

    result = _run_wheel_checker(wheels)

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "generated Python cache" in output
    assert "__pycache__" in output


def test_wheel_ownership_checker_rejects_meta_source(
    tmp_path: Path,
) -> None:
    wheels = _complete_wheel_set(tmp_path)
    meta = next(path for path in wheels if path.name.startswith("minions-"))
    with zipfile.ZipFile(meta, "a") as wheel:
        wheel.writestr("minions/meta_leak.py", "")

    result = _run_wheel_checker(wheels)

    assert result.returncode != 0
    assert "meta" in (result.stdout + result.stderr).lower()
    assert "minions/meta_leak.py" in result.stdout + result.stderr


def test_wheel_ownership_checker_rejects_missing_component_resource(
    tmp_path: Path,
) -> None:
    wheels = _complete_wheel_set(tmp_path)
    app = next(path for path in wheels if path.name.startswith("minions_app"))
    app.unlink()
    replacement = _write_wheel(
        tmp_path,
        "minions-app",
        (COMPONENT_MODULES["minions-app"],),
    )
    wheels = [replacement if path == app else path for path in wheels]

    result = _run_wheel_checker(wheels)

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "minions-app" in output
    assert "console" in output


def test_build_workspace_dry_run_orders_components_before_meta() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(BUILD_WORKSPACE),
            "--root",
            str(REPO_ROOT),
            "--dry-run",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    builds = [
        line.partition(": ")[2]
        for line in result.stdout.splitlines()
        if line.startswith("build ")
    ]
    assert len(builds) == 14
    assert builds[0].endswith("packages/minions-core")
    assert builds[-1].endswith("minions-package-refactor")
    assert all("packages/minions-" in item for item in builds[:-1])


def test_build_workspace_removes_generated_build_inputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    target = tmp_path / "packages" / "minions-core"
    source = target / "src" / "minions" / "core"
    cache = source / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "module.cpython-312.pyc").write_bytes(b"cache")
    (source / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    build_dir = target / "build"
    build_dir.mkdir()
    (build_dir / "stale.pyc").write_bytes(b"cache")
    egg_info = target / "src" / "minions_core.egg-info"
    egg_info.mkdir()
    (egg_info / "SOURCES.txt").write_text("stale\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(REPO_ROOT / "scripts"))
    namespace = runpy.run_path(str(BUILD_WORKSPACE))

    namespace["_clean_generated_build_inputs"](target, tmp_path)

    assert (source / "module.py").is_file()
    assert not cache.exists()
    assert not build_dir.exists()
    assert not egg_info.exists()


def test_architecture_entrypoint_exposes_source_root_report() -> None:
    result = subprocess.run(
        [sys.executable, str(ARCHITECTURE_ENTRYPOINT), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "--source-root" in result.stdout
    assert "--report" in result.stdout


def test_local_wheel_installer_rejects_wrong_wheel_count(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_wheel(dist, "minions-core", ("minions/constant.py",))

    result = subprocess.run(
        [
            sys.executable,
            str(INSTALL_WHEELS),
            "--venv",
            str(tmp_path / "venv"),
            "--dist",
            str(dist),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "exactly 14 wheels" in (result.stdout + result.stderr)


def test_component_installer_rejects_missing_internal_dependency(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    _complete_wheel_set(dist)

    result = subprocess.run(
        [
            sys.executable,
            str(CHECK_COMPONENT_INSTALLS),
            str(dist),
            "--component",
            "minions-runtime",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "minions-runtime" in output
    assert "minions-core==0.1.0" in output


def test_import_linter_uses_locked_namespace_bands() -> None:
    config = (REPO_ROOT / ".importlinter").read_text(encoding="utf-8")

    assert "exclude_type_checking_imports = False" in config
    assert "[importlinter:contract:bands]" in config
    assert "type = layers" in config
    assert "minions.__main__ : minions.cli" in config
    assert "minions.app : minions.backup : minions.agent_stats" in config
    assert "minions.agents : minions.market : minions.sage" in config
    assert "minions.agents._compat" in config
    assert "minions._compat" not in config
    assert "minions.governance : minions.sandbox : minions.loop" in config
    assert "minions.core : minions.config : minions.security" in config
