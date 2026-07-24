# -*- coding: utf-8 -*-
"""Tests for global/workspace skill synchronization and promotion."""

from __future__ import annotations

from pathlib import Path

import pytest

from minions import constant
from minions.agents.skill_system import global_skill_service as global_service
from minions.agents.skill_system import registry, store


def _skill_md(name: str, marker: str) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {marker}\n"
        "---\n\n"
        f"# {marker}\n"
    )


def _write_skill(root: Path, name: str, marker: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        _skill_md(name, marker),
        encoding="utf-8",
    )
    return skill_dir


@pytest.fixture
def skill_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(constant, "WORKING_DIR", tmp_path)
    monkeypatch.setattr(
        global_service,
        "ensure_global_skills_initialized",
        lambda: None,
    )
    monkeypatch.setattr(
        global_service,
        "scan_skill_dir_or_raise",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(registry, "get_packaged_builtin_versions", lambda: {})

    global_root = tmp_path / "global_skills"
    workspace = tmp_path / "workspaces" / "agent-a"
    global_root.mkdir(parents=True)
    (workspace / "skills").mkdir(parents=True)
    store.write_json_atomic(
        store.get_global_skill_manifest_path(),
        store.default_global_skills_manifest(),
    )
    store.write_json_atomic(
        store.get_workspace_skill_manifest_path(workspace),
        store.default_workspace_manifest(),
    )
    return global_root, workspace


def _register_global_skill(global_root: Path, name: str, config=None) -> Path:
    skill_dir = _write_skill(global_root, name, "global-v1")
    payload = store.default_global_skills_manifest()
    payload["skills"][name] = {
        "source": "customized",
        "config": config or {},
    }
    store.write_json_atomic(store.get_global_skill_manifest_path(), payload)
    return skill_dir


def test_content_hash_covers_auxiliary_files_and_ignores_cache(tmp_path: Path):
    skill_dir = _write_skill(tmp_path, "demo", "v1")
    initial = store.compute_skill_content_hash(skill_dir)

    scripts = skill_dir / "scripts"
    scripts.mkdir()
    (scripts / "run.py").write_text("print('v1')\n", encoding="utf-8")
    with_script = store.compute_skill_content_hash(skill_dir)

    cache_dir = skill_dir / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "run.pyc").write_bytes(b"cache")
    with_cache = store.compute_skill_content_hash(skill_dir)

    assert initial != with_script
    assert with_script == with_cache


def test_reconcile_preserves_sync_baseline(skill_env):
    _, workspace = skill_env
    skill_dir = _write_skill(workspace / "skills", "demo", "agent-v1")
    baseline = store.compute_skill_content_hash(skill_dir)
    manifest = store.default_workspace_manifest()
    manifest["skills"]["demo"] = {
        "enabled": True,
        "channels": ["console"],
        "source": "customized",
        "synced_from_global_hash": baseline,
        "last_synced_at": "2026-07-13T08:00:00Z",
    }
    store.write_json_atomic(
        store.get_workspace_skill_manifest_path(workspace),
        manifest,
    )

    reconciled = registry.reconcile_workspace_manifest(workspace)

    entry = reconciled["skills"]["demo"]
    assert entry["synced_from_global_hash"] == baseline
    assert entry["last_synced_at"] == "2026-07-13T08:00:00Z"


