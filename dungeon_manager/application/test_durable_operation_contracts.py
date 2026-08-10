from dataclasses import replace

import pytest

from .durable_operation_contracts import (
    CampaignOperationKey,
    CanonicalOperationIdentity,
    DurableOperationContractVersion,
    DurableOperationDiagnostic,
    DurableOperationDiagnosticCode,
    DurableOperationKind,
    DurableOperationLifecycle,
    DurableOperationSubmission,
    DurableReplayDisposition,
    DurableTerminalOutcome,
)


def identity(payload=None):
    return CanonicalOperationIdentity(
        DurableOperationContractVersion.V1,
        CampaignOperationKey(
            DurableOperationContractVersion.V1,
            "vertical-slice-v1",
            "round-operation-1",
        ),
        "player-1",
        DurableOperationKind.RESOLVE_CONTROLLED_ROUND,
        "phase2-m1-v1",
        "nekria",
        {"faces": [18, 4, 17, 6]} if payload is None else payload,
    )


def terminal_outcome():
    return DurableTerminalOutcome(
        {
            "command": {"kind": "command", "value": "command-1"},
            "diagnostic": None,
            "durable_commit": "committed",
            "events": [
                {
                    "event": {"kind": "event", "value": "event-1"},
                    "sequence": 2,
                }
            ],
            "local_publication": "published",
            "mechanical_details": {"outcome": "resolved"},
            "mechanics": "succeeded",
            "operation": {
                "kind": "caller_operation",
                "value": "round-operation-1",
            },
            "projection": "projected",
            "submission": "accepted",
            "synchronization": "synchronized",
            "version": "phase2-m1-v1",
        }
    )


def test_contracts_are_immutable_copied_equal_and_stably_serialized():
    payload = {"faces": [18, 4, 17, 6]}
    first = identity(payload)
    second = identity({"faces": [18, 4, 17, 6]})

    payload["faces"][0] = 1
    assert first == second
    assert first.canonical_json == second.canonical_json
    assert first.fingerprint == second.fingerprint
    assert first.to_dict()["payload"] == {"faces": [18, 4, 17, 6]}
    with pytest.raises(TypeError):
        first.payload["extra"] = True

    restored = CanonicalOperationIdentity.from_canonical_json(
        first.canonical_json
    )
    assert restored == first
    assert terminal_outcome().canonical_json == terminal_outcome().canonical_json


@pytest.mark.parametrize(
    "changed",
    (
        lambda value: replace(value, participant_id="player-2"),
        lambda value: replace(value, actor_id="goblin-1"),
        lambda value: replace(
            value, kind=DurableOperationKind.SELECT_PLAYER_CHARACTER
        ),
        lambda value: replace(value, request_contract_version="other-v1"),
        lambda value: replace(value, payload={"faces": [18, 4, 17, 5]}),
    ),
)
def test_canonical_fingerprint_detects_every_authority_relevant_difference(changed):
    original = identity()
    different = changed(original)
    assert different.canonical_json != original.canonical_json
    assert different.fingerprint != original.fingerprint


def test_public_submission_serialization_is_stable_and_presentation_is_transient():
    original = identity()
    submission = DurableOperationSubmission(
        DurableOperationContractVersion.V1,
        original.key,
        original.kind,
        DurableReplayDisposition.DELEGATED,
        DurableOperationLifecycle.TERMINAL,
        terminal_outcome(),
        transient_presentation={"text": "Transient only."},
    )
    assert submission.to_json() == submission.to_json()
    assert "Transient only." not in submission.terminal_outcome.canonical_json
    assert submission.to_dict()["transient_presentation"] == {
        "text": "Transient only."
    }


def test_unknown_malformed_and_inconsistent_contract_values_fail_closed():
    with pytest.raises((TypeError, ValueError)):
        CampaignOperationKey("phase2-m3-v2", "campaign", "operation")
    with pytest.raises(ValueError):
        identity({"bad": float("nan")})
    with pytest.raises(ValueError):
        DurableOperationSubmission(
            DurableOperationContractVersion.V1,
            identity().key,
            identity().kind,
            DurableReplayDisposition.COLLISION,
            DurableOperationLifecycle.RESERVED,
            terminal_outcome(),
            DurableOperationDiagnostic(
                DurableOperationDiagnosticCode.KEY_COLLISION
            ),
        )
