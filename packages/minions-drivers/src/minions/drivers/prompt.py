# -*- coding: utf-8 -*-
"""Prompt guidance owned by the Driver policy boundary."""

DRIVER_POLICY_RECHECK_HINT = (
    "Driver and MCP permission results are evaluated at the moment of a "
    "tool call. A previous `driver_policy_denied` result in the "
    "conversation history does not prove the tool is still denied in a "
    "later user turn, because users may change Driver policy between "
    "messages. If the user asks for the action again in a later turn, "
    "attempt the relevant tool again and let the current policy decide. "
    "Previous assistant messages that only explained such a denial are "
    "also point-in-time. "
    "Do not refuse solely because of an earlier `driver_policy_denied` "
    "result."
)


def build_driver_policy_recheck_hint() -> str:
    """Build guidance for point-in-time Driver/MCP policy results."""
    return DRIVER_POLICY_RECHECK_HINT


__all__ = ["DRIVER_POLICY_RECHECK_HINT", "build_driver_policy_recheck_hint"]
