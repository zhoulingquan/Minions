# -*- coding: utf-8 -*-
"""Source contracts for modes/governance/loop dependency direction."""
from __future__ import annotations

from pathlib import Path
import importlib


REPO_ROOT = Path(__file__).resolve().parents[3]
OWNER_ROOTS = {
    "modes": REPO_ROOT
    / "packages"
    / "minions-modes"
    / "src"
    / "minions"
    / "modes",
    "governance": REPO_ROOT
    / "packages"
    / "minions-governance"
    / "src"
    / "minions"
    / "governance",
    "loop": REPO_ROOT
    / "packages"
    / "minions-loop"
    / "src"
    / "minions"
    / "loop",
}


def _offenders(owner: str, forbidden: tuple[str, ...]) -> list[str]:
    result: list[str] = []
    for path in OWNER_ROOTS[owner].rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if any(token in source for token in forbidden):
            result.append(path.relative_to(REPO_ROOT).as_posix())
    return result


def test_modes_depend_only_downward_within_domain_band() -> None:
    assert _offenders(
        "modes",
        (
            "from minions.agents",
            "import minions.agents",
            "from minions.app",
            "import minions.app",
            "from ..agents",
            "from ...agents",
            "from ..app",
            "from ...app",
        ),
    ) == []


def test_governance_and_loop_do_not_depend_upward_or_on_each_other() -> None:
    forbidden = (
        "from minions.agents",
        "import minions.agents",
        "from minions.app",
        "import minions.app",
        "from minions.modes",
        "import minions.modes",
        "from ..agents",
        "from ...agents",
        "from ..app",
        "from ...app",
        "from ..modes",
        "from ...modes",
    )
    assert _offenders(
        "governance",
        forbidden + ("minions.loop", "from ..loop", "from ...loop"),
    ) == []
    assert _offenders(
        "loop",
        forbidden
        + ("minions.governance", "from ..governance", "from ...governance"),
    ) == []


def test_domain_layers_use_core_context_not_app_context() -> None:
    for owner in ("modes", "governance", "loop"):
        assert _offenders(owner, ("app.agent_context",)) == []


def test_driver_policy_prompt_is_owned_by_drivers() -> None:
    driver_prompt = importlib.import_module("minions.drivers.prompt")
    agent_prompt = importlib.import_module("minions.agents.prompt")

    assert agent_prompt.build_driver_policy_recheck_hint is (
        driver_prompt.build_driver_policy_recheck_hint
    )
