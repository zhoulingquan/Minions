# -*- coding: utf-8 -*-
"""Workspace and global-skills APIs."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import shutil
import tempfile
import threading
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from minions.exceptions import (
    AppBaseException,
)

from ...agents.skill_system.hub import (
    SkillImportCancelled,
    search_hub_skills,
    import_global_skill_from_hub as import_global_skill_from_hub_service,
    install_skill_from_hub,
)
from ...agents.skill_system import (
    SkillConflictError,
    GlobalSkillService,
    SkillService,
    run_global_auto_update_sync,
)
from ...agents.skill_system.models import SkillInfo
from ...agents.skill_system.registry import (
    BUILTIN_SKILL_LANGUAGES,
    get_global_builtin_sync_status,
    get_global_builtin_update_notice,
    import_builtin_skills,
    list_builtin_import_candidates,
    list_workspaces,
    reconcile_global_skills_manifest,
    reconcile_workspace_manifest,
    update_single_builtin,
)
from ...agents.skill_system.store import (
    default_global_skills_manifest,
    default_workspace_manifest,
    get_global_skill_manifest_path,
    get_skill_mtime,
    get_global_skills_dir,
    get_workspace_skill_manifest_path,
    get_workspace_skills_dir,
    mutate_json,
    normalize_skill_manifest_entry,
    read_skill_from_dir,
    read_skill_manifest,
    read_global_skills_manifest,
    resolve_global_skill_dir,
    suggest_conflict_name,
)
from ...security.skill_scanner import SkillScanError
from ..msg_store import append_event as append_msg_event
from ..utils import check_upload_size, schedule_agent_reload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["skills"])

MAX_TAGS = 8
MAX_TAG_LENGTH = 16

# Source type for skill auto-update msg events.
AUTO_UPDATE_MSG_SOURCE = "skill_autoupdate"


async def post_auto_update_msg(
    result: dict[str, Any] | None,
) -> None:
    """Post one msg notification summarising an auto-update run.

    A single sync run (startup / refresh / enable) becomes one event listing
    the synced skills plus any failures. Severity is ``error`` when any skill
    failed, otherwise ``info``. Nothing is posted when no skill propagated.
    """
    if not result:
        return
    synced = [
        item for item in (result.get("synced") or []) if item.get("agents")
    ]
    failed = result.get("failed") or []
    conflicts = result.get("conflicts") or []
    if not synced and not failed and not conflicts:
        return

    synced_names = [str(item["skill"]) for item in synced]
    failed_names = [str(item["skill"]) for item in failed]
    conflict_names = [str(item["skill"]) for item in conflicts]
    has_failure = bool(failed_names) or bool(conflict_names)

    lines: list[str] = []
    for item in synced:
        agents = ", ".join(item.get("agents") or [])
        lines.append(f"{item['skill']} → {agents}")
    for item in failed:
        agents = ", ".join(item.get("agents") or []) or "unknown"
        lines.append(f"{item['skill']} (failed) → {agents}")
    for item in conflicts:
        agents = ", ".join(item.get("agents") or []) or "unknown"
        lines.append(f"{item['skill']} (conflict) → {agents}")

    if has_failure:
        title = (
            f"Auto-update: {len(synced_names)} updated, "
            f"{len(failed_names)} failed, {len(conflict_names)} conflicts"
        )
    else:
        title = f"Auto-update: {len(synced_names)} skill(s) updated"

    await append_msg_event(
        agent_id="default",
        source_type=AUTO_UPDATE_MSG_SOURCE,
        source_id="",
        event_type="auto_update",
        status="error" if has_failure else "success",
        severity="error" if has_failure else "info",
        title=title,
        body="; ".join(lines),
        payload={
            "synced": synced,
            "failed": failed,
            "conflicts": conflicts,
        },
    )


async def _follow_auto_update(skill_name: str | None = None) -> None:
    """Propagate + notify after any global-skills-content change.

    Called by the content-mutating endpoints (edit / rename / builtin update /
    builtin import) so auto-update skills sync to their workspaces immediately
    instead of waiting for the next refresh or startup. The hash gate means
    only skills that actually changed are propagated.
    """
    try:
        result = await asyncio.to_thread(
            run_global_auto_update_sync,
            skill_name=skill_name,
        )
        await post_auto_update_msg(result)
    except Exception:
        logger.warning("auto-update follow-up failed", exc_info=True)


def _scan_error_payload(exc: SkillScanError) -> dict[str, Any]:
    """Normalize scanner exceptions into a stable API payload.

    Example response body:
        {
            "type": "security_scan_failed",
            "skill_name": "blocked_skill",
            "max_severity": "high",
            "findings": [...]
        }
    """
    result = exc.result
    return {
        "type": "security_scan_failed",
        "detail": str(exc),
        "skill_name": result.skill_name,
        "max_severity": result.max_severity.value,
        "findings": [
            {
                "severity": f.severity.value,
                "title": f.title,
                "description": f.description,
                "file_path": f.file_path,
                "line_number": f.line_number,
                "rule_id": f.rule_id,
            }
            for f in result.findings
        ],
    }


def _scan_error_response(exc: SkillScanError) -> JSONResponse:
    """Build a 422 JSON response for skill scan failures.

    Returns a JSONResponse so callers receive structured scan
    details rather than a bare HTTP error.
    """
    return JSONResponse(
        status_code=422,
        content=_scan_error_payload(exc),
    )


class SkillSpec(SkillInfo):
    enabled: bool = False
    channels: list[str] = Field(default_factory=lambda: ["all"])
    tags: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    last_updated: str = ""
    installed_from: str = ""
    in_global: bool = False
    sync_status: str = "not_synced"
    global_hash: str = ""
    agent_hash: str = ""
    last_synced_hash: str = ""
    last_synced_at: str = ""


class GlobalSkillSpec(SkillInfo):
    protected: bool = False
    external: bool = False
    external_path: str = ""
    commit_text: str = ""
    sync_status: str = ""
    latest_version_text: str = ""
    builtin_language: str = ""
    available_builtin_languages: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    last_updated: str = ""
    installed_from: str = ""
    auto_update: bool = False
    auto_update_targets: list[str] | None = None


class WorkspaceSkillSummary(BaseModel):
    agent_id: str
    agent_name: str = ""
    workspace_dir: str
    skills: list[SkillSpec] = Field(default_factory=list)


class HubSkillSpec(BaseModel):
    slug: str
    name: str
    description: str = ""
    version: str = ""
    source_url: str = ""
    author: str = ""
    icon_url: str = ""


class BuiltinImportSpec(BaseModel):
    name: str
    description: str = ""
    version_text: str = ""
    current_version_text: str = ""
    current_source: str = ""
    current_language: str = ""
    available_languages: list[str] = Field(default_factory=list)
    languages: dict[str, dict[str, Any]] = Field(default_factory=dict)
    status: str = ""


class BuiltinRemovedSpec(BaseModel):
    name: str
    description: str = ""
    current_version_text: str = ""
    current_source: str = ""


class BuiltinUpdateNotice(BaseModel):
    fingerprint: str = ""
    has_updates: bool = False
    total_changes: int = 0
    actionable_skill_names: list[str] = Field(default_factory=list)
    added: list[BuiltinImportSpec] = Field(default_factory=list)
    missing: list[BuiltinImportSpec] = Field(default_factory=list)
    updated: list[BuiltinImportSpec] = Field(default_factory=list)
    removed: list[BuiltinRemovedSpec] = Field(default_factory=list)


class BuiltinImportSelection(BaseModel):
    skill_name: str
    language: str = ""


class ImportBuiltinRequest(BaseModel):
    skill_names: list[str] = Field(
        default_factory=list,
    )  # Deprecated: use imports
    imports: list[BuiltinImportSelection] = Field(default_factory=list)
    overwrite_conflicts: bool = False


class UpdateBuiltinRequest(BaseModel):
    language: str = ""


class CreateSkillRequest(BaseModel):
    name: str
    content: str
    references: dict[str, Any] | None = None
    scripts: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    enable: bool = True


class UploadToGlobalRequest(BaseModel):
    workspace_id: str
    skill_name: str
    overwrite: bool = False
    preview_only: bool = False


class GlobalDownloadTarget(BaseModel):
    workspace_id: str


class DownloadFromGlobalRequest(BaseModel):
    skill_name: str
    targets: list[GlobalDownloadTarget] = Field(default_factory=list)
    all_workspaces: bool = False
    overwrite: bool = False
    preview_only: bool = False


class SkillConfigRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class AutoUpdateRequest(BaseModel):
    enabled: bool
    targets: list[str] | None = None


class SaveGlobalSkillRequest(BaseModel):
    name: str
    content: str
    source_name: str | None = None
    config: dict[str, Any] | None = None
    overwrite: bool = False


class SaveSkillRequest(BaseModel):
    name: str
    content: str
    source_name: str | None = None
    config: dict[str, Any] | None = None
    overwrite: bool = False


class HubInstallRequest(BaseModel):
    bundle_url: str = Field(..., description="Skill URL")
    version: str = Field(default="", description="Optional version tag")
    enable: bool = Field(default=True, description="Enable after import")
    target_name: str = Field(default="", description="Optional renamed skill")


class HubInstallTaskStatus(str, Enum):
    PENDING = "pending"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HubInstallTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    bundle_url: str
    version: str = ""
    enable: bool = True
    status: HubInstallTaskStatus = HubInstallTaskStatus.PENDING
    error: str | None = None
    result: dict[str, Any] | None = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


_hub_install_tasks: dict[str, HubInstallTask] = {}
_hub_install_runtime_tasks: dict[str, asyncio.Task] = {}
_hub_install_cancel_events: dict[str, threading.Event] = {}
_hub_install_lock = asyncio.Lock()

_ALLOWED_ZIP_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",
}


def _workspace_dir_for_agent(agent_id: str) -> Path:
    for workspace in list_workspaces():
        if workspace["agent_id"] == agent_id:
            return Path(workspace["workspace_dir"])
    raise HTTPException(
        status_code=404,
        detail=f"Workspace '{agent_id}' not found",
    )


def _snapshot_workspace_skill(
    workspace_dir: Path,
    skill_name: str,
) -> dict[str, Any]:
    manifest = read_skill_manifest(workspace_dir)
    entry = manifest.get("skills", {}).get(skill_name)
    skill_dir = workspace_dir / "skills" / skill_name
    backup_dir: Path | None = None
    if skill_dir.exists():
        backup_root = Path(
            tempfile.mkdtemp(prefix=f"minions_skill_rollback_{skill_name}_"),
        )
        backup_dir = backup_root / skill_name
        shutil.copytree(skill_dir, backup_dir)
    return {
        "workspace_dir": workspace_dir,
        "skill_name": skill_name,
        "entry": copy.deepcopy(entry) if entry is not None else None,
        "backup_dir": backup_dir,
    }


def _restore_workspace_skill(snapshot: dict[str, Any]) -> None:
    workspace_dir = Path(snapshot["workspace_dir"])
    skill_name = str(snapshot["skill_name"])
    skill_dir = workspace_dir / "skills" / skill_name
    backup_dir = snapshot.get("backup_dir")
    entry = snapshot.get("entry")

    if skill_dir.exists():
        shutil.rmtree(skill_dir)
    if backup_dir is not None and Path(backup_dir).exists():
        shutil.copytree(Path(backup_dir), skill_dir)

    def _restore(payload: dict[str, Any]) -> None:
        payload.setdefault("skills", {})
        if entry is None:
            payload["skills"].pop(skill_name, None)
            return
        payload["skills"][skill_name] = copy.deepcopy(entry)

    mutate_json(
        get_workspace_skill_manifest_path(workspace_dir),
        default_workspace_manifest(),
        _restore,
    )
    reconcile_workspace_manifest(workspace_dir)
    if backup_dir is not None:
        shutil.rmtree(Path(backup_dir).parent, ignore_errors=True)


async def _request_workspace_dir(request: Request) -> Path:
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    return Path(workspace.workspace_dir)


async def _hub_task_set_status(
    task_id: str,
    status: HubInstallTaskStatus,
    *,
    error: str | None = None,
    result: dict[str, Any] | None = None,
) -> None:
    async with _hub_install_lock:
        task = _hub_install_tasks.get(task_id)
        if task is None:
            return
        task.status = status
        task.updated_at = time.time()
        if error is not None:
            task.error = error
        if result is not None:
            task.result = result


async def _hub_task_get(task_id: str) -> HubInstallTask | None:
    async with _hub_install_lock:
        return _hub_install_tasks.get(task_id)


async def _hub_task_register_runtime(task_id: str, task: asyncio.Task) -> None:
    async with _hub_install_lock:
        _hub_install_runtime_tasks[task_id] = task


async def _hub_task_pop_runtime(task_id: str) -> asyncio.Task | None:
    async with _hub_install_lock:
        return _hub_install_runtime_tasks.pop(task_id, None)


async def _read_validated_zip_upload(file: UploadFile) -> bytes:
    if file.content_type and file.content_type not in _ALLOWED_ZIP_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Expected a zip file, "
                f"got content-type: {file.content_type}"
            ),
        )

    data = await file.read()
    check_upload_size(data)
    return data


def _cleanup_imported_skill(workspace_dir: Path, skill_name: str) -> None:
    if not skill_name:
        return
    try:
        skill_service = SkillService(workspace_dir)
        skill_service.disable_skill(skill_name)
        skill_service.delete_skill(skill_name)
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "Cleanup after cancelled import failed for '%s': %s",
            skill_name,
            exc,
        )


async def _run_hub_install_task(
    *,
    task_id: str,
    workspace_dir: Path,
    body: HubInstallRequest,
    cancel_event: threading.Event,
) -> None:
    await _hub_task_set_status(task_id, HubInstallTaskStatus.IMPORTING)
    imported_skill_name: str | None = None
    try:
        result = await install_skill_from_hub(
            workspace_dir=workspace_dir,
            bundle_url=body.bundle_url,
            version=body.version,
            enable=body.enable,
            target_name=body.target_name,
            cancel_checker=cancel_event.is_set,
        )
        imported_skill_name = result.name
        if cancel_event.is_set():
            _cleanup_imported_skill(workspace_dir, result.name)
            await _hub_task_set_status(
                task_id,
                HubInstallTaskStatus.CANCELLED,
                result={
                    "installed": False,
                    "name": result.name,
                    "enabled": False,
                    "source_url": result.source_url,
                    "installed_from": result.installed_from,
                },
            )
            return
        await _hub_task_set_status(
            task_id,
            HubInstallTaskStatus.COMPLETED,
            result={
                "installed": True,
                "name": result.name,
                "enabled": result.enabled,
                "source_url": result.source_url,
                "installed_from": result.installed_from,
            },
        )
    except SkillImportCancelled:
        if imported_skill_name:
            _cleanup_imported_skill(workspace_dir, imported_skill_name)
        await _hub_task_set_status(task_id, HubInstallTaskStatus.CANCELLED)
    except SkillScanError as exc:
        await _hub_task_set_status(
            task_id,
            HubInstallTaskStatus.FAILED,
            error=str(exc),
            result=_scan_error_payload(exc),
        )
    except SkillConflictError as exc:
        await _hub_task_set_status(
            task_id,
            HubInstallTaskStatus.FAILED,
            error=str(exc),
            result=exc.detail,
        )
    except (ValueError, AppBaseException) as exc:
        await _hub_task_set_status(
            task_id,
            HubInstallTaskStatus.FAILED,
            error=str(exc),
        )
    except RuntimeError as exc:
        await _hub_task_set_status(
            task_id,
            HubInstallTaskStatus.FAILED,
            error=str(exc),
        )
    except Exception as exc:  # pragma: no cover
        await _hub_task_set_status(
            task_id,
            HubInstallTaskStatus.FAILED,
            error=f"Skill hub import failed: {exc}",
        )
    finally:
        await _hub_task_pop_runtime(task_id)


def _build_workspace_skill_specs(workspace_dir: Path) -> list[SkillSpec]:
    manifest = read_skill_manifest(workspace_dir)
    entries = manifest.get("skills", {})
    skill_root = get_workspace_skills_dir(workspace_dir)
    try:
        sync_details = GlobalSkillService().get_sync_status(
            workspace_dir,
        ).get("skills", {})
    except Exception:
        logger.warning(
            "Failed to build workspace skill sync status for '%s'",
            workspace_dir,
            exc_info=True,
        )
        sync_details = {}
    specs: list[SkillSpec] = []
    for skill_name, raw_entry in sorted(entries.items()):
        entry = normalize_skill_manifest_entry(raw_entry)
        if raw_entry not in (None, entry):
            logger.warning(
                "Skipping malformed workspace skill entry '%s' in manifest",
                skill_name,
            )
        try:
            source = entry.get("source", "customized")
            skill_dir = skill_root / skill_name
            skill = read_skill_from_dir(skill_dir, source)
            if skill is None:
                continue
            dump = skill.model_dump()
            dump["tags"] = entry.get("tags") or []
            sync = sync_details.get(skill_name) or {}
            specs.append(
                SkillSpec(
                    **dump,
                    enabled=entry.get("enabled", False),
                    channels=entry.get("channels") or ["all"],
                    config=entry.get("config") or {},
                    last_updated=get_skill_mtime(skill_dir),
                    installed_from=str(
                        entry.get("installed_from", "") or "",
                    ),
                    in_global=bool(sync.get("in_global", False)),
                    sync_status=str(
                        sync.get("sync_status", "not_synced")
                        or "not_synced",
                    ),
                    global_hash=str(sync.get("global_hash", "") or ""),
                    agent_hash=str(sync.get("agent_hash", "") or ""),
                    last_synced_hash=str(
                        sync.get("last_synced_hash", "") or "",
                    ),
                    last_synced_at=str(
                        sync.get("last_synced_at", "") or "",
                    ),
                ),
            )
        except Exception:
            logger.warning(
                "Skipping workspace skill '%s': failed to build spec",
                skill_name,
                exc_info=True,
            )
    return specs


def _build_global_skill_specs() -> list[GlobalSkillSpec]:
    manifest = read_global_skills_manifest()
    entries = manifest.get("skills", {})
    global_dir = get_global_skills_dir()
    sync_info = get_global_builtin_sync_status(global_skills_data=entries)
    specs: list[GlobalSkillSpec] = []
    for skill_name, raw_entry in sorted(entries.items()):
        entry = normalize_skill_manifest_entry(raw_entry)
        if raw_entry not in (None, entry):
            logger.warning(
                "Skipping malformed global skill entry '%s' in manifest",
                skill_name,
            )
        try:
            source = entry.get("source", "customized")
            skill_dir = resolve_global_skill_dir(skill_name) or (
                global_dir / skill_name
            )
            skill = read_skill_from_dir(skill_dir, source)
            if skill is None:
                continue
            info = sync_info.get(skill_name, {})
            dump = skill.model_dump(exclude={"version_text"})
            dump["tags"] = entry.get("tags") or []
            is_external = bool(entry.get("external", False))
            specs.append(
                GlobalSkillSpec(
                    **dump,
                    protected=bool(entry.get("protected", False)),
                    external=is_external,
                    external_path=str(skill_dir) if is_external else "",
                    version_text=str(entry.get("version_text", "") or ""),
                    commit_text=str(entry.get("commit_text", "") or ""),
                    sync_status=str(info.get("sync_status", "") or ""),
                    latest_version_text=str(
                        info.get("latest_version_text", "") or "",
                    ),
                    builtin_language=str(
                        entry.get("builtin_language", "") or "",
                    ),
                    available_builtin_languages=[
                        str(language)
                        for language in (
                            info.get("available_languages")
                            or entry.get("available_builtin_languages")
                            or []
                        )
                        if str(language)
                    ],
                    config=entry.get("config") or {},
                    last_updated=get_skill_mtime(skill_dir),
                    installed_from=str(
                        entry.get("installed_from", "") or "",
                    ),
                    auto_update=bool(entry.get("auto_update", False)),
                    auto_update_targets=(
                        list(entry["auto_update_targets"])
                        if isinstance(
                            entry.get("auto_update_targets"),
                            list,
                        )
                        else None
                    ),
                ),
            )
        except Exception:
            logger.warning(
                "Skipping global skill '%s': failed to build spec",
                skill_name,
                exc_info=True,
            )
    return specs


@router.get("")
async def list_skills(request: Request) -> list[SkillSpec]:
    workspace_dir = await _request_workspace_dir(request)
    return _build_workspace_skill_specs(workspace_dir)


@router.post("/refresh")
async def refresh_skills(request: Request) -> list[SkillSpec]:
    """Force reconcile and return updated workspace skill list."""
    workspace_dir = await _request_workspace_dir(request)
    reconcile_workspace_manifest(workspace_dir)
    return _build_workspace_skill_specs(workspace_dir)


@router.get("/hub/search")
async def search_hub(
    q: str = "",
    limit: int = 20,
) -> list[HubSkillSpec]:
    results = await search_hub_skills(q, limit=limit)
    return [
        HubSkillSpec(
            slug=item.slug,
            name=item.name,
            description=item.description,
            version=item.version,
            source_url=item.source_url,
            author=item.author,
            icon_url=item.icon_url,
        )
        for item in results
    ]


@router.get("/workspaces")
async def list_workspace_skill_sources() -> list[WorkspaceSkillSummary]:
    summaries: list[WorkspaceSkillSummary] = []
    workspaces = list_workspaces()
    for workspace in workspaces:
        workspace_dir = Path(workspace["workspace_dir"])
        summaries.append(
            WorkspaceSkillSummary(
                agent_id=workspace["agent_id"],
                agent_name=workspace.get("agent_name", ""),
                workspace_dir=str(workspace_dir),
                skills=_build_workspace_skill_specs(workspace_dir),
            ),
        )
    return summaries


@router.post("/hub/install/start", response_model=HubInstallTask)
async def start_install_from_hub(
    request_body: HubInstallRequest,
    request: Request,
) -> HubInstallTask:
    workspace_dir = await _request_workspace_dir(request)
    task = HubInstallTask(
        bundle_url=request_body.bundle_url,
        version=request_body.version,
        enable=request_body.enable,
    )
    cancel_event = threading.Event()
    async with _hub_install_lock:
        _hub_install_tasks[task.task_id] = task
        _hub_install_cancel_events[task.task_id] = cancel_event

    runtime_task = asyncio.create_task(
        _run_hub_install_task(
            task_id=task.task_id,
            workspace_dir=workspace_dir,
            body=request_body,
            cancel_event=cancel_event,
        ),
        name=f"skill-hub-install-{task.task_id}",
    )
    await _hub_task_register_runtime(task.task_id, runtime_task)
    return task


@router.get("/hub/install/status/{task_id}", response_model=HubInstallTask)
async def get_hub_install_status(task_id: str) -> HubInstallTask:
    task = await _hub_task_get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="install task not found")
    return task


@router.post("/hub/install/cancel/{task_id}")
async def cancel_hub_install(task_id: str) -> dict[str, Any]:
    async with _hub_install_lock:
        task = _hub_install_tasks.get(task_id)
        if task is None:
            raise HTTPException(
                status_code=404,
                detail="install task not found",
            )
        if task.status in (
            HubInstallTaskStatus.COMPLETED,
            HubInstallTaskStatus.FAILED,
            HubInstallTaskStatus.CANCELLED,
        ):
            return {"task_id": task_id, "status": task.status.value}
        cancel_event = _hub_install_cancel_events.get(task_id)
        if cancel_event is not None:
            cancel_event.set()
        task.status = HubInstallTaskStatus.CANCELLED
        task.updated_at = time.time()
    return {"task_id": task_id, "status": "cancelled"}


@router.get("/global")
async def list_global_skills() -> list[GlobalSkillSpec]:
    return _build_global_skill_specs()


@router.post("/global/refresh")
async def refresh_global_skills() -> list[GlobalSkillSpec]:
    """Force reconcile and return updated global skill list."""
    reconcile_global_skills_manifest()
    await _follow_auto_update()
    return _build_global_skill_specs()


@router.get("/global/builtin-sources")
async def list_global_builtin_sources() -> list[BuiltinImportSpec]:
    return [
        BuiltinImportSpec(**item) for item in list_builtin_import_candidates()
    ]


@router.get("/global/builtin-notice")
async def get_global_builtin_notice() -> BuiltinUpdateNotice:
    notice = get_global_builtin_update_notice()
    return BuiltinUpdateNotice(
        fingerprint=str(notice.get("fingerprint", "") or ""),
        has_updates=bool(notice.get("has_updates", False)),
        total_changes=int(notice.get("total_changes", 0) or 0),
        actionable_skill_names=[
            str(name)
            for name in notice.get("actionable_skill_names", [])
            if str(name)
        ],
        added=[BuiltinImportSpec(**item) for item in notice.get("added", [])],
        missing=[
            BuiltinImportSpec(**item) for item in notice.get("missing", [])
        ],
        updated=[
            BuiltinImportSpec(**item) for item in notice.get("updated", [])
        ],
        removed=[
            BuiltinRemovedSpec(**item) for item in notice.get("removed", [])
        ],
    )


@router.post("")
async def create_skill(
    request: Request,
    body: CreateSkillRequest,
) -> dict[str, Any]:
    raise HTTPException(
        status_code=403,
        detail="技能只能在全局技能中新建。请切换到全局技能标签页创建。",
    )


@router.post("/upload")
async def upload_skill_zip(
    request: Request,
    file: UploadFile = File(...),
    enable: bool = True,
    target_name: str = "",
    rename_map: str = "",
) -> dict[str, Any]:
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    workspace_dir = Path(workspace.workspace_dir)
    data = await _read_validated_zip_upload(file)
    parsed_rename: dict[str, str] | None = None
    if rename_map.strip():
        try:
            parsed_rename = json.loads(rename_map)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="rename_map must be valid JSON",
            ) from exc
        if not isinstance(parsed_rename, dict):
            raise HTTPException(
                status_code=400,
                detail="rename_map must be a JSON object",
            )
    try:
        result = await asyncio.to_thread(
            SkillService(workspace_dir).import_from_zip,
            data=data,
            enable=enable,
            target_name=target_name,
            rename_map=parsed_rename,
        )
    except SkillScanError as exc:
        return _scan_error_response(exc)
    except (ValueError, AppBaseException) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result.get("conflicts"):
        raise HTTPException(status_code=409, detail=result)
    if enable and result.get("count", 0) > 0:
        schedule_agent_reload(request, workspace.agent_id)
    return result


@router.post("/global/create")
async def create_global_skill(body: CreateSkillRequest) -> dict[str, Any]:
    try:
        created = GlobalSkillService().create_skill(
            name=body.name,
            content=body.content,
            references=body.references,
            scripts=body.scripts,
            config=body.config,
        )
    except SkillScanError as exc:
        return _scan_error_response(exc)
    except (ValueError, AppBaseException) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not created:
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "conflict",
                "suggested_name": suggest_conflict_name(body.name),
            },
        )
    return {"created": True, "name": created}


@router.put("/global/save")
async def save_global_skill(body: SaveGlobalSkillRequest) -> dict[str, Any]:
    """Save one global skill.

    ``overwrite`` only matters when the save would replace an existing target
    skill during rename/save-as.
    """
    service = GlobalSkillService()
    try:
        result = service.save_global_skill(
            skill_name=body.source_name or body.name,
            target_name=body.name,
            content=body.content,
            config=body.config,
            overwrite=body.overwrite,
        )
    except SkillScanError as exc:
        return _scan_error_response(exc)
    except (ValueError, AppBaseException) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result.get("success"):
        reason = result.get("reason")
        status = 404 if reason == "not_found" else 409
        raise HTTPException(status_code=status, detail=result)
    await _follow_auto_update(result.get("name"))
    return result


@router.post("/global/upload-zip")
async def upload_global_skill_zip(
    file: UploadFile = File(...),
    target_name: str = "",
    rename_map: str = "",
) -> dict[str, Any]:
    data = await _read_validated_zip_upload(file)
    parsed_rename: dict[str, str] | None = None
    if rename_map.strip():
        try:
            parsed_rename = json.loads(rename_map)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="rename_map must be valid JSON",
            ) from exc
        if not isinstance(parsed_rename, dict):
            raise HTTPException(
                status_code=400,
                detail="rename_map must be a JSON object",
            )
    try:
        result = await asyncio.to_thread(
            GlobalSkillService().import_from_zip,
            data=data,
            target_name=target_name,
            rename_map=parsed_rename,
        )
    except SkillScanError as exc:
        return _scan_error_response(exc)
    except (ValueError, AppBaseException) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result.get("conflicts"):
        raise HTTPException(status_code=409, detail=result)
    await _follow_auto_update()
    return result


@router.post("/global/import")
async def import_global_skill_from_hub(
    body: HubInstallRequest,
) -> dict[str, Any]:
    try:
        result = await import_global_skill_from_hub_service(
            bundle_url=body.bundle_url,
            version=body.version,
            target_name=body.target_name,
        )
    except SkillScanError as exc:
        return _scan_error_response(exc)
    except SkillConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from exc
    except (ValueError, AppBaseException) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await _follow_auto_update(result.name)
    return {
        "installed": True,
        "name": result.name,
        "enabled": False,
        "source_url": result.source_url,
        "installed_from": result.installed_from,
    }


@router.post("/global/upload")
async def upload_workspace_skill_to_global(
    body: UploadToGlobalRequest,
) -> dict[str, Any]:
    workspace_dir = _workspace_dir_for_agent(body.workspace_id)
    try:
        result = GlobalSkillService().upload_from_workspace(
            workspace_dir=workspace_dir,
            skill_name=body.skill_name,
            overwrite=body.overwrite,
            preview_only=body.preview_only,
        )
    except SkillScanError as exc:
        return _scan_error_response(exc)
    except (ValueError, AppBaseException) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result.get("success"):
        status = 404 if result.get("reason") == "not_found" else 409
        raise HTTPException(status_code=status, detail=result)
    if not body.preview_only:
        await _follow_auto_update(result.get("name"))
    return result


def _preflight_download_conflicts(
    global_svc: GlobalSkillService,
    targets: list[GlobalDownloadTarget],
    skill_name: str,
    overwrite: bool,
) -> list[dict[str, Any]]:
    """Check all targets for conflicts before downloading."""
    conflicts: list[dict[str, Any]] = []
    for target in targets:
        workspace_dir = _workspace_dir_for_agent(target.workspace_id)
        result = global_svc.preflight_download_to_workspace(
            skill_name=skill_name,
            workspace_dir=workspace_dir,
            overwrite=overwrite,
        )
        if not result.get("success"):
            if result.get("reason") == "not_found":
                raise HTTPException(status_code=404, detail=result)
            conflicts.append(result)
    return conflicts


def _resolve_and_preflight(
    body: DownloadFromGlobalRequest,
) -> tuple[list[GlobalDownloadTarget], GlobalSkillService]:
    """Resolve targets and reject if any conflicts exist."""
    targets = list(body.targets)
    if body.all_workspaces:
        targets = [
            GlobalDownloadTarget(workspace_id=workspace["agent_id"])
            for workspace in list_workspaces()
        ]
    if not targets:
        raise HTTPException(
            status_code=400,
            detail="No workspace targets provided",
        )
    global_svc = GlobalSkillService()
    try:
        conflicts = _preflight_download_conflicts(
            global_svc,
            targets,
            body.skill_name,
            body.overwrite,
        )
    except (ValueError, AppBaseException) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    if conflicts:
        raise HTTPException(
            status_code=409,
            detail={
                "downloaded": [],
                "conflicts": conflicts,
            },
        )
    return targets, global_svc


def _build_download_plan(
    targets: list[GlobalDownloadTarget],
    skill_name: str,
) -> list[dict[str, Any]]:
    """Build execution plan with rollback snapshots."""
    plan: list[dict[str, Any]] = []
    for target in targets:
        workspace_dir = _workspace_dir_for_agent(target.workspace_id)
        snapshot = _snapshot_workspace_skill(
            workspace_dir,
            str(skill_name),
        )
        plan.append(
            {
                "workspace_id": target.workspace_id,
                "workspace_dir": workspace_dir,
                "snapshot": snapshot,
            },
        )
    return plan


def _download_one_or_raise(
    global_svc: GlobalSkillService,
    plan: dict[str, Any],
    execution_plan: list[dict[str, Any]],
    *,
    skill_name: str,
    overwrite: bool,
) -> dict[str, str]:
    """Download into one workspace; on failure roll back all and raise.

    A missing global skill is a target-independent 404; any other failure is
    a per-target 409 conflict.
    """
    result = global_svc.download_to_workspace(
        skill_name=skill_name,
        workspace_dir=plan["workspace_dir"],
        overwrite=overwrite,
    )
    if not result.get("success"):
        for rollback in reversed(execution_plan):
            _restore_workspace_skill(rollback["snapshot"])
        if result.get("reason") == "not_found":
            raise HTTPException(status_code=404, detail=result)
        raise HTTPException(
            status_code=409,
            detail={"downloaded": [], "conflicts": [result]},
        )
    return {
        "workspace_id": str(plan["workspace_id"]),
        "workspace_name": str(result.get("workspace_name", "") or ""),
        "name": str(result.get("name", "")),
    }


@router.post("/global/download")
async def download_global_skill_to_workspaces(
    body: DownloadFromGlobalRequest,
) -> dict[str, Any]:
    """Download one global skill into one or more workspaces.

    All-or-nothing: if any target conflicts, reject everything.
    """
    targets, global_svc = _resolve_and_preflight(body)
    if body.preview_only:
        return {"downloaded": []}

    execution_plan = _build_download_plan(targets, body.skill_name)

    downloaded: list[dict[str, str]] = []
    try:
        for plan in execution_plan:
            downloaded.append(
                _download_one_or_raise(
                    global_svc,
                    plan,
                    execution_plan,
                    skill_name=body.skill_name,
                    overwrite=body.overwrite,
                ),
            )
    except HTTPException:
        raise
    except SkillScanError as exc:
        for rollback in reversed(execution_plan):
            _restore_workspace_skill(rollback["snapshot"])
        return _scan_error_response(exc)
    except Exception:
        for rollback in reversed(execution_plan):
            _restore_workspace_skill(rollback["snapshot"])
        raise
    finally:
        for plan in execution_plan:
            backup_dir = plan["snapshot"].get("backup_dir")
            if backup_dir is not None:
                shutil.rmtree(Path(backup_dir).parent, ignore_errors=True)

    return {"downloaded": downloaded}


@router.post("/global/import-builtin")
async def import_global_builtins(
    body: ImportBuiltinRequest,
) -> dict[str, Any]:
    imports: list[dict[str, Any]] = (
        [item.model_dump() for item in body.imports]
        if body.imports
        else [{"skill_name": skill_name} for skill_name in body.skill_names]
    )
    result = import_builtin_skills(
        imports,
        overwrite_conflicts=body.overwrite_conflicts,
    )
    if result.get("conflicts") and not body.overwrite_conflicts:
        raise HTTPException(status_code=409, detail=result)
    await _follow_auto_update()
    return result


@router.post("/global/{skill_name}/update-builtin")
async def update_global_builtin(
    skill_name: str,
    body: UpdateBuiltinRequest | None = Body(default=None),
) -> dict[str, Any]:
    language = body.language if body is not None else ""
    if language and language not in BUILTIN_SKILL_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language '{language}', "
            f"must be one of {BUILTIN_SKILL_LANGUAGES}",
        )
    try:
        result = update_single_builtin(skill_name, language=language or None)
    except (ValueError, AppBaseException) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _follow_auto_update()
    return result


@router.delete("/global/{skill_name}")
async def delete_global_skill(skill_name: str) -> dict[str, Any]:
    deleted = GlobalSkillService().delete_skill(skill_name)
    if not deleted:
        raise HTTPException(
            status_code=409,
            detail="Global skills entry cannot be deleted",
        )
    # Remove the skill from every workspace since the content source is gone.
    try:
        cleanup = await asyncio.to_thread(
            GlobalSkillService().remove_skill_from_all_workspaces,
            skill_name,
        )
        logger.info("global delete cleanup '%s': %s", skill_name, cleanup)
    except Exception:
        logger.warning("global delete cleanup failed", exc_info=True)
    return {"deleted": True}


@router.get("/global/{skill_name}/config")
async def get_global_skill_config(skill_name: str) -> dict[str, Any]:
    manifest = read_global_skills_manifest()
    entry = manifest.get("skills", {}).get(skill_name)
    if entry is None:
        raise HTTPException(status_code=404, detail="Global skill not found")
    return {"config": entry.get("config", {})}


@router.put("/global/{skill_name}/config")
async def update_global_skill_config(
    skill_name: str,
    body: SkillConfigRequest,
) -> dict[str, Any]:
    manifest_path = get_global_skill_manifest_path()

    def _update(payload: dict[str, Any]) -> bool:
        entry = payload.get("skills", {}).get(skill_name)
        if entry is None:
            return False
        entry["config"] = dict(body.config)
        return True

    updated = mutate_json(manifest_path, default_global_skills_manifest(), _update)
    if not updated:
        raise HTTPException(status_code=404, detail="Global skill not found")
    return {"updated": True}


@router.delete("/global/{skill_name}/config")
async def delete_global_skill_config(skill_name: str) -> dict[str, Any]:
    manifest_path = get_global_skill_manifest_path()

    def _update(payload: dict[str, Any]) -> bool:
        entry = payload.get("skills", {}).get(skill_name)
        if entry is None:
            return False
        entry.pop("config", None)
        return True

    updated = mutate_json(manifest_path, default_global_skills_manifest(), _update)
    if not updated:
        raise HTTPException(status_code=404, detail="Global skill not found")
    return {"cleared": True}


def _validate_tags(tags: list[str]) -> list[str]:
    if len(tags) > MAX_TAGS:
        raise HTTPException(
            status_code=422,
            detail=f"At most {MAX_TAGS} tags allowed",
        )
    cleaned: list[str] = []
    for t in tags:
        t = str(t).strip()[:MAX_TAG_LENGTH]
        if t:
            cleaned.append(t)
    return cleaned


@router.put("/global/{skill_name}/tags")
async def update_global_skill_tags(
    skill_name: str,
    tags: list[str],
) -> dict[str, Any]:
    tags = _validate_tags(tags)
    updated = GlobalSkillService().set_global_skill_tags(skill_name, tags)
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Global skill not found",
        )
    return {"updated": True, "tags": tags}


@router.put("/global/{skill_name}/auto-update")
async def update_global_skill_auto_update(
    skill_name: str,
    body: AutoUpdateRequest,
) -> dict[str, Any]:
    """Toggle auto-update for a global skill and persist its target agents.

    Enabling triggers an immediate sync of the configured workspaces.
    """
    result = GlobalSkillService().set_skill_auto_update(
        skill_name,
        enabled=body.enabled,
        targets=body.targets,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Global skill not found",
        )
    await post_auto_update_msg(result)
    return {
        "updated": True,
        "enabled": body.enabled,
        "targets": body.targets,
    }


@router.post("/batch-delete")
async def batch_delete_skills(
    request: Request,
    skills: list[str],
) -> dict[str, Any]:
    """Auto-disable then delete each skill. Per-skill results."""
    workspace_dir = await _request_workspace_dir(request)
    service = SkillService(workspace_dir)
    results: dict[str, Any] = {}
    for skill_name in skills:
        try:
            service.disable_skill(skill_name)
            deleted = service.delete_skill(skill_name)
            results[skill_name] = {
                "success": deleted,
                "reason": None if deleted else "delete_failed",
            }
        except Exception as exc:
            results[skill_name] = {
                "success": False,
                "reason": str(exc),
            }
    return {"results": results}


@router.post("/global/batch-delete")
async def batch_delete_global_skills(
    skills: list[str],
) -> dict[str, Any]:
    """Delete multiple global skills. Per-skill results."""
    service = GlobalSkillService()
    results: dict[str, Any] = {}
    for skill_name in skills:
        try:
            deleted = service.delete_skill(skill_name)
            results[skill_name] = {
                "success": deleted,
                "reason": None if deleted else "delete_failed",
            }
        except Exception as exc:
            results[skill_name] = {
                "success": False,
                "reason": str(exc),
            }
    return {"results": results}


@router.post("/batch-disable")
async def batch_disable_skills(
    request: Request,
    skills: list[str],
) -> dict[str, Any]:
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    workspace_dir = Path(workspace.workspace_dir)
    service = SkillService(workspace_dir)
    results = {skill: service.disable_skill(skill) for skill in skills}
    if any(result.get("success") for result in results.values()):
        schedule_agent_reload(request, workspace.agent_id)
    return {"results": results}


@router.post("/batch-enable")
async def batch_enable_skills(
    request: Request,
    skills: list[str],
) -> dict[str, Any]:
    """Enable each requested skill independently and collect per-skill results.

    Example:
        enabling ``["ok_skill", "blocked_skill"]`` returns success for the
        first item and ``reason="security_scan_failed"`` for the second,
        rather than aborting the entire batch.
    """
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    workspace_dir = Path(workspace.workspace_dir)
    service = SkillService(workspace_dir)
    results: dict[str, Any] = {}
    for skill in skills:
        try:
            results[skill] = service.enable_skill(skill)
        except SkillScanError as exc:
            results[skill] = {
                "success": False,
                "reason": "security_scan_failed",
                "detail": _scan_error_payload(exc),
            }
    if any(
        isinstance(result, dict) and result.get("success")
        for result in results.values()
    ):
        schedule_agent_reload(request, workspace.agent_id)
    return {"results": results}


@router.post("/{skill_name}/disable")
async def disable_skill(
    request: Request,
    skill_name: str,
) -> dict[str, Any]:
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    workspace_dir = Path(workspace.workspace_dir)
    result = SkillService(workspace_dir).disable_skill(skill_name)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail="Skill not found")
    schedule_agent_reload(request, workspace.agent_id)
    return {"disabled": True, **result}


@router.post("/{skill_name}/enable")
async def enable_skill(
    request: Request,
    skill_name: str,
) -> dict[str, Any]:
    """Enable one workspace skill after a fresh scan."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    workspace_dir = Path(workspace.workspace_dir)
    try:
        result = SkillService(workspace_dir).enable_skill(skill_name)
    except SkillScanError as exc:
        return _scan_error_response(exc)
    if not result.get("success"):
        raise HTTPException(
            status_code=404,
            detail=result.get("reason", "Skill not found"),
        )
    schedule_agent_reload(request, workspace.agent_id)
    return {"enabled": True, **result}


