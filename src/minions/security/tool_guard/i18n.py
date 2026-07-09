# -*- coding: utf-8 -*-
"""Tool guard i18n bundles — Chinese only."""

from __future__ import annotations

_TOOL_GUARD_I18N: dict[str, dict[str, str]] = {
    "zh": {
        "wait_title": "⏳ 等待审批",
        "risk_detected": "⚠️ **检测到风险**",
        "tool_blocked": "⛔ **工具已拦截**",
        "timeout_title": "⏰ **审批超时**",
        "tool": "工具",
        "severity": "严重性",
        "findings": "发现",
        "risk_summary": "风险说明",
        "triggered_by": "触发来源",
        "parameters": "参数",
        "reason": "原因",
        "reason_denied": "用户拒绝执行",
        "instruction_no_retry": ("用户已拒绝此次工具调用。请不要重试该调用，也不要尝试其他方法来完成这一次调用。"),
        "reason_timeout": "审批超时（{timeout}秒），自动拒绝",
        "approve_hint": "输入 `/approve` 批准执行，或发送任意消息拒绝。",
        "blocked_footer": "该工具已被禁止，无法批准执行。",
        "denied_list_msg": "该工具在禁止列表中。",
        "word_unknown": "未知",
        "risk_not_available": "暂不可用",
        "na_count": "不适用",
        "severity_denied": "已拦截",
        "sev_CRITICAL": "危急",
        "sev_HIGH": "高",
        "sev_MEDIUM": "中",
        "sev_LOW": "低",
        "sev_INFO": "提示",
        "sev_SAFE": "无风险",
        "guard_label_mixed": "工具护栏与文件护栏",
        "guard_label_file": "文件护栏",
        "guard_label_tool": "工具护栏",
        "guard_hint_mixed": ("由工具与文件护栏触发（可在「安全 → 工具护栏 / 文件护栏」" "调整）。"),
        "guard_hint_file": ("由文件护栏触发（可在「安全 → 文件护栏」调整）。"),
        "guard_hint_tool": ("由工具护栏触发（可在「安全 → 工具护栏」调整）。"),
    },
}
