"""Storage-neutral domain models for SAGE.

SAGE uses immutable principal identity and explicit tenant/scope fields on all
long-lived objects. The domain layer remains storage-neutral.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Self
from uuid import UUID, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class ScopeType(StrEnum):
    TENANT = "tenant"
    TEAM = "team"
    USER = "user"
    AGENT = "agent"
    PROJECT = "project"
    CASE = "case"
    SESSION = "session"


class TraceType(StrEnum):
    USER_INPUT = "user_input"
    AGENT_OUTPUT = "agent_output"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FILE_CHANGE = "file_change"
    RECALL = "recall"
    FEEDBACK = "feedback"
    GOVERNANCE = "governance"
    OUTCOME = "outcome"


class Classification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class TraceStatus(StrEnum):
    ACTIVE = "active"
    REDACTED = "redacted"
    ERASED = "erased"


class CaseState(StrEnum):
    OPEN = "open"
    PENDING_REVIEW = "pending_review"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class CaseOutcome(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ItemKind(StrEnum):
    ANCHOR = "anchor"
    FACT = "fact"
    RULE = "rule"
    PREFERENCE = "preference"
    INSIGHT = "insight"
    WARNING = "warning"
    EXCEPTION = "exception"


class ItemState(StrEnum):
    DRAFT = "draft"
    VALIDATING = "validating"
    ACTIVE = "active"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    ERASED = "erased"


class InsightState(StrEnum):
    OBSERVED = "observed"
    DRAFT = "draft"
    VALIDATING = "validating"
    APPROVED = "approved"
    ACTIVE = "active"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    ROLLED_BACK = "rolled_back"
    ARCHIVED = "archived"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PlaybookState(StrEnum):
    DRAFT = "draft"
    TESTING = "testing"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ROLLED_BACK = "rolled_back"


class RecallSection(StrEnum):
    ANCHOR = "anchor"
    FACT = "fact"
    INSIGHT = "insight"
    PLAYBOOK = "playbook"
    WARNING = "warning"


class FeedbackVerdict(StrEnum):
    USEFUL = "useful"
    IRRELEVANT = "irrelevant"
    WRONG = "wrong"
    OUTDATED = "outdated"


class ActivationMode(StrEnum):
    OFF = "off"
    SHADOW = "shadow"
    APPROVAL = "approval"
    AUTO = "auto"


class SageCapability(StrEnum):
    HYBRID_RECALL = "hybrid_recall"
    FEEDBACK_LEARNING = "feedback_learning"
    NIGHTLY_CONSOLIDATION = "nightly_consolidation"
    KNOWLEDGE_MERGE = "knowledge_merge"
    PLAYBOOK_PROMOTION = "playbook_promotion"
    CROSS_SCOPE_TRANSFER = "cross_scope_transfer"


class GrowthJobType(StrEnum):
    REFLECT_CASE = "reflect_case"
    CONSOLIDATE_TENANT = "consolidate_tenant"
    RECALCULATE_UTILITY = "recalculate_utility"
    EVALUATE_RECALL = "evaluate_recall"


class GrowthJobState(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    COMPLETED = "completed"
    FAILED = "failed"


class SignalKind(StrEnum):
    FEEDBACK = "feedback"
    OUTCOME = "outcome"


class ConsolidationRunState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConsolidationKind(StrEnum):
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"
    STALE = "stale"
    LOW_UTILITY = "low_utility"
    PLAYBOOK_PROMOTION = "playbook_promotion"


class ConsolidationAction(StrEnum):
    MERGE = "merge"
    DISPUTE = "dispute"
    ARCHIVE = "archive"
    PROMOTE_PLAYBOOK = "promote_playbook"


class CandidateState(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"
    STALE = "stale"
    ROLLED_BACK = "rolled_back"


class ScopeRef(BaseModel):
    """A typed ownership/visibility scope."""

    model_config = ConfigDict(frozen=True)

    scope_type: ScopeType
    scope_id: str = Field(min_length=1, max_length=256)


class Principal(BaseModel):
    """Immutable identity propagated through every SAGE operation."""

    model_config = ConfigDict(frozen=True)

    tenant_id: UUID
    user_id: UUID
    agent_uid: UUID
    source: str = Field(min_length=1, max_length=64)
    session_id: str = Field(min_length=1, max_length=512)
    permissions: frozenset[str] = Field(default_factory=frozenset)
    team_ids: tuple[UUID, ...] = ()
    project_ids: tuple[UUID, ...] = ()
    case_ids: tuple[UUID, ...] = ()
    service_id: str | None = None
    token_id: str | None = None


class CapabilityPolicy(BaseModel):
    """Versioned tenant policy controlling one SAGE growth capability."""

    model_config = ConfigDict(frozen=True)

    policy_id: UUID
    tenant_id: UUID
    capability: SageCapability
    mode: ActivationMode
    scope: ScopeRef | None = None
    max_auto_risk: RiskLevel = RiskLevel.LOW
    settings: dict[str, Any] = Field(default_factory=dict)
    version: int = Field(default=1, ge=1)
    modified_by: UUID | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        capability: SageCapability,
        mode: ActivationMode,
        scope: ScopeRef | None = None,
        max_auto_risk: RiskLevel = RiskLevel.LOW,
        settings: dict[str, Any] | None = None,
        modified_by: UUID | None = None,
    ) -> Self:
        scope_key = (
            f"{scope.scope_type.value}:{scope.scope_id}"
            if scope is not None
            else "tenant-default"
        )
        return cls(
            policy_id=uuid5(
                tenant_id,
                f"sage-policy:{capability.value}:{scope_key}",
            ),
            tenant_id=tenant_id,
            capability=capability,
            mode=mode,
            scope=scope,
            max_auto_risk=max_auto_risk,
            settings=settings or {},
            modified_by=modified_by,
        )

    @classmethod
    def default_for(
        cls,
        tenant_id: UUID,
        capability: SageCapability,
    ) -> Self:
        defaults = {
            SageCapability.HYBRID_RECALL: ActivationMode.AUTO,
            SageCapability.FEEDBACK_LEARNING: ActivationMode.SHADOW,
            SageCapability.NIGHTLY_CONSOLIDATION: ActivationMode.SHADOW,
            SageCapability.KNOWLEDGE_MERGE: ActivationMode.APPROVAL,
            SageCapability.PLAYBOOK_PROMOTION: ActivationMode.APPROVAL,
            SageCapability.CROSS_SCOPE_TRANSFER: ActivationMode.OFF,
        }
        return cls.create(
            tenant_id=tenant_id,
            capability=capability,
            mode=defaults[capability],
        )


class Trace(BaseModel):
    """An immutable business observation stored in TraceBook."""

    model_config = ConfigDict(frozen=True)

    trace_id: UUID = Field(default_factory=uuid4)
    event_key: str = Field(min_length=1, max_length=512)
    tenant_id: UUID
    user_id: UUID
    agent_uid: UUID
    session_id: str = Field(min_length=1, max_length=512)
    case_id: UUID | None = None
    trace_type: TraceType
    content: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    classification: Classification = Classification.INTERNAL
    status: TraceStatus = TraceStatus.ACTIVE
    occurred_at: datetime = Field(default_factory=utc_now)

    @field_validator("occurred_at")
    @classmethod
    def _require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @classmethod
    def from_principal(
        cls,
        principal: Principal,
        **values: Any,
    ) -> Self:
        return cls(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            agent_uid=principal.agent_uid,
            session_id=principal.session_id,
            **values,
        )


class CaseRecord(BaseModel):
    """A complete business case assembled from one or more traces."""

    case_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    owner_user_id: UUID
    agent_uid: UUID
    scope: ScopeRef
    classification: Classification = Classification.INTERNAL
    domain: str = ""
    process: str = ""
    task_type: str = ""
    goal: str = ""
    constraints: dict[str, Any] = Field(default_factory=dict)
    scenario: dict[str, Any] = Field(default_factory=dict)
    decision_summary: str = ""
    outcome: CaseOutcome = CaseOutcome.UNKNOWN
    outcome_metrics: dict[str, Any] = Field(default_factory=dict)
    state: CaseState = CaseState.OPEN
    trace_ids: tuple[UUID, ...] = ()
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class KnowledgeItem(BaseModel):
    """A versioned fact, rule, preference, insight, warning, or exception."""

    item_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    kind: ItemKind
    scope: ScopeRef
    classification: Classification = Classification.INTERNAL
    title: str = Field(min_length=1, max_length=256)
    content: str = Field(min_length=1)
    structured_data: dict[str, Any] = Field(default_factory=dict)
    evidence_trace_ids: tuple[UUID, ...] = ()
    confidence: float = Field(default=0.5, ge=0, le=1)
    importance: float = Field(default=0.5, ge=0, le=1)
    utility: float = Field(default=0, ge=0, le=1)
    state: ItemState = ItemState.DRAFT
    version: int = Field(default=1, ge=1)
    supersedes_id: UUID | None = None
    valid_from: datetime = Field(default_factory=utc_now)
    valid_until: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class InsightDraft(BaseModel):
    """A proposed lesson that cannot become active without GrowthCycle."""

    insight_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    scope: ScopeRef
    classification: Classification = Classification.INTERNAL
    title: str = Field(min_length=1, max_length=256)
    content: str = Field(min_length=1)
    fingerprint: str = Field(default="", max_length=128)
    applicability: dict[str, Any] = Field(default_factory=dict)
    evidence_case_ids: tuple[UUID, ...] = ()
    confidence: float = Field(default=0.3, ge=0, le=1)
    risk_level: RiskLevel = RiskLevel.LOW
    state: InsightState = InsightState.DRAFT
    approved_by: UUID | None = None
    published_item_id: UUID | None = None
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Playbook(BaseModel):
    """A controlled and versioned standard operating procedure."""

    playbook_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    scope: ScopeRef
    classification: Classification = Classification.INTERNAL
    name: str = Field(min_length=1, max_length=256)
    scenario_schema: dict[str, Any] = Field(default_factory=dict)
    steps: tuple[dict[str, Any], ...] = ()
    decision_points: tuple[dict[str, Any], ...] = ()
    tool_requirements: tuple[str, ...] = ()
    pitfalls: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    state: PlaybookState = PlaybookState.DRAFT
    version: int = Field(default=1, ge=1)
    evidence_count: int = Field(default=0, ge=0)
    success_rate: float = Field(default=0, ge=0, le=1)
    approved_by: UUID | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RecallBudget(BaseModel):
    """Independent prompt budgets for each ActionPack section."""

    model_config = ConfigDict(frozen=True)

    anchors: int = Field(default=300, ge=0)
    facts: int = Field(default=250, ge=0)
    insights: int = Field(default=250, ge=0)
    playbooks: int = Field(default=300, ge=0)
    warnings: int = Field(default=150, ge=0)

    @property
    def total(self) -> int:
        return sum(self.by_section().values())

    def by_section(self) -> dict[RecallSection, int]:
        return {
            RecallSection.ANCHOR: self.anchors,
            RecallSection.FACT: self.facts,
            RecallSection.INSIGHT: self.insights,
            RecallSection.PLAYBOOK: self.playbooks,
            RecallSection.WARNING: self.warnings,
        }

    @classmethod
    def for_total(cls, total: int) -> "RecallBudget":
        """Scale the default proportions to an exact non-negative total."""
        total = max(0, int(total))
        anchors = total * 24 // 100
        facts = total * 20 // 100
        insights = total * 20 // 100
        playbooks = total * 24 // 100
        warnings = total - anchors - facts - insights - playbooks
        return cls(
            anchors=anchors,
            facts=facts,
            insights=insights,
            playbooks=playbooks,
            warnings=warnings,
        )


class RecallSelection(BaseModel):
    """Explain why one authorized source entered an ActionPack."""

    model_config = ConfigDict(frozen=True)

    source_id: UUID
    section: RecallSection
    scope: ScopeRef
    estimated_tokens: int = Field(ge=0)
    reasons: tuple[str, ...] = ()
    score_components: dict[str, float] = Field(default_factory=dict)


class RecallReceipt(BaseModel):
    """Immutable explanation of one bounded recall decision."""

    model_config = ConfigDict(frozen=True)

    receipt_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    query: str
    budget: RecallBudget
    selections: tuple[RecallSelection, ...] = ()
    section_tokens: dict[RecallSection, int] = Field(default_factory=dict)
    ranking_mode: str = "baseline"
    shadow_source_ids: tuple[UUID, ...] = ()
    degradations: tuple[str, ...] = ()
    generated_at: datetime = Field(default_factory=utc_now)


class RecallQuery(BaseModel):
    """Structured business context used by hybrid recall."""

    model_config = ConfigDict(frozen=True)

    text: str = ""
    entities: tuple[str, ...] = ()
    domain: str = ""
    process: str = ""
    task_type: str = ""
    as_of: datetime = Field(default_factory=utc_now)

    @field_validator("entities")
    @classmethod
    def _normalize_entities(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = (value.strip()[:256] for value in values)
        return tuple(dict.fromkeys(value for value in normalized if value))


class GrowthJob(BaseModel):
    """Durable, tenant-scoped background growth work."""

    job_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    job_type: GrowthJobType
    state: GrowthJobState = GrowthJobState.PENDING
    payload: dict[str, Any] = Field(default_factory=dict)
    attempts: int = Field(default=0, ge=0)
    available_at: datetime = Field(default_factory=utc_now)
    leased_until: datetime | None = None
    worker_id: str | None = Field(default=None, max_length=256)
    last_error: str = Field(default="", max_length=2000)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class KnowledgeSignal(BaseModel):
    """Immutable evidence about the usefulness of one recalled source."""

    model_config = ConfigDict(frozen=True)

    signal_id: UUID
    tenant_id: UUID
    source_id: UUID
    actor_user_id: UUID
    kind: SignalKind
    value: float = Field(ge=-1, le=1)
    weight: float = Field(default=1, gt=0, le=1)
    receipt_id: UUID | None = None
    case_id: UUID | None = None
    verdict: FeedbackVerdict | None = None
    occurred_at: datetime = Field(default_factory=utc_now)


class SourceQuality(BaseModel):
    """Bounded aggregate derived from immutable knowledge signals."""

    model_config = ConfigDict(frozen=True)

    source_id: UUID
    sample_count: int = Field(ge=0)
    positive_count: int = Field(ge=0)
    negative_count: int = Field(ge=0)
    score: float = Field(ge=-1, le=1)
    proposed_utility: float = Field(ge=0, le=1)
    applied_item_id: UUID | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class ConsolidationRun(BaseModel):
    """Idempotent tenant-wide knowledge consolidation execution."""

    run_id: UUID
    tenant_id: UUID
    local_date: str = Field(min_length=10, max_length=10)
    state: ConsolidationRunState = ConsolidationRunState.PENDING
    stats: dict[str, int] = Field(default_factory=dict)
    error: str = Field(default="", max_length=2000)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @classmethod
    def create(cls, tenant_id: UUID, local_date: str) -> Self:
        return cls(
            run_id=uuid5(tenant_id, f"sage-nightly:{local_date}"),
            tenant_id=tenant_id,
            local_date=local_date,
        )


class ConsolidationCandidate(BaseModel):
    """Governed proposal produced by a consolidation run."""

    candidate_id: UUID
    tenant_id: UUID
    run_id: UUID
    kind: ConsolidationKind
    action: ConsolidationAction
    source_ids: tuple[UUID, ...]
    scope: ScopeRef
    risk_level: RiskLevel
    state: CandidateState = CandidateState.PROPOSED
    rationale: str = Field(min_length=1, max_length=2000)
    proposed_change: dict[str, Any] = Field(default_factory=dict)
    before_snapshots: dict[str, dict[str, Any]] = Field(default_factory=dict)
    version: int = Field(default=1, ge=1)
    reviewed_by: UUID | None = None
    applied_by: UUID | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        run_id: UUID,
        kind: ConsolidationKind,
        action: ConsolidationAction,
        source_ids: tuple[UUID, ...],
        scope: ScopeRef,
        risk_level: RiskLevel,
        rationale: str,
        proposed_change: dict[str, Any] | None = None,
        before_snapshots: dict[str, dict[str, Any]] | None = None,
    ) -> Self:
        ordered = tuple(sorted(set(source_ids), key=str))
        identity = ":".join(str(value) for value in ordered)
        return cls(
            candidate_id=uuid5(run_id, f"{kind.value}:{identity}"),
            tenant_id=tenant_id,
            run_id=run_id,
            kind=kind,
            action=action,
            source_ids=ordered,
            scope=scope,
            risk_level=risk_level,
            rationale=rationale,
            proposed_change=proposed_change or {},
            before_snapshots=before_snapshots or {},
        )


class EvaluationSnapshot(BaseModel):
    """Point-in-time operational and learning health for one tenant."""

    model_config = ConfigDict(frozen=True)

    tenant_id: UUID
    knowledge_total: int = Field(ge=0)
    active_knowledge: int = Field(ge=0)
    signal_count: int = Field(ge=0)
    positive_signal_rate: float = Field(ge=0, le=1)
    recall_count: int = Field(ge=0)
    degradation_count: int = Field(ge=0)
    degradation_rate: float = Field(ge=0, le=1)
    pending_candidates: int = Field(ge=0)
    applied_candidates: int = Field(ge=0)
    rolled_back_candidates: int = Field(ge=0)
    completed_runs: int = Field(ge=0)
    failed_runs: int = Field(ge=0)
    pending_jobs: int = Field(ge=0)
    completed_jobs: int = Field(ge=0)
    failed_jobs: int = Field(ge=0)
    average_job_latency_ms: float = Field(ge=0)
    generated_at: datetime = Field(default_factory=utc_now)


class ActionPack(BaseModel):
    """The bounded, source-linked SAGE context prepared for one request."""

    tenant_id: UUID
    query: str
    anchors: tuple[KnowledgeItem, ...] = ()
    known_facts: tuple[KnowledgeItem, ...] = ()
    insights: tuple[KnowledgeItem, ...] = ()
    playbooks: tuple[Playbook, ...] = ()
    warnings: tuple[KnowledgeItem, ...] = ()
    source_ids: tuple[UUID, ...] = ()
    section_tokens: dict[RecallSection, int] = Field(default_factory=dict)
    receipt: RecallReceipt | None = None
    estimated_tokens: int = Field(default=0, ge=0)
    generated_at: datetime = Field(default_factory=utc_now)
