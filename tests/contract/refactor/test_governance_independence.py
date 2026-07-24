# -*- coding: utf-8 -*-
"""Contracts for governance dependency injection and isolation."""
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
GOVERNANCE_ROOT = (
    REPO_ROOT
    / "packages"
    / "minions-governance"
    / "src"
    / "minions"
    / "governance"
)


def test_governance_tree_has_no_agents_or_app_dependencies() -> None:
    offenders: list[str] = []
    forbidden = (
        "from ..agents",
        "from minions.agents",
        "import minions.agents",
        "from ..app",
        "from minions.app",
        "import minions.app",
    )
    for path in GOVERNANCE_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if any(token in source for token in forbidden):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert offenders == []