@router.delete("/{skill_name}")
async def delete_skill(
    request: Request,
    skill_name: str,
) -> dict[str, Any]:
    raise HTTPException(
        status_code=403,
        detail="技能只能在全局技能中删除。请切换到全局技能标签页删除。",
    )


@router.get("/{skill_name}/files/{file_path:path}")
async def load_skill_file(
    request: Request,
    skill_name: str,
    file_path: str,
) -> dict[str, Any]:
    workspace_dir = await _request_workspace_dir(request)
    content = SkillService(workspace_dir).load_skill_file(
        skill_name=skill_name,
        file_path=file_path,
    )
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {"content": content}


@router.put("/save")
async def save_workspace_skill(
    request: Request,
    body: SaveSkillRequest,
) -> dict[str, Any]:
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    workspace_dir = Path(workspace.workspace_dir)
    try:
        result = SkillService(workspace_dir).save_skill(
            skill_name=body.source_name or body.name,
            target_name=body.name,
            content=body.content,
            config=body.config,
            overwrite=body.overwrite,
        )
    except SkillScanError as exc:
        return _scan_error_response(exc)
    except (ValueError, AppBaseException) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result.get("success"):
        reason = result.get("reason")
        status = 404 if reason == "not_found" else 409
        raise HTTPException(status_code=status, detail=result)
    schedule_agent_reload(request, workspace.agent_id)
    return result


