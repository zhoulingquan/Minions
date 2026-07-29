# -*- coding: utf-8 -*-
"""Integration tests for global skills CRUD endpoints.

Global skills endpoints (``/api/skills/global/*``) use
``GlobalSkillService()`` — a global singleton that ignores the
``agentId`` path parameter when reached via agent-scoped routing.
Tests here hit the global ``/api/skills/global/*`` paths directly.

Agent-scoped routing coverage for global skills URLs is in
``test_agent_scoped_routing.py``.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

import pytest
from helpers import default_http_timeout

_HTTP_TIMEOUT = default_http_timeout(15.0)
_GLOBAL_BASE = "/api/skills/global"


# ------------------------------------------------------------------ #
# helpers
# ------------------------------------------------------------------ #


def _skill_md(name: str, description: str) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "---\n\n"
        "# Global Integration Skill\n"
        "This skill is created by global skills integration tests.\n"
    )


def _create_global_skill(
    app_server,
    name: str,
    *,
    description: str = "global test skill",
) -> dict[str, Any]:
    resp = app_server.api_request(
        "POST",
        f"{_GLOBAL_BASE}/create",
        json={
            "name": name,
            "content": _skill_md(name, description),
            "enable": False,
        },
        timeout=_HTTP_TIMEOUT,
    )
    assert resp.status_code == 200, app_server.logs_tail()
    return resp.json()


def _delete_global_skill_quietly(app_server, name: str) -> None:
    try:
        app_server.api_request(
            "DELETE",
            f"{_GLOBAL_BASE}/{name}",
            timeout=_HTTP_TIMEOUT,
        )
    except Exception:
        pass


def _list_global_skill_names(app_server) -> set[str]:
    resp = app_server.api_request(
        "GET",
        _GLOBAL_BASE,
        timeout=_HTTP_TIMEOUT,
    )
    assert resp.status_code == 200, app_server.logs_tail()
    return {item["name"] for item in resp.json()}


def _build_skill_zip(skills: dict[str, str]) -> bytes:
    """Build a zip containing one SKILL.md per skill name."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in skills.items():
            zf.writestr(f"{name}/SKILL.md", content)
    return buf.getvalue()


# ------------------------------------------------------------------ #
# lifecycle
# ------------------------------------------------------------------ #


@pytest.mark.integration
@pytest.mark.p0
def test_global_skill_lifecycle(app_server) -> None:
    """Test purpose:
    - Verify the create → list → get-config → delete lifecycle for a
      global skill. This is the primary happy-path CRUD coverage.

    Test flow:
    1. POST /global/create with a new skill.
    2. GET /global — assert the skill appears.
    3. GET /global/{name}/config — assert empty config.
    4. DELETE /global/{name} — assert ``deleted=True``.
    5. GET /global — assert the skill is gone.

    API endpoints:
    - POST /api/skills/global/create
    - GET  /api/skills/global
    - GET  /api/skills/global/{skill_name}/config
    - DELETE /api/skills/global/{skill_name}
    """
    name = "integ-global-lifecycle-01"
    try:
        result = _create_global_skill(app_server, name)
        assert result.get("created") is True

        assert name in _list_global_skill_names(app_server)

        config_resp = app_server.api_request(
            "GET",
            f"{_GLOBAL_BASE}/{name}/config",
            timeout=_HTTP_TIMEOUT,
        )
        assert config_resp.status_code == 200, app_server.logs_tail()
        assert config_resp.json().get("config") == {}

        del_resp = app_server.api_request(
            "DELETE",
            f"{_GLOBAL_BASE}/{name}",
            timeout=_HTTP_TIMEOUT,
        )
        assert del_resp.status_code == 200, app_server.logs_tail()
        assert del_resp.json().get("deleted") is True

        assert name not in _list_global_skill_names(app_server)
    finally:
        _delete_global_skill_quietly(app_server, name)


