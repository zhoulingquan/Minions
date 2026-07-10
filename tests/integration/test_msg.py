# -*- coding: utf-8 -*-
"""Integration tests for the Console msg header APIs.

These hit ``/api/console/msg/*`` (header routes, not agent-scoped). The
backing stores are file-based:

  - events: ``<working_dir>/msg_events.json`` (json list, asyncio.Lock)
  - traces: ``<working_dir>/msg_traces/<run_id>.json`` (one file per run)

Tests that need seeded data write these files directly via the helpers
below; the app subprocess re-reads them on each HTTP call, so no
restart is needed. An autouse fixture wipes both stores around every
test so cases stay independent within the module.
"""
from __future__ import annotations

from typing import Iterator

import pytest

from tests.integration.helpers import (
    clean_msg,
    default_http_timeout,
    make_event,
    seed_msg_events,
    seed_msg_trace,
)

_MSG_HTTP_TIMEOUT = default_http_timeout(15.0)


@pytest.fixture(autouse=True)
def _isolate_msg(app_server) -> Iterator[None]:
    """Wipe msg state before and after every test in this module."""
    clean_msg(app_server.working_dir)
    yield
    clean_msg(app_server.working_dir)


# --------------------------------------------------------------------------- #
# cases
# --------------------------------------------------------------------------- #


@pytest.mark.integration
@pytest.mark.p1
def test_msg_list_events_returns_empty_contract(app_server) -> None:
    """Test purpose:
    - Verify GET /api/console/msg/events returns ``{"events": []}`` on
      a fresh workspace. Console's Msg page hits this on first load;
      a regression breaks the msg tab for every user.

    Test flow:
    1. GET /api/console/msg/events without seeding any data.
    2. Assert 200, response is a dict containing the ``events`` key, and
       the value is an empty list.

    API endpoints:
    - GET /api/console/msg/events
    """
    resp = app_server.api_request(
        "GET",
        "/api/console/msg/events",
        timeout=_MSG_HTTP_TIMEOUT,
    )
    assert resp.status_code == 200, app_server.logs_tail()
    payload = resp.json()
    assert isinstance(payload, dict)
    assert payload.get("events") == []


@pytest.mark.integration
@pytest.mark.p1
def test_msg_list_events_with_seeded_data_returns_all(app_server) -> None:
    """Test purpose:
    - Verify list returns all seeded events with their core fields
      (id/agent_id/source_type/event_type/severity) intact. This is the
      first test that exercises the data path with real content.

    Test flow:
    1. Seed msg_events.json with 4 events (2 cron + 2 approval).
    2. GET /api/console/msg/events.
    3. Assert 200, ``events`` length 4, and every event keeps its
       seeded id / source_type / event_type / severity.

    API endpoints:
    - GET /api/console/msg/events
    """
    seeded = [
        make_event(
            event_id="evt-cron-01",
            source_type="cron",
            event_type="cron_executed",
            severity="info",
        ),
        make_event(
            event_id="evt-cron-02",
            source_type="cron",
            event_type="cron_failed",
            severity="warning",
        ),
        make_event(
            event_id="evt-approval-01",
            source_type="approval",
            event_type="approval_pending",
            severity="info",
        ),
        make_event(
            event_id="evt-approval-02",
            source_type="approval",
            event_type="approval_granted",
            severity="info",
        ),
    ]
    seed_msg_events(app_server.working_dir, seeded)

    resp = app_server.api_request(
        "GET",
        "/api/console/msg/events",
        timeout=_MSG_HTTP_TIMEOUT,
    )
    assert resp.status_code == 200, app_server.logs_tail()
    events = resp.json().get("events")
    assert isinstance(events, list)
    assert len(events) == 4

    by_id = {event["id"]: event for event in events}
    for seeded_event in seeded:
        returned = by_id.get(seeded_event["id"])
        assert returned is not None, f"missing {seeded_event['id']}"
        assert returned["source_type"] == seeded_event["source_type"]
        assert returned["event_type"] == seeded_event["event_type"]
        assert returned["severity"] == seeded_event["severity"]