@router.put("/{skill_name}/channels")
async def update_skill_channels_endpoint(
    request: Request,
    skill_name: str,
    channels: list[str],
) -> dict[str, Any]:
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    workspace_dir = Path(workspace.workspace_dir)
    updated = SkillService(workspace_dir).set_skill_channels(
        skill_name,
        channels,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Skill not found")
    schedule_agent_reload(request, workspace.agent_id)
    return {"updated": True, "channels": channels}


@router.put("/{skill_name}/tags")
async def update_skill_tags(
    request: Request,
    skill_name: str,
    tags: list[str],
) -> dict[str, Any]:
    from ..agent_context import get_agent_for_request

    tags = _validate_tags(tags)
    workspace = await get_agent_for_request(request)
    workspace_dir = Path(workspace.workspace_dir)
    updated = SkillService(workspace_dir).set_skill_tags(
        skill_name,
        tags,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"updated": True, "tags": tags}


@router.get("/{skill_name}/config")
async def get_skill_config_endpoint(
    request: Request,
    skill_name: str,
) -> dict[str, Any]:
    workspace_dir = await _request_workspace_dir(request)
    manifest = read_skill_manifest(workspace_dir)
    entry = manifest.get("skills", {}).get(skill_name)
    if entry is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"config": entry.get("config", {})}


