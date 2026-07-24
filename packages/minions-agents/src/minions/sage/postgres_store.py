"""PostgreSQL production adapter for SAGE.

The adapter uses a transaction-local tenant setting on every operation so
PostgreSQL RLS and application ScopePolicy enforce the same boundary.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any
from uuid import UUID

try:  # Optional production dependency.
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    from psycopg_pool import AsyncConnectionPool
except ImportError:  # pragma: no cover - exercised by factory tests
    dict_row = None
    Jsonb = None
    AsyncConnectionPool = None

from .errors import SageAccessDenied, SageConflict
from .models import (
    CapabilityPolicy,
    CandidateState,
    CaseRecord,
    CaseState,
    Classification,
    ConsolidationCandidate,
    ConsolidationRun,
    GrowthJob,
    GrowthJobState,
    InsightDraft,
    InsightState,
    ItemKind,
    ItemState,
    KnowledgeItem,
    KnowledgeSignal,
    Playbook,
    PlaybookState,
    Principal,
    ScopeRef,
    SageCapability,
    Trace,
    utc_now,
)
from .policy import ScopePolicy
from .postgres_schema import SET_LOCAL_TENANT_SQL, migration_manifest


class PostgresSageStore:
    """psycopg-backed SAGE store for tenant/production deployments."""

    supports_semantic = True

    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 10,
    ) -> None:
        if not dsn.strip():
            raise ValueError("SAGE PostgreSQL DSN is required")
        self._dsn = dsn
        self._min_size = max(1, min_size)
        self._max_size = max(self._min_size, max_size)
        self._pool: Any = None

    async def start(self) -> None:
        if AsyncConnectionPool is None or dict_row is None:
            raise RuntimeError(
                "PostgreSQL SAGE requires minions[postgres] (psycopg and psycopg_pool)",
            )
        if self._pool is not None:
            return
        self._pool = AsyncConnectionPool(
            conninfo=self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            open=False,
            kwargs={"row_factory": dict_row},
        )
        await self._pool.open()
        await self._pool.wait()
        try:
            async with self._pool.connection() as conn:
                cursor = await conn.execute(
                    "SELECT version, checksum FROM sage.schema_migration "
                    "ORDER BY version",
                )
                rows = await cursor.fetchall()
                installed = {int(row["version"]): str(row["checksum"]) for row in rows}
                expected = {
                    migration.version: migration.checksum
                    for migration in migration_manifest()
                }
                if installed != expected:
                    raise RuntimeError(
                        "SAGE PostgreSQL migrations are missing or mismatched",
                    )
        except Exception:
            await self.close()
            raise

    async def close(self) -> None:
        if self._pool is not None:
            pool, self._pool = self._pool, None
            await pool.close()

    async def append_trace(self, principal: Principal, trace: Trace) -> Trace:
        ScopePolicy.require_tenant(principal, trace.tenant_id)
        ScopePolicy.require_classification_write(
            principal,
            trace.classification,
        )
        if trace.user_id != principal.user_id and (
            "sage.trace.write.any" not in principal.permissions
        ):
            raise SageAccessDenied("cannot write a trace for another user")
        async with self._tenant_connection(principal) as conn:
            await conn.execute(
                "INSERT INTO sage.trace_event "
                "(tenant_id, trace_id, event_key, user_id, agent_uid, "
                "session_id, case_id, trace_type, classification, "
                "occurred_at, body_json) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, event_key) DO NOTHING",
                (
                    trace.tenant_id,
                    trace.trace_id,
                    trace.event_key,
                    trace.user_id,
                    trace.agent_uid,
                    trace.session_id,
                    trace.case_id,
                    trace.trace_type.value,
                    trace.classification.value,
                    trace.occurred_at,
                    self._json(trace),
                ),
            )
            cursor = await conn.execute(
                "SELECT body_json FROM sage.trace_event "
                "WHERE tenant_id = %s AND event_key = %s",
                (principal.tenant_id, trace.event_key),
            )
            row = await cursor.fetchone()
        persisted = Trace.model_validate(row["body_json"])
        if persisted.user_id != principal.user_id:
            raise SageAccessDenied("trace event key belongs to another user")
        return persisted

    async def list_traces(
        self,
        principal: Principal,
        *,
        case_id: UUID | None = None,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[Trace]:
        where = ["tenant_id = %s"]
        params: list[Any] = [principal.tenant_id]
        if "sage.trace.read.any" not in principal.permissions:
            where.append("user_id = %s")
            params.append(principal.user_id)
        if case_id is not None:
            where.append("case_id = %s")
            params.append(case_id)
        if session_id is not None:
            where.append("session_id = %s")
            params.append(session_id)
        params.append(max(1, min(int(limit), 1000)))
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.trace_event WHERE "
                + " AND ".join(where)
                + " ORDER BY occurred_at, trace_id LIMIT %s",
                params,
            )
            rows = await cursor.fetchall()
        traces = [Trace.model_validate(row["body_json"]) for row in rows]
        return [
            trace
            for trace in traces
            if self._classification_allowed(principal, trace.classification)
        ]

    async def save_case(
        self,
        principal: Principal,
        case: CaseRecord,
    ) -> CaseRecord:
        await self._save_scoped(
            principal,
            table="business_case",
            id_column="case_id",
            object_id=case.case_id,
            tenant_id=case.tenant_id,
            scope=case.scope,
            classification=case.classification,
            state=case.state.value,
            body=case,
        )
        return case

    async def commit_case_bundle(
        self,
        principal: Principal,
        case: CaseRecord,
        *,
        traces: tuple[Trace, ...] = (),
        growth_job: GrowthJob | None = None,
    ) -> tuple[CaseRecord, tuple[Trace, ...], GrowthJob | None]:
        """Commit evidence, case state, and outbox work in one transaction."""

        self._require_write(
            principal,
            case.tenant_id,
            case.scope,
            case.classification,
        )
        for trace in traces:
            ScopePolicy.require_tenant(principal, trace.tenant_id)
            ScopePolicy.require_classification_write(
                principal,
                trace.classification,
            )
            if trace.user_id != principal.user_id and (
                "sage.trace.write.any" not in principal.permissions
            ):
                raise SageAccessDenied("cannot write a trace for another user")
        if growth_job is not None:
            ScopePolicy.require_tenant(principal, growth_job.tenant_id)

        saved_traces: list[Trace] = []
        saved_job = None
        async with self._tenant_connection(principal) as conn:
            for trace in traces:
                await conn.execute(
                    "INSERT INTO sage.trace_event "
                    "(tenant_id, trace_id, event_key, user_id, agent_uid, "
                    "session_id, case_id, trace_type, classification, "
                    "occurred_at, body_json) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (tenant_id, event_key) DO NOTHING",
                    (
                        trace.tenant_id,
                        trace.trace_id,
                        trace.event_key,
                        trace.user_id,
                        trace.agent_uid,
                        trace.session_id,
                        trace.case_id,
                        trace.trace_type.value,
                        trace.classification.value,
                        trace.occurred_at,
                        self._json(trace),
                    ),
                )
                cursor = await conn.execute(
                    "SELECT body_json FROM sage.trace_event "
                    "WHERE tenant_id = %s AND event_key = %s",
                    (principal.tenant_id, trace.event_key),
                )
                row = await cursor.fetchone()
                persisted = Trace.model_validate(row["body_json"])
                if persisted.user_id != principal.user_id:
                    raise SageAccessDenied(
                        "trace event key belongs to another user",
                    )
                saved_traces.append(persisted)

            trace_ids = tuple(
                dict.fromkeys(
                    (*case.trace_ids, *(trace.trace_id for trace in saved_traces)),
                ),
            )
            saved_case = case.model_copy(update={"trace_ids": trace_ids})
            await conn.execute(
                "INSERT INTO sage.business_case "
                "(tenant_id, case_id, scope_type, scope_id, state, "
                "classification, body_json) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, case_id) DO UPDATE SET "
                "scope_type=excluded.scope_type, scope_id=excluded.scope_id, "
                "state=excluded.state, classification=excluded.classification, "
                "updated_at=clock_timestamp(), body_json=excluded.body_json",
                (
                    saved_case.tenant_id,
                    saved_case.case_id,
                    saved_case.scope.scope_type.value,
                    saved_case.scope.scope_id,
                    saved_case.state.value,
                    saved_case.classification.value,
                    self._json(saved_case),
                ),
            )

            if growth_job is not None:
                payload = dict(growth_job.payload)
                if growth_job.last_error:
                    payload["_sage_last_error"] = growth_job.last_error
                await conn.execute(
                    "INSERT INTO sage.growth_job "
                    "(tenant_id, job_id, job_type, state, payload, attempts, "
                    "available_at, leased_until, worker_id, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (tenant_id, job_id) DO NOTHING",
                    (
                        growth_job.tenant_id,
                        growth_job.job_id,
                        growth_job.job_type.value,
                        growth_job.state.value,
                        self._json_payload(payload),
                        growth_job.attempts,
                        growth_job.available_at,
                        growth_job.leased_until,
                        growth_job.worker_id,
                        growth_job.created_at,
                        growth_job.updated_at,
                    ),
                )
                cursor = await conn.execute(
                    "SELECT * FROM sage.growth_job "
                    "WHERE tenant_id = %s AND job_id = %s",
                    (principal.tenant_id, growth_job.job_id),
                )
                saved_job = self._growth_job_from_row(await cursor.fetchone())
        return saved_case, tuple(saved_traces), saved_job

    async def get_case(
        self,
        principal: Principal,
        case_id: UUID,
    ) -> CaseRecord | None:
        return await self._get_scoped(
            principal,
            "business_case",
            "case_id",
            case_id,
            CaseRecord,
        )

    async def list_cases(
        self,
        principal: Principal,
        *,
        states: tuple[CaseState, ...] | None = None,
        limit: int = 100,
    ) -> list[CaseRecord]:
        where = ["tenant_id = %s"]
        params: list[Any] = [principal.tenant_id]
        self._append_states(where, params, states)
        params.append(max(1, min(int(limit), 1000)))
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.business_case WHERE "
                + " AND ".join(where)
                + " ORDER BY updated_at DESC LIMIT %s",
                params,
            )
            rows = await cursor.fetchall()
        return self._filter_scoped(
            principal,
            [CaseRecord.model_validate(row["body_json"]) for row in rows],
        )

    async def save_item(
        self,
        principal: Principal,
        item: KnowledgeItem,
    ) -> KnowledgeItem:
        self._require_write(
            principal,
            item.tenant_id,
            item.scope,
            item.classification,
        )
        async with self._tenant_connection(principal) as conn:
            await conn.execute(
                "INSERT INTO sage.knowledge_item "
                "(tenant_id, item_id, scope_type, scope_id, kind, state, "
                "classification, title, content, valid_until, body_json) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, item_id) DO UPDATE SET "
                "scope_type=excluded.scope_type, scope_id=excluded.scope_id, "
                "kind=excluded.kind, state=excluded.state, "
                "classification=excluded.classification, title=excluded.title, "
                "content=excluded.content, valid_until=excluded.valid_until, "
                "updated_at=clock_timestamp(), body_json=excluded.body_json",
                (
                    item.tenant_id,
                    item.item_id,
                    item.scope.scope_type.value,
                    item.scope.scope_id,
                    item.kind.value,
                    item.state.value,
                    item.classification.value,
                    item.title,
                    item.content,
                    item.valid_until,
                    self._json(item),
                ),
            )
        return item

    async def get_item(
        self,
        principal: Principal,
        item_id: UUID,
    ) -> KnowledgeItem | None:
        return await self._get_scoped(
            principal,
            "knowledge_item",
            "item_id",
            item_id,
            KnowledgeItem,
        )

    async def search_items(
        self,
        principal: Principal,
        query: str,
        *,
        states: tuple[ItemState, ...] | None = None,
        limit: int = 20,
    ) -> list[KnowledgeItem]:
        if not query.strip():
            return []
        where = [
            "tenant_id = %s",
            "search_document @@ websearch_to_tsquery('simple', %s)",
        ]
        params: list[Any] = [principal.tenant_id, query]
        self._append_states(where, params, states)
        params.extend([query, max(1, min(int(limit) * 4, 200))])
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.knowledge_item WHERE "
                + " AND ".join(where)
                + " ORDER BY ts_rank(search_document, "
                "websearch_to_tsquery('simple', %s)) DESC, updated_at DESC "
                "LIMIT %s",
                params,
            )
            rows = await cursor.fetchall()
        return self._filter_scoped(
            principal,
            [KnowledgeItem.model_validate(row["body_json"]) for row in rows],
        )

    async def list_items(
        self,
        principal: Principal,
        *,
        states: tuple[ItemState, ...] | None = None,
        kinds: tuple[ItemKind, ...] | None = None,
        limit: int = 100,
    ) -> list[KnowledgeItem]:
        """List accessible items without requiring a text-search query."""

        where = ["tenant_id = %s"]
        params: list[Any] = [principal.tenant_id]
        self._append_states(where, params, states)
        if kinds:
            where.append("kind = ANY(%s)")
            params.append([kind.value for kind in kinds])
        cap = max(1, min(int(limit), 1000))
        params.append(min(cap * 4, 1000))
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.knowledge_item WHERE "
                + " AND ".join(where)
                + " ORDER BY updated_at DESC, item_id LIMIT %s",
                params,
            )
            rows = await cursor.fetchall()
        return self._filter_scoped(
            principal,
            [KnowledgeItem.model_validate(row["body_json"]) for row in rows],
        )[:cap]

    async def save_insight(
        self,
        principal: Principal,
        insight: InsightDraft,
    ) -> InsightDraft:
        await self._save_scoped(
            principal,
            table="insight",
            id_column="insight_id",
            object_id=insight.insight_id,
            tenant_id=insight.tenant_id,
            scope=insight.scope,
            classification=insight.classification,
            state=insight.state.value,
            body=insight,
            extra_columns={"fingerprint": insight.fingerprint},
        )
        return insight

    async def get_insight(
        self,
        principal: Principal,
        insight_id: UUID,
    ) -> InsightDraft | None:
        return await self._get_scoped(
            principal,
            "insight",
            "insight_id",
            insight_id,
            InsightDraft,
        )

    async def search_insights(
        self,
        principal: Principal,
        fingerprint: str,
        *,
        states: tuple[InsightState, ...] | None = None,
        limit: int = 20,
    ) -> list[InsightDraft]:
        if not fingerprint:
            return []
        where = ["tenant_id = %s", "fingerprint = %s"]
        params: list[Any] = [principal.tenant_id, fingerprint]
        self._append_states(where, params, states)
        params.append(max(1, min(int(limit), 100)))
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.insight WHERE "
                + " AND ".join(where)
                + " ORDER BY updated_at DESC LIMIT %s",
                params,
            )
            rows = await cursor.fetchall()
        return self._filter_scoped(
            principal,
            [InsightDraft.model_validate(row["body_json"]) for row in rows],
        )

    async def list_insights(
        self,
        principal: Principal,
        *,
        states: tuple[InsightState, ...] | None = None,
        limit: int = 100,
    ) -> list[InsightDraft]:
        where = ["tenant_id = %s"]
        params: list[Any] = [principal.tenant_id]
        self._append_states(where, params, states)
        params.append(max(1, min(int(limit), 1000)))
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.insight WHERE "
                + " AND ".join(where)
                + " ORDER BY updated_at DESC LIMIT %s",
                params,
            )
            rows = await cursor.fetchall()
        return self._filter_scoped(
            principal,
            [InsightDraft.model_validate(row["body_json"]) for row in rows],
        )

    async def save_playbook(
        self,
        principal: Principal,
        playbook: Playbook,
    ) -> Playbook:
        await self._save_scoped(
            principal,
            table="playbook",
            id_column="playbook_id",
            object_id=playbook.playbook_id,
            tenant_id=playbook.tenant_id,
            scope=playbook.scope,
            classification=playbook.classification,
            state=playbook.state.value,
            body=playbook,
        )
        return playbook

    async def get_playbook(
        self,
        principal: Principal,
        playbook_id: UUID,
    ) -> Playbook | None:
        return await self._get_scoped(
            principal,
            "playbook",
            "playbook_id",
            playbook_id,
            Playbook,
        )

    async def search_playbooks(
        self,
        principal: Principal,
        query: str,
        *,
        limit: int = 10,
    ) -> list[Playbook]:
        if not query.strip():
            return []
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.playbook "
                "WHERE tenant_id = %s AND body_json::text ILIKE %s "
                "ORDER BY updated_at DESC LIMIT %s",
                (
                    principal.tenant_id,
                    f"%{query.strip()}%",
                    max(1, min(int(limit) * 4, 100)),
                ),
            )
            rows = await cursor.fetchall()
        return self._filter_scoped(
            principal,
            [Playbook.model_validate(row["body_json"]) for row in rows],
        )

    async def list_playbooks(
        self,
        principal: Principal,
        *,
        states: tuple[PlaybookState, ...] | None = None,
        limit: int = 100,
    ) -> list[Playbook]:
        where = ["tenant_id = %s"]
        params: list[Any] = [principal.tenant_id]
        self._append_states(where, params, states)
        params.append(max(1, min(int(limit), 1000)))
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.playbook WHERE "
                + " AND ".join(where)
                + " ORDER BY updated_at DESC LIMIT %s",
                params,
            )
            rows = await cursor.fetchall()
        return self._filter_scoped(
            principal,
            [Playbook.model_validate(row["body_json"]) for row in rows],
        )

    async def save_capability_policy(
        self,
        principal: Principal,
        policy: CapabilityPolicy,
    ) -> CapabilityPolicy:
        ScopePolicy.require_tenant(principal, policy.tenant_id)
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.capability_policy "
                "WHERE tenant_id = %s AND policy_id = %s FOR UPDATE",
                (principal.tenant_id, policy.policy_id),
            )
            row = await cursor.fetchone()
            if row is not None:
                current = CapabilityPolicy.model_validate(row["body_json"])
                if current == policy:
                    return current
                if policy.version != current.version + 1:
                    raise SageConflict(
                        "capability policy update requires the next version",
                    )
            await conn.execute(
                "INSERT INTO sage.capability_policy "
                "(tenant_id, policy_id, capability, mode, scope_type, "
                "scope_id, version, updated_at, body_json) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, policy_id) DO UPDATE SET "
                "capability=excluded.capability, mode=excluded.mode, "
                "scope_type=excluded.scope_type, scope_id=excluded.scope_id, "
                "version=excluded.version, updated_at=excluded.updated_at, "
                "body_json=excluded.body_json",
                (
                    policy.tenant_id,
                    policy.policy_id,
                    policy.capability.value,
                    policy.mode.value,
                    policy.scope.scope_type.value if policy.scope else None,
                    policy.scope.scope_id if policy.scope else None,
                    policy.version,
                    policy.updated_at,
                    self._json(policy),
                ),
            )
        return policy

    async def get_capability_policy(
        self,
        principal: Principal,
        policy_id: UUID,
    ) -> CapabilityPolicy | None:
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.capability_policy "
                "WHERE tenant_id = %s AND policy_id = %s",
                (principal.tenant_id, policy_id),
            )
            row = await cursor.fetchone()
        return (
            CapabilityPolicy.model_validate(row["body_json"])
            if row is not None
            else None
        )

    async def list_capability_policies(
        self,
        principal: Principal,
        *,
        capability: SageCapability | None = None,
        limit: int = 100,
    ) -> list[CapabilityPolicy]:
        where = ["tenant_id = %s"]
        params: list[Any] = [principal.tenant_id]
        if capability is not None:
            where.append("capability = %s")
            params.append(capability.value)
        params.append(max(1, min(int(limit), 1000)))
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.capability_policy WHERE "
                + " AND ".join(where)
                + " ORDER BY capability, scope_type, scope_id, policy_id "
                "LIMIT %s",
                params,
            )
            rows = await cursor.fetchall()
        return [CapabilityPolicy.model_validate(row["body_json"]) for row in rows]

    async def save_knowledge_signal(
        self,
        principal: Principal,
        signal: KnowledgeSignal,
    ) -> KnowledgeSignal:
        ScopePolicy.require_tenant(principal, signal.tenant_id)
        async with self._tenant_connection(principal) as conn:
            await conn.execute(
                "INSERT INTO sage.knowledge_signal "
                "(tenant_id, signal_id, source_id, kind, occurred_at, "
                "body_json) VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, signal_id) DO NOTHING",
                (
                    signal.tenant_id,
                    signal.signal_id,
                    signal.source_id,
                    signal.kind.value,
                    signal.occurred_at,
                    self._json(signal),
                ),
            )
            cursor = await conn.execute(
                "SELECT body_json FROM sage.knowledge_signal "
                "WHERE tenant_id = %s AND signal_id = %s",
                (principal.tenant_id, signal.signal_id),
            )
            row = await cursor.fetchone()
        if row is None:
            raise SageConflict("knowledge signal was not persisted")
        return KnowledgeSignal.model_validate(row["body_json"])

    async def list_knowledge_signals(
        self,
        principal: Principal,
        *,
        source_id: UUID | None = None,
        limit: int = 1000,
    ) -> list[KnowledgeSignal]:
        where = ["tenant_id = %s"]
        params: list[Any] = [principal.tenant_id]
        if source_id is not None:
            where.append("source_id = %s")
            params.append(source_id)
        params.append(max(1, min(int(limit), 5000)))
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.knowledge_signal WHERE "
                + " AND ".join(where)
                + " ORDER BY occurred_at, signal_id LIMIT %s",
                params,
            )
            rows = await cursor.fetchall()
        return [KnowledgeSignal.model_validate(row["body_json"]) for row in rows]

    async def save_item_embedding(
        self,
        principal: Principal,
        item_id: UUID,
        embedding: tuple[float, ...],
        *,
        model: str = "",
        item_version: int = 1,
    ) -> None:
        item = await self.get_item(principal, item_id)
        if item is None:
            raise SageConflict("SAGE item is missing")
        self._require_write(
            principal,
            item.tenant_id,
            item.scope,
            item.classification,
        )
        async with self._tenant_connection(principal) as conn:
            await conn.execute(
                "UPDATE sage.knowledge_item SET embedding=%s::vector, "
                "embedding_model=%s, embedding_item_version=%s, "
                "updated_at=clock_timestamp() "
                "WHERE tenant_id=%s AND item_id=%s",
                (
                    self._vector_literal(embedding),
                    str(model)[:200],
                    max(1, int(item_version)),
                    principal.tenant_id,
                    item_id,
                ),
            )

    async def semantic_search_items(
        self,
        principal: Principal,
        embedding: tuple[float, ...],
        *,
        limit: int = 20,
    ) -> list[tuple[KnowledgeItem, float]]:
        vector = self._vector_literal(embedding)
        cap = max(1, min(int(limit), 100))
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json, 1 - (embedding <=> %s::vector) "
                "AS semantic_score FROM sage.knowledge_item "
                "WHERE tenant_id=%s AND embedding IS NOT NULL "
                "AND state=%s "
                "AND (valid_until IS NULL OR valid_until > clock_timestamp()) "
                "ORDER BY embedding <=> %s::vector LIMIT %s",
                (
                    vector,
                    principal.tenant_id,
                    ItemState.ACTIVE.value,
                    vector,
                    min(cap * 4, 400),
                ),
            )
            rows = await cursor.fetchall()
        matches: list[tuple[KnowledgeItem, float]] = []
        for row in rows:
            item = KnowledgeItem.model_validate(row["body_json"])
            if item not in self._filter_scoped(principal, [item]):
                continue
            matches.append((item, float(row["semantic_score"])))
            if len(matches) >= cap:
                break
        return matches

    async def save_consolidation_run(
        self,
        principal: Principal,
        run: ConsolidationRun,
    ) -> ConsolidationRun:
        ScopePolicy.require_tenant(principal, run.tenant_id)
        async with self._tenant_connection(principal) as conn:
            await conn.execute(
                "INSERT INTO sage.consolidation_run "
                "(tenant_id, run_id, local_date, state, updated_at, body_json) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, run_id) DO UPDATE SET "
                "state=excluded.state, updated_at=excluded.updated_at, "
                "body_json=excluded.body_json",
                (
                    run.tenant_id,
                    run.run_id,
                    run.local_date,
                    run.state.value,
                    run.updated_at,
                    self._json(run),
                ),
            )
        return run

    async def get_consolidation_run(
        self,
        principal: Principal,
        run_id: UUID,
    ) -> ConsolidationRun | None:
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.consolidation_run "
                "WHERE tenant_id=%s AND run_id=%s",
                (principal.tenant_id, run_id),
            )
            row = await cursor.fetchone()
        return (
            ConsolidationRun.model_validate(row["body_json"])
            if row is not None
            else None
        )

    async def list_consolidation_runs(
        self,
        principal: Principal,
        *,
        limit: int = 100,
    ) -> list[ConsolidationRun]:
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.consolidation_run "
                "WHERE tenant_id=%s ORDER BY local_date DESC, run_id LIMIT %s",
                (principal.tenant_id, max(1, min(int(limit), 1000))),
            )
            rows = await cursor.fetchall()
        return [ConsolidationRun.model_validate(row["body_json"]) for row in rows]

    async def save_consolidation_candidate(
        self,
        principal: Principal,
        candidate: ConsolidationCandidate,
    ) -> ConsolidationCandidate:
        ScopePolicy.require_tenant(principal, candidate.tenant_id)
        ScopePolicy.require_scope(principal, candidate.scope)
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.consolidation_candidate "
                "WHERE tenant_id=%s AND candidate_id=%s FOR UPDATE",
                (principal.tenant_id, candidate.candidate_id),
            )
            row = await cursor.fetchone()
            if row is not None:
                current = ConsolidationCandidate.model_validate(row["body_json"])
                if current == candidate:
                    return current
                if candidate.version != current.version + 1:
                    raise SageConflict(
                        "consolidation candidate update requires the next version",
                    )
            await conn.execute(
                "INSERT INTO sage.consolidation_candidate "
                "(tenant_id, candidate_id, run_id, kind, state, scope_type, "
                "scope_id, version, updated_at, body_json) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, candidate_id) DO UPDATE SET "
                "state=excluded.state, version=excluded.version, "
                "updated_at=excluded.updated_at, body_json=excluded.body_json",
                (
                    candidate.tenant_id,
                    candidate.candidate_id,
                    candidate.run_id,
                    candidate.kind.value,
                    candidate.state.value,
                    candidate.scope.scope_type.value,
                    candidate.scope.scope_id,
                    candidate.version,
                    candidate.updated_at,
                    self._json(candidate),
                ),
            )
        return candidate

    async def get_consolidation_candidate(
        self,
        principal: Principal,
        candidate_id: UUID,
    ) -> ConsolidationCandidate | None:
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.consolidation_candidate "
                "WHERE tenant_id=%s AND candidate_id=%s",
                (principal.tenant_id, candidate_id),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        candidate = ConsolidationCandidate.model_validate(row["body_json"])
        ScopePolicy.require_scope(principal, candidate.scope)
        return candidate

    async def list_consolidation_candidates(
        self,
        principal: Principal,
        *,
        states: tuple[CandidateState, ...] | None = None,
        limit: int = 100,
    ) -> list[ConsolidationCandidate]:
        where = ["tenant_id=%s"]
        params: list[Any] = [principal.tenant_id]
        self._append_states(where, params, states)
        params.append(max(1, min(int(limit) * 4, 1000)))
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT body_json FROM sage.consolidation_candidate WHERE "
                + " AND ".join(where)
                + " ORDER BY updated_at DESC, candidate_id LIMIT %s",
                params,
            )
            rows = await cursor.fetchall()
        values = [
            ConsolidationCandidate.model_validate(row["body_json"]) for row in rows
        ]
        visible = []
        for value in values:
            try:
                ScopePolicy.require_scope(principal, value.scope)
                visible.append(value)
            except SageAccessDenied:
                continue
        return visible[: max(1, int(limit))]

    async def enqueue_growth_job(
        self,
        principal: Principal,
        job: GrowthJob,
    ) -> GrowthJob:
        ScopePolicy.require_tenant(principal, job.tenant_id)
        payload = dict(job.payload)
        if job.last_error:
            payload["_sage_last_error"] = job.last_error
        async with self._tenant_connection(principal) as conn:
            await conn.execute(
                "INSERT INTO sage.growth_job "
                "(tenant_id, job_id, job_type, state, payload, attempts, "
                "available_at, leased_until, worker_id, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, job_id) DO NOTHING",
                (
                    job.tenant_id,
                    job.job_id,
                    job.job_type.value,
                    job.state.value,
                    self._json_payload(payload),
                    job.attempts,
                    job.available_at,
                    job.leased_until,
                    job.worker_id,
                    job.created_at,
                    job.updated_at,
                ),
            )
            cursor = await conn.execute(
                "SELECT * FROM sage.growth_job WHERE tenant_id = %s AND job_id = %s",
                (principal.tenant_id, job.job_id),
            )
            row = await cursor.fetchone()
        return self._growth_job_from_row(row)

    async def list_growth_jobs(
        self,
        principal: Principal,
        *,
        limit: int = 100,
    ) -> list[GrowthJob]:
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "SELECT * FROM sage.growth_job WHERE tenant_id = %s "
                "ORDER BY updated_at DESC, job_id LIMIT %s",
                (
                    principal.tenant_id,
                    max(1, min(int(limit), 5000)),
                ),
            )
            rows = await cursor.fetchall()
        return [self._growth_job_from_row(row) for row in rows]

    async def acknowledge_growth_job(
        self,
        principal: Principal,
        job_id: UUID,
    ) -> GrowthJob:
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "UPDATE sage.growth_job SET state=%s, "
                "updated_at=clock_timestamp() "
                "WHERE tenant_id=%s AND job_id=%s AND state=%s RETURNING *",
                (
                    GrowthJobState.COMPLETED.value,
                    principal.tenant_id,
                    job_id,
                    GrowthJobState.PENDING.value,
                ),
            )
            row = await cursor.fetchone()
            if row is None:
                cursor = await conn.execute(
                    "SELECT * FROM sage.growth_job WHERE tenant_id=%s AND job_id=%s",
                    (principal.tenant_id, job_id),
                )
                row = await cursor.fetchone()
        job = self._growth_job_from_row(row)
        if job.state is not GrowthJobState.COMPLETED:
            raise SageConflict("SAGE growth job is already leased")
        return job

    async def claim_growth_jobs(
        self,
        principal: Principal,
        *,
        worker_id: str,
        limit: int = 1,
        lease_seconds: int = 60,
    ) -> list[GrowthJob]:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        cap = max(1, min(int(limit), 100))
        lease = max(1, int(lease_seconds))
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "WITH candidates AS ("
                "SELECT job_id FROM sage.growth_job "
                "WHERE tenant_id = %s AND "
                "((state = %s AND available_at <= clock_timestamp()) OR "
                "(state = %s AND leased_until <= clock_timestamp())) "
                "ORDER BY available_at, job_id "
                "LIMIT %s FOR UPDATE SKIP LOCKED"
                ") UPDATE sage.growth_job AS j SET "
                "state=%s, attempts=j.attempts + 1, "
                "leased_until=clock_timestamp() + (%s * interval '1 second'), "
                "worker_id=%s, updated_at=clock_timestamp() "
                "FROM candidates AS c "
                "WHERE j.tenant_id = %s AND j.job_id = c.job_id "
                "RETURNING j.*",
                (
                    principal.tenant_id,
                    GrowthJobState.PENDING.value,
                    GrowthJobState.LEASED.value,
                    cap,
                    GrowthJobState.LEASED.value,
                    lease,
                    worker_id[:256],
                    principal.tenant_id,
                ),
            )
            rows = await cursor.fetchall()
        return [self._growth_job_from_row(row) for row in rows]

    async def complete_growth_job(
        self,
        principal: Principal,
        job_id: UUID,
        *,
        worker_id: str,
    ) -> GrowthJob:
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "UPDATE sage.growth_job SET state=%s, leased_until=NULL, "
                "worker_id=NULL, updated_at=clock_timestamp() "
                "WHERE tenant_id=%s AND job_id=%s AND state=%s "
                "AND worker_id=%s RETURNING *",
                (
                    GrowthJobState.COMPLETED.value,
                    principal.tenant_id,
                    job_id,
                    GrowthJobState.LEASED.value,
                    worker_id,
                ),
            )
            row = await cursor.fetchone()
        if row is None:
            raise SageConflict("growth job is not leased by this worker")
        return self._growth_job_from_row(row)

    async def fail_growth_job(
        self,
        principal: Principal,
        job_id: UUID,
        *,
        worker_id: str,
        error: str,
        retry_delay_seconds: int | None = 60,
    ) -> GrowthJob:
        state = (
            GrowthJobState.PENDING
            if retry_delay_seconds is not None
            else GrowthJobState.FAILED
        )
        available_at = utc_now()
        if retry_delay_seconds is not None:
            available_at += timedelta(seconds=max(0, retry_delay_seconds))
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                "UPDATE sage.growth_job SET state=%s, available_at=%s, "
                "leased_until=NULL, worker_id=NULL, "
                "payload=payload || %s, updated_at=clock_timestamp() "
                "WHERE tenant_id=%s AND job_id=%s AND state=%s "
                "AND worker_id=%s RETURNING *",
                (
                    state.value,
                    available_at,
                    self._json_payload({"_sage_last_error": error[:2000]}),
                    principal.tenant_id,
                    job_id,
                    GrowthJobState.LEASED.value,
                    worker_id,
                ),
            )
            row = await cursor.fetchone()
        if row is None:
            raise SageConflict("growth job is not leased by this worker")
        return self._growth_job_from_row(row)

    async def _save_scoped(
        self,
        principal: Principal,
        *,
        table: str,
        id_column: str,
        object_id: UUID,
        tenant_id: UUID,
        scope: ScopeRef,
        classification: Classification,
        state: str,
        body: Any,
        extra_columns: dict[str, Any] | None = None,
    ) -> None:
        allowed = {
            ("business_case", "case_id"),
            ("insight", "insight_id"),
            ("playbook", "playbook_id"),
        }
        if (table, id_column) not in allowed:
            raise ValueError("unsupported SAGE PostgreSQL upsert target")
        self._require_write(principal, tenant_id, scope, classification)
        extras = extra_columns or {}
        if extras and (table != "insight" or set(extras) != {"fingerprint"}):
            raise ValueError("unsupported SAGE PostgreSQL extra columns")
        columns = [
            "tenant_id",
            id_column,
            "scope_type",
            "scope_id",
            "state",
            "classification",
            *extras,
            "body_json",
        ]
        values = [
            tenant_id,
            object_id,
            scope.scope_type.value,
            scope.scope_id,
            state,
            classification.value,
            *extras.values(),
            self._json(body),
        ]
        updates = [
            "scope_type=excluded.scope_type",
            "scope_id=excluded.scope_id",
            "state=excluded.state",
            "classification=excluded.classification",
            *(f"{name}=excluded.{name}" for name in extras),
            "updated_at=clock_timestamp()",
            "body_json=excluded.body_json",
        ]
        placeholders = ", ".join("%s" for _ in columns)
        async with self._tenant_connection(principal) as conn:
            await conn.execute(
                f"INSERT INTO sage.{table} ({', '.join(columns)}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT (tenant_id, {id_column}) DO UPDATE SET "
                + ", ".join(updates),
                values,
            )

    async def _get_scoped(
        self,
        principal: Principal,
        table: str,
        id_column: str,
        object_id: UUID,
        model: Any,
    ) -> Any | None:
        allowed = {
            ("business_case", "case_id"),
            ("knowledge_item", "item_id"),
            ("insight", "insight_id"),
            ("playbook", "playbook_id"),
        }
        if (table, id_column) not in allowed:
            raise ValueError("unsupported SAGE PostgreSQL read target")
        async with self._tenant_connection(principal) as conn:
            cursor = await conn.execute(
                f"SELECT body_json FROM sage.{table} "
                f"WHERE tenant_id = %s AND {id_column} = %s",
                (principal.tenant_id, object_id),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        value = model.model_validate(row["body_json"])
        ScopePolicy.require_scope(principal, value.scope)
        ScopePolicy.require_classification_read(
            principal,
            value.classification,
        )
        return value

    @asynccontextmanager
    async def _tenant_connection(
        self,
        principal: Principal,
    ) -> AsyncIterator[Any]:
        if self._pool is None:
            raise RuntimeError("PostgresSageStore has not been started")
        async with self._pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    SET_LOCAL_TENANT_SQL,
                    (str(principal.tenant_id),),
                )
                yield conn

    @staticmethod
    def _json(value: Any) -> Any:
        if Jsonb is None:
            raise RuntimeError("psycopg JSON support is unavailable")
        return Jsonb(value.model_dump(mode="json"))

    @staticmethod
    def _json_payload(value: dict[str, Any]) -> Any:
        if Jsonb is None:
            raise RuntimeError("psycopg JSON support is unavailable")
        return Jsonb(value)

    @staticmethod
    def _growth_job_from_row(row: Any) -> GrowthJob:
        if row is None:
            raise SageConflict("growth job was not persisted")
        payload = dict(row["payload"] or {})
        last_error = str(payload.pop("_sage_last_error", ""))
        return GrowthJob(
            job_id=row["job_id"],
            tenant_id=row["tenant_id"],
            job_type=row["job_type"],
            state=row["state"],
            payload=payload,
            attempts=row["attempts"],
            available_at=row["available_at"],
            leased_until=row["leased_until"],
            worker_id=row["worker_id"],
            last_error=last_error,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _vector_literal(values: tuple[float, ...]) -> str:
        if not values:
            raise ValueError("embedding vector cannot be empty")
        return "[" + ",".join(format(float(value), ".12g") for value in values) + "]"

    @staticmethod
    def _append_states(
        where: list[str],
        params: list[Any],
        states: tuple[Any, ...] | None,
    ) -> None:
        if not states:
            return
        where.append("state = ANY(%s)")
        params.append([state.value for state in states])

    @staticmethod
    def _require_write(
        principal: Principal,
        tenant_id: UUID,
        scope: ScopeRef,
        classification: Classification,
    ) -> None:
        ScopePolicy.require_tenant(principal, tenant_id)
        ScopePolicy.require_write_scope(principal, scope)
        ScopePolicy.require_classification_write(principal, classification)

    @staticmethod
    def _classification_allowed(
        principal: Principal,
        classification: Classification,
    ) -> bool:
        try:
            ScopePolicy.require_classification_read(principal, classification)
            return True
        except SageAccessDenied:
            return False

    @classmethod
    def _filter_scoped(cls, principal: Principal, values: list[Any]) -> list[Any]:
        filtered = []
        for value in values:
            try:
                ScopePolicy.require_scope(principal, value.scope)
                ScopePolicy.require_classification_read(
                    principal,
                    value.classification,
                )
                filtered.append(value)
            except SageAccessDenied:
                continue
        return filtered


__all__ = ["PostgresSageStore"]
