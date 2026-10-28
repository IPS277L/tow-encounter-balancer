"""Closed M8 journal vocabulary; existing bound results retain all evidence."""
from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from towr.domain.npc_broken_recover_models import NpcBrokenRecoverResult
from towr.domain.npc_broken_run_models import NpcBrokenRunResult
from towr.domain.npc_magic_scene_models import NpcMagicSceneKey, _identifier, _ids, _ordered
from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionResult
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingState
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_dead_champion_models import NpcRosterDeadChampionExclusionResult
from towr.domain.npc_roster_minion_attack_models import NpcRosterMinionAttackResult
from towr.domain.npc_roster_minion_defeat_models import NpcRosterMinionDefeatResult
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartResult, NpcRosterRoundAdvanceResult
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndResult
from towr.domain.resolution_models import CowardlyFlightMovementCompletion


NpcMagicStepResult: TypeAlias = (
    NpcRosterTurnStartResult | NpcRosterRoundAdvanceResult | NpcRosterCastingResult
    | NpcRosterCastingCompletionResult | NpcRosterChampionAttackResult | NpcRosterMinionAttackResult
    | NpcRosterMinionDefeatResult | NpcRosterDeadChampionExclusionResult
    | NpcBrokenRecoverResult | NpcBrokenRunResult | NpcWoundTurnEndResult
)
_RESULT_TYPES = (
    NpcRosterTurnStartResult, NpcRosterRoundAdvanceResult, NpcRosterCastingResult,
    NpcRosterCastingCompletionResult, NpcRosterChampionAttackResult, NpcRosterMinionAttackResult,
    NpcRosterMinionDefeatResult, NpcRosterDeadChampionExclusionResult,
    NpcBrokenRecoverResult, NpcBrokenRunResult, NpcWoundTurnEndResult,
)


@dataclass(frozen=True, slots=True)
class NpcMagicStep:
    result: NpcMagicStepResult

    def __post_init__(self) -> None:
        if type(self.result) not in _RESULT_TYPES:
            raise TypeError('magic step requires a supported full-owner bound result')

    @property
    def before(self) -> NpcRosterCastingState:
        return self.result.source.state

    @property
    def after(self) -> NpcRosterCastingState:
        return self.result.state

    @property
    def id(self) -> str:
        result = self.result
        if isinstance(result, NpcRosterCastingResult):
            return result.source.casting.id
        if isinstance(result, NpcRosterCastingCompletionResult):
            return result.source.completion.pending.source.id + ':completion'
        if isinstance(result, (NpcRosterChampionAttackResult, NpcRosterMinionAttackResult)):
            return result.source.attack.execution.id
        return result.source.id

    @property
    def actor_id(self) -> str | None:
        if isinstance(self.result, NpcRosterRoundAdvanceResult):
            return None
        if isinstance(self.result, NpcRosterTurnStartResult):
            return self.result.source.actor_id
        return self.before.round_state.active_turn.actor_id


class NpcMagicScenarioOutcome(str, Enum):
    OBJECTIVE_ACHIEVED = 'objective_achieved'
    PERSPECTIVE_DEFEATED = 'perspective_defeated'
    ROUND_LIMIT_REACHED = 'round_limit_reached'
    UNSUPPORTED_PATH = 'unsupported_path'


class NpcMagicPhase(str, Enum):
    SCHEDULING = 'scheduling'
    ACTION = 'action'
    CONTINUATION = 'continuation'
    END_TURN = 'end_turn'


class NpcMagicUnsupportedReason(str, Enum):
    MISSING_SCENE = 'missing_scene'
    MISSING_ROUTE = 'missing_route'
    NO_LEGAL_TARGET = 'no_legal_target'
    BROKEN_ROUTE = 'unsupported_broken_route'
    ACTOR_INJURY = 'unsupported_actor_injury'
    TARGET_INJURY = 'unsupported_target_injury'
    WOUND_EFFECT = 'pending_wound_effect'
    ATTACK_GIVE_GROUND = 'attack_give_ground'
    MISCAST_PREPARATION = 'miscast_preparation'
    MISCAST_ROLL = 'miscast_roll'
    MISCAST_EFFECT = 'miscast_effect'
    END_TURN = 'unsupported_end_turn'
    CHRONOLOGY = 'unsupported_chronology'


@dataclass(frozen=True, slots=True)
class NpcMagicUnsupported:
    phase: NpcMagicPhase
    reason: NpcMagicUnsupportedReason
    actor_id: str | None
    source_id: str
    missing_actor_ids: tuple[str, ...] = ()
    missing_zone_ids: tuple[str, ...] = ()
    required_scene_key: NpcMagicSceneKey | None = None
    staged_movements: tuple[CowardlyFlightMovementCompletion, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.phase, NpcMagicPhase) or not isinstance(self.reason, NpcMagicUnsupportedReason):
            raise TypeError('unsupported phase/reason must be typed')
        _identifier(self.source_id)
        if self.actor_id is not None:
            _identifier(self.actor_id)
        object.__setattr__(self, 'missing_actor_ids', _ids(self.missing_actor_ids))
        object.__setattr__(self, 'missing_zone_ids', _ids(self.missing_zone_ids))
        object.__setattr__(self, 'staged_movements', _ordered(
            self.staged_movements, CowardlyFlightMovementCompletion, 'staged movements'))
        if self.required_scene_key is not None and not isinstance(self.required_scene_key, NpcMagicSceneKey):
            raise TypeError('required scene key must be typed')
        if (self.reason is NpcMagicUnsupportedReason.MISSING_SCENE) != (self.required_scene_key is not None):
            raise ValueError('missing scene requires its exact key, other stops cannot contain one')
