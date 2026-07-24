# -*- coding: utf-8 -*-
"""Shared ACP metadata keys.

Kept separate from the ACP server so the TUI and lifecycle hooks can use the
wire contract without importing the server implementation.
"""

ACP_EPHEMERAL_META_KEY = "minions.ephemeral"
ACP_APPROVAL_EXPIRES_AT_META_KEY = "minions.approval_expires_at"

__all__ = [
    "ACP_APPROVAL_EXPIRES_AT_META_KEY",
    "ACP_EPHEMERAL_META_KEY",
]