def test_promote_agent_improvement_to_global_without_copying_config(skill_env):
    global_root, workspace = skill_env
    global_dir = _register_global_skill(
        global_root,
        "demo",
        config={"GLOBAL_DEFAULT": "keep"},
    )
    service = global_service.GlobalSkillService()
    downloaded = service.download_to_workspace("demo", workspace)
    assert downloaded["success"] is True

    workspace_dir = workspace / "skills" / "demo"
    (workspace_dir / "SKILL.md").write_text(
        _skill_md("demo", "agent-improved"),
        encoding="utf-8",
    )
    manifest = store.read_skill_manifest(workspace)
    manifest["skills"]["demo"]["config"] = {"AGENT_SECRET": "private"}
    store.write_json_atomic(
        store.get_workspace_skill_manifest_path(workspace),
        manifest,
    )

    status = service.get_sync_status(workspace)["skills"]["demo"]
    assert status["sync_status"] == "outdated_agent"

    result = service.promote_workspace_skill_to_global(
        workspace,
        "demo",
        expected_global_hash=status["global_hash"],
    )

    assert result["success"] is True
    assert "agent-improved" in (global_dir / "SKILL.md").read_text(
        encoding="utf-8",
    )
    global_manifest = store.read_global_skills_manifest()
    assert global_manifest["skills"]["demo"]["config"] == {
        "GLOBAL_DEFAULT": "keep",
    }
    synced = store.read_skill_manifest(workspace)["skills"]["demo"]
    assert synced["synced_from_global_hash"] == result["global_hash"]


def test_promote_rejects_concurrent_change_and_force_resolves(skill_env):
    global_root, workspace = skill_env
    global_dir = _register_global_skill(global_root, "demo")
    service = global_service.GlobalSkillService()
    assert service.download_to_workspace("demo", workspace)["success"] is True

    (workspace / "skills" / "demo" / "SKILL.md").write_text(
        _skill_md("demo", "agent-improved"),
        encoding="utf-8",
    )
    (global_dir / "SKILL.md").write_text(
        _skill_md("demo", "global-v2"),
        encoding="utf-8",
    )

    conflict = service.promote_workspace_skill_to_global(workspace, "demo")
    assert conflict["success"] is False
    assert conflict["reason"] == "conflict"

    forced = service.promote_workspace_skill_to_global(
        workspace,
        "demo",
        force=True,
        expected_global_hash=conflict["global_hash"],
    )
    assert forced["success"] is True
    assert "agent-improved" in (global_dir / "SKILL.md").read_text(
        encoding="utf-8",
    )


def test_promote_does_not_overwrite_unregistered_global_directory(skill_env):
    global_root, workspace = skill_env
    global_dir = _write_skill(global_root, "demo", "unregistered-global")
    _write_skill(workspace / "skills", "demo", "agent-version")
    manifest = store.default_workspace_manifest()
    manifest["skills"]["demo"] = {"source": "customized"}
    store.write_json_atomic(
        store.get_workspace_skill_manifest_path(workspace),
        manifest,
    )

    result = (
        global_service.GlobalSkillService().promote_workspace_skill_to_global(
            workspace,
            "demo",
        )
    )

    assert result["success"] is False
    assert result["reason"] == "not_linked"
    assert "unregistered-global" in (global_dir / "SKILL.md").read_text(
        encoding="utf-8",
    )


def test_promotion_without_rollout_does_not_trigger_later_auto_update(
    skill_env,
):
    global_root, workspace = skill_env
    global_dir = _register_global_skill(global_root, "demo")
    manifest = store.read_global_skills_manifest()
    manifest["skills"]["demo"]["auto_update"] = True
    manifest["skills"]["demo"][
        "auto_update_synced_hash"
    ] = store.compute_skill_content_hash(global_dir)
    store.write_json_atomic(store.get_global_skill_manifest_path(), manifest)

    service = global_service.GlobalSkillService()
    assert service.download_to_workspace("demo", workspace)["success"] is True
    (workspace / "skills" / "demo" / "SKILL.md").write_text(
        _skill_md("demo", "agent-improved"),
        encoding="utf-8",
    )

    promoted = service.promote_workspace_skill_to_global(workspace, "demo")

    assert promoted["success"] is True
    global_entry = store.read_global_skills_manifest()["skills"]["demo"]
    assert global_entry["auto_update_synced_hash"] == promoted["global_hash"]
    rollout = global_service.run_global_auto_update_sync(skill_name="demo")
    assert rollout["checked"] == 1
    assert rollout["synced"] == []