@pytest.mark.integration
@pytest.mark.p1
def test_msg_list_events_filter_by_source_type(app_server) -> None:
    """Test purpose:
    - Verify the ``source_type`` query filter actually partitions events
      by category. Console's Msg tabs (定时任务 / 审批) rely on this
      filter; a broken filter shows every event under every tab.

    Test flow:
    1. Seed 2 cron events + 2 approval events.
    2. GET ?source_type=cron — assert exactly the 2 cron events.
    3. GET ?source_type=approval — assert exactly the 2 approval events.

    API endpoints:
    - GET /api/console/msg/events
    """
    seeded = [
        make_event(event_id="evt-cron-01", source_type="cron"),
        make_event(event_id="evt-cron-02", source_type="cron"),
        make_event(event_id="evt-approval-01", source_type="approval"),
        make_event(event_id="evt-approval-02", source_type="approval"),
    ]
    seed_msg_events(app_server.working_dir, seeded)

    cron_resp = app_server.api_request(
        "GET",
        "/api/console/msg/events",
        params={"source_type": "cron"},
        timeout=_MSG_HTTP_TIMEOUT,
    )
    assert cron_resp.status_code == 200, app_server.logs_tail()
    cron_events = cron_resp.json().get("events")
    assert {event["id"] for event in cron_events} == {
        "evt-cron-01",
        "evt-cron-02",
    }
    assert all(event["source_type"] == "cron" for event in cron_events)

    approval_resp = app_server.api_request(
        "GET",
        "/api/console/msg/events",
        params={"source_type": "approval"},
        timeout=_MSG_HTTP_TIMEOUT,
    )
    assert approval_resp.status_code == 200, app_server.logs_tail()
    approval_events = approval_resp.json().get("events")
    assert {event["id"] for event in approval_events} == {
        "evt-approval-01",
        "evt-approval-02",
    }
    assert all(event["source_type"] == "approval" for event in approval_events)


@pytest.mark.integration
@pytest.mark.p2
def test_msg_list_events_unread_only_filter(app_server) -> None:
    """Test purpose:
    - Verify ``unread_only=true`` returns only events with ``read=False``.
      Console's "未读" tab and the unread badge both rely on this path.

    Test flow:
    1. Seed 3 events: 2 unread + 1 already read.
    2. GET ?unread_only=true.
    3. Assert exactly the 2 unread events come back; the read event is
       excluded.

    API endpoints:
    - GET /api/console/msg/events
    """
    seeded = [
        make_event(event_id="evt-unread-01", read=False),
        make_event(event_id="evt-unread-02", read=False),
        make_event(event_id="evt-read-01", read=True),
    ]
    seed_msg_events(app_server.working_dir, seeded)

    resp = app_server.api_request(
        "GET",
        "/api/console/msg/events",
        params={"unread_only": "true"},
        timeout=_MSG_HTTP_TIMEOUT,
    )
    assert resp.status_code == 200, app_server.logs_tail()
    events = resp.json().get("events")
    assert {event["id"] for event in events} == {
        "evt-unread-01",
        "evt-unread-02",
    }
    assert all(event["read"] is False for event in events)


