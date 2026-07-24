"""Tenant capability control plane for governed SAGE activation."""

from __future__ import annotations

from dataclasses import dataclass

from .models import (
    ActivationMode,
    CapabilityPolicy,
    Principal,
    RiskLevel,
    SageCapability,
    ScopeRef,
    utc_now,
)
from .policy import ScopePolicy
from .store import SageStore


_RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """An executable interpretation of one resolved capability policy."""

    policy: CapabilityPolicy
    execute: bool
    apply: bool
    requires_approval: bool
    reason: str


class PolicyCenter:
    """Resolve tenant defaults and exact-scope activation overrides."""

    def __init__(self, store: SageStore) -> None:
        self._store = store

    async def resolve(
        self,
        principal: Principal,
        capability: SageCapability,
        *,
        scope: ScopeRef | None = None,
    ) -> CapabilityPolicy:
        if scope is not None:
            ScopePolicy.require_scope(principal, scope)
        policies = await self._store.list_capability_policies(
            principal,
            capability=capability,
        )
        if scope is not None:
            exact = next((policy for policy in policies if policy.scope == scope), None)
            if exact is not None:
                return exact
        tenant_default = next(
            (policy for policy in policies if policy.scope is None),
            None,
        )
        return tenant_default or CapabilityPolicy.default_for(
            principal.tenant_id,
            capability,
        )

    async def set_policy(
        self,
        principal: Principal,
        *,
        capability: SageCapability,
        mode: ActivationMode,
        scope: ScopeRef | None = None,
        max_auto_risk: RiskLevel = RiskLevel.LOW,
        settings: dict[str, object] | None = None,
    ) -> CapabilityPolicy:
        ScopePolicy.require_permission(principal, "sage.policy.manage")
        if scope is not None:
            ScopePolicy.require_write_scope(principal, scope)
        proposed = CapabilityPolicy.create(
            tenant_id=principal.tenant_id,
            capability=capability,
            mode=mode,
            scope=scope,
            max_auto_risk=max_auto_risk,
            settings=dict(settings or {}),
            modified_by=principal.user_id,
        )
        current = await self._store.get_capability_policy(
            principal,
            proposed.policy_id,
        )
        if current is not None:
            proposed = current.model_copy(
                update={
                    "mode": mode,
                    "max_auto_risk": max_auto_risk,
                    "settings": dict(settings or {}),
                    "version": current.version + 1,
                    "modified_by": principal.user_id,
                    "updated_at": utc_now(),
                },
            )
        return await self._store.save_capability_policy(principal, proposed)

    async def decision(
        self,
        principal: Principal,
        capability: SageCapability,
        *,
        scope: ScopeRef | None = None,
        risk: RiskLevel = RiskLevel.LOW,
        force_approval: bool = False,
    ) -> PolicyDecision:
        policy = await self.resolve(principal, capability, scope=scope)
        if policy.mode is ActivationMode.OFF:
            return PolicyDecision(policy, False, False, False, "capability_off")
        if policy.mode is ActivationMode.SHADOW:
            return PolicyDecision(policy, True, False, False, "shadow_only")
        if policy.mode is ActivationMode.APPROVAL:
            return PolicyDecision(policy, True, False, True, "approval_mode")
        within_risk = _RISK_ORDER[risk] <= _RISK_ORDER[policy.max_auto_risk]
        if force_approval or not within_risk:
            reason = "forced_approval" if force_approval else "risk_above_auto_limit"
            return PolicyDecision(policy, True, False, True, reason)
        return PolicyDecision(policy, True, True, False, "automatic")


__all__ = ["PolicyCenter", "PolicyDecision"]
