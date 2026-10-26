"""Source/clock records for the first M8 timed Wound (ADR-0036).

PG1.4 Rules / Wounds & Conditions pp121-123; Wounds Table p190.
Only Stomach Blow from a completed ordinary Champion attack is scheduled.
"""
from dataclasses import dataclass

from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionEffect, WoundEffectDuration, WoundEntryId, WoundRecord
from towr.domain.npc_champion_attack_models import NpcChampionAttackResult
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleOutcome


@dataclass(frozen=True, slots=True)
class NpcStomachBlowExpiry:
    source: NpcChampionAttackResult

    def __post_init__(self) -> None:
        if not isinstance(self.source, NpcChampionAttackResult):
            raise TypeError('expiry requires a complete Champion attack result')
        completion = self.source.completion
        if (completion is None or completion.outcome is not CharacterWoundLifecycleOutcome.ACCEPTED
                or completion.wound_effect is None
                or completion.wound_effect.request.entry_id is not WoundEntryId.STOMACH_BLOW
                or self.effect not in completion.state.active_wound_effects):
            raise ValueError('expiry requires an accepted resolved Stomach Blow')

    @property
    def actor_id(self) -> str:
        return self.source.execution.target_id

    @property
    def attack_id(self) -> str:
        return self.source.execution.request_id

    @property
    def wound(self) -> WoundRecord:
        sequence = self.source.completion.wound_effect.request.wound_sequence
        return next(w for w in self.source.completion.state.wounds if w.sequence == sequence)

    @property
    def effect(self) -> WoundConditionEffect:
        return WoundConditionEffect(self.source.completion.wound_effect.request.wound_sequence,
                                    Condition.DRAINED, WoundEffectDuration.END_OF_NEXT_TURN)

    @property
    def deadline_round_number(self) -> int:
        combat = self.source.source.state.round_state
        if self.actor_id in combat.excluded_turn_entity_ids:
            raise ValueError('excluded target requires a separate next-turn chronology contract')
        # The source is an ordinary attack by another active actor. A target
        # which already completed its turn next acts in the following round.
        return combat.round_number + int(self.actor_id in combat.completed_turn_entity_ids)

    def matches_wound(self, wound: WoundRecord) -> bool:
        old = self.wound
        return (wound.sequence, wound.entry_id, wound.table_total, wound.roll_values, wound.origin) == (
            old.sequence, old.entry_id, old.table_total, old.roll_values, old.origin)


@dataclass(frozen=True, slots=True)
class NpcWoundTurnEndReceipt:
    id: str
    actor_id: str
    round_number: int
    expired_attack_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for value in (self.id, self.actor_id):
            if not isinstance(value, str):
                raise TypeError('turn-end receipt IDs must be strings')
            if not value.strip():
                raise ValueError('turn-end receipt IDs must not be blank')
        if not isinstance(self.round_number, int) or isinstance(self.round_number, bool):
            raise TypeError('turn-end round must be an integer')
        if self.round_number < 1:
            raise ValueError('turn-end round must be positive')
        if not isinstance(self.expired_attack_ids, (tuple, list)):
            raise TypeError('expired attack IDs must be an ordered tuple or list')
        identifiers = tuple(self.expired_attack_ids)
        if any(not isinstance(i, str) or not i.strip() for i in identifiers) or len(set(identifiers)) != len(identifiers):
            raise ValueError('expired attack IDs must be unique nonblank strings')
        object.__setattr__(self, 'expired_attack_ids', identifiers)
