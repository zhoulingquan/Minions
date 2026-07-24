"""Durable scheduling for SAGE tenant maintenance work."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid5

from .control import PolicyCenter
from .models import GrowthJob, GrowthJobType, Principal, SageCapability
from .store import SageStore


class MaintenanceCoordinator:
    """Persist deterministic nightly jobs; workers remain fully restartable."""

    _NIGHTLY_JOBS = (
        GrowthJobType.CONSOLIDATE_TENANT,
        GrowthJobType.RECALCULATE_UTILITY,
        GrowthJobType.EVALUATE_RECALL,
    )

    def __init__(self, store: SageStore, control: PolicyCenter) -> None:
        self._store = store
        self._control = control

    async def schedule_due(
        self,
        principal: Principal,
        *,
        local_date: str | None = None,
    ) -> list[GrowthJob]:
        """Create one idempotent job of each type for a tenant business date."""

        decision = await self._control.decision(
            principal,
            SageCapability.NIGHTLY_CONSOLIDATION,
        )
        if not decision.execute:
            return []
        business_date = local_date or date.today().isoformat()
        # Validate rather than accepting arbitrary unbounded identifiers.
        date.fromisoformat(business_date)
        jobs = []
        for job_type in self._NIGHTLY_JOBS:
            job = GrowthJob(
                job_id=uuid5(
                    principal.tenant_id,
                    f"sage-maintenance:{business_date}:{job_type.value}",
                ),
                tenant_id=principal.tenant_id,
                job_type=job_type,
                payload={
                    "local_date": business_date,
                    "principal": principal.model_dump(mode="json"),
                },
            )
            jobs.append(await self._store.enqueue_growth_job(principal, job))
        return jobs

    async def schedule_catch_up(
        self,
        principal: Principal,
        *,
        through_date: str | None = None,
        days: int = 3,
    ) -> list[GrowthJob]:
        """Backfill a bounded date window after application downtime."""

        end = date.fromisoformat(through_date) if through_date else date.today()
        bounded_days = max(1, min(int(days), 31))
        scheduled: list[GrowthJob] = []
        for offset in reversed(range(bounded_days)):
            scheduled.extend(
                await self.schedule_due(
                    principal,
                    local_date=(end - timedelta(days=offset)).isoformat(),
                ),
            )
        return scheduled


__all__ = ["MaintenanceCoordinator"]
