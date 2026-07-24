# -*- coding: utf-8 -*-
"""Register application-owned control command handlers into runtime."""
from __future__ import annotations

from ...runtime.commands.control import register_command
from .approval import (
    ApprovalCommandHandler,
    ApproveCommandHandler,
    DenyCommandHandler,
)


def register_app_control_handlers() -> None:
    """Idempotently configure the application-owned command slots."""
    register_command(ApprovalCommandHandler())
    register_command(ApproveCommandHandler())
    register_command(DenyCommandHandler())


__all__ = [
    "ApprovalCommandHandler",
    "ApproveCommandHandler",
    "DenyCommandHandler",
    "register_app_control_handlers",
]
