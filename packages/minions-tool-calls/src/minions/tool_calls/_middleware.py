# -*- coding: utf-8 -*-
"""on_acting middleware delegating tool execution to ToolCoordinator."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable

from agentscope.middleware import MiddlewareBase

if TYPE_CHECKING:
    from agentscope.agent import Agent

    from ._coordinator import ToolCoordinator
    from ._result_limiter import ToolResultLimiter

logger = logging.getLogger(__name__)


class ToolCoordinatorMiddleware(MiddlewareBase):
    """Thin on_acting middleware delegating to ToolCoordinator.

    Uses agentscope 2.0's official extension point — no Toolkit subclass.
    Direct access to agent.request_context (no ContextVar indirection).
    ``_execute_tool_call`` side effects work automatically.
    """

    def __init__(
        self,
        coordinator: "ToolCoordinator",
        result_limiter: "ToolResultLimiter | None" = None,
        parallel_enabled: bool = True,
    ) -> None:
        self._coordinator = coordinator
        self._result_limiter = result_limiter
        # When True, callers may use ``execute_parallel`` to run multiple tool
        # calls concurrently. Set to False to disable parallel execution for
        # debugging purposes.
        self.parallel_enabled = parallel_enabled

    async def execute_parallel(
        self,
        agent: "Agent",
        tool_calls: list[tuple[Any, Callable[..., AsyncGenerator[Any, None]]]],
    ) -> list[list[Any]]:
        """Execute multiple tool calls in parallel.

        Returns a list of event lists, one per tool_call, preserving order.
        """
        request_context = getattr(agent, "_request_context", None) or {}
        session_id = request_context.get("session_id", "")
        agent_id = request_context.get("agent_id", "")
        root_session_id = request_context.get("root_session_id", "")

        async def _execute_one(
            tool_call: Any,
            next_handler: Callable[..., AsyncGenerator[Any, None]],
        ) -> list[Any]:
            events: list[Any] = []
            async for item in self._coordinator.execute(
                tool_call=tool_call,
                next_handler=next_handler,
                session_id=session_id,
                agent_id=agent_id,
                root_session_id=root_session_id,
                result_finalizer=(
                    self._result_limiter.limit_async
                    if self._result_limiter is not None
                    else None
                ),
            ):
                events.append(item)
            return events

        tasks = [
            _execute_one(tc, nh)
            for tc, nh in tool_calls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to empty event lists with error logging
        final_results: list[list[Any]] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Parallel tool execution failed for tool_call %s: %s",
                    getattr(tool_calls[i][0], "id", "unknown"),
                    result,
                    exc_info=True,
                )
                final_results.append([])
            else:
                final_results.append(result)
        return final_results

    async def on_acting(
        self,
        agent: "Agent",
        input_kwargs: dict[str, Any],
        next_handler: Callable[..., AsyncGenerator[Any, None]],
    ) -> AsyncGenerator[Any, None]:
        tool_call = input_kwargs["tool_call"]

        request_context = getattr(agent, "_request_context", None) or {}
        session_id = request_context.get("session_id", "")
        agent_id = request_context.get("agent_id", "")
        root_session_id = request_context.get("root_session_id", "")

        async for item in self._coordinator.execute(
            tool_call=tool_call,
            next_handler=next_handler,
            session_id=session_id,
            agent_id=agent_id,
            root_session_id=root_session_id,
            result_finalizer=(
                self._result_limiter.limit_async
                if self._result_limiter is not None
                else None
            ),
        ):
            yield item
