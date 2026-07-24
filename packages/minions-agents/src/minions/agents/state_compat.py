# -*- coding: utf-8 -*-
"""Compatibility parsing for pre-AgentScope-2 session state."""
from __future__ import annotations

from agentscope.message import Msg


def parse_legacy_memory_state(
    memory_raw: dict,
) -> tuple[list[Msg], str]:
    """Parse a 1.x ``InMemoryMemory.state_dict()`` payload."""
    messages: list[Msg] = []
    for item in memory_raw.get("content", []) or []:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            payload = item[0]
        else:
            payload = item
        if isinstance(payload, dict):
            messages.append(Msg.from_dict(payload))
        elif isinstance(payload, Msg):
            messages.append(payload)
    summary = memory_raw.get("_compressed_summary") or ""
    return messages, summary
