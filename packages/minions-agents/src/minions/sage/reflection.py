"""Conservative reflection over server-recorded SAGE evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .models import CaseOutcome, CaseRecord, Principal, RiskLevel, Trace, TraceType

if TYPE_CHECKING:
    from .store import SageStore


_SECRET_LINE = re.compile(
    r"(?i)(password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"authorization|credential|cookie|secret|密码|密钥|令牌)\s*[:=]",
)


@dataclass(frozen=True, slots=True)
class ReflectedLesson:
    """Bounded lesson proposal derived from immutable traces."""

    title: str
    content: str
    applicability: dict[str, object]
    confidence: float
    risk_level: RiskLevel
    lesson: str


class ReflectionEngine:
    """Build reviewable lessons without declaring business success."""

    def __init__(self, store: "SageStore") -> None:
        self._store = store

    async def reflect(
        self,
        principal: Principal,
        case: CaseRecord,
        *,
        provisional: bool,
    ) -> ReflectedLesson:
        traces = await self._store.list_traces(
            principal,
            case_id=case.case_id,
            limit=1000,
        )
        user_input = self._latest(traces, TraceType.USER_INPUT)
        agent_output = self._latest(traces, TraceType.AGENT_OUTPUT)
        tool_results = self._latest_many(traces, TraceType.TOOL_RESULT, limit=3)

        goal = self.safe_excerpt(case.goal or user_input, max_chars=900)
        verified_summary = self.safe_excerpt(case.decision_summary, max_chars=1800)
        approach = verified_summary or self.safe_excerpt(
            agent_output or "\n".join(tool_results),
            max_chars=1800,
        )
        if not approach:
            approach = "已记录执行过程，等待复核人员补充可复用做法。"

        subject = case.process or case.task_type or case.domain or "业务任务"
        result = (
            "等待有权限的成员确认，当前内容不能作为已验证知识。"
            if provisional
            else self._verified_result(case.outcome)
        )
        parts = [
            f"业务目标：{goal or subject}",
            f"已采取的做法：{approach}",
            f"业务结果：{result}",
        ]
        context = [
            value
            for value in (
                f"领域={case.domain}" if case.domain else "",
                f"流程={case.process}" if case.process else "",
                f"任务类型={case.task_type}" if case.task_type else "",
            )
            if value
        ]
        if context:
            parts.append("适用条件：" + "；".join(context))
        parts.append(
            "使用边界：历史经验仅供参考，应用前仍需核对当前业务条件。",
        )
        return ReflectedLesson(
            title=f"{subject[:220]}经验",
            content="\n".join(parts)[:4000],
            applicability={
                "domain": case.domain,
                "process": case.process,
                "task_type": case.task_type,
                "provisional": provisional,
                "outcome": case.outcome.value,
            },
            confidence=(
                0.15
                if provisional
                else 0.45
                if case.outcome is CaseOutcome.SUCCESS
                else 0.35
            ),
            risk_level=RiskLevel.LOW,
            lesson=verified_summary or approach,
        )

    @staticmethod
    def safe_excerpt(value: str, *, max_chars: int = 2400) -> str:
        """Remove credential-shaped lines and bound persisted reflection text."""

        lines = []
        for raw_line in str(value or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lines.append("[敏感内容已省略]" if _SECRET_LINE.search(line) else line)
        return "\n".join(lines)[: max(0, int(max_chars))]

    @staticmethod
    def _latest(traces: list[Trace], trace_type: TraceType) -> str:
        return next(
            (
                trace.content
                for trace in reversed(traces)
                if trace.trace_type is trace_type and trace.content.strip()
            ),
            "",
        )

    @staticmethod
    def _latest_many(
        traces: list[Trace],
        trace_type: TraceType,
        *,
        limit: int,
    ) -> list[str]:
        values = [
            trace.content
            for trace in reversed(traces)
            if trace.trace_type is trace_type and trace.content.strip()
        ]
        return list(reversed(values[: max(0, limit)]))

    @staticmethod
    def _verified_result(outcome: CaseOutcome) -> str:
        return {
            CaseOutcome.SUCCESS: "已由可信主体确认成功。",
            CaseOutcome.PARTIAL: "已由可信主体确认部分达成。",
            CaseOutcome.FAILURE: "已由可信主体确认未达成。",
            CaseOutcome.CANCELLED: "任务已取消。",
            CaseOutcome.UNKNOWN: "结果尚未确认。",
        }[outcome]


__all__ = ["ReflectedLesson", "ReflectionEngine"]
