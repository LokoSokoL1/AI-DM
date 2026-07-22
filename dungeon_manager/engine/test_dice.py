import json
from dataclasses import FrozenInstanceError

import pytest

from .dice import (
    AutomaticFaceSource,
    DiceResolutionStatus,
    DiceRollMode,
    DiceRollProvenance,
    DiceRollRequest,
    SequenceFaceSource,
    resolve_dice_roll,
)


class RaisingSource:
    def __init__(self):
        self.calls = 0

    def next_face(self, minimum, maximum):
        self.calls += 1
        raise RuntimeError("private random implementation failure")


class ValuesSource:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = []

    def next_face(self, minimum, maximum):
        self.calls.append((minimum, maximum))
        return next(self.values)


def request(**overrides):
    values = {"roll_id": "roll-001", "dice_count": 1, "sides": 20, "modifier": 0}
    values.update(overrides)
    return DiceRollRequest(**values)


def test_valid_d20_and_d8_requests_are_immutable_and_defensive():
    d20 = request(modifier=5)
    d8 = request(roll_id="damage-d8", sides=8)

    assert d20.to_dict() == {"dice_count": 1, "modifier": 5, "roll_id": "roll-001", "sides": 20}
    assert d8.sides == 8
    with pytest.raises(FrozenInstanceError):
        d20.sides = 8
    serialized = d20.to_dict()
    serialized["sides"] = 1
    assert d20.sides == 20


@pytest.mark.parametrize(
    "values",
    [
        {"roll_id": " ", "dice_count": 1, "sides": 20, "modifier": 0},
        {"roll_id": "ok", "dice_count": 0, "sides": 20, "modifier": 0},
        {"roll_id": "ok", "dice_count": True, "sides": 20, "modifier": 0},
        {"roll_id": "ok", "dice_count": 1, "sides": 1, "modifier": 0},
        {"roll_id": "ok", "dice_count": 1, "sides": False, "modifier": 0},
        {"roll_id": "ok", "dice_count": 1, "sides": 20, "modifier": True},
        {"roll_id": "ok", "dice_count": 1, "sides": 20, "modifier": 1001},
    ],
)
def test_request_rejects_invalid_or_boolean_values(values):
    with pytest.raises(ValueError):
        DiceRollRequest(**values)


def test_manual_missing_faces_requires_input_without_using_randomness():
    source = RaisingSource()

    result = resolve_dice_roll(request(), DiceRollMode.MANUAL, automatic_source=source)

    assert result.status is DiceResolutionStatus.INPUT_REQUIRED
    assert result.roll is None
    assert source.calls == 0
    assert result.to_dict()["roll"] is None


@pytest.mark.parametrize(
    ("dice_request", "faces", "expected_subtotal", "expected_total"),
    [
        (request(modifier=5), [14], 14, 19),
        (request(roll_id="d8", sides=8, modifier=-2), [7], 7, 5),
        (request(roll_id="multi", dice_count=3, sides=8, modifier=2), [1, 8, 4], 13, 15),
    ],
)
def test_manual_roll_calculates_from_ordered_natural_faces(dice_request, faces, expected_subtotal, expected_total):
    result = resolve_dice_roll(dice_request, DiceRollMode.MANUAL, manual_faces=faces)

    assert result.status is DiceResolutionStatus.SUCCESS
    assert result.roll.natural_faces == tuple(faces)
    assert result.roll.subtotal == expected_subtotal
    assert result.roll.total == expected_total
    assert result.roll.provenance is DiceRollProvenance.HUMAN_MANUAL


@pytest.mark.parametrize("faces", [[], [1, 2], [0], [21], ["14"], [True]])
def test_manual_faces_must_exactly_match_requested_valid_die_faces(faces):
    result = resolve_dice_roll(request(), DiceRollMode.MANUAL, manual_faces=faces)

    assert result.status is DiceResolutionStatus.INVALID_INPUT
    assert result.roll is None