@pytest.mark.integration
@pytest.mark.p1
def test_msg_mark_read_specific_events_returns_updated_count(
    app_server,
) -> None:
    """Test purpose:
    - Verify POST /api/console/msg/read with explicit ``event_ids``
      marks only those events as read and returns the count of events
      that actually flipped from unread to read.

    Test flow:
    1. Seed 3 unread events.
    2. POST /msg/read with body ``{"event_ids": [id_1, id_2]}``.
    3. Assert ``updated`` == 2 in the response.
    4. GET /msg/events and assert id_1/id_2 are now ``read=True`` and
       id_3 is still ``read=False``.

    API endpoints:
    - POST /api/console/msg/read
    - GET /api/console/msg/events
    """
    seeded = [
        make_event(event_id="evt-mark-01", read=False),
        make_event(event_id="evt-mark-02", read=False),
        make_event(event_id="evt-mark-03", read=False),
    ]
    seed_msg_events(app_server.working_dir, seeded)

    mark_resp = app_server.api_request(
        "POST",
        "/api/console/msg/read",
        json={"event_ids": ["evt-mark-01", "evt-mark-02"], "all": False},
        timeout=_MSG_HTTP_TIMEOUT,
    )
    assert mark_resp.status_code == 200, app_server.logs_tail()
    assert mark_resp.json().get("updated") == 2

    list_resp = app_server.api_request(
        "GET",
        "/api/console/msg/events",
        timeout=_MSG_HTTP_TIMEOUT,
    )
    assert list_resp.status_code == 200, app_server.logs_tail()
    read_state = {
        event["id"]: event["read"] for event in list_resp.json()["events"]
    }
    assert read_state == {
        "evt-mark-01": True,
        "evt-mark-02": True,
        "evt-mark-03": False,
    }


@pytest.mark.integration
@pytest.mark.p2
def test_msg_mark_read_all_updates_only_unread(app_server) -> None:
    """Test purpose:
    - Verify POST /msg/read with ``{"all": true}`` returns the count
      of events that actually transitioned — events already in ``read``
      state are NOT counted (otherwise the "全部已读" button would
      inflate its notification toast).

    Test flow:
    1. Seed 4 events: 3 unread + 1 already read.
    2. POST /msg/read with body ``{"all": true}``.
    3. Assert ``updated`` == 3 (not 4 — the already-read event is
       excluded from the count).

    API endpoints:
    - POST /api/console/msg/read
    """
    seeded = [
        make_event(event_id="evt-all-01", read=False),
        make_event(event_id="evt-all-02", read=False),
        make_event(event_id="evt-all-03", read=False),
        make_event(event_id="evt-all-04", read=True),
    ]
    seed_msg_events(app_server.working_dir, seeded)

    resp = app_server.api_request(
        "POST",
        "/api/console/msg/read",
        json={"event_ids": [], "all": True},
        timeout=_MSG_HTTP_TIMEOUT,
    )
    assert resp.status_code == 200, app_server.logs_tail()
    assert resp.json().get("updated") == 3


@pytest.mark.integration
@pytest.mark.p1
def test_msg_delete_event_cleans_orphan_trace(app_server) -> None:
    """Test purpose:
    - Verify DELETE /msg/events/{id} also removes the associated trace
      file when no other msg event references the same ``run_id``.
      Cascade-cleanup keeps trace storage from leaking when users delete
      msg entries.

    Test flow:
    1. Seed one event whose ``payload.run_id`` is ``"run-orphan-01"``.
    2. Seed a trace file at msg_traces/run-orphan-01.json.
    3. DELETE the event; assert ``deleted=True``, ``trace_deleted=True``,
       and ``run_id == "run-orphan-01"`` in the response.
    4. GET /msg/traces/run-orphan-01 — assert 404, confirming the
       trace really got cascaded.

    API endpoints:
    - DELETE /api/console/msg/events/{event_id}
    - GET /api/console/msg/traces/{run_id}
    """
    run_id = "run-orphan-01"
    seeded_event = make_event(
        event_id="evt-delete-with-trace",
        payload={"run_id": run_id},
    )
    seed_msg_events(app_server.working_dir, [seeded_event])
    seed_msg_trace(
        app_server.working_dir,
        run_id,
        {"run_id": run_id, "events": []},
    )

    delete_resp = app_server.api_request(
        "DELETE",
        f"/api/console/msg/events/{seeded_event['id']}",
        timeout=_MSG_HTTP_TIMEOUT,
    )
    assert delete_resp.status_code == 200, app_server.logs_tail()
    payload = delete_resp.json()
    assert payload.get("deleted") is True
    assert payload.get("trace_deleted") is True
    assert payload.get("run_id") == run_id

    trace_resp = app_server.api_request(
        "GET",
        f"/api/console/msg/traces/{run_id}",
        timeout=_MSG_HTTP_TIMEOUT,
    )
    assert trace_resp.status_code == 404, app_server.logs_tail()


