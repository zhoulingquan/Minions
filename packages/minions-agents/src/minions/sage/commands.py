"""SAGE-native slash commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from ..runtime.slash_command_registry import CommandSpec
from .lifecycle import resolve_sage_principal
from .models import FeedbackVerdict, SageCapability

if TYPE_CHECKING:
    from agentscope.message import Msg


def build_sage_command_specs() -> list[CommandSpec]:
    return [
        CommandSpec(
            name="sage-status",
            handler=_sage_status,
            category="sage",
            help_text="Show trusted SAGE identity and storage availability.",
        ),
        CommandSpec(
            name="sage-find",
            handler=_sage_find,
            category="sage",
            help_text="Find authorized SAGE facts, lessons, and playbooks.",
        ),
        CommandSpec(
            name="sage-feedback",
            handler=_sage_feedback,
            category="sage",
            help_text="Correct a SAGE recall result so future recall can improve.",
        ),
        CommandSpec(
            name="sage-policy",
            handler=_sage_policy,
            category="sage",
            help_text="Show the effective SAGE capability activation policy.",
        ),
    ]


async def _sage_status(ctx: Any, _args: str) -> "Msg":
    principal = resolve_sage_principal(ctx)
    runtime = _runtime(ctx)
    if principal is None:
        return _message(
            "SAGE is disabled for this request: no trusted tenant identity.",
        )
    if runtime is None:
        return _message("SAGE workspace service is unavailable.")
    backend = type(runtime.store).__name__
    return _message(
        "SAGE is active.\n"
        f"Tenant: {principal.tenant_id}\n"
        f"User: {principal.user_id}\n"
        f"Agent: {principal.agent_uid}\n"
        f"Store: {backend}",
    )


async def _sage_find(ctx: Any, args: str) -> "Msg":
    query = args.strip()
    if not query:
        return _message("Usage: /sage-find <business question>")
    principal = resolve_sage_principal(ctx)
    runtime = _runtime(ctx)
    if principal is None or runtime is None:
        return _message("SAGE search requires a trusted tenant identity.")
    pack = await runtime.prepare(principal, query, token_budget=800)
    if not pack.source_ids:
        return _message("No authorized SAGE experience matched this query.")
    lines = [f"SAGE results for: {query}"]
    if pack.receipt is not None:
        lines.append(f"Receipt: {pack.receipt.receipt_id}")
    for item in (
        *pack.anchors,
        *pack.known_facts,
        *pack.insights,
        *pack.warnings,
    ):
        lines.append(
            f"- [{item.kind.value}] {item.title}: {item.content} "
            f"(source {item.item_id})",
        )
    for playbook in pack.playbooks:
        lines.append(
            f"- [playbook] {playbook.name} "
            f"(source {playbook.playbook_id})",
        )
    return _message("\n".join(lines))


async def _sage_feedback(ctx: Any, args: str) -> "Msg":
    parts = args.strip().split(maxsplit=2)
    if len(parts) < 2:
        return _message(
            "Usage: /sage-feedback <receipt-id> "
            "<useful|irrelevant|wrong|outdated> [source-id] [comment]",
        )
    try:
        receipt_id = UUID(parts[0])
        verdict = FeedbackVerdict(parts[1].lower())
    except ValueError:
        return _message("Invalid receipt id or feedback verdict.")

    source_id = None
    comment = ""
    if len(parts) == 3:
        candidate, separator, remainder = parts[2].partition(" ")
        try:
            source_id = UUID(candidate)
            comment = remainder if separator else ""
        except ValueError:
            comment = parts[2]

    principal = resolve_sage_principal(ctx)
    runtime = _runtime(ctx)
    if principal is None or runtime is None:
        return _message("SAGE feedback requires a trusted tenant identity.")
    await runtime.feedback(
        principal,
        receipt_id=receipt_id,
        verdict=verdict,
        source_id=source_id,
        comment=comment,
    )
    return _message(f"Feedback recorded for receipt {receipt_id}.")


async def _sage_policy(ctx: Any, args: str) -> "Msg":
    principal = resolve_sage_principal(ctx)
    runtime = _runtime(ctx)
    if principal is None or runtime is None:
        return _message("SAGE policy requires a trusted tenant identity.")
    requested = args.strip().lower()
    if requested:
        try:
            capabilities = (SageCapability(requested),)
        except ValueError:
            return _message(f"Unknown SAGE capability: {requested}")
    else:
        capabilities = tuple(SageCapability)
    lines = ["SAGE capability policy:"]
    for capability in capabilities:
        policy = await runtime.control.resolve(principal, capability)
        source = "configured" if policy.modified_by is not None else "default"
        lines.append(f"- {capability.value}: {policy.mode.value} ({source})")
    return _message("\n".join(lines))


def _runtime(ctx: Any) -> Any:
    workspace = getattr(ctx, "workspace", None)
    return getattr(workspace, "sage_runtime", None) if workspace else None


def _message(text: str) -> "Msg":
    from agentscope.message import Msg, TextBlock

    return Msg(
        name="assistant",
        role="assistant",
        content=[TextBlock(type="text", text=text)],
    )


__all__ = ["build_sage_command_specs"]
