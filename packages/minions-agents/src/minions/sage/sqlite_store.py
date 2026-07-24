"""Durable SQLite development adapter for SAGE.

The adapter enforces tenant identity for every operation and never accepts a
raw unscoped query.  Production deployments can implement the same SageStore
port with PostgreSQL and row-level security.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import sqlite3
import threading
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID

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

T = TypeVar("T")


class SQLiteSageStore:
    """SQLite implementation of the SAGE storage port."""

    supports_semantic = True

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self._fts_available = False

    async def start(self) -> None:
        await asyncio.to_thread(self._start_sync)

    def _start_sync(self) -> None:
        with self._lock:
            if self._conn is not None:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                str(self.path),
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            self._conn = conn
            self._init_schema_sync()

    async def close(self) -> None:
        await asyncio.to_thread(self._close_sync)

    def _close_sync(self) -> None:
        with self._lock:
            if self._conn is None:
                return
            self._conn.close()
            self._conn = None

    async def journal_mode(self) -> str:
        return await self._call(self._journal_mode_sync)

    def _journal_mode_sync(self) -> str:
        row = self._connection().execute("PRAGMA journal_mode").fetchone()
        return str(row[0]).lower()

    async def table_names(self) -> set[str]:
        return await self._call(self._table_names_sync)

    def _table_names_sync(self) -> set[str]:
        rows = (
            self._connection()
            .execute(
                "SELECT name FROM sqlite_master WHERE type='table'",
            )
            .fetchall()
        )
        return {str(row["name"]) for row in rows}

    async def append_trace(
        self,
        principal: Principal,
        trace: Trace,
    ) -> Trace:
        ScopePolicy.require_tenant(principal, trace.tenant_id)
        ScopePolicy.require_classification_write(
            principal,
            trace.classification,
        )
        if trace.user_id != principal.user_id and (
            "sage.trace.write.any" not in principal.permissions
        ):
            raise SageAccessDenied("cannot write a trace for another user")
        persisted = await self._call(self._append_trace_sync, trace)
        if persisted.user_id != principal.user_id:
            raise SageAccessDenied("trace event key belongs to another user")
        return persisted

    def _append_trace_sync(self, trace: Trace) -> Trace:
        conn = self._connection()
        with self._lock, conn:
            conn.execute(
                "INSERT INTO sage_trace "
                "(trace_id, event_key, tenant_id, user_id, agent_uid, "
                "session_id, case_id, trace_type, occurred_at, body_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(tenant_id, event_key) DO NOTHING",
                (
                    str(trace.trace_id),
                    trace.event_key,
                    str(trace.tenant_id),
                    str(trace.user_id),
                    str(trace.agent_uid),
                    trace.session_id,
                    str(trace.case_id) if trace.case_id else None,
                    trace.trace_type.value,
                    trace.occurred_at.isoformat(),
                    trace.model_dump_json(),
                ),
            )
            row = conn.execute(
                "SELECT body_json FROM sage_trace "
                "WHERE tenant_id = ? AND event_key = ?",
                (str(trace.tenant_id), trace.event_key),
            ).fetchone()
        return Trace.model_validate_json(row["body_json"])

    async def list_traces(
        self,
        principal: Principal,
        *,
        case_id: UUID | None = None,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[Trace]:
        traces = await self._call(
            self._list_traces_sync,
            principal,
            case_id,
            session_id,
            limit,
        )
        return [
            trace
            for trace in traces
            if self._classification_allowed(principal, trace.classification)
        ]

    def _list_traces_sync(
        self,
        principal: Principal,
        case_id: UUID | None,
        session_id: str | None,
        limit: int,
    ) -> list[Trace]:
        where = ["tenant_id = ?"]
        params: list[Any] = [str(principal.tenant_id)]
        if "sage.trace.read.any" not in principal.permissions:
            where.append("user_id = ?")
            params.append(str(principal.user_id))
        if case_id is not None:
            where.append("case_id = ?")
            params.append(str(case_id))
        if session_id is not None:
            where.append("session_id = ?")
            params.append(session_id)
        params.append(max(1, min(int(limit), 1000)))
        rows = (
            self._connection()
            .execute(
                "SELECT body_json FROM sage_trace WHERE "
                + " AND ".join(where)
                + " ORDER BY occurred_at, trace_id LIMIT ?",
                params,
            )
            .fetchall()
        )
        return [Trace.model_validate_json(row["body_json"]) for row in rows]

    async def save_case(
        self,
        principal: Principal,
        case: CaseRecord,
    ) -> CaseRecord:
        self._require_owned_object(
            principal,
            case.tenant_id,
            case.scope,
            case.classification,
        )
        return await self._call(self._save_case_sync, case)

    def _save_case_sync(self, case: CaseRecord) -> CaseRecord:
        self._upsert_body(
            table="sage_case",
            id_column="case_id",
            object_id=case.case_id,
            tenant_id=case.tenant_id,
            scope=case.scope,
            state=case.state.value,
            body_json=case.model_dump_json(),
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
        """Commit the request-completion boundary as one SQLite transaction."""

        self._require_owned_object(
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
        saved_case, saved_traces, saved_job = await self._call(
            self._commit_case_bundle_sync,
            case,
            traces,
            growth_job,
        )
        if any(trace.user_id != principal.user_id for trace in saved_traces):
            raise SageAccessDenied("trace event key belongs to another user")
        return saved_case, saved_traces, saved_job

    def _commit_case_bundle_sync(
        self,
        case: CaseRecord,
        traces: tuple[Trace, ...],
        growth_job: GrowthJob | None,
    ) -> tuple[CaseRecord, tuple[Trace, ...], GrowthJob | None]:
        conn = self._connection()
        saved_traces: list[Trace] = []
        with self._lock, conn:
            self._require_id_tenant_sync(
                "sage_case",
                "case_id",
                case.case_id,
                case.tenant_id,
            )
            for trace in traces:
                conn.execute(
                    "INSERT INTO sage_trace "
                    "(trace_id, event_key, tenant_id, user_id, agent_uid, "
                    "session_id, case_id, trace_type, occurred_at, body_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(tenant_id, event_key) DO NOTHING",
                    (
                        str(trace.trace_id),
                        trace.event_key,
                        str(trace.tenant_id),
                        str(trace.user_id),
                        str(trace.agent_uid),
                        trace.session_id,
                        str(trace.case_id) if trace.case_id else None,
                        trace.trace_type.value,
                        trace.occurred_at.isoformat(),
                        trace.model_dump_json(),
                    ),
                )
                row = conn.execute(
                    "SELECT body_json FROM sage_trace "
                    "WHERE tenant_id = ? AND event_key = ?",
                    (str(trace.tenant_id), trace.event_key),
                ).fetchone()
                saved_traces.append(Trace.model_validate_json(row["body_json"]))

            trace_ids = tuple(
                dict.fromkeys(
                    (*case.trace_ids, *(trace.trace_id for trace in saved_traces)),
                ),
            )
            saved_case = case.model_copy(update={"trace_ids": trace_ids})
            conn.execute(
                "INSERT INTO sage_case "
                "(case_id, tenant_id, scope_type, scope_id, state, "
                "updated_at, body_json) VALUES (?, ?, ?, ?, ?, "
                "strftime('%Y-%m-%dT%H:%M:%fZ','now'), ?) "
                "ON CONFLICT(case_id) DO UPDATE SET "
                "scope_type=excluded.scope_type, scope_id=excluded.scope_id, "
                "state=excluded.state, updated_at=excluded.updated_at, "
                "body_json=excluded.body_json "
                "WHERE sage_case.tenant_id=excluded.tenant_id",
                (
                    str(saved_case.case_id),
                    str(saved_case.tenant_id),
                    saved_case.scope.scope_type.value,
                    saved_case.scope.scope_id,
                    saved_case.state.value,
                    saved_case.model_dump_json(),
                ),
            )

            saved_job = None
            if growth_job is not None:
                self._require_id_tenant_sync(
                    "sage_growth_job",
                    "job_id",
                    growth_job.job_id,
                    growth_job.tenant_id,
                )
                conn.execute(
                    "INSERT INTO sage_growth_job "
                    "(job_id, tenant_id, job_type, state, available_at, "
                    "leased_until, worker_id, updated_at, body_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(job_id) DO NOTHING",
                    self._growth_job_values(growth_job),
                )
                row = conn.execute(
                    "SELECT body_json FROM sage_growth_job "
                    "WHERE tenant_id = ? AND job_id = ?",
                    (str(growth_job.tenant_id), str(growth_job.job_id)),
                ).fetchone()
                saved_job = GrowthJob.model_validate_json(row["body_json"])
        return saved_case, tuple(saved_traces), saved_job

    async def get_case(
        self,
        principal: Principal,
        case_id: UUID,
    ) -> CaseRecord | None:
        case = await self._call(
            self._get_model_sync,
            "sage_case",
            "case_id",
            case_id,
            principal.tenant_id,
            CaseRecord,
        )
        if case is not None:
            ScopePolicy.require_scope(principal, case.scope)
            ScopePolicy.require_classification_read(
                principal,
                case.classification,
            )
        return case

    async def list_cases(
        self,
        principal: Principal,
        *,
        states: tuple[CaseState, ...] | None = None,
        limit: int = 100,
    ) -> list[CaseRecord]:
        values = await self._call(
            self._list_models_sync,
            "sage_case",
            principal.tenant_id,
            CaseRecord,
            states,
            limit,
        )
        return [
            value
            for value in values
            if self._scope_allowed(principal, value.scope)
            and self._classification_allowed(principal, value.classification)
        ]

    async def save_item(
        self,
        principal: Principal,
        item: KnowledgeItem,
    ) -> KnowledgeItem:
        self._require_owned_object(
            principal,
            item.tenant_id,
            item.scope,
            item.classification,
        )
        await self._call(self._save_item_sync, item)
        return item

    def _save_item_sync(self, item: KnowledgeItem) -> None:
        conn = self._connection()
        with self._lock, conn:
            self._require_id_tenant_sync(
                "sage_item",
                "item_id",
                item.item_id,
                item.tenant_id,
            )
            conn.execute(
                "INSERT INTO sage_item "
                "(item_id, tenant_id, scope_type, scope_id, kind, state, "
                "title, content, valid_until, updated_at, body_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(item_id) DO UPDATE SET "
                "scope_type=excluded.scope_type, scope_id=excluded.scope_id, "
                "kind=excluded.kind, state=excluded.state, "
                "title=excluded.title, content=excluded.content, "
                "valid_until=excluded.valid_until, "
                "updated_at=excluded.updated_at, body_json=excluded.body_json "
                "WHERE sage_item.tenant_id = excluded.tenant_id",
                (
                    str(item.item_id),
                    str(item.tenant_id),
                    item.scope.scope_type.value,
                    item.scope.scope_id,
                    item.kind.value,
                    item.state.value,
                    item.title,
                    item.content,
                    item.valid_until.isoformat() if item.valid_until else None,
                    item.updated_at.isoformat(),
                    item.model_dump_json(),
                ),
            )
            if self._fts_available:
                conn.execute(
                    "DELETE FROM sage_item_fts WHERE item_id = ?",
                    (str(item.item_id),),
                )
                conn.execute(
                    "INSERT INTO sage_item_fts "
                    "(item_id, tenant_id, title, content) VALUES (?, ?, ?, ?)",
                    (
                        str(item.item_id),
                        str(item.tenant_id),
                        item.title,
                        item.content,
                    ),
                )

    async def get_item(
        self,
        principal: Principal,
        item_id: UUID,
    ) -> KnowledgeItem | None:
        item = await self._call(
            self._get_model_sync,
            "sage_item",
            "item_id",
            item_id,
            principal.tenant_id,
            KnowledgeItem,
        )
        if item is not None:
            ScopePolicy.require_scope(principal, item.scope)
            ScopePolicy.require_classification_read(
                principal,
                item.classification,
            )
        return item

    async def search_items(
        self,
        principal: Principal,
        query: str,
        *,
        states: tuple[ItemState, ...] | None = None,
        limit: int = 20,
    ) -> list[KnowledgeItem]:
        items = await self._call(
            self._search_items_sync,
            principal.tenant_id,
            query,
            states,
            limit,
        )
        return [
            item
            for item in items
            if self._scope_allowed(principal, item.scope)
            and self._classification_allowed(principal, item.classification)
        ]

    async def list_items(
        self,
        principal: Principal,
        *,
        states: tuple[ItemState, ...] | None = None,
        kinds: tuple[ItemKind, ...] | None = None,
        limit: int = 100,
    ) -> list[KnowledgeItem]:
        items = await self._call(
            self._list_items_sync,
            principal.tenant_id,
            states,
            kinds,
            limit,
        )
        return [
            item
            for item in items
            if self._scope_allowed(principal, item.scope)
            and self._classification_allowed(principal, item.classification)
        ][: max(1, min(int(limit), 1000))]

    def _list_items_sync(
        self,
        tenant_id: UUID,
        states: tuple[ItemState, ...] | None,
        kinds: tuple[ItemKind, ...] | None,
        limit: int,
    ) -> list[KnowledgeItem]:
        where = ["tenant_id = ?"]
        params: list[Any] = [str(tenant_id)]
        if states:
            where.append("state IN (" + ",".join("?" for _ in states) + ")")
            params.extend(state.value for state in states)
        if kinds:
            where.append("kind IN (" + ",".join("?" for _ in kinds) + ")")
            params.extend(kind.value for kind in kinds)
        params.append(max(1, min(int(limit) * 4, 4000)))
        rows = (
            self._connection()
            .execute(
                "SELECT body_json FROM sage_item WHERE "
                + " AND ".join(where)
                + " ORDER BY updated_at DESC LIMIT ?",
                params,
            )
            .fetchall()
        )
        return [KnowledgeItem.model_validate_json(row["body_json"]) for row in rows]

    def _search_items_sync(
        self,
        tenant_id: UUID,
        query: str,
        states: tuple[ItemState, ...] | None,
        limit: int,
    ) -> list[KnowledgeItem]:
        query = query.strip()
        if not query:
            return []
        state_values = tuple(state.value for state in states or ())
        cap = max(1, min(int(limit), 200))
        rows: list[sqlite3.Row]
        match_query = self._fts_query(query)
        if self._fts_available and match_query:
            where = [
                "sage_item_fts.tenant_id = ?",
                "sage_item_fts MATCH ?",
            ]
            params: list[Any] = [str(tenant_id), match_query]
            if state_values:
                where.append(
                    "i.state IN (" + ",".join("?" for _ in state_values) + ")",
                )
                params.extend(state_values)
            params.append(cap * 4)
            try:
                rows = (
                    self._connection()
                    .execute(
                        "SELECT i.body_json FROM sage_item_fts "
                        "JOIN sage_item i ON i.item_id = sage_item_fts.item_id "
                        "WHERE "
                        + " AND ".join(where)
                        + " ORDER BY bm25(sage_item_fts) LIMIT ?",
                        params,
                    )
                    .fetchall()
                )
            except sqlite3.OperationalError:
                rows = self._search_items_like(tenant_id, query, state_values, cap)
        else:
            rows = self._search_items_like(tenant_id, query, state_values, cap)
        return [KnowledgeItem.model_validate_json(row["body_json"]) for row in rows]

    def _search_items_like(
        self,
        tenant_id: UUID,
        query: str,
        states: tuple[str, ...],
        cap: int,
    ) -> list[sqlite3.Row]:
        where = ["tenant_id = ?", "(title LIKE ? OR content LIKE ?)"]
        params: list[Any] = [str(tenant_id), f"%{query}%", f"%{query}%"]
        if states:
            where.append("state IN (" + ",".join("?" for _ in states) + ")")
            params.extend(states)
        params.append(cap * 4)
        return (
            self._connection()
            .execute(
                "SELECT body_json FROM sage_item WHERE "
                + " AND ".join(where)
                + " ORDER BY updated_at DESC LIMIT ?",
                params,
            )
            .fetchall()
        )

    async def save_insight(
        self,
        principal: Principal,
        insight: InsightDraft,
    ) -> InsightDraft:
        self._require_owned_object(
            principal,
            insight.tenant_id,
            insight.scope,
            insight.classification,
        )
        await self._call(
            self._upsert_body,
            "sage_insight",
            "insight_id",
            insight.insight_id,
            insight.tenant_id,
            insight.scope,
            insight.state.value,
            insight.model_dump_json(),
        )
        return insight

    async def get_insight(
        self,
        principal: Principal,
        insight_id: UUID,
    ) -> InsightDraft | None:
        insight = await self._call(
            self._get_model_sync,
            "sage_insight",
            "insight_id",
            insight_id,
            principal.tenant_id,
            InsightDraft,
        )
        if insight is not None:
            ScopePolicy.require_scope(principal, insight.scope)
            ScopePolicy.require_classification_read(
                principal,
                insight.classification,
            )
        return insight

    async def search_insights(
        self,
        principal: Principal,
        fingerprint: str,
        *,
        states: tuple[InsightState, ...] | None = None,
        limit: int = 20,
    ) -> list[InsightDraft]:
        insights = await self._call(
            self._search_insights_sync,
            principal.tenant_id,
            fingerprint,
            states,
            limit,
        )
        return [
            insight
            for insight in insights
            if self._scope_allowed(principal, insight.scope)
            and self._classification_allowed(
                principal,
                insight.classification,
            )
        ]

    async def list_insights(
        self,
        principal: Principal,
        *,
        states: tuple[InsightState, ...] | None = None,
        limit: int = 100,
    ) -> list[InsightDraft]:
        values = await self._call(
            self._list_models_sync,
            "sage_insight",
            principal.tenant_id,
            InsightDraft,
            states,
            limit,
        )
        return [
            value
            for value in values
            if self._scope_allowed(principal, value.scope)
            and self._classification_allowed(principal, value.classification)
        ]

    def _list_models_sync(
        self,
        table: str,
        tenant_id: UUID,
        model: type[Any],
        states: tuple[Any, ...] | None,
        limit: int,
    ) -> list[Any]:
        if table not in {"sage_case", "sage_insight"}:
            raise ValueError("unsupported SAGE list table")
        where = ["tenant_id = ?"]
        params: list[Any] = [str(tenant_id)]
        state_values = tuple(value.value for value in states or ())
        if state_values:
            where.append("state IN (" + ",".join("?" for _ in state_values) + ")")
            params.extend(state_values)
        params.append(max(1, min(int(limit), 1000)))
        rows = (
            self._connection()
            .execute(
                f"SELECT body_json FROM {table} WHERE "
                + " AND ".join(where)
                + " ORDER BY updated_at DESC LIMIT ?",
                params,
            )
            .fetchall()
        )
        return [model.model_validate_json(row["body_json"]) for row in rows]

    def _search_insights_sync(
        self,
        tenant_id: UUID,
        fingerprint: str,
        states: tuple[InsightState, ...] | None,
        limit: int,
    ) -> list[InsightDraft]:
        if not fingerprint:
            return []
        where = ["tenant_id = ?", "body_json LIKE ?"]
        params: list[Any] = [
            str(tenant_id),
            f'%"fingerprint":"{fingerprint}"%',
        ]
        state_values = tuple(state.value for state in states or ())
        if state_values:
            placeholders = ",".join("?" for _ in state_values)
            where.append(f"state IN ({placeholders})")
            params.extend(state_values)
        params.append(max(1, min(int(limit), 100)))
        rows = (
            self._connection()
            .execute(
                "SELECT body_json FROM sage_insight WHERE "
                + " AND ".join(where)
                + " ORDER BY updated_at DESC LIMIT ?",
                params,
            )
            .fetchall()
        )
        return [InsightDraft.model_validate_json(row["body_json"]) for row in rows]

    async def save_playbook(
        self,
        principal: Principal,
        playbook: Playbook,
    ) -> Playbook:
        self._require_owned_object(
            principal,
            playbook.tenant_id,
            playbook.scope,
            playbook.classification,
        )
        await self._call(
            self._upsert_body,
            "sage_playbook",
            "playbook_id",
            playbook.playbook_id,
            playbook.tenant_id,
            playbook.scope,
            playbook.state.value,
            playbook.model_dump_json(),
        )
        return playbook

    async def get_playbook(
        self,
        principal: Principal,
        playbook_id: UUID,
    ) -> Playbook | None:
        playbook = await self._call(
            self._get_model_sync,
            "sage_playbook",
            "playbook_id",
            playbook_id,
            principal.tenant_id,
            Playbook,
        )
        if playbook is not None:
            ScopePolicy.require_scope(principal, playbook.scope)
            ScopePolicy.require_classification_read(
                principal,
                playbook.classification,
            )
        return playbook

    async def search_playbooks(
        self,
        principal: Principal,
        query: str,
        *,
        limit: int = 10,
    ) -> list[Playbook]:
        rows = await self._call(
            self._search_playbooks_sync,
            principal.tenant_id,
            query,
            limit,
        )
        return [
            item
            for item in rows
            if self._scope_allowed(principal, item.scope)
            and self._classification_allowed(principal, item.classification)
        ]

    def _search_playbooks_sync(
        self,
        tenant_id: UUID,
        query: str,
        limit: int,
    ) -> list[Playbook]:
        rows = (
            self._connection()
            .execute(
                "SELECT body_json FROM sage_playbook "
                "WHERE tenant_id = ? AND body_json LIKE ? "
                "ORDER BY updated_at DESC LIMIT ?",
                (str(tenant_id), f"%{query.strip()}%", max(1, min(limit * 4, 100))),
            )
            .fetchall()
        )
        return [Playbook.model_validate_json(row["body_json"]) for row in rows]

    async def list_playbooks(
        self,
        principal: Principal,
        *,
        states: tuple[PlaybookState, ...] | None = None,
        limit: int = 100,
    ) -> list[Playbook]:
        values = await self._call(
            self._list_playbooks_sync,
            principal.tenant_id,
            states,
            limit,
        )
        return [
            value
            for value in values
            if self._scope_allowed(principal, value.scope)
            and self._classification_allowed(principal, value.classification)
        ]

    def _list_playbooks_sync(
        self,
        tenant_id: UUID,
        states: tuple[PlaybookState, ...] | None,
        limit: int,
    ) -> list[Playbook]:
        where = ["tenant_id = ?"]
        params: list[Any] = [str(tenant_id)]
        state_values = tuple(value.value for value in states or ())
        if state_values:
            where.append("state IN (" + ",".join("?" for _ in state_values) + ")")
            params.extend(state_values)
        params.append(max(1, min(int(limit), 1000)))
        rows = (
            self._connection()
            .execute(
                "SELECT body_json FROM sage_playbook WHERE "
                + " AND ".join(where)
                + " ORDER BY updated_at DESC LIMIT ?",
                params,
            )
            .fetchall()
        )
        return [Playbook.model_validate_json(row["body_json"]) for row in rows]

    async def save_capability_policy(
        self,
        principal: Principal,
        policy: CapabilityPolicy,
    ) -> CapabilityPolicy:
        ScopePolicy.require_tenant(principal, policy.tenant_id)
        return await self._call(self._save_capability_policy_sync, policy)

    def _save_capability_policy_sync(
        self,
        policy: CapabilityPolicy,
    ) -> CapabilityPolicy:
        conn = self._connection()
        with self._lock, conn:
            self._require_id_tenant_sync(
                "sage_capability_policy",
                "policy_id",
                policy.policy_id,
                policy.tenant_id,
            )
            row = conn.execute(
                "SELECT body_json FROM sage_capability_policy "
                "WHERE tenant_id = ? AND policy_id = ?",
                (str(policy.tenant_id), str(policy.policy_id)),
            ).fetchone()
            if row is not None:
                current = CapabilityPolicy.model_validate_json(row["body_json"])
                if current == policy:
                    return current
                if policy.version != current.version + 1:
                    raise SageConflict(
                        "capability policy update requires the next version",
                    )
            conn.execute(
                "INSERT INTO sage_capability_policy "
                "(policy_id, tenant_id, capability, mode, scope_type, "
                "scope_id, version, updated_at, body_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(policy_id) DO UPDATE SET "
                "capability=excluded.capability, mode=excluded.mode, "
                "scope_type=excluded.scope_type, scope_id=excluded.scope_id, "
                "version=excluded.version, updated_at=excluded.updated_at, "
                "body_json=excluded.body_json "
                "WHERE sage_capability_policy.tenant_id=excluded.tenant_id",
                (
                    str(policy.policy_id),
                    str(policy.tenant_id),
                    policy.capability.value,
                    policy.mode.value,
                    policy.scope.scope_type.value if policy.scope else None,
                    policy.scope.scope_id if policy.scope else None,
                    policy.version,
                    policy.updated_at.isoformat(),
                    policy.model_dump_json(),
                ),
            )
        return policy

    async def get_capability_policy(
        self,
        principal: Principal,
        policy_id: UUID,
    ) -> CapabilityPolicy | None:
        return await self._call(
            self._get_capability_policy_sync,
            principal.tenant_id,
            policy_id,
        )

    def _get_capability_policy_sync(
        self,
        tenant_id: UUID,
        policy_id: UUID,
    ) -> CapabilityPolicy | None:
        row = (
            self._connection()
            .execute(
                "SELECT body_json FROM sage_capability_policy "
                "WHERE tenant_id = ? AND policy_id = ?",
                (str(tenant_id), str(policy_id)),
            )
            .fetchone()
        )
        return (
            CapabilityPolicy.model_validate_json(row["body_json"])
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
        return await self._call(
            self._list_capability_policies_sync,
            principal.tenant_id,
            capability,
            limit,
        )

    def _list_capability_policies_sync(
        self,
        tenant_id: UUID,
        capability: SageCapability | None,
        limit: int,
    ) -> list[CapabilityPolicy]:
        where = ["tenant_id = ?"]
        params: list[Any] = [str(tenant_id)]
        if capability is not None:
            where.append("capability = ?")
            params.append(capability.value)
        params.append(max(1, min(int(limit), 1000)))
        rows = (
            self._connection()
            .execute(
                "SELECT body_json FROM sage_capability_policy WHERE "
                + " AND ".join(where)
                + " ORDER BY capability, scope_type, scope_id, policy_id LIMIT ?",
                params,
            )
            .fetchall()
        )
        return [CapabilityPolicy.model_validate_json(row["body_json"]) for row in rows]

    async def save_knowledge_signal(
        self,
        principal: Principal,
        signal: KnowledgeSignal,
    ) -> KnowledgeSignal:
        ScopePolicy.require_tenant(principal, signal.tenant_id)
        return await self._call(self._save_knowledge_signal_sync, signal)

    def _save_knowledge_signal_sync(
        self,
        signal: KnowledgeSignal,
    ) -> KnowledgeSignal:
        conn = self._connection()
        with self._lock, conn:
            self._require_id_tenant_sync(
                "sage_knowledge_signal",
                "signal_id",
                signal.signal_id,
                signal.tenant_id,
            )
            conn.execute(
                "INSERT INTO sage_knowledge_signal "
                "(signal_id, tenant_id, source_id, kind, occurred_at, "
                "body_json) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(signal_id) DO NOTHING",
                (
                    str(signal.signal_id),
                    str(signal.tenant_id),
                    str(signal.source_id),
                    signal.kind.value,
                    signal.occurred_at.isoformat(),
                    signal.model_dump_json(),
                ),
            )
            row = conn.execute(
                "SELECT body_json FROM sage_knowledge_signal "
                "WHERE tenant_id = ? AND signal_id = ?",
                (str(signal.tenant_id), str(signal.signal_id)),
            ).fetchone()
        return KnowledgeSignal.model_validate_json(row["body_json"])

    async def list_knowledge_signals(
        self,
        principal: Principal,
        *,
        source_id: UUID | None = None,
        limit: int = 1000,
    ) -> list[KnowledgeSignal]:
        return await self._call(
            self._list_knowledge_signals_sync,
            principal.tenant_id,
            source_id,
            limit,
        )

    def _list_knowledge_signals_sync(
        self,
        tenant_id: UUID,
        source_id: UUID | None,
        limit: int,
    ) -> list[KnowledgeSignal]:
        where = ["tenant_id = ?"]
        params: list[Any] = [str(tenant_id)]
        if source_id is not None:
            where.append("source_id = ?")
            params.append(str(source_id))
        params.append(max(1, min(int(limit), 5000)))
        rows = (
            self._connection()
            .execute(
                "SELECT body_json FROM sage_knowledge_signal WHERE "
                + " AND ".join(where)
                + " ORDER BY occurred_at, signal_id LIMIT ?",
                params,
            )
            .fetchall()
        )
        return [KnowledgeSignal.model_validate_json(row["body_json"]) for row in rows]

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
        self._require_owned_object(
            principal,
            item.tenant_id,
            item.scope,
            item.classification,
        )
        vector = tuple(float(value) for value in embedding)
        if not vector or not all(math.isfinite(value) for value in vector):
            raise ValueError("embedding vector must be finite and non-empty")
        await self._call(
            self._save_item_embedding_sync,
            principal.tenant_id,
            item_id,
            vector,
            model,
            item_version,
        )

    def _save_item_embedding_sync(
        self,
        tenant_id: UUID,
        item_id: UUID,
        embedding: tuple[float, ...],
        model: str,
        item_version: int,
    ) -> None:
        conn = self._connection()
        with self._lock, conn:
            conn.execute(
                "INSERT INTO sage_item_embedding("
                "item_id, tenant_id, dimensions, model, item_version, "
                "embedding_json, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(item_id) DO UPDATE SET "
                "tenant_id=excluded.tenant_id, dimensions=excluded.dimensions, "
                "model=excluded.model, item_version=excluded.item_version, "
                "embedding_json=excluded.embedding_json, "
                "updated_at=excluded.updated_at",
                (
                    str(item_id),
                    str(tenant_id),
                    len(embedding),
                    str(model)[:200],
                    max(1, int(item_version)),
                    json.dumps(embedding, separators=(",", ":")),
                    utc_now().isoformat(),
                ),
            )

    async def semantic_search_items(
        self,
        principal: Principal,
        embedding: tuple[float, ...],
        *,
        limit: int = 20,
    ) -> list[tuple[KnowledgeItem, float]]:
        vector = tuple(float(value) for value in embedding)
        if not vector or not all(math.isfinite(value) for value in vector):
            return []
        rows = await self._call(
            self._semantic_search_items_sync,
            principal.tenant_id,
            vector,
        )
        matches = []
        for item, score in rows:
            if not self._scope_allowed(principal, item.scope):
                continue
            if not self._classification_allowed(principal, item.classification):
                continue
            matches.append((item, score))
            if len(matches) >= max(1, min(int(limit), 100)):
                break
        return matches

    def _semantic_search_items_sync(
        self,
        tenant_id: UUID,
        query: tuple[float, ...],
    ) -> list[tuple[KnowledgeItem, float]]:
        rows = (
            self._connection()
            .execute(
                "SELECT i.body_json, e.embedding_json "
                "FROM sage_item_embedding e "
                "JOIN sage_item i ON i.item_id=e.item_id "
                "WHERE e.tenant_id=? AND i.tenant_id=? AND i.state=? "
                "AND (i.valid_until IS NULL OR i.valid_until > ?) "
                "ORDER BY i.updated_at DESC LIMIT 2000",
                (
                    str(tenant_id),
                    str(tenant_id),
                    ItemState.ACTIVE.value,
                    utc_now().isoformat(),
                ),
            )
            .fetchall()
        )
        query_norm = math.sqrt(sum(value * value for value in query))
        if query_norm == 0:
            return []
        matches: list[tuple[KnowledgeItem, float]] = []
        for row in rows:
            candidate = tuple(
                float(value) for value in json.loads(row["embedding_json"])
            )
            if len(candidate) != len(query):
                continue
            candidate_norm = math.sqrt(sum(value * value for value in candidate))
            if candidate_norm == 0:
                continue
            score = sum(
                left * right for left, right in zip(query, candidate, strict=True)
            ) / (query_norm * candidate_norm)
            matches.append(
                (
                    KnowledgeItem.model_validate_json(row["body_json"]),
                    max(0.0, min(float(score), 1.0)),
                ),
            )
        matches.sort(key=lambda value: (value[1], value[0].updated_at), reverse=True)
        return matches

    async def save_consolidation_run(
        self,
        principal: Principal,
        run: ConsolidationRun,
    ) -> ConsolidationRun:
        ScopePolicy.require_tenant(principal, run.tenant_id)
        return await self._call(self._save_consolidation_run_sync, run)

    def _save_consolidation_run_sync(
        self,
        run: ConsolidationRun,
    ) -> ConsolidationRun:
        conn = self._connection()
        with self._lock, conn:
            self._require_id_tenant_sync(
                "sage_consolidation_run",
                "run_id",
                run.run_id,
                run.tenant_id,
            )
            conn.execute(
                "INSERT INTO sage_consolidation_run "
                "(run_id, tenant_id, local_date, state, updated_at, body_json) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(run_id) DO UPDATE SET state=excluded.state, "
                "updated_at=excluded.updated_at, body_json=excluded.body_json "
                "WHERE sage_consolidation_run.tenant_id=excluded.tenant_id",
                (
                    str(run.run_id),
                    str(run.tenant_id),
                    run.local_date,
                    run.state.value,
                    run.updated_at.isoformat(),
                    run.model_dump_json(),
                ),
            )
        return run

    async def get_consolidation_run(
        self,
        principal: Principal,
        run_id: UUID,
    ) -> ConsolidationRun | None:
        return await self._call(
            self._get_consolidation_run_sync,
            principal.tenant_id,
            run_id,
        )

    def _get_consolidation_run_sync(
        self,
        tenant_id: UUID,
        run_id: UUID,
    ) -> ConsolidationRun | None:
        row = (
            self._connection()
            .execute(
                "SELECT body_json FROM sage_consolidation_run "
                "WHERE tenant_id=? AND run_id=?",
                (str(tenant_id), str(run_id)),
            )
            .fetchone()
        )
        return (
            ConsolidationRun.model_validate_json(row["body_json"])
            if row is not None
            else None
        )

    async def list_consolidation_runs(
        self,
        principal: Principal,
        *,
        limit: int = 100,
    ) -> list[ConsolidationRun]:
        rows = await self._call(
            self._list_consolidation_runs_sync,
            principal.tenant_id,
            limit,
        )
        return rows

    def _list_consolidation_runs_sync(
        self,
        tenant_id: UUID,
        limit: int,
    ) -> list[ConsolidationRun]:
        rows = (
            self._connection()
            .execute(
                "SELECT body_json FROM sage_consolidation_run WHERE tenant_id=? "
                "ORDER BY local_date DESC, run_id LIMIT ?",
                (str(tenant_id), max(1, min(int(limit), 1000))),
            )
            .fetchall()
        )
        return [ConsolidationRun.model_validate_json(row["body_json"]) for row in rows]

    async def save_consolidation_candidate(
        self,
        principal: Principal,
        candidate: ConsolidationCandidate,
    ) -> ConsolidationCandidate:
        ScopePolicy.require_tenant(principal, candidate.tenant_id)
        ScopePolicy.require_scope(principal, candidate.scope)
        return await self._call(
            self._save_consolidation_candidate_sync,
            candidate,
        )

    def _save_consolidation_candidate_sync(
        self,
        candidate: ConsolidationCandidate,
    ) -> ConsolidationCandidate:
        conn = self._connection()
        with self._lock, conn:
            self._require_id_tenant_sync(
                "sage_consolidation_candidate",
                "candidate_id",
                candidate.candidate_id,
                candidate.tenant_id,
            )
            row = conn.execute(
                "SELECT body_json FROM sage_consolidation_candidate "
                "WHERE tenant_id=? AND candidate_id=?",
                (str(candidate.tenant_id), str(candidate.candidate_id)),
            ).fetchone()
            if row is not None:
                current = ConsolidationCandidate.model_validate_json(
                    row["body_json"],
                )
                if current == candidate:
                    return current
                if candidate.version != current.version + 1:
                    raise SageConflict(
                        "consolidation candidate update requires the next version",
                    )
            conn.execute(
                "INSERT INTO sage_consolidation_candidate "
                "(candidate_id, tenant_id, run_id, kind, state, scope_type, "
                "scope_id, version, updated_at, body_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(candidate_id) DO UPDATE SET state=excluded.state, "
                "version=excluded.version, updated_at=excluded.updated_at, "
                "body_json=excluded.body_json "
                "WHERE sage_consolidation_candidate.tenant_id=excluded.tenant_id",
                (
                    str(candidate.candidate_id),
                    str(candidate.tenant_id),
                    str(candidate.run_id),
                    candidate.kind.value,
                    candidate.state.value,
                    candidate.scope.scope_type.value,
                    candidate.scope.scope_id,
                    candidate.version,
                    candidate.updated_at.isoformat(),
                    candidate.model_dump_json(),
                ),
            )
        return candidate

    async def get_consolidation_candidate(
        self,
        principal: Principal,
        candidate_id: UUID,
    ) -> ConsolidationCandidate | None:
        candidate = await self._call(
            self._get_consolidation_candidate_sync,
            principal.tenant_id,
            candidate_id,
        )
        if candidate is not None:
            ScopePolicy.require_scope(principal, candidate.scope)
        return candidate

    def _get_consolidation_candidate_sync(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
    ) -> ConsolidationCandidate | None:
        row = (
            self._connection()
            .execute(
                "SELECT body_json FROM sage_consolidation_candidate "
                "WHERE tenant_id=? AND candidate_id=?",
                (str(tenant_id), str(candidate_id)),
            )
            .fetchone()
        )
        return (
            ConsolidationCandidate.model_validate_json(row["body_json"])
            if row is not None
            else None
        )

    async def list_consolidation_candidates(
        self,
        principal: Principal,
        *,
        states: tuple[CandidateState, ...] | None = None,
        limit: int = 100,
    ) -> list[ConsolidationCandidate]:
        rows = await self._call(
            self._list_consolidation_candidates_sync,
            principal.tenant_id,
            states,
            limit,
        )
        return [row for row in rows if self._scope_allowed(principal, row.scope)]

    def _list_consolidation_candidates_sync(
        self,
        tenant_id: UUID,
        states: tuple[CandidateState, ...] | None,
        limit: int,
    ) -> list[ConsolidationCandidate]:
        where = ["tenant_id=?"]
        params: list[Any] = [str(tenant_id)]
        values = [state.value for state in states or ()]
        if values:
            where.append("state IN (" + ",".join("?" for _ in values) + ")")
            params.extend(values)
        params.append(max(1, min(int(limit), 1000)))
        rows = (
            self._connection()
            .execute(
                "SELECT body_json FROM sage_consolidation_candidate WHERE "
                + " AND ".join(where)
                + " ORDER BY updated_at DESC, candidate_id LIMIT ?",
                params,
            )
            .fetchall()
        )
        return [
            ConsolidationCandidate.model_validate_json(row["body_json"]) for row in rows
        ]

    async def enqueue_growth_job(
        self,
        principal: Principal,
        job: GrowthJob,
    ) -> GrowthJob:
        ScopePolicy.require_tenant(principal, job.tenant_id)
        return await self._call(self._enqueue_growth_job_sync, job)

    async def list_growth_jobs(
        self,
        principal: Principal,
        *,
        limit: int = 100,
    ) -> list[GrowthJob]:
        return await self._call(
            self._list_growth_jobs_sync,
            principal.tenant_id,
            limit,
        )

    def _list_growth_jobs_sync(
        self,
        tenant_id: UUID,
        limit: int,
    ) -> list[GrowthJob]:
        rows = (
            self._connection()
            .execute(
                "SELECT body_json FROM sage_growth_job "
                "WHERE tenant_id = ? ORDER BY updated_at DESC, job_id LIMIT ?",
                (str(tenant_id), max(1, min(int(limit), 5000))),
            )
            .fetchall()
        )
        return [GrowthJob.model_validate_json(row["body_json"]) for row in rows]

    async def acknowledge_growth_job(
        self,
        principal: Principal,
        job_id: UUID,
    ) -> GrowthJob:
        return await self._call(
            self._acknowledge_growth_job_sync,
            principal.tenant_id,
            job_id,
        )

    def _acknowledge_growth_job_sync(
        self,
        tenant_id: UUID,
        job_id: UUID,
    ) -> GrowthJob:
        conn = self._connection()
        with self._lock, conn:
            row = conn.execute(
                "SELECT body_json FROM sage_growth_job "
                "WHERE tenant_id = ? AND job_id = ?",
                (str(tenant_id), str(job_id)),
            ).fetchone()
            if row is None:
                raise SageConflict("SAGE growth job is missing")
            job = GrowthJob.model_validate_json(row["body_json"])
            if job.state is GrowthJobState.PENDING:
                job = job.model_copy(
                    update={
                        "state": GrowthJobState.COMPLETED,
                        "updated_at": utc_now(),
                    },
                )
                self._update_growth_job_sync(job)
            elif job.state is not GrowthJobState.COMPLETED:
                raise SageConflict("SAGE growth job is already leased")
        return job

    def _enqueue_growth_job_sync(self, job: GrowthJob) -> GrowthJob:
        conn = self._connection()
        with self._lock, conn:
            self._require_id_tenant_sync(
                "sage_growth_job",
                "job_id",
                job.job_id,
                job.tenant_id,
            )
            conn.execute(
                "INSERT INTO sage_growth_job "
                "(job_id, tenant_id, job_type, state, available_at, "
                "leased_until, worker_id, updated_at, body_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(job_id) DO NOTHING",
                self._growth_job_values(job),
            )
            row = conn.execute(
                "SELECT body_json FROM sage_growth_job "
                "WHERE tenant_id = ? AND job_id = ?",
                (str(job.tenant_id), str(job.job_id)),
            ).fetchone()
        return GrowthJob.model_validate_json(row["body_json"])

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
        return await self._call(
            self._claim_growth_jobs_sync,
            principal.tenant_id,
            worker_id[:256],
            limit,
            lease_seconds,
        )

    def _claim_growth_jobs_sync(
        self,
        tenant_id: UUID,
        worker_id: str,
        limit: int,
        lease_seconds: int,
    ) -> list[GrowthJob]:
        now = utc_now()
        leased_until = now + timedelta(seconds=max(1, int(lease_seconds)))
        cap = max(1, min(int(limit), 100))
        conn = self._connection()
        claimed: list[GrowthJob] = []
        with self._lock, conn:
            rows = conn.execute(
                "SELECT body_json FROM sage_growth_job "
                "WHERE tenant_id = ? AND "
                "((state = ? AND available_at <= ?) OR "
                "(state = ? AND leased_until <= ?)) "
                "ORDER BY available_at, job_id LIMIT ?",
                (
                    str(tenant_id),
                    GrowthJobState.PENDING.value,
                    now.isoformat(),
                    GrowthJobState.LEASED.value,
                    now.isoformat(),
                    cap,
                ),
            ).fetchall()
            for row in rows:
                job = GrowthJob.model_validate_json(row["body_json"])
                job = job.model_copy(
                    update={
                        "state": GrowthJobState.LEASED,
                        "attempts": job.attempts + 1,
                        "leased_until": leased_until,
                        "worker_id": worker_id,
                        "updated_at": now,
                    },
                )
                self._update_growth_job_sync(job)
                claimed.append(job)
        return claimed

    async def complete_growth_job(
        self,
        principal: Principal,
        job_id: UUID,
        *,
        worker_id: str,
    ) -> GrowthJob:
        return await self._call(
            self._finish_growth_job_sync,
            principal.tenant_id,
            job_id,
            worker_id,
            "",
            None,
            True,
        )

    async def fail_growth_job(
        self,
        principal: Principal,
        job_id: UUID,
        *,
        worker_id: str,
        error: str,
        retry_delay_seconds: int | None = 60,
    ) -> GrowthJob:
        return await self._call(
            self._finish_growth_job_sync,
            principal.tenant_id,
            job_id,
            worker_id,
            error[:2000],
            retry_delay_seconds,
            False,
        )

    def _finish_growth_job_sync(
        self,
        tenant_id: UUID,
        job_id: UUID,
        worker_id: str,
        error: str,
        retry_delay_seconds: int | None,
        completed: bool,
    ) -> GrowthJob:
        conn = self._connection()
        with self._lock, conn:
            row = conn.execute(
                "SELECT body_json FROM sage_growth_job "
                "WHERE tenant_id = ? AND job_id = ?",
                (str(tenant_id), str(job_id)),
            ).fetchone()
            if row is None:
                raise SageConflict("SAGE growth job is missing")
            job = GrowthJob.model_validate_json(row["body_json"])
            if job.state is not GrowthJobState.LEASED or (job.worker_id != worker_id):
                raise SageConflict("SAGE growth job lease is not owned")
            now = utc_now()
            if completed:
                state = GrowthJobState.COMPLETED
                available_at = job.available_at
            elif retry_delay_seconds is None:
                state = GrowthJobState.FAILED
                available_at = job.available_at
            else:
                state = GrowthJobState.PENDING
                available_at = now + timedelta(
                    seconds=max(0, int(retry_delay_seconds)),
                )
            job = job.model_copy(
                update={
                    "state": state,
                    "available_at": available_at,
                    "leased_until": None,
                    "worker_id": None,
                    "last_error": error,
                    "updated_at": now,
                },
            )
            self._update_growth_job_sync(job)
        return job

    def _update_growth_job_sync(self, job: GrowthJob) -> None:
        self._connection().execute(
            "UPDATE sage_growth_job SET state = ?, available_at = ?, "
            "leased_until = ?, worker_id = ?, updated_at = ?, body_json = ? "
            "WHERE tenant_id = ? AND job_id = ?",
            (
                job.state.value,
                job.available_at.isoformat(),
                job.leased_until.isoformat() if job.leased_until else None,
                job.worker_id,
                job.updated_at.isoformat(),
                job.model_dump_json(),
                str(job.tenant_id),
                str(job.job_id),
            ),
        )

    @staticmethod
    def _growth_job_values(job: GrowthJob) -> tuple[Any, ...]:
        return (
            str(job.job_id),
            str(job.tenant_id),
            job.job_type.value,
            job.state.value,
            job.available_at.isoformat(),
            job.leased_until.isoformat() if job.leased_until else None,
            job.worker_id,
            job.updated_at.isoformat(),
            job.model_dump_json(),
        )

    def _upsert_body(
        self,
        table: str,
        id_column: str,
        object_id: UUID,
        tenant_id: UUID,
        scope: ScopeRef,
        state: str,
        body_json: str,
    ) -> None:
        allowed = {
            ("sage_case", "case_id"),
            ("sage_insight", "insight_id"),
            ("sage_playbook", "playbook_id"),
        }
        if (table, id_column) not in allowed:
            raise ValueError("unsupported SAGE upsert target")
        conn = self._connection()
        with self._lock, conn:
            self._require_id_tenant_sync(
                table,
                id_column,
                object_id,
                tenant_id,
            )
            conn.execute(
                f"INSERT INTO {table} "
                f"({id_column}, tenant_id, scope_type, scope_id, state, "
                "updated_at, body_json) VALUES (?, ?, ?, ?, ?, "
                "strftime('%Y-%m-%dT%H:%M:%fZ','now'), ?) "
                f"ON CONFLICT({id_column}) DO UPDATE SET "
                "scope_type=excluded.scope_type, scope_id=excluded.scope_id, "
                "state=excluded.state, updated_at=excluded.updated_at, "
                "body_json=excluded.body_json "
                f"WHERE {table}.tenant_id = excluded.tenant_id",
                (
                    str(object_id),
                    str(tenant_id),
                    scope.scope_type.value,
                    scope.scope_id,
                    state,
                    body_json,
                ),
            )

    def _get_model_sync(
        self,
        table: str,
        id_column: str,
        object_id: UUID,
        tenant_id: UUID,
        model: Any,
    ) -> Any | None:
        allowed = {
            ("sage_case", "case_id"),
            ("sage_item", "item_id"),
            ("sage_insight", "insight_id"),
            ("sage_playbook", "playbook_id"),
        }
        if (table, id_column) not in allowed:
            raise ValueError("unsupported SAGE read target")
        row = (
            self._connection()
            .execute(
                f"SELECT body_json FROM {table} "
                f"WHERE tenant_id = ? AND {id_column} = ?",
                (str(tenant_id), str(object_id)),
            )
            .fetchone()
        )
        if row is None:
            return None
        return model.model_validate_json(row["body_json"])

    def _require_owned_object(
        self,
        principal: Principal,
        tenant_id: UUID,
        scope: ScopeRef,
        classification: Classification,
    ) -> None:
        ScopePolicy.require_tenant(principal, tenant_id)
        ScopePolicy.require_write_scope(principal, scope)
        ScopePolicy.require_classification_write(principal, classification)

    def _require_id_tenant_sync(
        self,
        table: str,
        id_column: str,
        object_id: UUID,
        tenant_id: UUID,
    ) -> None:
        row = (
            self._connection()
            .execute(
                f"SELECT tenant_id FROM {table} WHERE {id_column} = ?",
                (str(object_id),),
            )
            .fetchone()
        )
        if row is not None and row["tenant_id"] != str(tenant_id):
            raise SageConflict(
                "SAGE object identifier belongs to another tenant",
            )

    @staticmethod
    def _scope_allowed(principal: Principal, scope: ScopeRef) -> bool:
        try:
            ScopePolicy.require_scope(principal, scope)
            return True
        except SageAccessDenied:
            return False

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

    @staticmethod
    def _fts_query(query: str) -> str:
        terms = re.findall(r"[\w\u3400-\u9fff]+", query, flags=re.UNICODE)
        return " OR ".join(f'"{term}"' for term in terms[:12])

    async def _call(
        self,
        fn: Callable[..., T],
        *args: Any,
    ) -> T:
        # Cancelling ``asyncio.to_thread`` does not stop its worker thread. If
        # runtime shutdown then closes SQLite immediately, the still-running
        # query can use a closed connection (and some Python/SQLite builds can
        # crash the process). Shield the operation and drain it before
        # propagating cancellation so ``close`` is a real lifecycle barrier.
        operation = asyncio.create_task(asyncio.to_thread(fn, *args))
        try:
            return await asyncio.shield(operation)
        except asyncio.CancelledError:
            await operation
            raise

    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SQLiteSageStore has not been started")
        return self._conn

    def _init_schema_sync(self) -> None:
        conn = self._connection()
        schema = """
        CREATE TABLE IF NOT EXISTS sage_trace (
            trace_id TEXT PRIMARY KEY,
            event_key TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            agent_uid TEXT NOT NULL,
            session_id TEXT NOT NULL,
            case_id TEXT,
            trace_type TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            body_json TEXT NOT NULL,
            UNIQUE(tenant_id, event_key)
        );
        CREATE INDEX IF NOT EXISTS ix_sage_trace_tenant_session
            ON sage_trace(tenant_id, session_id, occurred_at);
        CREATE INDEX IF NOT EXISTS ix_sage_trace_tenant_case
            ON sage_trace(tenant_id, case_id, occurred_at);

        CREATE TABLE IF NOT EXISTS sage_case (
            case_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            state TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            body_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_sage_case_tenant_scope
            ON sage_case(tenant_id, scope_type, scope_id, state);

        CREATE TABLE IF NOT EXISTS sage_item (
            item_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            state TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            valid_until TEXT,
            updated_at TEXT NOT NULL,
            body_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_sage_item_tenant_scope
            ON sage_item(tenant_id, scope_type, scope_id, state);
        CREATE INDEX IF NOT EXISTS ix_sage_item_tenant_kind
            ON sage_item(tenant_id, kind, state, valid_until);

        CREATE TABLE IF NOT EXISTS sage_item_embedding (
            item_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            dimensions INTEGER NOT NULL,
            model TEXT NOT NULL,
            item_version INTEGER NOT NULL,
            embedding_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_sage_embedding_tenant
            ON sage_item_embedding(tenant_id, model, item_version);

        CREATE TABLE IF NOT EXISTS sage_insight (
            insight_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            state TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            body_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_sage_insight_tenant_scope
            ON sage_insight(tenant_id, scope_type, scope_id, state);

        CREATE TABLE IF NOT EXISTS sage_playbook (
            playbook_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            state TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            body_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_sage_playbook_tenant_scope
            ON sage_playbook(tenant_id, scope_type, scope_id, state);

        CREATE TABLE IF NOT EXISTS sage_growth_job (
            job_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            job_type TEXT NOT NULL,
            state TEXT NOT NULL,
            available_at TEXT NOT NULL,
            leased_until TEXT,
            worker_id TEXT,
            updated_at TEXT NOT NULL,
            body_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_sage_growth_job_tenant_claim
            ON sage_growth_job(
                tenant_id,
                state,
                available_at,
                leased_until
            );

        CREATE TABLE IF NOT EXISTS sage_capability_policy (
            policy_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            capability TEXT NOT NULL,
            mode TEXT NOT NULL,
            scope_type TEXT,
            scope_id TEXT,
            version INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            body_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_sage_policy_tenant_capability
            ON sage_capability_policy(
                tenant_id,
                capability,
                scope_type,
                scope_id
            );

        CREATE TABLE IF NOT EXISTS sage_knowledge_signal (
            signal_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            body_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_sage_signal_tenant_source
            ON sage_knowledge_signal(
                tenant_id,
                source_id,
                occurred_at
            );

        CREATE TABLE IF NOT EXISTS sage_consolidation_run (
            run_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            local_date TEXT NOT NULL,
            state TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            body_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_sage_run_tenant_date
            ON sage_consolidation_run(tenant_id, local_date, state);

        CREATE TABLE IF NOT EXISTS sage_consolidation_candidate (
            candidate_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            state TEXT NOT NULL,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            body_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_sage_candidate_tenant_state
            ON sage_consolidation_candidate(
                tenant_id,
                state,
                kind,
                updated_at
            );
        """
        with self._lock, conn:
            conn.executescript(schema)
            try:
                conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS sage_item_fts "
                    "USING fts5(item_id UNINDEXED, tenant_id UNINDEXED, "
                    "title, content, tokenize='unicode61')",
                )
                self._fts_available = True
            except sqlite3.OperationalError:
                self._fts_available = False