@router.put("/{skill_name}/config")
async def update_skill_config_endpoint(
    request: Request,
    skill_name: str,
    body: SkillConfigRequest,
) -> dict[str, Any]:
    workspace_dir = await _request_workspace_dir(request)
    manifest_path = get_workspace_skill_manifest_path(workspace_dir)

    def _update(payload: dict[str, Any]) -> bool:
        entry = payload.get("skills", {}).get(skill_name)
        if entry is None:
            return False
        entry["config"] = dict(body.config)
        return True

    updated = mutate_json(
        manifest_path,
        default_workspace_manifest(),
        _update,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"updated": True}


@router.delete("/{skill_name}/config")
async def delete_skill_config_endpoint(
    request: Request,
    skill_name: str,
) -> dict[str, Any]:
    workspace_dir = await _request_workspace_dir(request)
    manifest_path = get_workspace_skill_manifest_path(workspace_dir)

    def _update(payload: dict[str, Any]) -> bool:
        entry = payload.get("skills", {}).get(skill_name)
        if entry is None:
            return False
        entry.pop("config", None)
        return True

    updated = mutate_json(
        manifest_path,
        default_workspace_manifest(),
        _update,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"cleared": True}


# ─── Sync status + push + resolve ──────────────────────────────────────────


class SyncPushRequest(BaseModel):
    skill_name: str
    force: bool = False
    expected_global_hash: str | None = None
    include_config: bool = False
    propagate: bool = False