@pytest.mark.integration
@pytest.mark.p1
def test_msg_delete_event_preserves_shared_trace(app_server) -> None:
    """Test purpose:
    - Verify DELETE event does NOT cascade-delete the trace when another
      event still references the same ``run_id``. This guards the
      "trace_deleted only when last reference goes" branch in
      msg_store.delete_event; without this case we only test the
      orphan-cleanup direction and a bug that always cascades would
      slip through.

    Test flow:
    1. Seed two events both with ``payload.run_id="run-shared-01"``.
    2. Seed a single trace file at msg_traces/run-shared-01.json.
    3. DELETE the first event. Assert ``deleted=True``,
       ``trace_deleted=False`` (one event still references the run),
       and ``run_id == "run-shared-01"``.
    4. GET /api/console/msg/traces/run-shared-01 — assert 200 (trace
       was preserved).
    5. Confirm via GET /events the second event is still present.

    API endpoints:
    - DELETE /api/console/msg/events/{event_id}
    - GET /api/console/msg/traces/{run_id}
    - GET /api/console/msg/events
    """
    run_id = "run-shared-01"
    keeper_id = "evt-shared-keeper"
    seeded_events = [
        make_event(
            event_id="evt-shared-deleted",
            payload={"run_id": run_id},
        ),
        make_event(
            event_id=keeper_id,
            payload={"run_id": run_id},
        ),
    ]
    seed_msg_events(app_server.working_dir, seeded_events)
    seed_msg_trace(
        app_server.working_dir,
        run_id,
        {"run_id": run_id, "events": []},
    )

    delete_resp = app_server.api_request(
        "DELETE",
        "/api/console/msg/events/evt-shared-deleted",
        timeout=_MSG_HTTP_TIMEOUT,
    )
    assert delete_resp.status_code == 200, app_server.logs_tail()
    payload = delete_resp.json()
    assert payload.get("deleted") is True
    assert payload.get("trace_deleted") is False
    assert payload.get("run_id") == run_id

    trace_resp = app_server.api_request(
        "GET",
        f"/api/console/msg/traces/{run_id}",
        timeout=_MSG_HTTP_TIMEOUT,
    )
    assert trace_resp.status_code == 200, app_server.logs_tail()

    list_resp = app_server.api_request(
        "GET",
        "/api/console/msg/events",
        timeout=_MSG_HTTP_TIMEOUT,
    )
    assert list_resp.status_code == 200, app_server.logs_tail()
    remaining_ids = {event["id"] for event in list_resp.json()["events"]}
    assert remaining_ids == {keeper_id}


@pytest.mark.integration
@pytest.mark.p1
def test_msg_delete_event_returns_404_for_missing(app_server) -> None:
    """Test purpose:
    - Verify DELETE on a non-existent event id returns 404 with the
      expected detail rather than silently succeeding.

    Test flow:
    1. DELETE /api/console/msg/events/<synthetic-missing-id>.
    2. Assert 404 and detail == ``event not found``.

    API endpoints:
    - DELETE /api/console/msg/events/{event_id}
    """
    resp = app_server.api_request(
        "DELETE",
        "/api/console/msg/events/integ-missing-event-id-0001",
        timeout=_MSG_HTTP_TIMEOUT,
    )
    assert resp.status_code == 404, app_server.logs_tail()
    assert resp.json().get("detail") == "event not found"
