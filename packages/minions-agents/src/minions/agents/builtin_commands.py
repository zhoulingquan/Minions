# -*- coding: utf-8 -*-
"""Built-in slash command adapters.

Wraps the agent-owned command mechanisms (control, conversation,
skill, and SAGE) as :class:`CommandSpec` instances registered
into a single :class:`SlashCommandRegistry`.  Each adapter reads
from :class:`HookContext` (``ctx.workspace``, ``ctx.agent``, etc.)
and delegates to the original handler.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..runtime._state_utils import StateProxy
from ..runtime.slash_command_registry import CommandSpec, FallbackHandler

if TYPE_CHECKING:
    from agentscope.message import Msg

logger = logging.getLogger(__name__)


# ======================================================================
# Control command adapters
# ======================================================================


def _make_control_adapter(
    handler: Any,
    command_name: str,
) -> CommandSpec:
    """Wrap a :class:`BaseControlCommandHandler` as
    a :class:`CommandSpec`.
    """

    async def _handler(ctx: Any, args: str) -> "Msg | None":
        from ..runtime.commands.control import parse_args
        from ..runtime.commands.control.base import ControlContext
        from agentscope.message import Msg, TextBlock

        workspace = getattr(ctx, "workspace", None)
        request = getattr(ctx, "request", None)

        if workspace is None:
            return Msg(
                name="assistant",
                role="assistant",
                content=[
                    TextBlock(
                        type="text",
                        text="**Error**\n\nControl command "
                        "unavailable (workspace not initialized)",
                    ),
                ],
            )

        channel = None
        channel_mgr = getattr(workspace, "channel_manager", None)
        if channel_mgr is not None:
            channel_id = getattr(request, "channel", None) or "console"
            try:
                channel = await channel_mgr.get_channel(
                    channel_id,
                )
            except Exception:
                pass

        full_query = (
            f"/{command_name} {args}".strip() if args else f"/{command_name}"
        )
        parsed_args = parse_args(
            full_query,
            f"/{command_name}",
        )

        ctrl_ctx = ControlContext(
            workspace=workspace,
            payload=request,
            channel=channel,
            session_id=getattr(ctx, "session_id", "") or "",
            user_id=(getattr(request, "user_id", "") if request else "") or "",
            agent_id=getattr(ctx, "agent_id", "") or "",
            args=parsed_args,
        )

        try:
            text = await handler.handle(ctrl_ctx)
        except Exception as e:
            logger.exception(
                "Control command failed: /%s",
                command_name,
            )
            text = f"**Command Failed**\n\n{e}"

        return Msg(
            name="assistant",
            role="assistant",
            content=[TextBlock(type="text", text=text)],
        )

    return CommandSpec(
        name=command_name,
        handler=_handler,
        category="control",
    )


def _collect_control_specs() -> list[CommandSpec]:
    from ..runtime.commands.control import _COMMAND_REGISTRY

    specs = []
    seen_names: set[str] = set()
    for raw_name, handler in _COMMAND_REGISTRY.items():
        name = raw_name.lstrip("/")
        if name in seen_names:
            continue
        seen_names.add(name)
        specs.append(_make_control_adapter(handler, name))
    return specs


# ======================================================================
# Conversation command adapters
# ======================================================================

_CONVERSATION_COMMANDS = frozenset(
    {
        "compact",
        "new",
        "clear",
        "history",
        "compact_str",
        "message",
        "dump_history",
        "load_history",
        "plan",
        "system_prompt",
    },
)


async def _load_agent_state(ctx: Any) -> "tuple[Any, dict]":
    """Load AgentState from workspace.session without building the agent.

    Returns ``(state, payload)`` where ``payload`` is the raw saved session
    dict — so callers can read/preserve the persisted ``"scroll"`` checkpoint
    block (the scroll context manager's bookkeeping) instead of dropping it.
    """
    from agentscope.state import AgentState

    workspace = getattr(ctx, "workspace", None)
    if workspace is None:
        return None, {}
    session = getattr(workspace, "session", None)
    if session is None:
        return None, {}

    request = getattr(ctx, "request", None)
    user_id = (getattr(request, "user_id", "") if request else "") or ""
    channel = (getattr(request, "channel", "") if request else "") or ""

    proxy = StateProxy()
    await session.load_session_state(
        session_id=ctx.session_id,
        user_id=user_id or ctx.session_id,
        channel=channel,
        agent=proxy,
    )
    payload = proxy.data or {}
    if not payload:
        return AgentState(), {}

    raw = payload.get("state")
    if raw is not None:
        return AgentState.model_validate(raw), payload

    # Legacy 1.x format
    memory_raw = payload.get("memory")
    if isinstance(memory_raw, dict):
        from .state_compat import parse_legacy_memory_state

        msgs, summary = parse_legacy_memory_state(memory_raw)
        state = AgentState()
        state.context.extend(msgs)
        state.summary = summary
        return state, payload

    return AgentState(), payload


async def _save_agent_state(
    ctx: Any,
    state: "Any",
    *,
    scroll_block: dict | None = None,
) -> None:
    """Save AgentState back to workspace.session.

    ``scroll_block`` is the scroll context manager's checkpoint to persist
    alongside the state (mirroring ``MinionsAgent.state_dict``'s ``"scroll"``
    key). Passing ``None`` writes no scroll block — callers that want to
    *preserve* the existing one must pass it back in explicitly.
    """
    workspace = getattr(ctx, "workspace", None)
    if workspace is None:
        return
    session = getattr(workspace, "session", None)
    if session is None:
        return

    request = getattr(ctx, "request", None)
    user_id = (getattr(request, "user_id", "") if request else "") or ""
    channel = (getattr(request, "channel", "") if request else "") or ""

    proxy = StateProxy()
    proxy.data = {"state": state.model_dump(mode="json")}
    if scroll_block is not None:
        proxy.data["scroll"] = scroll_block
    await session.save_session_state(
        session_id=ctx.session_id,
        user_id=user_id or ctx.session_id,
        channel=channel,
        agent=proxy,
    )


def _resolve_scroll_block(
    *,
    updated: dict | None,
    context_empty: bool,
    existing: dict | None,
) -> dict | None:
    """Decide which scroll checkpoint a conversation command should persist.

    Keeps the scroll context manager's bookkeeping consistent with the
    command's effect on ``state.context``:

    * ``updated`` set    — a scroll ``/compact`` refreshed it → save it.
    * ``context_empty``  — ``/clear`` / ``/new`` wiped the window → drop it
      (reset), so a stale eviction index doesn't resurface old turns.
    * otherwise          — preserve the existing block (read-only commands must
      not nuke it, which was the prior bug).
    """
    if updated is not None:
        return updated
    if context_empty:
        return None
    return existing


def _make_conversation_adapter(name: str) -> CommandSpec:
    """Wrap one conversation command via standalone CommandHandler.

    Loads AgentState directly from session — no agent instance required.
    """

    async def _handler(ctx: Any, args: str) -> "Msg | None":
        from .command_handler import CommandHandler

        # /plan with arguments is NOT a command — fall through to model
        if name == "plan" and args.strip():
            return None

        workspace = getattr(ctx, "workspace", None)
        if workspace is None:
            return None

        state, payload = await _load_agent_state(ctx)
        if state is None:
            return None
        existing_scroll = payload.get("scroll")

        agent_id = getattr(ctx, "agent_id", None) or "default"
        ws_dir = str(getattr(workspace, "workspace_dir", "")) or None

        offloader = None
        from .offloader import MinionsOffloader

        try:
            if ws_dir:
                import os

                from ..config.config import load_agent_config

                cfg = load_agent_config(agent_id)
                lcc = cfg.running.light_context_config
                # Under scroll, dialog archiving is opt-in (history.db is the
                # source of truth); only wire an offloader for the commands
                # when ``offload_dialog`` is on. Native keeps it always.
                want_dialog = lcc.strategy != "scroll" or getattr(
                    lcc.scroll_config,
                    "offload_dialog",
                    False,
                )
                if want_dialog:
                    offloader = MinionsOffloader(
                        dialog_path=os.path.join(ws_dir, lcc.dialog_path),
                        tool_results_dir=os.path.join(
                            ws_dir,
                            lcc.tool_result_pruning_config.tool_results_cache,
                        ),
                    )
        except Exception:
            pass

        try:
            cfg = load_agent_config(agent_id)
            agent_name = cfg.name if cfg and cfg.name else "Minions"
        except Exception:
            agent_name = "Minions"

        cmd_handler = CommandHandler(
            agent_name=agent_name,
            state=state,
            agent_id=agent_id,
            offloader=offloader,
            workspace_dir=ws_dir,
            scroll_state=existing_scroll,
            session_id=getattr(ctx, "session_id", None),
            prompt_context=ctx,
        )

        full_query = f"/{name} {args}".strip() if args else f"/{name}"
        result = await cmd_handler.handle_command(full_query)

        scroll_block = _resolve_scroll_block(
            updated=cmd_handler.updated_scroll_state,
            context_empty=not state.context,
            existing=existing_scroll,
        )
        await _save_agent_state(ctx, state, scroll_block=scroll_block)
        return result

    return CommandSpec(
        name=name,
        handler=_handler,
        category="conversation",
    )


def _collect_conversation_specs() -> list[CommandSpec]:
    return [
        _make_conversation_adapter(n) for n in sorted(_CONVERSATION_COMMANDS)
    ]


# ======================================================================
# Skill fallback handler
# ======================================================================


def _parse_skill_query(query: str) -> tuple[str, str] | None:
    """Parse ``/name [input]`` or ``/[name with spaces] [input]``."""
    stripped = query.strip()
    if not stripped.startswith("/"):
        return None
    rest = stripped[1:]
    if rest.startswith("["):
        close = rest.find("]")
        if close < 0:
            return None
        name = rest[1:close].strip().lower()
        user_input = rest[close + 1 :].strip()
        return (name, user_input) if name else None
    parts = rest.split(None, 1)
    if not parts:
        return None
    name = parts[0].lower()
    user_input = parts[1] if len(parts) > 1 else ""
    return (name, user_input) if name else None


# pylint: disable-next=too-many-return-statements
async def _skill_fallback_handler(
    raw_text: str,
    ctx: Any,
) -> "Msg | None":
    """Fallback handler for ``/<skill_name>`` dispatch.

    Resolves skills directly from the filesystem (workspace/skills/
    directory) — no agent or toolkit required.
    """
    from agentscope.message import Msg, TextBlock

    workspace = getattr(ctx, "workspace", None)
    if workspace is None:
        return None

    workspace_dir = getattr(workspace, "workspace_dir", None)
    if not workspace_dir:
        return None

    parsed = _parse_skill_query(raw_text)
    if not parsed:
        return None
    skill_name, user_input = parsed

    from .skill_system.registry import (
        get_workspace_skills_dir,
        resolve_effective_skills,
    )

    request = getattr(ctx, "request", None)
    channel = (getattr(request, "channel", "") if request else "") or "console"

    try:
        effective_skills = resolve_effective_skills(
            Path(workspace_dir),
            channel,
        )
    except Exception:
        return None

    skills_dir = get_workspace_skills_dir(Path(workspace_dir))
    skill_dir = next(
        (
            skills_dir / sn
            for sn in effective_skills
            if sn.lower() == skill_name
        ),
        None,
    )
    if skill_dir is None or not skill_dir.exists():
        return None

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    from .utils.file_handling import (
        read_text_file_with_encoding_fallback,
    )

    import frontmatter as fm

    raw = read_text_file_with_encoding_fallback(skill_md)
    post = fm.loads(raw)
    display_name = post.get("name") or skill_name

    if not user_input:
        desc = post.get("description") or "No description."
        return Msg(
            name="assistant",
            role="assistant",
            content=[
                TextBlock(
                    type="text",
                    text=(
                        f"**{skill_name}**\n\n"
                        f"- **command**: `/{skill_name} <input>` to invoke\n"
                        f"- **name**: {display_name}\n"
                        f"- **description**: {desc}\n"
                        f"- **path**: `{skill_dir}`"
                    ),
                ),
            ],
        )

    # Rewrite last message with skill body — agent will execute with it
    merged = (
        f"Use the [{display_name}] skill in "
        f"`{skill_dir}` to fulfill "
        f"user's task: {user_input}\n\n"
        f"{post.content}"
    )
    msgs = getattr(ctx, "input_msgs", None)
    if msgs:
        last = msgs[-1]
        content = getattr(last, "content", None)
        if isinstance(content, list):
            for i, block in enumerate(content):
                btype = (
                    block.get("type")
                    if isinstance(block, dict)
                    else getattr(block, "type", None)
                )
                if btype == "text":
                    content[i] = TextBlock(type="text", text=merged)
                    return None
            content.insert(0, TextBlock(type="text", text=merged))
        elif isinstance(content, str):
            last.content = merged
    return None


# ======================================================================
# Factory
# ======================================================================


def collect_builtin_command_specs() -> list[CommandSpec]:
    """Return all agent-owned built-in command specs.

    These are registered into each workspace's :class:`SlashCommandRegistry`
    via ``bootstrap_plugins(builtin_command_specs=...)``.
    """
    specs: list[CommandSpec] = []
    specs.extend(_collect_control_specs())
    specs.extend(_collect_conversation_specs())
    from ..sage.commands import build_sage_command_specs

    specs.extend(build_sage_command_specs())
    return specs


def get_skill_fallback_handler() -> FallbackHandler:
    """Return the ``/<skill_name>`` fallback dispatch handler."""
    return _skill_fallback_handler


__all__ = [
    "collect_builtin_command_specs",
    "get_skill_fallback_handler",
]