class SyncResolveRequest(BaseModel):
    skill_name: str
    resolution: str  # "keep_global" | "keep_agent"
    merged_content: str | None = None  # reserved for future manual merge


@router.get("/sync/status")
async def get_sync_status(
    request: Request,
) -> dict[str, Any]:
    """Return sync status for all skills in the current workspace."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    workspace_dir = Path(workspace.workspace_dir)
    try:
        result = GlobalSkillService().get_sync_status(workspace_dir)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sync status: {exc}",
        ) from exc
    return result


@router.post("/sync/push")
async def push_skill_to_global(
    request: Request,
    body: SyncPushRequest,
) -> dict[str, Any]:
    """Push a workspace skill to global skills (Agent → Global sync)."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    workspace_dir = Path(workspace.workspace_dir)
    try:
        result = await asyncio.to_thread(
            GlobalSkillService().promote_workspace_skill_to_global,
            workspace_dir,
            body.skill_name,
            force=body.force,
            expected_global_hash=body.expected_global_hash,
            include_config=body.include_config,
            propagate=body.propagate,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to push skill: {exc}",
        ) from exc
    if not result.get("success"):
        if result.get("reason") in {
            "conflict",
            "not_linked",
            "outdated_global",
            "stale_global",
        }:
            raise HTTPException(status_code=409, detail=result)
        raise HTTPException(status_code=404, detail="Skill not found")
    if body.propagate:
        rollout = await asyncio.to_thread(
            run_global_auto_update_sync,
            skill_name=body.skill_name,
        )
        await post_auto_update_msg(rollout)
        result["rollout"] = rollout
        result["propagated"] = True
    return result


