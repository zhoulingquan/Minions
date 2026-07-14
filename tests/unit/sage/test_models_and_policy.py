"""Domain and policy tests for the SAGE subsystem."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from minions.sage.errors import SageAccessDenied
from minions.sage.models import (
    ActivationMode,
    CapabilityPolicy,
    Classification,
    GrowthJob,
    GrowthJobState,
    GrowthJobType,
    RecallBudget,
    RecallReceipt,
    RecallSection,
    RecallSelection,
    RiskLevel,
    SageCapability,
    Principal,
    ScopeRef,
    ScopeType,
    Trace,
    TraceType,
)
from minions.sage.policy import ScopePolicy


def _principal(**overrides) -> Principal:
    values = {
        "tenant_id": uuid4(),
        "user_id": uuid4(),
        "agent_uid": uuid4(),
        "source": "web",
        "session_id": "session-1",
    }
    values.update(overrides)
    return Principal(**values)


def test_principal_requires_tenant_user_and_agent() -> None:
    with pytest.raises(ValidationError):
        Principal(source="web", session_id="s")


def test_principal_is_immutable() -> None:
    principal = _principal()
    with pytest.raises(ValidationError):
        principal.session_id = "changed"  # type: ignore[misc]


def test_trace_uses_principal_identity_and_utc_time() -> None:
    principal = _principal()
    trace = Trace.from_principal(
        principal,
        event_key="request:1:user",
        trace_type=TraceType.USER_INPUT,
        content="Prepare the monthly report",
        classification=Classification.INTERNAL,
    )

    assert trace.tenant_id == principal.tenant_id
    assert trace.user_id == principal.user_id
    assert trace.agent_uid == principal.agent_uid
    assert trace.occurred_at.tzinfo == timezone.utc


def test_trace_rejects_naive_datetime() -> None:
    principal = _principal()
    with pytest.raises(ValidationError):
        Trace.from_principal(
            principal,
            event_key="bad-time",
            trace_type=TraceType.USER_INPUT,
            occurred_at=datetime(2026, 7, 12),
        )


def test_policy_rejects_cross_tenant_access() -> None:
    principal = _principal()
    with pytest.raises(SageAccessDenied, match="tenant"):
        ScopePolicy.require_tenant(principal, uuid4())


@pytest.mark.parametrize(
    ("scope_type", "scope_value"),
    [
        (ScopeType.USER, "user_id"),
        (ScopeType.AGENT, "agent_uid"),
        (ScopeType.SESSION, "session_id"),
    ],
)
def test_policy_allows_owned_scopes(
    scope_type: ScopeType,
    scope_value: str,
) -> None:
    principal = _principal()
    value = str(getattr(principal, scope_value))
    ScopePolicy.require_scope(
        principal,
        ScopeRef(scope_type=scope_type, scope_id=value),
    )


def test_policy_denies_foreign_user_scope() -> None:
    principal = _principal()
    scope = ScopeRef(scope_type=ScopeType.USER, scope_id=str(uuid4()))
    with pytest.raises(SageAccessDenied, match="scope"):
        ScopePolicy.require_scope(principal, scope)


def test_policy_requires_explicit_tenant_scope_permission() -> None:
    principal = _principal()
    scope = ScopeRef(
        scope_type=ScopeType.TENANT,
        scope_id=str(principal.tenant_id),
    )
    with pytest.raises(SageAccessDenied, match="scope"):
        ScopePolicy.require_scope(principal, scope)

    permitted = principal.model_copy(
        update={"permissions": frozenset({"sage.scope.tenant.read"})},
    )
    ScopePolicy.require_scope(permitted, scope)


def test_shared_scope_write_requires_explicit_permission() -> None:
    team_id = uuid4()
    principal = _principal(team_ids=(team_id,))
    scope = ScopeRef(scope_type=ScopeType.TEAM, scope_id=str(team_id))
    ScopePolicy.require_scope(principal, scope)
    with pytest.raises(SageAccessDenied, match="write"):
        ScopePolicy.require_write_scope(principal, scope)

    writer = principal.model_copy(
        update={"permissions": frozenset({"sage.scope.team.write"})},
    )
    ScopePolicy.require_write_scope(writer, scope)


def test_recall_budget_scales_to_exact_total() -> None:
    budget = RecallBudget.for_total(1250)

    assert budget.total == 1250
    assert sum(budget.by_section().values()) == 1250
    assert budget.anchors > 0
    assert budget.warnings > 0


def test_recall_receipt_serializes_selection_reasons() -> None:
    principal = _principal()
    selection = RecallSelection(
        source_id=uuid4(),
        section=RecallSection.ANCHOR,
        scope=ScopeRef(
            scope_type=ScopeType.USER,
            scope_id=str(principal.user_id),
        ),
        estimated_tokens=12,
        reasons=("active", "user_scope"),
    )
    receipt = RecallReceipt(
        tenant_id=principal.tenant_id,
        query="monthly close",
        budget=RecallBudget.for_total(500),
        selections=(selection,),
        section_tokens={RecallSection.ANCHOR: 12},
    )

    restored = RecallReceipt.model_validate_json(receipt.model_dump_json())
    assert restored.selections[0].reasons == ("active", "user_scope")
    assert restored.section_tokens[RecallSection.ANCHOR] == 12


def test_growth_job_defaults_to_pending_and_is_json_roundtrippable() -> None:
    principal = _principal()
    job = GrowthJob(
        tenant_id=principal.tenant_id,
        job_type=GrowthJobType.REFLECT_CASE,
        payload={"case_id": str(uuid4())},
    )

    restored = GrowthJob.model_validate_json(job.model_dump_json())
    assert restored.state is GrowthJobState.PENDING
    assert restored.attempts == 0


@pytest.mark.parametrize(
    ("capability", "expected"),
    [
        (SageCapability.HYBRID_RECALL, ActivationMode.AUTO),
        (SageCapability.FEEDBACK_LEARNING, ActivationMode.SHADOW),
        (SageCapability.NIGHTLY_CONSOLIDATION, ActivationMode.SHADOW),
        (SageCapability.KNOWLEDGE_MERGE, ActivationMode.APPROVAL),
        (SageCapability.PLAYBOOK_PROMOTION, ActivationMode.APPROVAL),
        (SageCapability.CROSS_SCOPE_TRANSFER, ActivationMode.OFF),
    ],
)
def test_capability_policy_has_conservative_defaults(
    capability: SageCapability,
    expected: ActivationMode,
) -> None:
    tenant_id = uuid4()
    policy = CapabilityPolicy.default_for(tenant_id, capability)

    assert policy.tenant_id == tenant_id
    assert policy.capability is capability
    assert policy.mode is expected
    assert policy.max_auto_risk is RiskLevel.LOW


def test_capability_policy_id_is_deterministic_per_scope() -> None:
    tenant_id = uuid4()
    user_scope = ScopeRef(scope_type=ScopeType.USER, scope_id=str(uuid4()))

    first = CapabilityPolicy.create(
        tenant_id=tenant_id,
        capability=SageCapability.FEEDBACK_LEARNING,
        mode=ActivationMode.AUTO,
        scope=user_scope,
    )
    repeated = CapabilityPolicy.create(
        tenant_id=tenant_id,
        capability=SageCapability.FEEDBACK_LEARNING,
        mode=ActivationMode.SHADOW,
        scope=user_scope,
    )
    tenant_default = CapabilityPolicy.create(
        tenant_id=tenant_id,
        capability=SageCapability.FEEDBACK_LEARNING,
        mode=ActivationMode.SHADOW,
    )

    assert first.policy_id == repeated.policy_id
    assert first.policy_id != tenant_default.policy_id
    restored = CapabilityPolicy.model_validate_json(first.model_dump_json())
    assert restored.scope == user_scope
