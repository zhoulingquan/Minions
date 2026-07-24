# -*- coding: utf-8 -*-
"""Register agent-owned control command handlers into runtime."""
from __future__ import annotations

from ...runtime.commands.control import register_command
from .model import ModelCommandHandler
from .skills import SkillsCommandHandler


def register_agent_control_handlers() -> None:
    """Idempotently configure the agent-owned command slots."""
    register_command(ModelCommandHandler())
    register_command(SkillsCommandHandler())


__all__ = [
    "ModelCommandHandler",
    "SkillsCommandHandler",
    "register_agent_control_handlers",
]
