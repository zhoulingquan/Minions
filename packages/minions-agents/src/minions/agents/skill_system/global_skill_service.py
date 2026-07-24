# -*- coding: utf-8 -*-
"""Global skills lifecycle service."""

from __future__ import annotations

import hashlib
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...exceptions import SkillsError
from ..utils.file_handling import read_text_file_with_encoding_fallback
from .models import SkillInfo
from .registry import (
    ensure_global_skills_initialized,
    list_workspaces,
)
from .store import (
    build_import_conflict,
    build_skill_metadata,
    compute_skill_content_hash,
    compute_skill_md_hash,
    compute_workspace_skill_hash,
    copy_skill_dir,
    default_global_skills_manifest,
    default_workspace_manifest,
    extract_zip_skills,
    get_global_skill_manifest_path,
    get_global_skills_dir,
    get_workspace_identity,
    get_workspace_skill_manifest_path,
    get_workspace_skills_dir,
    import_skill_dir,
    is_ignored_skill_entry,
    is_primary_global_skill_dir,
    mutate_json,
    normalize_skill_dir_name,
    read_json,
    read_skill_from_dir,
    read_skill_manifest,
    read_global_skills_manifest,
    resolve_global_skill_dir,
    safe_skill_dir,
    scan_skill_dir_or_raise,
    skill_hash_matches,
    staged_skill_dir,
    suggest_conflict_name,
    validate_skill_content,
    write_skill_to_dir,
)

logger = logging.getLogger(__name__)


def _get_synced_hash(ws_entry: dict[str, Any]) -> str:
    """Read the synced-from-global hash, with legacy key fallback.

    New manifests store ``synced_from_global_hash``; older manifests used
    ``synced_from_pool_hash``. We prefer the new key and fall back to the
    legacy key so existing data keeps working after the rename.
    """
    return str(
        ws_entry.get("synced_from_global_hash")
        or ws_entry.get("synced_from_pool_hash", "")
        or "",
    )


def _register_global_skill_entry(
    payload: dict[str, Any],
    skill_name: str,
    skill_dir: Path,
    *,
    source: str = "customized",
    protected: bool = False,
    installed_from: str = "",
    config: dict[str, Any] | None = None,
    tags: Any | None = None,
    preserve_from: dict[str, Any] | None = None,
) -> None:
    """Upsert a global skill entry — single source of truth for entry shape."""
    payload.setdefault("skills", {})
    if preserve_from is None:
        preserve_from = payload["skills"].get(skill_name) or {}

    entry = build_skill_metadata(
        skill_name,
        skill_dir,
        source=source,
        protected=protected,
    )
    entry["external"] = not is_primary_global_skill_dir(skill_dir)

    installed_from_final = installed_from or str(
        preserve_from.get("installed_from", "") or "",
    )
    if installed_from_final:
        entry["installed_from"] = installed_from_final

    if config is not None:
        entry["config"] = dict(config)
    elif "config" in preserve_from:
        entry["config"] = preserve_from["config"]

    if tags is not None:
        entry["tags"] = tags
    elif preserve_from.get("tags") is not None:
        entry["tags"] = preserve_from["tags"]

    if source == "builtin":
        builtin_language = (
            str(
                preserve_from.get("builtin_language", "") or "",
            )
            .strip()
            .lower()
        )
        if builtin_language:
            entry["builtin_language"] = builtin_language
        builtin_source_name = str(
            preserve_from.get("builtin_source_name", "") or "",
        ).strip()
        if builtin_source_name:
            entry["builtin_source_name"] = builtin_source_name

    for au_key in (
        "auto_update",
        "auto_update_targets",
        "auto_update_synced_hash",
    ):
        if au_key in preserve_from:
            entry[au_key] = preserve_from.get(au_key)

    payload["skills"][skill_name] = entry


