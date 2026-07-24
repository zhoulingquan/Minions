# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest

from minions.agents.workspace_markdown import WorkspaceMarkdownManager


def test_workspace_markdown_round_trip(tmp_path: Path) -> None:
    manager = WorkspaceMarkdownManager(tmp_path)

    manager.write_document("AGENTS", "# Agent")

    assert manager.read_document("AGENTS.md") == "# Agent"
    assert [item["filename"] for item in manager.list_documents()] == [
        "AGENTS.md",
    ]


@pytest.mark.parametrize("name", ["../escape.md", "nested/../escape.md"])
def test_workspace_markdown_rejects_traversal(
    tmp_path: Path,
    name: str,
) -> None:
    manager = WorkspaceMarkdownManager(tmp_path)

    with pytest.raises(ValueError, match="traversal"):
        manager.write_document(name, "blocked")


def test_workspace_markdown_uses_only_top_level_documents(
    tmp_path: Path,
) -> None:
    manager = WorkspaceMarkdownManager(tmp_path)
    manager.write_document("SOUL.md", "soul")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "hidden.md").write_text("hidden", encoding="utf-8")

    assert [item["filename"] for item in manager.list_documents()] == [
        "SOUL.md",
    ]