def test_manual_identical_input_produces_equal_complete_results():
    dice_request = request(roll_id="repeat", dice_count=2, sides=8, modifier=-1)

    first = resolve_dice_roll(dice_request, DiceRollMode.MANUAL, manual_faces=[3, 8])
    second = resolve_dice_roll(dice_request, DiceRollMode.MANUAL, manual_faces=[3, 8])

    assert first == second
    assert first.roll == second.roll


def test_automatic_roll_uses_injected_source_once_per_die_and_inclusive_bounds():
    source = SequenceFaceSource([1, 20])
    dice_request = request(dice_count=2, modifier=3)

    result = resolve_dice_roll(dice_request, DiceRollMode.AUTOMATIC, automatic_source=source)

    assert result.status is DiceResolutionStatus.SUCCESS
    assert result.roll.natural_faces == (1, 20)
    assert result.roll.total == 24
    assert result.roll.provenance is DiceRollProvenance.ENGINE_AUTOMATIC
    assert source.calls == [(1, 20), (1, 20)]


def test_automatic_mode_rejects_manual_faces_and_invalid_source_without_calls():
    source = RaisingSource()

    conflict = resolve_dice_roll(request(), DiceRollMode.AUTOMATIC, manual_faces=[14], automatic_source=source)
    invalid = resolve_dice_roll(request(), DiceRollMode.AUTOMATIC, automatic_source=object())

    assert conflict.status is DiceResolutionStatus.INVALID_MODE
    assert invalid.status is DiceResolutionStatus.RANDOMNESS_FAILURE
    assert conflict.roll is None and invalid.roll is None
    assert source.calls == 0


@pytest.mark.parametrize("values", [[True], [0], [21]])
def test_invalid_automatic_values_fail_without_a_partial_roll(values):
    result = resolve_dice_roll(request(), DiceRollMode.AUTOMATIC, automatic_source=ValuesSource(values))

    assert result.status is DiceResolutionStatus.RANDOMNESS_FAILURE
    assert result.roll is None


def test_automatic_exception_has_no_retry_or_source_details_in_safe_serialization():
    source = RaisingSource()

    result = resolve_dice_roll(request(dice_count=2), DiceRollMode.AUTOMATIC, automatic_source=source)

    assert result.status is DiceResolutionStatus.RANDOMNESS_FAILURE
    assert result.roll is None
    assert source.calls == 1
    serialized = json.dumps(result.to_dict())
    assert "private random" not in serialized
    assert "RaisingSource" not in serialized


def test_later_automatic_failure_never_exposes_the_earlier_face_as_a_partial_roll():
    source = ValuesSource([6])

    result = resolve_dice_roll(request(dice_count=2, sides=8), DiceRollMode.AUTOMATIC, automatic_source=source)

    assert result.status is DiceResolutionStatus.RANDOMNESS_FAILURE
    assert result.roll is None
    assert source.calls == [(1, 8), (1, 8)]


def test_same_authoritative_faces_have_cross_mode_calculation_equivalence():
    dice_request = request(roll_id="equivalent", dice_count=2, sides=8, modifier=4)

    manual = resolve_dice_roll(dice_request, DiceRollMode.MANUAL, manual_faces=[2, 7])
    automatic = resolve_dice_roll(dice_request, DiceRollMode.AUTOMATIC, automatic_source=SequenceFaceSource([2, 7]))

    assert manual.roll.natural_faces == automatic.roll.natural_faces
    assert manual.roll.subtotal == automatic.roll.subtotal
    assert manual.roll.total == automatic.roll.total
    assert manual.roll.mode is not automatic.roll.mode
    assert manual.roll.provenance is not automatic.roll.provenance


def test_invalid_request_or_mode_is_controlled_and_never_creates_domain_events():
    invalid_request = resolve_dice_roll(object(), DiceRollMode.MANUAL)
    invalid_mode = resolve_dice_roll(request(), "manual")

    assert invalid_request.status is DiceResolutionStatus.INVALID_REQUEST
    assert invalid_mode.status is DiceResolutionStatus.INVALID_MODE
    assert invalid_request.roll is None and invalid_mode.roll is None
    assert "event" not in json.dumps(invalid_request.to_dict()).lower()