class GlobalSkillService:
    """Global skills lifecycle service.

    This service manages reusable skills in the global skills
    ``WORKING_DIR/global_skills``. It supports creating global-native skills,
    importing zips, syncing packaged builtins, uploading skills from a
    workspace into global skills, and downloading global skills back into one or more
    workspaces.

    The global skills dir is intentionally separate from any single workspace: it is the
    place for shared reuse, conflict detection, and builtin version management.

    Example:
        uploading ``demo_skill`` from workspace ``a1`` stores a shared copy in
        ``global_skills/demo_skill`` and records the workspace-to-global linkage in
        the workspace manifest.

        downloading global skill ``shared_docx`` into workspace ``b1`` creates
        ``workspaces/b1/skills/shared_docx`` and marks its sync state against
        the global skills entry.
    """

    def __init__(self):
        ensure_global_skills_initialized()

    def list_all_skills(self) -> list[SkillInfo]:
        manifest = read_global_skills_manifest()
        global_dir = get_global_skills_dir()
        skills: list[SkillInfo] = []
        for skill_name, entry in sorted(manifest.get("skills", {}).items()):
            skill_dir = resolve_global_skill_dir(skill_name) or (
                global_dir / skill_name
            )
            skill = read_skill_from_dir(
                skill_dir,
                entry.get("source", "customized"),
            )
            if skill is not None:
                skills.append(skill)
        return skills

    def create_skill(
        self,
        name: str,
        content: str,
        references: dict[str, Any] | None = None,
        scripts: dict[str, Any] | None = None,
        extra_files: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
        installed_from: str = "",
    ) -> str | None:
        validate_skill_content(content)
        skill_name = normalize_skill_dir_name(name)
        global_dir = get_global_skills_dir()
        skill_dir = safe_skill_dir(global_dir, skill_name)
        manifest = read_global_skills_manifest()
        existing = manifest.get("skills", {}).get(skill_name)
        if existing is not None or skill_dir.exists():
            return None

        with staged_skill_dir(skill_name) as staged_dir:
            write_skill_to_dir(
                staged_dir,
                content,
                references,
                scripts,
                extra_files,
            )
            scan_skill_dir_or_raise(staged_dir, skill_name)
            copy_skill_dir(staged_dir, skill_dir)

        def _update(payload: dict[str, Any]) -> None:
            _register_global_skill_entry(
                payload,
                skill_name,
                skill_dir,
                source="customized",
                installed_from=installed_from,
                config=config,
                preserve_from={},
            )

        try:
            mutate_json(
                get_global_skill_manifest_path(),
                default_global_skills_manifest(),
                _update,
            )
        except Exception as exc:
            try:
                if skill_dir.exists():
                    shutil.rmtree(skill_dir, ignore_errors=True)
            except Exception as cleanup_exc:
                raise SkillsError(
                    message=(
                        "Global skill files were created, but manifest update "
                        "failed and rollback cleanup also failed."
                    ),
                    details={
                        "skill_name": skill_name,
                        "manifest_path": str(get_global_skill_manifest_path()),
                        "cleanup_error": str(cleanup_exc),
                    },
                ) from exc
            raise SkillsError(
                message=(
                    "Global skills manifest update failed after file creation. "
                    "File changes were rolled back."
                ),
                details={
                    "skill_name": skill_name,
                    "manifest_path": str(get_global_skill_manifest_path()),
                },
            ) from exc
        return skill_name

    def import_from_zip(
        self,
        data: bytes,
        target_name: str | None = None,
        rename_map: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        global_dir = get_global_skills_dir()
        tmp_dir, found = extract_zip_skills(data)
        renames = rename_map or {}
        try:
            normalized_target = str(target_name or "").strip()
            if normalized_target:
                normalized_target = normalize_skill_dir_name(
                    normalized_target,
                )
                if len(found) != 1:
                    raise SkillsError(
                        message=(
                            "target_name is only supported for "
                            "single-skill zip imports"
                        ),
                    )
                found = [(found[0][0], normalized_target)]
            found = [
                (d, normalize_skill_dir_name(renames.get(n, n)))
                for d, n in found
            ]
            manifest = read_global_skills_manifest()
            existing_global_names = (
                set(
                    manifest.get("skills", {}).keys(),
                )
                | {
                    p.name
                    for p in global_dir.iterdir()
                    if p.is_dir() and not is_ignored_skill_entry(p.name)
                }
                if global_dir.exists()
                else set(
                    manifest.get("skills", {}).keys(),
                )
            )
            for skill_dir, skill_name in found:
                validate_skill_content(
                    (skill_dir / "SKILL.md").read_text(encoding="utf-8"),
                )
                scan_skill_dir_or_raise(skill_dir, skill_name)
            conflicts: list[dict[str, Any]] = []
            planned: list[tuple[Path, str]] = []
            seen_names: set[str] = set()
            for skill_dir, skill_name in found:
                if skill_name in seen_names:
                    conflicts.append(
                        build_import_conflict(
                            skill_name,
                            existing_global_names,
                        ),
                    )
                    continue
                seen_names.add(skill_name)
                existing = manifest.get("skills", {}).get(
                    skill_name,
                )
                occupied = (
                    existing is not None or (global_dir / skill_name).exists()
                )
                if occupied:
                    conflicts.append(
                        build_import_conflict(
                            skill_name,
                            existing_global_names,
                        ),
                    )
                    continue
                planned.append((skill_dir, skill_name))
            if conflicts:
                return {
                    "imported": [],
                    "count": 0,
                    "conflicts": conflicts,
                }
            imported: list[str] = []
            for skill_dir, skill_name in planned:
                if import_skill_dir(
                    skill_dir,
                    global_dir,
                    skill_name,
                ):
                    imported.append(skill_name)

            if imported:

                def _update(payload: dict[str, Any]) -> None:
                    for name in imported:
                        _register_global_skill_entry(
                            payload,
                            name,
                            global_dir / name,
                            source="customized",
                            installed_from="zip",
                            preserve_from={},
                        )

                mutate_json(
                    get_global_skill_manifest_path(),
                    default_global_skills_manifest(),
                    _update,
                )
            return {
                "imported": imported,
                "count": len(imported),
                "conflicts": conflicts,
            }
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def delete_skill(self, name: str) -> bool:
        try:
            skill_name = normalize_skill_dir_name(name)
        except SkillsError:
            return False
        manifest = read_global_skills_manifest()
        entry = manifest.get("skills", {}).get(skill_name)
        if entry is None:
            return False

        skill_dir = resolve_global_skill_dir(skill_name) or safe_skill_dir(
            get_global_skills_dir(),
            skill_name,
        )
        if skill_dir.exists():
            shutil.rmtree(skill_dir)

        def _update(payload: dict[str, Any]) -> None:
            payload.get("skills", {}).pop(skill_name, None)

        try:
            mutate_json(
                get_global_skill_manifest_path(),
                default_global_skills_manifest(),
                _update,
            )
        except Exception as exc:
            raise SkillsError(
                message=(
                    "Global skill files were deleted, but manifest update "
                    "failed."
                ),
                details={
                    "skill_name": skill_name,
                    "manifest_path": str(get_global_skill_manifest_path()),
                },
            ) from exc
        return True

    def set_global_skill_tags(
        self,
        name: str,
        tags: list[str] | None,
    ) -> bool:
        """Update one global skill's user tags."""
        try:
            skill_name = normalize_skill_dir_name(name)
        except SkillsError:
            return False
        normalized = tags or []

        def _update(payload: dict[str, Any]) -> bool:
            entry = payload.get("skills", {}).get(skill_name)
            if entry is None:
                return False
            entry["tags"] = normalized
            return True

        return mutate_json(
            get_global_skill_manifest_path(),
            default_global_skills_manifest(),
            _update,
        )

    def set_skill_auto_update(
        self,
        name: str,
        *,
        enabled: bool,
        targets: list[str] | None,
    ) -> dict[str, Any] | None:
        """Enable/disable auto-update for a global skill and persist targets."""

        try:
            skill_name = normalize_skill_dir_name(name)
        except SkillsError:
            return None

        normalized_targets = [str(t) for t in (targets or [])]

        def _update(payload: dict[str, Any]) -> bool:
            entry = payload.get("skills", {}).get(skill_name)
            if entry is None:
                return False
            entry["auto_update"] = bool(enabled)
            if normalized_targets:
                entry["auto_update_targets"] = normalized_targets
            else:
                entry.pop("auto_update_targets", None)
            if enabled:
                # Force the immediate sync below to reconcile the current
                # target set even when the content hash is unchanged (e.g. the
                # user just added a new target agent).
                entry.pop("auto_update_synced_hash", None)
            return True

        updated = mutate_json(
            get_global_skill_manifest_path(),
            default_global_skills_manifest(),
            _update,
        )
        if not updated:
            return None
        if enabled:
            return run_global_auto_update_sync(skill_name=skill_name)
        return {"synced": [], "failed": [], "checked": 0}

    def get_edit_target_name(
        self,
        skill_name: str,
        *,
        target_name: str | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        try:
            skill_name = normalize_skill_dir_name(skill_name)
        except SkillsError:
            return {"success": False, "reason": "not_found"}
        normalized_target = normalize_skill_dir_name(
            target_name or skill_name,
        )
        manifest = read_global_skills_manifest()
        entry = manifest.get("skills", {}).get(skill_name)
        if entry is None:
            return {"success": False, "reason": "not_found"}

        global_names = set(manifest.get("skills", {}).keys())
        if normalized_target == skill_name:
            return {
                "success": True,
                "mode": "edit",
                "name": skill_name,
            }

        existing = manifest.get("skills", {}).get(normalized_target)
        if existing is not None and not overwrite:
            return {
                "success": False,
                "reason": "conflict",
                "mode": "rename",
                "suggested_name": suggest_conflict_name(
                    normalized_target,
                    global_names,
                ),
            }
        return {
            "success": True,
            "mode": "rename",
            "name": normalized_target,
        }

    def save_global_skill(
        self,
        *,
        skill_name: str,
        content: str,
        target_name: str | None = None,
        config: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        validate_skill_content(content)
        try:
            skill_name = normalize_skill_dir_name(skill_name)
        except SkillsError:
            return {"success": False, "reason": "not_found"}
        manifest = read_global_skills_manifest()
        entry = manifest.get("skills", {}).get(skill_name)
        if entry is None:
            return {"success": False, "reason": "not_found"}

        edit_target = self.get_edit_target_name(
            skill_name,
            target_name=target_name,
            overwrite=overwrite,
        )
        if not edit_target.get("success"):
            return edit_target

        final_name = str(edit_target["name"])
        if str(edit_target["mode"]) == "rename" and final_name != skill_name:
            return self._save_global_skill_as_rename(
                skill_name=skill_name,
                final_name=final_name,
                content=content,
                config=config,
                entry=entry,
            )
        return self._save_global_skill_in_place(
            skill_name=skill_name,
            content=content,
            config=config,
            entry=entry,
        )

    def _save_global_skill_in_place(
        self,
        *,
        skill_name: str,
        content: str,
        config: dict[str, Any] | None,
        entry: dict[str, Any],
    ) -> dict[str, Any]:
        skill_dir = resolve_global_skill_dir(skill_name) or safe_skill_dir(
            get_global_skills_dir(),
            skill_name,
        )
        new_config = (
            config if config is not None else entry.get("config") or {}
        )
        old_md = (
            (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            if (skill_dir / "SKILL.md").exists()
            else ""
        )
        content_changed = content != old_md
        if not content_changed and new_config == (entry.get("config") or {}):
            return {
                "success": True,
                "mode": "noop",
                "name": skill_name,
            }

        if content_changed:
            with staged_skill_dir(skill_name) as staged_dir:
                if skill_dir.exists():
                    copy_skill_dir(skill_dir, staged_dir)
                (staged_dir / "SKILL.md").write_text(
                    content,
                    encoding="utf-8",
                )
                scan_skill_dir_or_raise(staged_dir, skill_name)
            (skill_dir / "SKILL.md").write_text(
                content,
                encoding="utf-8",
            )

        source = (
            "customized"
            if content_changed
            else entry.get("source", "customized")
        )

        def _update(payload: dict[str, Any]) -> None:
            current_entry = payload["skills"].get(skill_name) or entry or {}
            _register_global_skill_entry(
                payload,
                skill_name,
                skill_dir,
                source=source,
                config=new_config,
                preserve_from=current_entry,
            )

        mutate_json(
            get_global_skill_manifest_path(),
            default_global_skills_manifest(),
            _update,
        )
        return {
            "success": True,
            "mode": "edit",
            "name": skill_name,
        }

    def _save_global_skill_as_rename(
        self,
        *,
        skill_name: str,
        final_name: str,
        content: str,
        config: dict[str, Any] | None,
        entry: dict[str, Any],
    ) -> dict[str, Any]:
        old_skill_dir = resolve_global_skill_dir(skill_name) or safe_skill_dir(
            get_global_skills_dir(),
            skill_name,
        )
        root_dir = old_skill_dir.parent
        skill_dir = safe_skill_dir(root_dir, final_name)

        with staged_skill_dir(final_name) as staged_dir:
            if old_skill_dir.exists():
                copy_skill_dir(old_skill_dir, staged_dir)
            (staged_dir / "SKILL.md").write_text(
                content,
                encoding="utf-8",
            )
            scan_skill_dir_or_raise(staged_dir, final_name)
            copy_skill_dir(staged_dir, skill_dir)
        if old_skill_dir.exists():
            shutil.rmtree(old_skill_dir)

        new_config = (
            config if config is not None else entry.get("config") or {}
        )

        def _update(payload: dict[str, Any]) -> None:
            current_entry = payload["skills"].get(skill_name) or entry or {}
            _register_global_skill_entry(
                payload,
                final_name,
                skill_dir,
                source="customized",
                config=new_config,
                preserve_from=current_entry,
            )
            payload["skills"].pop(skill_name, None)

        mutate_json(
            get_global_skill_manifest_path(),
            default_global_skills_manifest(),
            _update,
        )

        migration = (
            self.rename_in_workspaces(
                skill_name,
                final_name,
                targets=entry.get("auto_update_targets"),
            )
            if entry.get("auto_update")
            else {"renamed": [], "overwritten": []}
        )
        return {
            "success": True,
            "mode": "rename",
            "name": final_name,
            "renamed": migration["renamed"],
            "overwritten": migration["overwritten"],
        }

    def rename_in_workspaces(
        self,
        old_name: str,
        new_name: str,
        *,
        targets: list[str] | None = None,
    ) -> dict[str, list[str]]:
        """Migrate auto-update copies of ``old_name`` to ``new_name``."""
        try:
            old_name = normalize_skill_dir_name(old_name)
            new_name = normalize_skill_dir_name(new_name)
        except SkillsError:
            return {"renamed": [], "overwritten": []}
        if old_name == new_name:
            return {"renamed": [], "overwritten": []}
        source_dir = resolve_global_skill_dir(new_name)
        if source_dir is None:
            return {"renamed": [], "overwritten": []}

        pinned = (
            {str(t) for t in targets}
            if isinstance(targets, list) and targets
            else None
        )
        renamed: list[str] = []
        overwritten: list[str] = []
        for ws in list_workspaces():
            agent_id = str(ws.get("agent_id", "") or "")
            if pinned is not None and agent_id not in pinned:
                continue
            workspace_dir = Path(ws["workspace_dir"])
            skills = read_skill_manifest(workspace_dir).get("skills", {})
            old_entry = skills.get(old_name)
            if not isinstance(old_entry, dict):
                continue
            if new_name in skills:
                # A rename is an update: overwrite any existing target skill.
                overwritten.append(agent_id)
                logger.info(
                    "rename: overwriting existing '%s' in workspace '%s'",
                    new_name,
                    agent_id,
                )

            workspace_skills_dir = get_workspace_skills_dir(workspace_dir)
            target_dir = safe_skill_dir(workspace_skills_dir, new_name)
            old_dir = safe_skill_dir(workspace_skills_dir, old_name)
            try:
                target_dir.parent.mkdir(parents=True, exist_ok=True)
                with staged_skill_dir(new_name) as staged_dir:
                    copy_skill_dir(source_dir, staged_dir)
                    scan_skill_dir_or_raise(staged_dir, new_name)
                    copy_skill_dir(staged_dir, target_dir)
            except Exception:
                logger.warning(
                    "rename: failed migrating '%s'->'%s' in workspace '%s'",
                    old_name,
                    new_name,
                    agent_id,
                    exc_info=True,
                )
                continue

            def _update(
                payload: dict[str, Any],
                _old: dict[str, Any] = old_entry,
                _target: Path = target_dir,
            ) -> None:
                payload.setdefault("skills", {})
                metadata = build_skill_metadata(
                    new_name,
                    _target,
                    source=str(
                        _old.get("source", "customized") or "customized",
                    ),
                    protected=False,
                )
                ws_entry: dict[str, Any] = {
                    "enabled": bool(_old.get("enabled", True)),
                    "channels": _old.get("channels") or ["all"],
                    "source": metadata["source"],
                    "installed_from": str(
                        _old.get("installed_from", "") or "",
                    ),
                    "config": _old.get("config") or {},
                    "metadata": metadata,
                    "requirements": metadata["requirements"],
                    "updated_at": metadata["updated_at"],
                }
                if _old.get("builtin_language"):
                    ws_entry["builtin_language"] = _old["builtin_language"]
                if _old.get("tags") is not None:
                    ws_entry["tags"] = _old["tags"]
                payload["skills"][new_name] = ws_entry
                payload["skills"].pop(old_name, None)

            mutate_json(
                get_workspace_skill_manifest_path(workspace_dir),
                default_workspace_manifest(),
                _update,
            )
            if old_dir.exists():
                shutil.rmtree(old_dir, ignore_errors=True)
            renamed.append(agent_id)

        return {"renamed": renamed, "overwritten": overwritten}

    def upload_from_workspace(
        self,
        workspace_dir: Path,
        skill_name: str,
        *,
        overwrite: bool = False,
        preview_only: bool = False,
    ) -> dict[str, Any]:
        try:
            skill_name = normalize_skill_dir_name(skill_name)
            source_dir = safe_skill_dir(
                get_workspace_skills_dir(workspace_dir),
                skill_name,
            )
        except SkillsError:
            return {"success": False, "reason": "not_found"}
        if not source_dir.exists():
            return {"success": False, "reason": "not_found"}

        final_name = normalize_skill_dir_name(skill_name)
        target_dir = safe_skill_dir(get_global_skills_dir(), final_name)
        manifest = read_global_skills_manifest()
        existing = manifest.get("skills", {}).get(final_name)
        if existing:
            if not overwrite:
                return {
                    "success": False,
                    "reason": "conflict",
                    "suggested_name": suggest_conflict_name(
                        final_name,
                    ),
                }
        if preview_only:
            return {"success": True, "name": final_name}

        with staged_skill_dir(final_name) as staged_dir:
            copy_skill_dir(source_dir, staged_dir)
            scan_skill_dir_or_raise(staged_dir, final_name)
            copy_skill_dir(staged_dir, target_dir)

        ws_manifest = read_json(
            get_workspace_skill_manifest_path(workspace_dir),
            default_workspace_manifest(),
        )
        workspace_entry = ws_manifest.get("skills", {}).get(skill_name, {})
        ws_config = workspace_entry.get("config") or {}
        ws_tags = workspace_entry.get("tags")
        ws_installed_from = str(
            workspace_entry.get("installed_from", "") or "",
        )

        def _update(payload: dict[str, Any]) -> None:
            _register_global_skill_entry(
                payload,
                final_name,
                target_dir,
                source="customized",
                installed_from=ws_installed_from,
                config=ws_config if ws_config else None,
                tags=ws_tags,
                preserve_from={},
            )

        mutate_json(
            get_global_skill_manifest_path(),
            default_global_skills_manifest(),
            _update,
        )

        return {"success": True, "name": final_name}

    def promote_workspace_skill_to_global(
        self,
        workspace_dir: Path,
        skill_name: str,
        *,
        force: bool = False,
        expected_global_hash: str | None = None,
        include_config: bool = False,
        propagate: bool = False,
    ) -> dict[str, Any]:
        """Promote one agent's skill copy into the global skill source.

        The workspace's last synchronized hash acts as an optimistic lock.
        Promotion is rejected when the global source changed since that base,
        unless ``force`` is explicitly requested.  Runtime config remains
        agent-local by default, and rollout is deliberately separate.
        """
        try:
            skill_name = normalize_skill_dir_name(skill_name)
        except SkillsError:
            return {"success": False, "reason": "not_found"}

        ws_manifest = read_skill_manifest(workspace_dir)
        ws_entry = ws_manifest.get("skills", {}).get(skill_name)
        if ws_entry is None:
            return {"success": False, "reason": "not_found"}

        workspace_skills_dir = get_workspace_skills_dir(workspace_dir)
        ws_skill_dir = workspace_skills_dir / skill_name
        if not ws_skill_dir.exists():
            return {"success": False, "reason": "not_found"}

        ws_hash = compute_workspace_skill_hash(workspace_dir, skill_name)
        if not ws_hash:
            return {"success": False, "reason": "not_found"}

        global_manifest = read_global_skills_manifest()
        global_entry = global_manifest.get("skills", {}).get(skill_name)
        global_dir = resolve_global_skill_dir(skill_name)
        global_exists = global_dir is not None
        global_hash = (
            compute_skill_content_hash(global_dir) if global_dir else ""
        )
        synced_hash = _get_synced_hash(ws_entry)

        if (
            expected_global_hash is not None
            and str(expected_global_hash) != global_hash
        ):
            return {
                "success": False,
                "reason": "stale_global",
                "skill_name": skill_name,
                "global_hash": global_hash,
                "agent_hash": ws_hash,
                "last_synced_hash": synced_hash,
            }

        if global_exists and global_hash == ws_hash:
            sync_timestamp = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )

            def _restamp(payload: dict[str, Any]) -> None:
                entry = payload.get("skills", {}).get(skill_name)
                if isinstance(entry, dict):
                    entry["synced_from_global_hash"] = global_hash
                    entry.pop("synced_from_pool_hash", None)
                    entry["last_synced_at"] = sync_timestamp

            mutate_json(
                get_workspace_skill_manifest_path(workspace_dir),
                default_workspace_manifest(),
                _restamp,
            )
            return {
                "success": True,
                "mode": "noop",
                "name": skill_name,
                "global_hash": global_hash,
                "created": False,
                "propagated": False,
            }

        if global_exists and not force:
            global_at_base = bool(
                global_dir
                and synced_hash
                and skill_hash_matches(global_dir, synced_hash)
            )
            agent_at_base = bool(
                synced_hash and skill_hash_matches(ws_skill_dir, synced_hash)
            )
            if not synced_hash:
                reason = "not_linked"
            elif not global_at_base:
                reason = "conflict" if not agent_at_base else "outdated_global"
            else:
                reason = ""
            if reason:
                return {
                    "success": False,
                    "reason": reason,
                    "skill_name": skill_name,
                    "global_hash": global_hash,
                    "agent_hash": ws_hash,
                    "last_synced_hash": synced_hash,
                }

        # No conflict (or an explicit force) — promote the agent files.
        target_dir = safe_skill_dir(get_global_skills_dir(), skill_name)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        with staged_skill_dir(skill_name) as staged_dir:
            copy_skill_dir(ws_skill_dir, staged_dir)
            scan_skill_dir_or_raise(staged_dir, skill_name)
            with staged_skill_dir(f"{skill_name}-rollback") as rollback_dir:
                had_primary_target = target_dir.exists()
                if had_primary_target:
                    copy_skill_dir(target_dir, rollback_dir)
                copy_skill_dir(staged_dir, target_dir)

                ws_config = ws_entry.get("config") or {}
                ws_installed_from = str(
                    ws_entry.get("installed_from", "") or "",
                )

                def _update_global(payload: dict[str, Any]) -> None:
                    _register_global_skill_entry(
                        payload,
                        skill_name,
                        target_dir,
                        source="customized",
                        installed_from=(
                            "" if global_entry else ws_installed_from
                        ),
                        config=ws_config if include_config else None,
                        tags=None,
                        preserve_from=global_entry or {},
                    )
                    promoted = payload["skills"][skill_name]
                    if not propagate and promoted.get("auto_update"):
                        promoted["auto_update_synced_hash"] = ws_hash

                try:
                    mutate_json(
                        get_global_skill_manifest_path(),
                        default_global_skills_manifest(),
                        _update_global,
                    )
                except Exception:
                    if had_primary_target:
                        copy_skill_dir(rollback_dir, target_dir)
                    elif target_dir.exists():
                        shutil.rmtree(target_dir, ignore_errors=True)
                    raise

        new_global_hash = compute_skill_content_hash(target_dir)
        sync_timestamp = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        def _update_ws(payload: dict[str, Any]) -> None:
            entry = payload.get("skills", {}).get(skill_name)
            if entry is not None and new_global_hash:
                entry["synced_from_global_hash"] = new_global_hash
                entry.pop("synced_from_pool_hash", None)
                entry["last_synced_at"] = sync_timestamp

        mutate_json(
            get_workspace_skill_manifest_path(workspace_dir),
            default_workspace_manifest(),
            _update_ws,
        )

        return {
            "success": True,
            "mode": "promoted",
            "name": skill_name,
            "global_hash": new_global_hash,
            "previous_global_hash": global_hash,
            "created": not global_exists,
            "propagated": False,
        }

    def push_workspace_skill_to_global(
        self,
        workspace_dir: Path,
        skill_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Backward-compatible alias for agent skill promotion."""
        return self.promote_workspace_skill_to_global(
            workspace_dir,
            skill_name,
            **kwargs,
        )

    @staticmethod
    def _check_download_conflict(
        entry: dict[str, Any],
        existing: dict[str, Any] | None,
        final_name: str,
        workspace_identity: dict[str, str],
        workspace_dir: Path,
    ) -> dict[str, Any] | None:
        """Return a conflict dict if download should be blocked."""
        if not existing:
            return None
        ws_id = workspace_identity["workspace_id"]
        ws_name = workspace_identity["workspace_name"]
        if (
            entry.get("source") == "builtin"
            and existing.get("source") == "builtin"
        ):
            global_ver = entry.get("version_text", "")
            ws_ver = (existing.get("metadata") or {}).get(
                "version_text",
                "",
            )
            if global_ver and ws_ver and global_ver == ws_ver:
                global_lang = str(
                    entry.get("builtin_language", "") or "",
                )
                ws_lang = str(
                    existing.get("builtin_language", "") or "",
                )
                if global_lang and ws_lang and global_lang != ws_lang:
                    return {
                        "success": False,
                        "reason": "language_switch",
                        "workspace_id": ws_id,
                        "workspace_name": ws_name,
                        "skill_name": final_name,
                        "source_language": global_lang,
                        "current_language": ws_lang,
                    }
                if global_lang and not ws_lang:
                    global_md = (
                        safe_skill_dir(get_global_skills_dir(), final_name)
                        / "SKILL.md"
                    )
                    ws_md = (
                        safe_skill_dir(
                            get_workspace_skills_dir(workspace_dir),
                            final_name,
                        )
                        / "SKILL.md"
                    )
                    try:
                        global_hash = hashlib.sha256(
                            read_text_file_with_encoding_fallback(
                                global_md,
                            ).encode("utf-8"),
                        ).hexdigest()
                        ws_hash = hashlib.sha256(
                            read_text_file_with_encoding_fallback(
                                ws_md,
                            ).encode("utf-8"),
                        ).hexdigest()
                    except OSError:
                        global_hash = ws_hash = ""
                    if global_hash and ws_hash and global_hash != ws_hash:
                        return {
                            "success": False,
                            "reason": "language_switch",
                            "workspace_id": ws_id,
                            "workspace_name": ws_name,
                            "skill_name": final_name,
                            "source_language": global_lang,
                            "current_language": ws_lang,
                        }
                return {
                    "success": True,
                    "mode": "unchanged",
                    "name": final_name,
                    "workspace_id": ws_id,
                    "workspace_name": ws_name,
                    "backfill_language": global_lang or "",
                }
            return {
                "success": False,
                "reason": "builtin_upgrade",
                "workspace_id": ws_id,
                "workspace_name": ws_name,
                "skill_name": final_name,
                "source_version_text": global_ver,
                "current_version_text": ws_ver,
            }
        return {
            "success": False,
            "reason": "conflict",
            "workspace_id": ws_id,
            "workspace_name": ws_name,
            "suggested_name": suggest_conflict_name(final_name),
        }

    @staticmethod
    def _backfill_workspace_language(
        workspace_dir: Path,
        skill_name: str,
        language: str,
    ) -> None:
        """Write ``builtin_language`` into an existing workspace entry."""

        def _patch(payload: dict[str, Any]) -> None:
            ws_entry = payload.get("skills", {}).get(skill_name)
            if ws_entry is not None:
                ws_entry["builtin_language"] = language

        mutate_json(
            get_workspace_skill_manifest_path(workspace_dir),
            default_workspace_manifest(),
            _patch,
        )

    def download_to_workspace(
        self,
        skill_name: str,
        workspace_dir: Path,
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        try:
            skill_name = normalize_skill_dir_name(skill_name)
        except SkillsError:
            return {"success": False, "reason": "not_found"}
        manifest = read_global_skills_manifest()
        entry = manifest.get("skills", {}).get(skill_name)
        if entry is None:
            return {"success": False, "reason": "not_found"}

        source_dir = resolve_global_skill_dir(skill_name)
        if source_dir is None:
            return {"success": False, "reason": "not_found"}
        final_name = normalize_skill_dir_name(skill_name)
        target_dir = safe_skill_dir(
            get_workspace_skills_dir(workspace_dir),
            final_name,
        )
        workspace_manifest = read_skill_manifest(workspace_dir)
        existing = workspace_manifest.get("skills", {}).get(final_name)
        workspace_identity = get_workspace_identity(workspace_dir)
        if not overwrite:
            conflict = self._check_download_conflict(
                entry,
                existing,
                final_name,
                workspace_identity,
                workspace_dir,
            )
            if conflict is not None:
                if conflict.get("backfill_language"):
                    self._backfill_workspace_language(
                        workspace_dir,
                        final_name,
                        conflict["backfill_language"],
                    )
                return conflict

        target_dir.parent.mkdir(parents=True, exist_ok=True)
        with staged_skill_dir(final_name) as staged_dir:
            copy_skill_dir(source_dir, staged_dir)
            scan_skill_dir_or_raise(staged_dir, final_name)
            copy_skill_dir(staged_dir, target_dir)

        global_config_data = entry.get("config") or {}
        global_tags = entry.get("tags")
        global_installed_from = str(entry.get("installed_from", "") or "")
        global_skill_hash = compute_skill_content_hash(source_dir)
        from datetime import datetime, timezone

        sync_timestamp = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        def _update(payload: dict[str, Any]) -> None:
            payload.setdefault("skills", {})
            prior = payload["skills"].get(final_name) or {}
            metadata = build_skill_metadata(
                final_name,
                target_dir,
                source="builtin"
                if entry.get("source") == "builtin"
                else "customized",
                protected=False,
            )
            ws_entry: dict[str, Any] = {
                "enabled": bool(prior.get("enabled", True)),
                "channels": prior.get("channels") or ["all"],
                "source": metadata["source"],
                "installed_from": global_installed_from,
                "config": prior["config"]
                if "config" in prior
                else global_config_data,
                "metadata": metadata,
                "requirements": metadata["requirements"],
                "updated_at": metadata["updated_at"],
            }
            global_lang = str(
                entry.get("builtin_language", "") or "",
            )
            if entry.get("source") == "builtin" and global_lang:
                ws_entry["builtin_language"] = global_lang
            prior_tags = prior.get("tags")
            if prior_tags is not None:
                ws_entry["tags"] = prior_tags
            elif global_tags is not None:
                ws_entry["tags"] = global_tags
            # Record sync state for bidirectional sync tracking
            if global_skill_hash:
                ws_entry["synced_from_global_hash"] = global_skill_hash
                ws_entry["last_synced_at"] = sync_timestamp
            payload["skills"][final_name] = ws_entry

        mutate_json(
            get_workspace_skill_manifest_path(workspace_dir),
            default_workspace_manifest(),
            _update,
        )
        return {
            "success": True,
            "name": final_name,
            "workspace_id": workspace_identity["workspace_id"],
            "workspace_name": workspace_identity["workspace_name"],
        }

    def preflight_download_to_workspace(
        self,
        skill_name: str,
        workspace_dir: Path,
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        manifest = read_global_skills_manifest()
        entry = manifest.get("skills", {}).get(skill_name)
        if entry is None:
            return {"success": False, "reason": "not_found"}

        final_name = normalize_skill_dir_name(skill_name)
        workspace_manifest = read_skill_manifest(workspace_dir)
        existing = workspace_manifest.get("skills", {}).get(final_name)
        workspace_identity = get_workspace_identity(workspace_dir)
        if not overwrite:
            conflict = self._check_download_conflict(
                entry,
                existing,
                final_name,
                workspace_identity,
                workspace_dir,
            )
            if conflict is not None:
                return conflict
        return {
            "success": True,
            "workspace_id": workspace_identity["workspace_id"],
            "workspace_name": workspace_identity["workspace_name"],
            "name": final_name,
        }

    def get_sync_status(
        self,
        workspace_dir: Path,
    ) -> dict[str, Any]:
        """Return sync status for all skills in a workspace.

        Returns a dict mapping skill names to their sync state:
        - ``in_global``: whether the skill exists in global skills
        - ``global_hash``: current global skill hash
        - ``agent_hash``: current workspace skill hash
        - ``last_synced_hash``: hash at last sync point
        - ``sync_status``: one of synced, outdated_global, outdated_agent,
          conflict, not_synced
        - ``last_synced_at``: ISO timestamp of last sync
        """
        ws_manifest = read_skill_manifest(workspace_dir)
        global_manifest = read_global_skills_manifest()
        global_skills_data = global_manifest.get("skills", {})
        ws_skills = ws_manifest.get("skills", {})

        result: dict[str, dict[str, Any]] = {}
        for skill_name, ws_entry in ws_skills.items():
            if not isinstance(ws_entry, dict):
                continue

            global_entry = global_skills_data.get(skill_name)
            in_global = global_entry is not None

            agent_hash = compute_workspace_skill_hash(
                workspace_dir,
                skill_name,
            )
            synced_hash = _get_synced_hash(ws_entry)
            last_synced_at = str(ws_entry.get("last_synced_at", "") or "")

            global_hash = ""
            if in_global:
                global_dir = resolve_global_skill_dir(skill_name)
                if global_dir is not None:
                    global_hash = compute_skill_content_hash(global_dir)

            # Determine sync status
            if not synced_hash:
                sync_status = "not_synced"
            elif not global_hash:
                # Global skill was deleted
                sync_status = "not_synced"
            else:
                global_at_base = bool(
                    global_dir and skill_hash_matches(global_dir, synced_hash)
                )
                agent_dir = (
                    get_workspace_skills_dir(workspace_dir) / skill_name
                )
                agent_at_base = skill_hash_matches(agent_dir, synced_hash)
                if global_hash == agent_hash:
                    sync_status = "synced"
                elif global_at_base and agent_at_base:
                    sync_status = "synced"
                elif not global_at_base and not agent_at_base:
                    sync_status = "conflict"
                elif not global_at_base:
                    sync_status = "outdated_global"
                else:
                    sync_status = "outdated_agent"

            result[skill_name] = {
                "in_global": in_global,
                "global_hash": global_hash,
                "agent_hash": agent_hash,
                "last_synced_hash": synced_hash,
                "sync_status": sync_status,
                "last_synced_at": last_synced_at,
            }

        return {"skills": result}

    def sync_skill_to_all_workspaces(
        self,
        skill_name: str,
    ) -> dict[str, Any]:
        """Push a global skill's content to every workspace that has it installed.

        Uses ``overwrite=True`` so the workspace SKILL.md is replaced with the
        global version.  Per-agent runtime state (``enabled`` / ``channels`` /
        ``config``) is preserved by ``download_to_workspace``.
        """
        try:
            skill_name = normalize_skill_dir_name(skill_name)
        except SkillsError:
            return {"success": False, "reason": "not_found"}

        synced: list[str] = []
        failed: list[dict[str, str]] = []
        for ws in list_workspaces():
            ws_dir = Path(ws["workspace_dir"])
            ws_manifest = read_skill_manifest(ws_dir)
            if skill_name not in (ws_manifest.get("skills") or {}):
                continue
            try:
                result = self.download_to_workspace(
                    skill_name=skill_name,
                    workspace_dir=ws_dir,
                    overwrite=True,
                )
                if result.get("success"):
                    synced.append(ws.get("agent_id") or ws.get("agent_name") or str(ws_dir))
                else:
                    failed.append({
                        "agent": ws.get("agent_id") or str(ws_dir),
                        "reason": str(result.get("reason", "unknown")),
                    })
            except Exception as exc:
                failed.append({
                    "agent": ws.get("agent_id") or str(ws_dir),
                    "reason": str(exc),
                })
        return {"synced": synced, "failed": failed}

    def remove_skill_from_all_workspaces(
        self,
        skill_name: str,
    ) -> dict[str, Any]:
        """Delete a skill from every workspace (used after global skills deletion)."""
        try:
            skill_name = normalize_skill_dir_name(skill_name)
        except SkillsError:
            return {"success": False, "reason": "not_found"}

        removed: list[str] = []
        failed: list[dict[str, str]] = []
        for ws in list_workspaces():
            ws_dir = Path(ws["workspace_dir"])
            ws_manifest = read_skill_manifest(ws_dir)
            ws_skills = ws_manifest.get("skills") or {}
            if skill_name not in ws_skills:
                continue
            entry = ws_skills[skill_name]
            # Force-disable before deletion (delete_skill requires disabled)
            if isinstance(entry, dict) and entry.get("enabled"):
                def _disable(payload: dict[str, Any]) -> None:
                    e = payload.get("skills", {}).get(skill_name)
                    if isinstance(e, dict):
                        e["enabled"] = False
                try:
                    mutate_json(
                        get_workspace_skill_manifest_path(ws_dir),
                        default_workspace_manifest(),
                        _disable,
                    )
                except Exception:
                    pass
            try:
                from .workspace_service import SkillService
                ok = SkillService(ws_dir).delete_skill(skill_name)
                if ok:
                    removed.append(ws.get("agent_id") or ws.get("agent_name") or str(ws_dir))
                else:
                    failed.append({
                        "agent": ws.get("agent_id") or str(ws_dir),
                        "reason": "delete_skill returned False",
                    })
            except Exception as exc:
                failed.append({
                    "agent": ws.get("agent_id") or str(ws_dir),
                    "reason": str(exc),
                })
        return {"removed": removed, "failed": failed}


def _resolve_auto_update_targets(
    skill_name: str,
    entry: dict[str, Any],
    workspaces: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Resolve which workspaces an auto-update skill should sync to."""
    explicit = entry.get("auto_update_targets")
    if isinstance(explicit, list) and explicit:
        wanted = {str(agent_id) for agent_id in explicit}
        return [ws for ws in workspaces if ws.get("agent_id") in wanted]

    targets: list[dict[str, str]] = []
    for ws in workspaces:
        try:
            ws_manifest = read_skill_manifest(Path(ws["workspace_dir"]))
        except Exception:
            continue
        if skill_name in (ws_manifest.get("skills") or {}):
            targets.append(ws)
    return targets


def _push_auto_update_skill(
    service: GlobalSkillService,
    name: str,
    targets: list[dict[str, str]],
) -> dict[str, list[str]]:
    """Push one global skill into each target workspace.

    Before overwriting, checks if the agent has local changes (hash differs
    from ``synced_from_global_hash``).  If so, the skill is skipped for that
    workspace and added to a ``conflicts`` list.

    Returns
    -------
    ``{"ok": [...], "failed": [...], "conflicts": [...]}``
    """
    ok: list[str] = []
    failed: list[str] = []
    conflicts: list[str] = []
    for ws in targets:
        label = str(ws.get("agent_name") or ws.get("agent_id", "") or "")
        ws_dir = Path(ws["workspace_dir"])
        # Check for agent-side changes before pushing
        ws_manifest = read_skill_manifest(ws_dir)
        ws_entry = ws_manifest.get("skills", {}).get(name)
        if isinstance(ws_entry, dict):
            synced_hash = _get_synced_hash(ws_entry)
            if synced_hash:
                agent_dir = get_workspace_skills_dir(ws_dir) / name
                if not skill_hash_matches(agent_dir, synced_hash):
                    # Agent has local changes — skip auto-sync, flag conflict
                    conflicts.append(label)
                    logger.info(
                        "autoupdate: skipping '%s' in workspace '%s' "
                        "(agent has local changes)",
                        name,
                        ws.get("agent_id", ""),
                    )
                    continue
        try:
            result = service.download_to_workspace(
                skill_name=name,
                workspace_dir=ws_dir,
                overwrite=True,
            )
        except Exception:
            failed.append(label)
            logger.warning(
                "autoupdate: failed to sync '%s' to workspace '%s'",
                name,
                ws.get("agent_id", ""),
                exc_info=True,
            )
            continue
        if result.get("success"):
            ok.append(label)
            logger.info(
                "autoupdate: synced '%s' -> workspace '%s'",
                name,
                label,
            )
        else:
            failed.append(label)
            logger.warning(
                "autoupdate: could not sync '%s' to workspace '%s' (%s)",
                name,
                ws.get("agent_id", ""),
                result.get("reason", "unknown"),
            )
    return {"ok": ok, "failed": failed, "conflicts": conflicts}


def _detect_changed_auto_update_skills(
    entries: dict[str, Any],
    skill_name: str | None,
) -> tuple[list[tuple[str, dict[str, Any], str]], int]:
    """Cheap detection pass for ``run_global_auto_update_sync``.

    Reads each enabled skill directory to build a stable content hash.
    """
    changed: list[tuple[str, dict[str, Any], str]] = []
    checked = 0
    for name, raw_entry in entries.items():
        entry = raw_entry if isinstance(raw_entry, dict) else {}
        if not entry.get("auto_update"):
            continue
        if skill_name is not None and name != skill_name:
            continue
        checked += 1
        skill_dir = resolve_global_skill_dir(name)
        if skill_dir is None:
            continue
        current_hash = compute_skill_content_hash(skill_dir)
        if not current_hash:
            continue
        prior_hash = str(entry.get("auto_update_synced_hash", "") or "")
        if current_hash != prior_hash:
            changed.append((name, entry, current_hash))
    return changed, checked


def run_global_auto_update_sync(
    skill_name: str | None = None,
) -> dict[str, Any]:
    """Sync changed auto-update global skills into their target workspaces."""
    manifest = read_global_skills_manifest()
    entries = manifest.get("skills", {})
    changed, checked = _detect_changed_auto_update_skills(entries, skill_name)
    if not changed:
        return {"synced": [], "failed": [], "conflicts": [], "checked": checked}

    workspaces = list_workspaces()
    service = GlobalSkillService()
    new_hashes: dict[str, str] = {}
    synced: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    conflict_list: list[dict[str, Any]] = []

    for name, entry, current_hash in changed:
        targets = _resolve_auto_update_targets(name, entry, workspaces)
        logger.info(
            "autoupdate: '%s' content changed; syncing %d workspace(s)",
            name,
            len(targets),
        )
        push = _push_auto_update_skill(service, name, targets)
        if push.get("conflicts"):
            conflict_list.append({
                "skill": name,
                "agents": push["conflicts"],
            })
        if push["failed"]:
            failed.append({"skill": name, "agents": push["failed"]})
        # Only stamp hash if ALL targets synced successfully (no conflicts)
        if not push["failed"] and not push.get("conflicts"):
            new_hashes[name] = current_hash
            synced.append({"skill": name, "agents": push["ok"]})

    if new_hashes:

        def _stamp(payload: dict[str, Any]) -> None:
            skills = payload.setdefault("skills", {})
            for synced_name, synced_hash in new_hashes.items():
                entry = skills.get(synced_name)
                if isinstance(entry, dict):
                    entry["auto_update_synced_hash"] = synced_hash

        mutate_json(
            get_global_skill_manifest_path(),
            default_global_skills_manifest(),
            _stamp,
        )

    return {
        "synced": synced,
        "failed": failed,
        "conflicts": conflict_list,
        "checked": checked,
    }