@pytest.mark.integration
@pytest.mark.p0
def test_global_skill_duplicate_409(app_server) -> None:
    """Test purpose:
    - Verify POST /global/create with an existing name returns 409 and
      includes a ``suggested_name``.

    Test flow:
    1. Create global skill ``integ-global-dup-01``.
    2. POST /global/create with the same name.
    3. Assert 409 and detail.reason == ``conflict``.

    API endpoints:
    - POST /api/skills/global/create
    """
    name = "integ-global-dup-01"
    try:
        _create_global_skill(app_server, name)

        dup_resp = app_server.api_request(
            "POST",
            f"{_GLOBAL_BASE}/create",
            json={
                "name": name,
                "content": _skill_md(name, "duplicate"),
                "enable": False,
            },
            timeout=_HTTP_TIMEOUT,
        )
        assert dup_resp.status_code == 409, app_server.logs_tail()
        detail = dup_resp.json().get("detail", {})
        assert detail.get("reason") == "conflict"
        assert "suggested_name" in detail
    finally:
        _delete_global_skill_quietly(app_server, name)


# ------------------------------------------------------------------ #
# save
# ------------------------------------------------------------------ #


@pytest.mark.integration
@pytest.mark.p0
def test_global_save_missing_404(app_server) -> None:
    """Test purpose:
    - Verify PUT /global/save on a non-existent global skill returns 404.

    Test flow:
    1. PUT /global/save with a name that does not exist.
    2. Assert 404.

    API endpoints:
    - PUT /api/skills/global/save
    """
    resp = app_server.api_request(
        "PUT",
        f"{_GLOBAL_BASE}/save",
        json={
            "name": "integ-global-nosuch-01",
            "content": _skill_md("nosuch", "missing"),
        },
        timeout=_HTTP_TIMEOUT,
    )
    assert resp.status_code == 404, app_server.logs_tail()


# ------------------------------------------------------------------ #
# delete
# ------------------------------------------------------------------ #


@pytest.mark.integration
@pytest.mark.p0
def test_global_delete_missing_409(app_server) -> None:
    """Test purpose:
    - Verify DELETE /global/{name} for a non-existent skill returns 409
      ``cannot be deleted``.

    Test flow:
    1. DELETE /global/<nonexistent>.
    2. Assert 409.

    API endpoints:
    - DELETE /api/skills/global/{skill_name}
    """
    resp = app_server.api_request(
        "DELETE",
        f"{_GLOBAL_BASE}/integ-global-gone-01",
        timeout=_HTTP_TIMEOUT,
    )
    assert resp.status_code == 409, app_server.logs_tail()


# ------------------------------------------------------------------ #
# config
# ------------------------------------------------------------------ #


@pytest.mark.integration
@pytest.mark.p0
def test_global_config_put_missing_404(app_server) -> None:
    """Test purpose:
    - Verify PUT /global/{name}/config returns 404 when the skill does
      not exist.

    API endpoints:
    - PUT /api/skills/global/{skill_name}/config
    """
    resp = app_server.api_request(
        "PUT",
        f"{_GLOBAL_BASE}/integ-global-cfg-miss-01/config",
        json={"config": {"key": "value"}},
        timeout=_HTTP_TIMEOUT,
    )
    assert resp.status_code == 404, app_server.logs_tail()


@pytest.mark.integration
@pytest.mark.p0
def test_global_config_delete_missing_404(app_server) -> None:
    """Test purpose:
    - Verify DELETE /global/{name}/config returns 404 when the skill
      does not exist.

    API endpoints:
    - DELETE /api/skills/global/{skill_name}/config
    """
    resp = app_server.api_request(
        "DELETE",
        f"{_GLOBAL_BASE}/integ-global-cfg-del-miss-01/config",
        timeout=_HTTP_TIMEOUT,
    )
    assert resp.status_code == 404, app_server.logs_tail()