@router.post("/sync/resolve")
async def resolve_sync_conflict(
    request: Request,
    body: SyncResolveRequest,
) -> dict[str, Any]:
    """Resolve a sync conflict by choosing global or agent version."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    workspace_dir = Path(workspace.workspace_dir)
    service = GlobalSkillService()

    try:
        skill_name = body.skill_name
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if body.resolution == "keep_global":
        # Overwrite agent with global version
        result = await asyncio.to_thread(
            service.download_to_workspace,
            skill_name,
            workspace_dir,
            overwrite=True,
        )
        if not result.get("success"):
            raise HTTPException(
                status_code=404,
                detail="Skill not found in global skills",
            )
        schedule_agent_reload(request, workspace.agent_id)
        return {"resolved": True, "resolution": "keep_global"}

    if body.resolution == "keep_agent":
        # Push agent version to global skills
        result = await asyncio.to_thread(
            service.promote_workspace_skill_to_global,
            workspace_dir,
            skill_name,
            force=True,
        )
        if not result.get("success"):
            if result.get("reason") == "conflict":
                raise HTTPException(status_code=409, detail=result)
            raise HTTPException(
                status_code=404,
                detail="Skill not found",
            )
        schedule_agent_reload(request, workspace.agent_id)
        return {"resolved": True, "resolution": "keep_agent"}

    raise HTTPException(
        status_code=400,
        detail=f"Unknown resolution: {body.resolution}",
    )
