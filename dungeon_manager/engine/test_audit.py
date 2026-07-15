import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from . import audit as audit_module
from .audit import AuditStage, CommandAuditRecord
from .command import CommandProvenance, CommandSource


FIXED_UTC = datetime(2026, 7, 15, 10, 11, 12, 345678, timezone.utc)


def provenance(
    source=CommandSource.HUMAN,
    initiator_id="human-gm",
):
    return CommandProvenance(source=source, initiator_id=initiator_id)


def make_record(**overrides):
    values = {
        "audit_record_id": "audit-test-001",
        "command_id": "command-audit-001",
        "command_type": "world.inspect",
        "stage": AuditStage.POLICY_EVALUATED,
        "outcome": "automatic",
        "provenance": provenance(),
        "recorded_at": FIXED_UTC,
    }
    values.update(overrides)
    return CommandAuditRecord(**values)


def test_audit_record_generates_unique_ids_and_accepts_explicit_id():
    values = {
        "command_id": "command-audit-001",
        "command_type": "world.inspect",
        "stage": AuditStage.POLICY_EVALUATED,
        "outcome": "automatic",
        "provenance": provenance(),
        "recorded_at": FIXED_UTC,
    }
    first = CommandAuditRecord(**values)
    second = CommandAuditRecord(**values)
    explicit = make_record(audit_record_id="audit-deterministic-001")

    assert first.audit_record_id
    assert first.audit_record_id.strip() == first.audit_record_id
    assert first.audit_record_id != second.audit_record_id
    assert explicit.audit_record_id == "audit-deterministic-001"


def test_generated_audit_time_uses_isolated_injectable_clock(monkeypatch):
    generated = datetime(
        2026,
        7,
        15,
        6,
        11,
        12,
        345678,
        timezone(timedelta(hours=-4)),
    )
    monkeypatch.setattr(audit_module, "utc_now", lambda: generated)

    record = CommandAuditRecord(
        command_id="command-audit-001",
        command_type="world.inspect",
        stage=AuditStage.GATE_RESOLVED,
        outcome="ready",
        provenance=provenance(),
    )

    assert record.recorded_at == FIXED_UTC
    assert record.recorded_at.tzinfo is timezone.utc


def test_explicit_audit_time_is_normalized_and_serialized_as_utc():
    local_time = datetime(
        2026,
        7,
        15,
        12,
        11,
        12,
        345678,
        timezone(timedelta(hours=2)),
    )

    record = make_record(recorded_at=local_time)

    assert record.recorded_at == FIXED_UTC
    assert record.recorded_at.tzinfo is timezone.utc
    assert record.to_dict()["recorded_at"] == "2026-07-15T10:11:12.345678Z"


@pytest.mark.parametrize(
    "timestamp",
    [datetime(2026, 7, 15, 10, 11, 12), "malformed", None],
    ids=["naive", "string", "none"],
)
def test_naive_or_malformed_audit_timestamps_are_rejected(timestamp):
    with pytest.raises(ValueError, match="recording time"):
        make_record(recorded_at=timestamp)


def test_every_audit_stage_is_typed_and_serializes_exactly():
    assert {stage.value for stage in AuditStage} == {
        "command_proposed",
        "policy_evaluated",
        "approval_evaluated",
        "approval_recorded",
        "gate_resolved",
        "dispatch_blocked",
        "dispatch_attempted",
        "dispatch_completed",
        "coordinator_failure",
    }

    for stage in AuditStage:
        record = make_record(stage=stage)
        assert record.stage is stage
        assert record.to_dict()["stage"] == stage.value


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("audit_record_id", " ", "Audit record ID"),
        ("command_id", " command ", "Audit command ID"),
        ("command_type", "", "Audit command type"),
        ("stage", "policy_evaluated", "Audit stage"),
        ("outcome", " ", "Audit outcome"),
        ("provenance", "human", "provenance"),
        ("actor_id", " actor ", "actor ID"),
    ],
)
def test_invalid_audit_structures_are_rejected(field, value, message):
    with pytest.raises(ValueError, match=message):
        make_record(**{field: value})


@pytest.mark.parametrize(
    "details",
    [
        ["not", "an", "object"],
        {1: "non-string key"},
        {"unsupported": object()},
        {"not_finite": float("nan")},
    ],
    ids=["non-object", "non-string-key", "unsupported", "not-finite"],
)
def test_unsafe_or_non_json_audit_detail_structures_are_rejected(details):
    with pytest.raises(ValueError, match="Audit details"):
        make_record(details=details)


def test_audit_details_are_optional_deeply_immutable_and_defensive():
    assert make_record().details is None
    original = {
        "decision": {
            "reason_code": "exact_rule",
            "checks": ["capability", {"matched": True}],
        }
    }
    record = make_record(details=original)

    original["decision"]["checks"].append("invented")

    assert record.details["decision"]["checks"] == (
        "capability",
        {"matched": True},
    )
    with pytest.raises(TypeError):
        record.details["decision"]["checks"][1]["matched"] = False
    with pytest.raises(FrozenInstanceError):
        record.outcome = "changed"


def test_audit_preserves_initiator_provenance_and_optional_actor_identity():
    record = make_record(
        provenance=provenance(CommandSource.AI, "local-model"),
        actor_id="npc-guard-17",
    )

    assert record.provenance.source is CommandSource.AI
    assert record.provenance.initiator_id == "local-model"
    assert record.actor_id == "npc-guard-17"


def test_audit_serialization_is_json_compatible_and_independent():
    record = make_record(
        details={"gate": {"status": "ready", "notes": [None]}},
        actor_id="character-1",
    )

    serialized = record.to_dict()
    serialized["details"]["gate"]["status"] = "changed"
    serialized["provenance"]["initiator_id"] = "changed"

    fresh = record.to_dict()
    assert fresh["details"]["gate"]["status"] == "ready"
    assert fresh["provenance"]["initiator_id"] == "human-gm"
    assert json.loads(json.dumps(fresh, allow_nan=False)) == fresh
