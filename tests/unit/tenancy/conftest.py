from __future__ import annotations

import pytest

from minions.tenancy.factory import TenancySettings, build_tenancy_service
from minions.tenancy.models import DeploymentMode, StoreBackend


@pytest.fixture()
def tenancy_service(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MINIONS_TENANCY_SIGNING_KEY_FILE",
        str(tmp_path / "tenancy.key"),
    )
    service = build_tenancy_service(
        TenancySettings(
            mode=DeploymentMode.TEST,
            backend=StoreBackend.SQLITE,
            sqlite_path=tmp_path / "tenancy.db",
            token_ttl_seconds=3600,
        ),
    )
    yield service
    service.close()
