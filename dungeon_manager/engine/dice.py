"""Provider-neutral deterministic resolution from authoritative die faces.

This foundation intentionally knows no campaign, combat, persistence, or command
semantics.  It resolves an already-defined request only.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

from ._json import validate_trimmed_identifier


MIN_DICE_COUNT = 1
MAX_DICE_COUNT = 20
MIN_DIE_SIDES = 2
MAX_DIE_SIDES = 100
MIN_MODIFIER = -1000
MAX_MODIFIER = 1000


class DiceRollMode(str, Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class DiceRollProvenance(str, Enum):
    HUMAN_MANUAL = "human_manual"
    ENGINE_AUTOMATIC = "engine_automatic"


class DiceResolutionStatus(str, Enum):
    SUCCESS = "success"
    INPUT_REQUIRED = "input_required"
    INVALID_INPUT = "invalid_input"
    INVALID_REQUEST = "invalid_request"
    INVALID_MODE = "invalid_mode"
    RANDOMNESS_FAILURE = "randomness_failure"


def _validate_integer(value: Any, label: str, minimum: int, maximum: int) -> None:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < minimum
        or value > maximum
    ):
        raise ValueError(f"{label} is outside the supported range.")


@dataclass(frozen=True)
class DiceRollRequest:
    """One caller-identified dice specification with deliberately narrow bounds."""

    roll_id: str
    dice_count: int
    sides: int
    modifier: int = 0

    def __post_init__(self) -> None:
        validate_trimmed_identifier(self.roll_id, "Dice roll ID")
        _validate_integer(self.dice_count, "Dice count", MIN_DICE_COUNT, MAX_DICE_COUNT)
        _validate_integer(self.sides, "Die sides", MIN_DIE_SIDES, MAX_DIE_SIDES)
        _validate_integer(self.modifier, "Dice modifier", MIN_MODIFIER, MAX_MODIFIER)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dice_count": self.dice_count,
            "modifier": self.modifier,
            "roll_id": self.roll_id,
            "sides": self.sides,
        }


@runtime_checkable
class AutomaticFaceSource(Protocol):
    """The one-face-at-a-time automatic randomness dependency."""

    def next_face(self, minimum: int, maximum: int) -> int:
        ...


class SystemRandomFaceSource:
    """Production automatic source using an isolated SystemRandom instance."""

    def __init__(self) -> None:
        self.__random = random.SystemRandom()

    def next_face(self, minimum: int, maximum: int) -> int:
        return self.__random.randint(minimum, maximum)


class SequenceFaceSource:
    """Small deterministic injected source for tests and controlled callers."""

    def __init__(self, faces: Sequence[Any]) -> None:
        if isinstance(faces, (str, bytes, bytearray)) or not isinstance(faces, Sequence):
            raise ValueError("Sequence faces must be an ordered collection.")
        self.__faces = tuple(faces)
        self.__next_index = 0
        self.calls: list[tuple[int, int]] = []

    def next_face(self, minimum: int, maximum: int) -> int:
        self.calls.append((minimum, maximum))
        if self.__next_index >= len(self.__faces):
            raise RuntimeError("No configured automatic face remains.")
        value = self.__faces[self.__next_index]
        self.__next_index += 1
        return value


@dataclass(frozen=True)
class DiceRoll:
    """One complete immutable resolution, suitable for later durable inclusion."""

    request: DiceRollRequest
    mode: DiceRollMode
    provenance: DiceRollProvenance
    natural_faces: tuple[int, ...]
    subtotal: int
    total: int

    def __post_init__(self) -> None:
        if not isinstance(self.request, DiceRollRequest):
            raise ValueError("Dice roll requires a valid request.")
        if not isinstance(self.mode, DiceRollMode) or not isinstance(self.provenance, DiceRollProvenance):
            raise ValueError("Dice roll mode and provenance must be typed.")
        expected_provenance = {
            DiceRollMode.MANUAL: DiceRollProvenance.HUMAN_MANUAL,
            DiceRollMode.AUTOMATIC: DiceRollProvenance.ENGINE_AUTOMATIC,
        }[self.mode]
        if self.provenance is not expected_provenance:
            raise ValueError("Dice roll provenance must match its mode.")
        if not isinstance(self.natural_faces, tuple) or len(self.natural_faces) != self.request.dice_count:
            raise ValueError("Dice roll faces must exactly match the request.")
        for face in self.natural_faces:
            _validate_integer(face, "Natural face", 1, self.request.sides)
        expected_subtotal = sum(self.natural_faces)
        if self.subtotal != expected_subtotal or self.total != expected_subtotal + self.request.modifier:
            raise ValueError("Dice roll totals must be calculated from natural faces.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "dice_count": self.request.dice_count,
            "mode": self.mode.value,
            "modifier": self.request.modifier,
            "natural_faces": list(self.natural_faces),
            "provenance": self.provenance.value,
            "roll_id": self.request.roll_id,
            "sides": self.request.sides,
            "subtotal": self.subtotal,
            "total": self.total,
        }


@dataclass(frozen=True)
class DiceResolutionResult:
    """Safe complete or failed dice resolution without source internals."""

    status: DiceResolutionStatus
    request: Optional[DiceRollRequest] = None
    mode: Optional[DiceRollMode] = None
    roll: Optional[DiceRoll] = None
    reason_code: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, DiceResolutionStatus):
            raise ValueError("Dice resolution status must be typed.")
        if self.request is not None and not isinstance(self.request, DiceRollRequest):
            raise ValueError("Dice resolution request must be typed.")
        if self.mode is not None and not isinstance(self.mode, DiceRollMode):
            raise ValueError("Dice resolution mode must be typed.")
        if self.status is DiceResolutionStatus.SUCCESS:
            if not isinstance(self.roll, DiceRoll) or self.request is not self.roll.request or self.mode is not self.roll.mode or self.reason_code is not None or self.error is not None:
                raise ValueError("Successful dice resolution requires exactly one complete roll.")
            return
        if self.roll is not None:
            raise ValueError("Failed dice resolution cannot expose a partial roll.")
        validate_trimmed_identifier(self.reason_code, "Dice resolution reason code")
        validate_trimmed_identifier(self.error, "Dice resolution error")
        if self.status is DiceResolutionStatus.INPUT_REQUIRED:
            if self.request is None or self.mode is not DiceRollMode.MANUAL:
                raise ValueError("Manual input-required resolution needs a manual request.")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "error": self.error,
            "mode": None if self.mode is None else self.mode.value,
            "reason_code": self.reason_code,
            "status": self.status.value,
        }
        if self.request is not None:
            data.update(self.request.to_dict())
        else:
            data.update({"dice_count": None, "modifier": None, "roll_id": None, "sides": None})
        data["roll"] = None if self.roll is None else self.roll.to_dict()
        return data


def _failure(status: DiceResolutionStatus, reason_code: str, error: str, request: Optional[DiceRollRequest] = None, mode: Optional[DiceRollMode] = None) -> DiceResolutionResult:
    return DiceResolutionResult(status, request, mode, reason_code=reason_code, error=error)


def _validated_faces(faces: Any, request: DiceRollRequest) -> Optional[tuple[int, ...]]:
    if isinstance(faces, (str, bytes, bytearray)) or not isinstance(faces, Sequence):
        return None
    values = tuple(faces)
    if len(values) != request.dice_count:
        return None
    try:
        for face in values:
            _validate_integer(face, "Natural face", 1, request.sides)
    except ValueError:
        return None
    return values


def _completed(request: DiceRollRequest, mode: DiceRollMode, faces: tuple[int, ...]) -> DiceResolutionResult:
    provenance = {
        DiceRollMode.MANUAL: DiceRollProvenance.HUMAN_MANUAL,
        DiceRollMode.AUTOMATIC: DiceRollProvenance.ENGINE_AUTOMATIC,
    }[mode]
    subtotal = sum(faces)
    roll = DiceRoll(request, mode, provenance, faces, subtotal, subtotal + request.modifier)
    return DiceResolutionResult(DiceResolutionStatus.SUCCESS, request, mode, roll)


def resolve_dice_roll(request: Any, mode: Any, *, manual_faces: Any = None, automatic_source: Any = None) -> DiceResolutionResult:
    """Resolve one request once without persistence, retries, or side effects."""
    if not isinstance(request, DiceRollRequest):
        return _failure(DiceResolutionStatus.INVALID_REQUEST, "invalid_request", "The dice roll request is invalid.")
    if not isinstance(mode, DiceRollMode):
        return _failure(DiceResolutionStatus.INVALID_MODE, "invalid_mode", "The dice roll mode is invalid.", request)
    if mode is DiceRollMode.MANUAL:
        if manual_faces is None:
            return _failure(DiceResolutionStatus.INPUT_REQUIRED, "manual_faces_required", "Natural face values are required.", request, mode)
        faces = _validated_faces(manual_faces, request)
        if faces is None:
            return _failure(DiceResolutionStatus.INVALID_INPUT, "invalid_manual_faces", "The supplied natural face values are invalid.", request, mode)
        return _completed(request, mode, faces)
    if manual_faces is not None:
        return _failure(DiceResolutionStatus.INVALID_MODE, "manual_faces_not_allowed", "Manual faces are not allowed for automatic rolls.", request, mode)
    if not isinstance(automatic_source, AutomaticFaceSource):
        return _failure(DiceResolutionStatus.RANDOMNESS_FAILURE, "invalid_automatic_source", "Automatic roll generation failed safely.", request, mode)
    faces: list[int] = []
    for _ in range(request.dice_count):
        try:
            face = automatic_source.next_face(1, request.sides)
            _validate_integer(face, "Automatic natural face", 1, request.sides)
        except Exception:
            return _failure(DiceResolutionStatus.RANDOMNESS_FAILURE, "automatic_face_unavailable", "Automatic roll generation failed safely.", request, mode)
        faces.append(face)
    return _completed(request, mode, tuple(faces))
