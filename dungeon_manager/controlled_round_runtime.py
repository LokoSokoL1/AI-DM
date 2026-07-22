"""Command/pipeline composition for the one durable controlled combat round."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from threading import local
from typing import Any, Mapping, Optional

from dungeon_manager.campaign_runtime import CampaignRuntime, NEKRIA_ID
from dungeon_manager.combat_runtime import ControlledCombatDomain
from dungeon_manager.engine.controlled_round import (
    CONTROLLED_ROUND_COMMAND, CONTROLLED_ROUND_EVENT, CONTROLLED_ROUND_SCHEMA_VERSION,
    ControlledRoundResolution, ControlledRoundStatus, resolve_controlled_round,
)
from dungeon_manager.engine.dice import AutomaticFaceSource, DiceRollMode
from dungeon_manager.engine.game_event import GameEvent
from dungeon_manager.engine.command import CommandProvenance, CommandSource, GameCommand
from dungeon_manager.engine.result import GameResult


class ControlledRoundRuntimeStatus(str, Enum):
    SUCCESS = "success"
    INITIATIVE_INPUT_REQUIRED = "initiative_input_required"
    ATTACK_INPUT_REQUIRED = "attack_input_required"
    DAMAGE_INPUT_REQUIRED = "damage_input_required"
    INVALID_INPUT = "invalid_input"
    INVALID_MODE = "invalid_mode"
    DICE_FAILURE = "dice_failure"
    ALREADY_RESOLVED = "already_resolved"
    PUBLICATION_FAILURE = "publication_failure"


@dataclass(frozen=True)
class ControlledRoundRuntimeResult:
    status: ControlledRoundRuntimeStatus
    pipeline_result: Any
    details: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"details": dict(self.details), "status": self.status.value}


class ControlledRoundRuntime:
    """One narrow command handler bound to one validated combat domain."""

    def __init__(self, runtime: CampaignRuntime, domain: ControlledCombatDomain) -> None:
        if not isinstance(runtime, CampaignRuntime) or not isinstance(domain, ControlledCombatDomain):
            raise ValueError("Controlled round runtime requires runtime and domain.")
        self._runtime = runtime
        self._domain = domain
        self._context = local()
        runtime.game_engine.register_handler(CONTROLLED_ROUND_COMMAND, self._handle)

    def resolve(self, *, command_id: str, event_id: str, occurred_at: datetime, mode: DiceRollMode, roll_ids: Mapping[str, str], manual_faces: Mapping[str, Any], automatic_source: Optional[AutomaticFaceSource] = None, initiator_id: str = "player") -> ControlledRoundRuntimeResult:
        payload = {
            "attacker_id": NEKRIA_ID,
            "campaign_id": self._domain.definition.campaign_id,
            "encounter_id": self._domain.definition.scene_id,
            "event_id": event_id,
            "manual_faces": dict(manual_faces),
            "mode": mode.value if isinstance(mode, DiceRollMode) else mode,
            "occurred_at": occurred_at.isoformat() if isinstance(occurred_at, datetime) else occurred_at,
            "roll_ids": dict(roll_ids),
            "scene_id": self._domain.definition.scene_id,
            "target_id": "goblin-1",
            "attack_id": "nekria-rapier",
        }
        command = GameCommand(CONTROLLED_ROUND_COMMAND, CommandProvenance(CommandSource.HUMAN, initiator_id), payload, NEKRIA_ID, command_id)
        self._context.automatic_source = automatic_source
        try:
            pipeline_result = self._runtime.pipeline.dispatch(command)
        finally:
            self._context.automatic_source = None
        game_result = None if pipeline_result.policy_gated_result is None else pipeline_result.policy_gated_result.game_result
        output = {} if game_result is None or game_result.output is None else dict(game_result.output)
        outcome = output.get("outcome")
        status = {
            "resolved": ControlledRoundRuntimeStatus.SUCCESS,
            "nekria_initiative_input_required": ControlledRoundRuntimeStatus.INITIATIVE_INPUT_REQUIRED,
            "goblin_initiative_input_required": ControlledRoundRuntimeStatus.INITIATIVE_INPUT_REQUIRED,
            "attack_input_required": ControlledRoundRuntimeStatus.ATTACK_INPUT_REQUIRED,
            "damage_input_required": ControlledRoundRuntimeStatus.DAMAGE_INPUT_REQUIRED,
            "already_resolved": ControlledRoundRuntimeStatus.ALREADY_RESOLVED,
            "invalid_mode": ControlledRoundRuntimeStatus.INVALID_MODE,
            "dice_failure": ControlledRoundRuntimeStatus.DICE_FAILURE,
        }.get(outcome, ControlledRoundRuntimeStatus.INVALID_INPUT)
        if pipeline_result.durable_publication.status.value not in {"not_applicable", "no_events", "committed_synchronized"}:
            status = ControlledRoundRuntimeStatus.PUBLICATION_FAILURE
        return ControlledRoundRuntimeResult(status, pipeline_result, output)

    def _handle(self, command: GameCommand) -> GameResult:
        payload = command.payload
        expected = {"attacker_id", "campaign_id", "encounter_id", "event_id", "manual_faces", "mode", "occurred_at", "roll_ids", "scene_id", "target_id", "attack_id"}
        if set(payload) != expected or payload["campaign_id"] != self._domain.definition.campaign_id or payload["scene_id"] != self._domain.definition.scene_id or payload["encounter_id"] != self._domain.definition.scene_id or payload["attacker_id"] != NEKRIA_ID or payload["target_id"] != "goblin-1" or payload["attack_id"] != "nekria-rapier":
            return GameResult.success(command.command_id, {"outcome": "invalid_input"})
        if "controlled_combat" in self._runtime.state_holder.snapshot.data:
            return GameResult.success(command.command_id, {"outcome": "already_resolved"})
        try:
            resolution = resolve_controlled_round(self._domain.definition, mode=DiceRollMode(payload["mode"]), roll_ids=payload["roll_ids"], manual_faces=payload["manual_faces"], automatic_source=getattr(self._context, "automatic_source", None))
        except Exception:
            return GameResult.success(command.command_id, {"outcome": "invalid_input"})
        if resolution.status is not ControlledRoundStatus.RESOLVED:
            return GameResult.success(command.command_id, self._output_for(resolution))
        try:
            event = GameEvent(CONTROLLED_ROUND_EVENT, command.provenance, resolution.payload, command.command_id, NEKRIA_ID, CONTROLLED_ROUND_SCHEMA_VERSION, datetime.fromisoformat(payload["occurred_at"]), payload["event_id"])
        except (TypeError, ValueError):
            return GameResult.success(command.command_id, {"outcome": "invalid_input"})
        return GameResult.success(command.command_id, {"outcome": "resolved"}, (event,))

    @staticmethod
    def _output_for(resolution: ControlledRoundResolution) -> dict[str, Any]:
        return {"outcome": resolution.status.value, **resolution.to_dict()}