@pytest.mark.integration
@pytest.mark.p0
def test_global_config_roundtrip(app_server) -> None:
    """Test purpose:
    - Verify PUT → GET → DELETE config roundtrip on a global skill.
      This is the happy-path coverage for the global skills config endpoints.

    Test flow:
    1. Create global skill.
    2. PUT config with ``{"llm_model": "qwen-max"}``.
    3. GET config — assert value matches.
    4. DELETE config — assert ``cleared=True``.
    5. GET config — assert empty.

    API endpoints:
    - PUT    /api/skills/global/{skill_name}/config
    - GET    /api/skills/global/{skill_name}/config
    - DELETE /api/skills/global/{skill_name}/config
    """
    name = "integ-global-cfg-rt-01"
    try:
        _create_global_skill(app_server, name)

        put_resp = app_server.api_request(
            "PUT",
            f"{_GLOBAL_BASE}/{name}/config",
            json={"config": {"llm_model": "qwen-max"}},
            timeout=_HTTP_TIMEOUT,
        )
        assert put_resp.status_code == 200, app_server.logs_tail()
        assert put_resp.json().get("updated") is True

        get_resp = app_server.api_request(
            "GET",
            f"{_GLOBAL_BASE}/{name}/config",
            timeout=_HTTP_TIMEOUT,
        )
        assert get_resp.status_code == 200, app_server.logs_tail()
        assert get_resp.json()["config"]["llm_model"] == "qwen-max"

        del_resp = app_server.api_request(
            "DELETE",
            f"{_GLOBAL_BASE}/{name}/config",
            timeout=_HTTP_TIMEOUT,
        )
        assert del_resp.status_code == 200, app_server.logs_tail()
        assert del_resp.json().get("cleared") is True

        empty_resp = app_server.api_request(
            "GET",
            f"{_GLOBAL_BASE}/{name}/config",
            timeout=_HTTP_TIMEOUT,
        )
        assert empty_resp.status_code == 200, app_server.logs_tail()
        assert empty_resp.json()["config"] == {}
    finally:
        _delete_global_skill_quietly(app_server, name)


# ------------------------------------------------------------------ #
# tags
# ------------------------------------------------------------------ #


@pytest.mark.integration
@pytest.mark.p0
def test_global_tags_put_missing_404(app_server) -> None:
    """Test purpose:
    - Verify PUT /global/{name}/tags returns 404 when the skill does
      not exist.

    API endpoints:
    - PUT /api/skills/global/{skill_name}/tags
    """
    resp = app_server.api_request(
        "PUT",
        f"{_GLOBAL_BASE}/integ-global-tags-miss-01/tags",
        json=["automation"],
        timeout=_HTTP_TIMEOUT,
    )
    assert resp.status_code == 404, app_server.logs_tail()


# ------------------------------------------------------------------ #
# batch-delete
# ------------------------------------------------------------------ #


