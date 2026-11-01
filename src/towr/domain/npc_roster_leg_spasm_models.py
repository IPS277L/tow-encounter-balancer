"""Full-owner self-stand for canonical, untreated Leg Spasm wounds (ADR-0048).

PG1.4 Wounds Table p190; Rules / Free Actions p116, Conditions pp122-123.
GM1.1 Champions p92. No movement, treatment or automatic runner admission.
"""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    CharacterInjuryState, WoundConditionEffect, WoundEffectDuration,
    WoundEntryId, WoundRecordOrigin, WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.movement_models import (
    FreeMoveProneRemovalRequest, FreeMoveProneRemovalResult, ProneRemovalTargetKind,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_roster_turn_models import _identifier, _validate_phase_source
from towr.domain.turn_models import ActionSlotGrant


def _leg_spasm_prone_effects(injury: CharacterInjuryState) -> tuple[WoundConditionEffect, ...]:
    """Validate both canonical effects of every wound, retaining source order."""
    expected = set()
    for wound in injury.wounds:
        if not wound.effect_resolved or wound.treated or wound.healed:
            raise ValueError('Leg Spasm stand requires resolved untreated and unhealed Wounds')
        if type(wound.sequence) is not int or type(wound.table_total) is not int:
            raise TypeError('Wound sequence and total must be strict integers')
        if wound.origin is WoundRecordOrigin.TABLE_ROLL:
            if (not wound.roll_values or any(type(v) is not int or not 1 <= v <= 10 for v in wound.roll_values)
                    or sum(wound.roll_values) != wound.table_total):
                raise ValueError('Wound must preserve its exact d10 values and sum')
        elif wound.origin is not WoundRecordOrigin.FIXED_ENTRY or wound.roll_values:
            raise ValueError('fixed-entry Wounds must preserve their provenance without invented dice')
        if wound.entry_id is WoundEntryId.SUPERFICIAL_INJURY:
            if not 1 <= wound.table_total <= 3:
                raise ValueError('Superficial Injury requires its canonical table total')
        elif wound.entry_id is WoundEntryId.LEG_SPASM:
            if wound.table_total != 9:
                raise ValueError('Leg Spasm requires the canonical table total 9')
            expected.add(WoundConditionEffect(wound.sequence, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED))
            expected.add(WoundRestrictionEffect(wound.sequence, WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN,
                                                WoundEffectDuration.UNTIL_TREATED))
        else:
            raise ValueError('Leg Spasm stand excludes other Wound entries')
    actual = injury.active_wound_effects
    if not expected or len(actual) != len(expected) or set(actual) != expected:
        raise ValueError('Leg Spasm stand requires exactly one canonical effect pair per Leg Spasm')
    return tuple(effect for effect in actual if isinstance(effect, WoundConditionEffect))


def leg_spasm_prone_effects_supported(injury: CharacterInjuryState) -> bool:
    """Non-throwing scope decision for canonical effects, not a stand executor."""
    if not isinstance(injury, CharacterInjuryState):
        raise TypeError('Leg Spasm scope requires CharacterInjuryState')
    try:
        _leg_spasm_prone_effects(injury)
    except ValueError:
        return False
    return True


@dataclass(frozen=True, slots=True)
class NpcRosterLegSpasmStandRequest:
    id: str
    state: NpcRosterCastingState
    actor_id: str
    actor_has_enemy_in_close_range: bool
    underlying_cause_allows_removal: bool

    def __post_init__(self) -> None:
        _identifier(self.id)
        _identifier(self.actor_id)
        _validate_phase_source(self.state)
        for name in ('actor_has_enemy_in_close_range', 'underlying_cause_allows_removal'):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f'{name} must be an explicit boolean')
        if self.actor_has_enemy_in_close_range:
            raise ValueError('an enemy in Close Range prevents self-stand')
        if not self.underlying_cause_allows_removal:
            raise ValueError('the underlying Prone cause must allow removal')
        state = self.state
        if self.actor_id != state.wizard.actor_id:
            raise ValueError('Leg Spasm stand requires the owner Wizard')
        turn = state.round_state.active_turn
        if (turn is None or turn.actor_id != self.actor_id or len(turn.action_slots) != 1
                or turn.action_slots[0].grant is not ActionSlotGrant.STANDARD
                or turn.action_slots[0].executed):
            raise ValueError('Leg Spasm stand requires one active unexecuted standard slot')
        if self.actor_id in state.spatial_state.free_move_used_entity_ids:
            raise ValueError('Leg Spasm stand requires unused free movement')
        injury = state.roster.participant(self.actor_id).state.injury
        if not isinstance(injury, CharacterInjuryState):
            raise TypeError('Leg Spasm stand requires a Character injury state')
        if (injury.dead or not injury.conditions.has(Condition.PRONE)
                or not injury.conditions.conditions <= {Condition.PRONE, Condition.STAGGERED}):
            raise ValueError('Leg Spasm stand requires living Prone Wizard with optional Staggered only')
        _leg_spasm_prone_effects(injury)

    @property
    def stand_request(self) -> FreeMoveProneRemovalRequest:
        return FreeMoveProneRemovalRequest(
            self.id, self.state.round_state, self.state.spatial_state, self.actor_id,
            ProneRemovalTargetKind.SELF, self.actor_id,
            self.state.roster.participant(self.actor_id).state.injury.conditions,
            None, self.actor_has_enemy_in_close_range)


@dataclass(frozen=True, slots=True)
class NpcRosterLegSpasmStandResult:
    source: NpcRosterLegSpasmStandRequest
    stand: FreeMoveProneRemovalResult

    def __post_init__(self) -> None:
        if (not isinstance(self.source, NpcRosterLegSpasmStandRequest)
                or not isinstance(self.stand, FreeMoveProneRemovalResult)):
            raise TypeError('Leg Spasm stand result requires typed full source and K1 result')
        replace(self.source)
        request = self.source.stand_request
        expected = FreeMoveProneRemovalResult(
            request.id, request.rule_id, request.round_state, request.actor_id,
            ProneRemovalTargetKind.SELF, request.target_id, None, False,
            request.target_conditions, request.target_conditions.without_condition(Condition.PRONE),
            request.state, replace(request.state, free_move_used_entity_ids=(
                *request.state.free_move_used_entity_ids, request.actor_id)),
            (request.rule_id, 'RULE-COMBAT-014:free-movement'))
        if (self.stand != expected or self.stand.target_kind is not ProneRemovalTargetKind.SELF
                or self.stand.target_in_close_range is not None
                or self.stand.actor_has_enemy_in_close_range is not False):
            raise ValueError('Leg Spasm stand differs from its complete source and K1 transition')

    @property
    def removed_effects(self) -> tuple[WoundConditionEffect, ...]:
        return _leg_spasm_prone_effects(self.source.state.roster.participant(self.source.actor_id).state.injury)

    @property
    def state(self) -> NpcRosterCastingState:
        old = self.source.state
        actor = old.roster.participant(self.source.actor_id)
        removed = set(self.removed_effects)
        injury = replace(actor.state.injury, conditions=self.stand.target_conditions,
                         active_wound_effects=tuple(e for e in actor.state.injury.active_wound_effects
                                                    if e not in removed))
        roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=injury))
                                 if p.state.actor_id == self.source.actor_id else p
                                 for p in old.roster.participants))
        return replace(old, roster=roster, spatial_state=self.stand.state,
            champion_attack=(None if old.champion_attack is None else replace(old.champion_attack, roster=roster)),
            minion_attack=(None if old.minion_attack is None else replace(old.minion_attack, roster=roster)))
