import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from app.rules.engine import run_rules
from app.rules.enums import ExecutionStatus
from app.rules.registry import register_action
from app.workflow import engine as workflow_engine

CALLS: list[dict] = []


class EchoParams(BaseModel):
    message: str


@register_action("test_echo", params=EchoParams, is_async=False)
async def _echo(ctx, p: EchoParams) -> None:
    CALLS.append({"message": p.message, "event": ctx.event})


class FakeDB:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


def make_request(rules: list[dict]):
    return SimpleNamespace(
        id=uuid.uuid4(),
        request_no="LV-0001",
        status=SimpleNamespace(value="in_progress"),
        form=SimpleNamespace(code="LEAVE_REQUEST"),
        requester_id=uuid.uuid4(),
        requester=SimpleNamespace(staff_id="S001", full_name="Sokha Lim", email="s@example.com"),
        workflow_snapshot={"rules": rules},
    )


def make_rule(**overrides) -> dict:
    rule = {
        "id": str(uuid.uuid4()),
        "name": "Long leave",
        "event": "approved",
        "step_no": None,
        "conditions": [{"field": "days", "op": "gt", "value": 3}],
        "actions": [{"type": "test_echo",
                     "params": {"message": "{{ requester.name }}: {{ data.days }} days"}}],
    }
    return rule | overrides


async def _run(request, db, *, event="approved", step_no=None, data=None):
    await run_rules(db, event, request, event_id=uuid.uuid4(), step_no=step_no,
                    actor=None, data=data if data is not None else {"days": 5})


@pytest.fixture(autouse=True)
def _clear_calls():
    CALLS.clear()


async def test_matching_rule_runs_sync_action_with_rendered_params():
    db = FakeDB()
    await _run(make_request([make_rule()]), db)

    assert CALLS == [{"message": "Sokha Lim: 5 days", "event": "approved"}]
    [exe] = db.added
    assert exe.status == ExecutionStatus.SUCCEEDED
    assert exe.params == {"message": "Sokha Lim: 5 days"}


async def test_condition_not_met_skips_rule():
    db = FakeDB()
    await _run(make_request([make_rule()]), db, data={"days": 2})

    assert CALLS == []
    assert db.added == []


async def test_other_event_or_step_is_ignored():
    db = FakeDB()
    request = make_request([make_rule(event="step_approved", step_no=2)])

    await _run(request, db, event="approved")
    await _run(request, db, event="step_approved", step_no=1)
    assert CALLS == []

    await _run(request, db, event="step_approved", step_no=2)
    assert len(CALLS) == 1


async def test_start_snapshots_rules_under_key_read_by_engine():
    """The workflow snapshot and the rule engine must agree on the key."""
    rule = make_rule()
    workflow = SimpleNamespace(id=uuid.uuid4(), completed_status="approved", steps=[])
    db = SimpleNamespace(scalar=AsyncMock(return_value=workflow))
    request = SimpleNamespace(form_code="LEAVE_REQUEST", workflow_snapshot=None)

    with patch.object(workflow_engine, "_snapshot_rules", AsyncMock(return_value=[rule])), \
         patch.object(workflow_engine, "_open_step", AsyncMock()):
        await workflow_engine.start(db, request, actor=None)

    assert request.workflow_snapshot["rules"] == [rule]