@pytest.mark.integration
@pytest.mark.p0
def test_global_batch_delete_partial(app_server) -> None:
    """Test purpose:
    - Verify POST /global/batch-delete with a mix of existing and
      non-existent names returns per-skill results (success for
      existing, failure for missing).

    Test flow:
    1. Create global skill ``integ-global-bd-a``.
    2. POST batch-delete with both the existing and missing names.
    3. Assert ``integ-global-bd-a`` succeeds, ``integ-global-bd-ghost`` fails.

    API endpoints:
    - POST /api/skills/global/batch-delete
    """
    name = "integ-global-bd-a"
    ghost = "integ-global-bd-ghost"
    try:
        _create_global_skill(app_server, name)

        resp = app_server.api_request(
            "POST",
            f"{_GLOBAL_BASE}/batch-delete",
            json=[name, ghost],
            timeout=_HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, app_server.logs_tail()
        results = resp.json().get("results", {})
        assert results[name]["success"] is True
        assert results[ghost]["success"] is False
    finally:
        _delete_global_skill_quietly(app_server, name)


@pytest.mark.integration
@pytest.mark.p0
def test_global_batch_delete_all_success(app_server) -> None:
    """Test purpose:
    - Verify POST /global/batch-delete succeeds for all names when all
      skills exist. This is the normal-flow batch cleanup scenario.

    Test flow:
    1. Create 3 global skills.
    2. POST batch-delete with all 3 names.
    3. Assert all 3 succeed.
    4. GET /global — assert none remain.

    API endpoints:
    - POST /api/skills/global/batch-delete
    - GET  /api/skills/global
    """
    names = [
        "integ-global-bd-all-a",
        "integ-global-bd-all-b",
        "integ-global-bd-all-c",
    ]
    try:
        for n in names:
            _create_global_skill(app_server, n)

        resp = app_server.api_request(
            "POST",
            f"{_GLOBAL_BASE}/batch-delete",
            json=names,
            timeout=_HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, app_server.logs_tail()
        results = resp.json().get("results", {})
        for n in names:
            assert results[n]["success"] is True

        remaining = _list_global_skill_names(app_server)
        for n in names:
            assert n not in remaining
    finally:
        for n in names:
            _delete_global_skill_quietly(app_server, n)


# ------------------------------------------------------------------ #
# upload-zip
# ------------------------------------------------------------------ #


@pytest.mark.integration
@pytest.mark.p0
def test_global_upload_zip_valid(app_server) -> None:
    """Test purpose:
    - Verify POST /global/upload-zip with a valid skill zip imports the
      skill into global skills. This is the happy-path for zip ingestion.

    Test flow:
    1. Build a zip with a single skill ``integ-global-zip-01``.
    2. POST /global/upload-zip.
    3. Assert 200 and ``count >= 1``.
    4. GET /global — assert the skill appears.

    API endpoints:
    - POST /api/skills/global/upload-zip
    - GET  /api/skills/global
    """
    name = "integ-global-zip-01"
    zip_bytes = _build_skill_zip(
        {
            name: _skill_md(name, "zip-imported global skill"),
        },
    )
    try:
        resp = app_server.api_request(
            "POST",
            f"{_GLOBAL_BASE}/upload-zip",
            files={
                "file": (
                    "skills.zip",
                    zip_bytes,
                    "application/zip",
                ),
            },
            timeout=_HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, app_server.logs_tail()
        payload = resp.json()
        assert payload.get("count", 0) >= 1

        assert name in _list_global_skill_names(app_server)
    finally:
        _delete_global_skill_quietly(app_server, name)


# ------------------------------------------------------------------ #
# upload from workspace
# ------------------------------------------------------------------ #


@pytest.mark.integration
@pytest.mark.p0
def test_global_upload_from_workspace(app_server) -> None:
    """Test purpose:
    - Verify POST /global/upload copies a workspace skill into global skills.
      Requires a pre-existing workspace skill as input.

    Test flow:
    1. Create an agent and seed a legacy workspace-only skill on disk.
    2. POST /global/upload with ``workspace_id`` and ``skill_name``.
    3. Assert 200 and ``success=True``.
    4. GET /global — assert skill appears.

    API endpoints:
    - POST /api/skills/global/upload
    - GET  /api/skills/global
    """
    agent_id = "integ_global_upload_ws_01"
    skill_name = "integ-global-from-ws-01"
    create_agent = app_server.api_request(
        "POST",
        "/api/agents",
        json={
            "id": agent_id,
            "name": "Global skills upload source",
            "description": "",
        },
    )
    assert create_agent.status_code == 201, app_server.logs_tail()

    try:
        # Workspace skill creation is intentionally global-only now. The
        # upload endpoint remains useful for migrating skills created by older
        # versions, so seed that legacy on-disk state directly.
        workspace_dir = Path(create_agent.json()["workspace_dir"])
        skill_dir = workspace_dir / "skills" / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            _skill_md(skill_name, "source for global skills"),
            encoding="utf-8",
        )

        upload_resp = app_server.api_request(
            "POST",
            f"{_GLOBAL_BASE}/upload",
            json={
                "workspace_id": agent_id,
                "skill_name": skill_name,
                "overwrite": False,
            },
            timeout=_HTTP_TIMEOUT,
        )
        assert upload_resp.status_code == 200, app_server.logs_tail()
        assert upload_resp.json().get("success") is True

        assert skill_name in _list_global_skill_names(app_server)
    finally:
        _delete_global_skill_quietly(app_server, skill_name)
        app_server.api_request("DELETE", f"/api/agents/{agent_id}")


# ------------------------------------------------------------------ #
# download
# ------------------------------------------------------------------ #


@pytest.mark.integration
@pytest.mark.p0
def test_global_download_no_targets_400(app_server) -> None:
    """Test purpose:
    - Verify POST /global/download with an empty targets list returns
      400 ``No workspace targets provided``.

    API endpoints:
    - POST /api/skills/global/download
    """
    resp = app_server.api_request(
        "POST",
        f"{_GLOBAL_BASE}/download",
        json={
            "skill_name": "integ-global-dl-notar-01",
            "targets": [],
        },
        timeout=_HTTP_TIMEOUT,
    )
    assert resp.status_code == 400, app_server.logs_tail()
    assert "No workspace targets" in resp.json().get("detail", "")


@pytest.mark.integration
@pytest.mark.p0
def test_global_download_to_workspace(app_server) -> None:
    """Test purpose:
    - Verify POST /global/download copies a global skill into a workspace.
      End-to-end happy path: create global skill → create agent →
      download → verify in workspace.

    Test flow:
    1. Create global skill ``integ-global-dl-01``.
    2. Create agent.
    3. POST /global/download targeting that agent.
    4. Assert 200 and ``downloaded`` list has 1 entry.
    5. GET /api/agents/{id}/skills — assert the skill appears.

    API endpoints:
    - POST /api/skills/global/download
    - GET  /api/agents/{agentId}/skills
    """
    global_name = "integ-global-dl-01"
    agent_id = "integ_global_dl_agent_01"

    try:
        _create_global_skill(app_server, global_name)

        create_agent = app_server.api_request(
            "POST",
            "/api/agents",
            json={
                "id": agent_id,
                "name": "Download target",
                "description": "",
            },
        )
        assert create_agent.status_code == 201, app_server.logs_tail()

        dl_resp = app_server.api_request(
            "POST",
            f"{_GLOBAL_BASE}/download",
            json={
                "skill_name": global_name,
                "targets": [{"workspace_id": agent_id}],
                "overwrite": False,
            },
            timeout=_HTTP_TIMEOUT,
        )
        assert dl_resp.status_code == 200, app_server.logs_tail()
        downloaded = dl_resp.json().get("downloaded", [])
        assert len(downloaded) == 1
        assert downloaded[0]["workspace_id"] == agent_id

        ws_skills = app_server.api_request(
            "GET",
            f"/api/agents/{agent_id}/skills",
            timeout=_HTTP_TIMEOUT,
        )
        assert ws_skills.status_code == 200, app_server.logs_tail()
        ws_names = {item["name"] for item in ws_skills.json()}
        assert global_name in ws_names
    finally:
        app_server.api_request(
            "DELETE",
            f"/api/agents/{agent_id}/skills/{global_name}",
        )
        app_server.api_request("DELETE", f"/api/agents/{agent_id}")
        _delete_global_skill_quietly(app_server, global_name)


# ------------------------------------------------------------------ #
# import-builtin + update-builtin
# ------------------------------------------------------------------ #


@pytest.mark.integration
@pytest.mark.p0
def test_global_import_builtin_and_update(app_server) -> None:
    """Test purpose:
    - Verify POST /global/import-builtin imports a builtin skill into
      global skills, and POST /global/{name}/update-builtin refreshes it.
      Uses ``file_reader-zh`` (smallest builtin).

    Test flow:
    1. POST /global/import-builtin with ``skill_names=["file_reader-zh"]``.
    2. Assert 200 and ``imported`` list is non-empty.
    3. GET /global — assert ``file_reader-zh`` appears.
    4. POST /global/file_reader-zh/update-builtin.
    5. Assert 200.

    API endpoints:
    - POST /api/skills/global/import-builtin
    - POST /api/skills/global/{skill_name}/update-builtin
    - GET  /api/skills/global
    """
    source = "file_reader-zh"
    global_name = "file_reader"
    try:
        import_resp = app_server.api_request(
            "POST",
            f"{_GLOBAL_BASE}/import-builtin",
            json={
                "skill_names": [source],
                "overwrite_conflicts": True,
            },
            timeout=_HTTP_TIMEOUT,
        )
        assert import_resp.status_code == 200, app_server.logs_tail()
        payload = import_resp.json()
        total = len(payload.get("imported", [])) + len(
            payload.get("updated", []),
        )
        assert total >= 1

        assert global_name in _list_global_skill_names(app_server)

        update_resp = app_server.api_request(
            "POST",
            f"{_GLOBAL_BASE}/{global_name}/update-builtin",
            timeout=_HTTP_TIMEOUT,
        )
        assert update_resp.status_code == 200, app_server.logs_tail()
    finally:
        _delete_global_skill_quietly(app_server, global_name)


@pytest.mark.integration
@pytest.mark.p0
def test_global_update_builtin_missing_400(app_server) -> None:
    """Test purpose:
    - Verify POST /global/{name}/update-builtin for a non-existent
      skill returns 400.

    API endpoints:
    - POST /api/skills/global/{skill_name}/update-builtin
    """
    resp = app_server.api_request(
        "POST",
        f"{_GLOBAL_BASE}/integ-global-nobuiltin-01/update-builtin",
        timeout=_HTTP_TIMEOUT,
    )
    assert resp.status_code == 400, app_server.logs_tail()


# ------------------------------------------------------------------ #
# import from hub
# ------------------------------------------------------------------ #


@pytest.mark.integration
@pytest.mark.p0
def test_global_import_hub_invalid_400(app_server) -> None:
    """Test purpose:
    - Verify POST /global/import with an invalid ``bundle_url`` returns
      400. The handler validates the URL before attempting to fetch.

    API endpoints:
    - POST /api/skills/global/import
    """
    resp = app_server.api_request(
        "POST",
        f"{_GLOBAL_BASE}/import",
        json={
            "bundle_url": "not-a-valid-url",
        },
        timeout=_HTTP_TIMEOUT,
    )
    assert resp.status_code == 400, app_server.logs_tail()


# ------------------------------------------------------------------ #
# hub install start → poll → complete
# ------------------------------------------------------------------ #


@pytest.mark.integration
@pytest.mark.p0
def test_hub_install_start_poll_complete(app_server) -> None:
    """Test purpose:
    - Verify the async hub install pipeline: start → status poll →
      terminal state. Uses the ``file_reader-zh`` skill from the
      upstream repo (smallest builtin, ~1.6 KB).

    Test flow:
    1. Create agent.
    2. POST /skills/hub/install/start with the upstream
       ``file_reader-zh`` GitHub URL.
    3. Assert 200 and response contains ``task_id``.
    4. Poll GET /skills/hub/install/status/{task_id} until terminal.
    5. Assert status is ``completed`` or ``failed`` (network-dependent).
    6. Cleanup: delete agent + workspace skill.

    API endpoints:
    - POST /api/skills/hub/install/start
    - GET  /api/skills/hub/install/status/{task_id}
    """
    agent_id = "integ_hub_install_poll_01"
    skill_url = (
        "https://github.com/agentscope-ai/Minions"
        "/tree/main/packages/minions-agents/src/minions/agents/skills/file_reader-zh"
    )
    create_agent = app_server.api_request(
        "POST",
        "/api/agents",
        json={
            "id": agent_id,
            "name": "Hub install poll agent",
            "description": "",
        },
    )
    assert create_agent.status_code == 201, app_server.logs_tail()

    try:
        start_resp = app_server.api_request(
            "POST",
            f"/api/agents/{agent_id}/skills/hub/install/start",
            json={
                "bundle_url": skill_url,
                "enable": False,
            },
            timeout=30.0,
        )
        assert start_resp.status_code == 200, app_server.logs_tail()
        task_id = start_resp.json().get("task_id")
        assert task_id

        import time

        terminal = {"completed", "failed", "cancelled"}
        deadline = time.time() + 60
        last_status = None
        while time.time() < deadline:
            status_resp = app_server.api_request(
                "GET",
                f"/api/agents/{agent_id}/skills"
                f"/hub/install/status/{task_id}",
                timeout=_HTTP_TIMEOUT,
            )
            assert status_resp.status_code == 200, app_server.logs_tail()
            last_status = status_resp.json().get("status")
            if last_status in terminal:
                break
            time.sleep(1.0)

        assert (
            last_status in terminal
        ), f"task {task_id} stuck at {last_status}"
    finally:
        app_server.api_request(
            "DELETE",
            f"/api/agents/{agent_id}/skills/file_reader-zh",
        )
        app_server.api_request("DELETE", f"/api/agents/{agent_id}")
