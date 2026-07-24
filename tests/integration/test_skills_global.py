# -*- coding: utf-8 -*-
"""Smoke tests for header-scoped ``/api/skills`` endpoints."""
from __future__ import annotations

import io
import zipfile

import pytest


def _skill_md(name: str, description: str) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "---\n\n"
        "# Integration Skill\n"
        "This skill is created by integration tests.\n"
    )


def _skill_zip(skills: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in skills.items():
            archive.writestr(f"{name}/SKILL.md", content)
    return buffer.getvalue()


def _create_agent(app_server, agent_id: str) -> None:
    response = app_server.api_request(
        "POST",
        "/api/agents",
        json={"id": agent_id, "name": f"Agent {agent_id}", "description": ""},
    )
    assert response.status_code == 201, app_server.logs_tail()


def _upload_workspace_skills(
    app_server,
    agent_id: str,
    skills: dict[str, str],
    *,
    enable: bool = False,
) -> dict:
    response = app_server.api_request(
        "POST",
        "/api/skills/upload",
        headers={"X-Agent-Id": agent_id},
        files={
            "file": (
                "skills.zip",
                _skill_zip(skills),
                "application/zip",
            ),
        },
        data={"enable": str(enable).lower()},
    )
    assert response.status_code == 200, app_server.logs_tail()
    return response.json()


@pytest.mark.integration
@pytest.mark.p0
def test_skills_direct_create_delete_are_global_only(app_server) -> None:
    """Header-scoped routes enforce the same global-only authoring policy."""
    agent_id = "integ-skills-global-only-01"
    skill_name = "integ-skills-global-only-skill"
    headers = {"X-Agent-Id": agent_id}
    _create_agent(app_server, agent_id)

    try:
        create = app_server.api_request(
            "POST",
            "/api/skills",
            headers=headers,
            json={
                "name": skill_name,
                "content": _skill_md(skill_name, "must be global"),
                "enable": False,
            },
        )
        assert create.status_code == 403, app_server.logs_tail()

        delete = app_server.api_request(
            "DELETE",
            f"/api/skills/{skill_name}",
            headers=headers,
        )
        assert delete.status_code == 403, app_server.logs_tail()
    finally:
        app_server.api_request("DELETE", f"/api/agents/{agent_id}")


@pytest.mark.integration
@pytest.mark.p0
def test_skills_import_list_batch_delete(app_server) -> None:
    """Imported workspace skills can be listed and batch-removed."""
    agent_id = "integ-skills-import-01"
    skill_name = "integ-skill-import-01"
    headers = {"X-Agent-Id": agent_id}
    _create_agent(app_server, agent_id)

    try:
        imported = _upload_workspace_skills(
            app_server,
            agent_id,
            {skill_name: _skill_md(skill_name, "integration import skill")},
        )
        assert imported.get("count") == 1

        listed = app_server.api_request("GET", "/api/skills", headers=headers)
        assert listed.status_code == 200, app_server.logs_tail()
        assert skill_name in {item["name"] for item in listed.json()}

        deleted = app_server.api_request(
            "POST",
            "/api/skills/batch-delete",
            headers=headers,
            json=[skill_name],
        )
        assert deleted.status_code == 200, app_server.logs_tail()
        assert deleted.json()["results"][skill_name]["success"] is True
    finally:
        app_server.api_request("DELETE", f"/api/agents/{agent_id}")


@pytest.mark.integration
@pytest.mark.p0
def test_skills_disable_enable(app_server) -> None:
    """Single-skill enable state changes persist through header routing."""
    agent_id = "integ-skills-toggle-01"
    skill_name = "integ-skill-toggle-01"
    headers = {"X-Agent-Id": agent_id}
    _create_agent(app_server, agent_id)

    try:
        _upload_workspace_skills(
            app_server,
            agent_id,
            {skill_name: _skill_md(skill_name, "integration toggle skill")},
            enable=True,
        )
        disabled = app_server.api_request(
            "POST",
            f"/api/skills/{skill_name}/disable",
            headers=headers,
        )
        assert disabled.status_code == 200, app_server.logs_tail()
        assert disabled.json().get("disabled") is True

        enabled = app_server.api_request(
            "POST",
            f"/api/skills/{skill_name}/enable",
            headers=headers,
        )
        assert enabled.status_code == 200, app_server.logs_tail()
        assert enabled.json().get("enabled") is True
    finally:
        app_server.api_request("DELETE", f"/api/agents/{agent_id}")


@pytest.mark.integration
@pytest.mark.p1
def test_skills_batch_enable_disable_partial_success(app_server) -> None:
    """Batch state changes report success independently for each name."""
    agent_id = "integ-skills-batch-state-01"
    skill_names = ["integ-skill-batch-a", "integ-skill-batch-b"]
    missing = "integ-skill-batch-missing"
    headers = {"X-Agent-Id": agent_id}
    _create_agent(app_server, agent_id)

    try:
        _upload_workspace_skills(
            app_server,
            agent_id,
            {
                name: _skill_md(name, "integration batch skill")
                for name in skill_names
            },
        )
        enabled = app_server.api_request(
            "POST",
            "/api/skills/batch-enable",
            headers=headers,
            json=[*skill_names, missing],
        )
        assert enabled.status_code == 200, app_server.logs_tail()
        enable_results = enabled.json()["results"]
        assert all(enable_results[name]["success"] for name in skill_names)
        assert enable_results[missing]["success"] is False

        disabled = app_server.api_request(
            "POST",
            "/api/skills/batch-disable",
            headers=headers,
            json=[*skill_names, missing],
        )
        assert disabled.status_code == 200, app_server.logs_tail()
        disable_results = disabled.json()["results"]
        assert all(disable_results[name]["success"] for name in skill_names)
        assert disable_results[missing]["success"] is False
    finally:
        app_server.api_request("DELETE", f"/api/agents/{agent_id}")


@pytest.mark.integration
@pytest.mark.p2
def test_skills_upload_duplicate_name_rejected(app_server) -> None:
    """A second ZIP import reports a conflict without overwriting."""
    agent_id = "integ-skills-duplicate-01"
    skill_name = "integ-skill-duplicate-01"
    headers = {"X-Agent-Id": agent_id}
    content = _skill_md(skill_name, "integration duplicate skill")
    _create_agent(app_server, agent_id)

    try:
        _upload_workspace_skills(
            app_server,
            agent_id,
            {skill_name: content},
        )
        duplicate = app_server.api_request(
            "POST",
            "/api/skills/upload",
            headers=headers,
            files={
                "file": (
                    "skills.zip",
                    _skill_zip({skill_name: content}),
                    "application/zip",
                ),
            },
            data={"enable": "false"},
        )
        assert duplicate.status_code == 409, app_server.logs_tail()
        detail = duplicate.json().get("detail", {})
        assert detail.get("conflicts")
    finally:
        app_server.api_request("DELETE", f"/api/agents/{agent_id}")


@pytest.mark.integration
@pytest.mark.p2
def test_skills_upload_invalid_skill_md_rejected(app_server) -> None:
    """ZIP import validates required SKILL.md frontmatter."""
    agent_id = "integ-skills-invalid-01"
    skill_name = "integ-skill-invalid-01"
    headers = {"X-Agent-Id": agent_id}
    invalid_md = f"---\nname: {skill_name}\n---\n\n# Missing description\n"
    _create_agent(app_server, agent_id)

    try:
        invalid = app_server.api_request(
            "POST",
            "/api/skills/upload",
            headers=headers,
            files={
                "file": (
                    "skills.zip",
                    _skill_zip({skill_name: invalid_md}),
                    "application/zip",
                ),
            },
            data={"enable": "true"},
        )
        assert invalid.status_code == 400, app_server.logs_tail()
        assert "frontmatter" in str(invalid.json().get("detail", "")).lower()
    finally:
        app_server.api_request("DELETE", f"/api/agents/{agent_id}")


@pytest.mark.integration
@pytest.mark.p2
def test_skills_enable_missing_skill_returns_404(app_server) -> None:
    agent_id = "integ-skills-enable-missing-01"
    headers = {"X-Agent-Id": agent_id}
    _create_agent(app_server, agent_id)

    try:
        response = app_server.api_request(
            "POST",
            "/api/skills/integ-skill-missing/enable",
            headers=headers,
        )
        assert response.status_code == 404, app_server.logs_tail()
    finally:
        app_server.api_request("DELETE", f"/api/agents/{agent_id}")


@pytest.mark.integration
@pytest.mark.p2
def test_skills_batch_delete_partial_success(app_server) -> None:
    agent_id = "integ-skills-batch-delete-01"
    existing = "integ-skill-batch-delete-existing"
    missing = "integ-skill-batch-delete-missing"
    headers = {"X-Agent-Id": agent_id}
    _create_agent(app_server, agent_id)

    try:
        _upload_workspace_skills(
            app_server,
            agent_id,
            {existing: _skill_md(existing, "integration batch delete")},
        )
        response = app_server.api_request(
            "POST",
            "/api/skills/batch-delete",
            headers=headers,
            json=[existing, missing],
        )
        assert response.status_code == 200, app_server.logs_tail()
        results = response.json()["results"]
        assert results[existing]["success"] is True
        assert results[missing]["success"] is False
    finally:
        app_server.api_request("DELETE", f"/api/agents/{agent_id}")
