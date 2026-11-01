"""Explicit full-owner stationary Wound9 context (PG1.4 pp115,119,123,190)."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    CharacterInjuryState, WoundConditionEffect, WoundEffectDuration, WoundEntryId,
    WoundRecord, WoundRecordOrigin, WoundRestriction, WoundRestrictionEffect,
)

if TYPE_CHECKING:
    from towr.domain.npc_roster_casting_models import NpcRosterCastingState
    from towr.domain.npc_wound_turn_models import NpcStomachBlowExpiry


def _record_identity(wound: WoundRecord) -> tuple:
    return (wound.sequence, wound.entry_id, wound.table_total, wound.roll_values, wound.origin)


def _parts(state: NpcRosterCastingState, actor_id: str) -> tuple[tuple, tuple, tuple[str, ...]]:
    injury = state.roster.participant(actor_id).state.injury
    expected = set()
    expired = []
    legs = 0
    active = {e.wound.sequence: e for e in state.wound_expiries}
    if len(active) != len(state.wound_expiries):
        raise ValueError('stationary Wounds exclude duplicate expiry sequences')
    for wound in injury.wounds:
        if any(type(getattr(wound, f)) is not bool for f in ('effect_resolved', 'treated', 'healed')):
            raise TypeError('Wound flags must be strict booleans')
        if not wound.effect_resolved or wound.treated or wound.healed:
            raise ValueError('stationary Wounds must be resolved untreated and unhealed')
        if type(wound.sequence) is not int or type(wound.table_total) is not int:
            raise TypeError('Wound sequence and total must be strict integers')
        if wound.origin is WoundRecordOrigin.TABLE_ROLL:
            if (not wound.roll_values or any(type(v) is not int or not 1 <= v <= 10 for v in wound.roll_values)
                    or sum(wound.roll_values) != wound.table_total):
                raise ValueError('Wound must preserve exact d10 values and sum')
        elif wound.origin is not WoundRecordOrigin.FIXED_ENTRY or wound.roll_values:
            raise ValueError('fixed Wound provenance must not invent dice')
        if wound.entry_id is WoundEntryId.SUPERFICIAL_INJURY:
            if not 1 <= wound.table_total <= 3:
                raise ValueError('noncanonical Superficial Injury total')
        elif wound.entry_id is WoundEntryId.LEG_SPASM:
            if wound.table_total != 9:
                raise ValueError('noncanonical Leg Spasm total')
            legs += 1
            expected.add(WoundRestrictionEffect(wound.sequence,
                WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN, WoundEffectDuration.UNTIL_TREATED))
        elif wound.entry_id is WoundEntryId.STOMACH_BLOW:
            if wound.table_total != 6 or wound.origin is not WoundRecordOrigin.TABLE_ROLL:
                raise ValueError('Stomach Blow requires canonical rolled provenance')
            champion = state.champion_attack
            if champion is None:
                raise ValueError('Stomach Blow requires its bound Champion history')
            receipts = tuple(r for r in champion.daily_wounds.receipts
                             if r.wound.sequence == wound.sequence)
            if len(receipts) != 1 or _record_identity(receipts[0].wound) != _record_identity(wound):
                raise ValueError('Stomach Blow must match its exact daily receipt')
            receipt = receipts[0]
            if receipt.source_request_id + '-lifecycle' not in champion.consumed_wound_roll_ids:
                raise ValueError('Stomach Blow loses its consumed lifecycle roll')
            expiry = active.get(wound.sequence)
            if expiry is not None:
                source_round = expiry.source.source.state.round_state
                current_round = state.round_state
                if (source_round.round_number > current_round.round_number
                        or source_round.round_number == current_round.round_number
                        and (not set(source_round.completed_turn_entity_ids) <= set(current_round.completed_turn_entity_ids)
                             or not set(source_round.excluded_turn_entity_ids) <= set(current_round.excluded_turn_entity_ids))
                        or current_round.active_turn is not None
                        and current_round.active_turn.actor_id == actor_id
                        and expiry.deadline_round_number != current_round.round_number):
                    raise ValueError('active expiry differs from the full current target-turn chronology')
                if (not expiry.matches_wound(wound)
                        or expiry.source.completion.daily_registration.receipt != receipt):
                    raise ValueError('Stomach Blow differs from its active attack witness')
                expected.add(expiry.effect)
            else:
                proofs = tuple(e for end in state.wound_turn_end_receipts
                               if end.actor_id == actor_id
                               for e in end.expired_sources
                               if receipt.id == e.attack_id + ':daily-wound:receipt')
                if (len(proofs) != 1 or not proofs[0].matches_wound(wound)
                        or proofs[0].source.completion.daily_registration.receipt != receipt
                        or proofs[0].attack_id not in state.consumed_execution_ids
                        or proofs[0].attack_id not in champion.consumed_execution_ids):
                    raise ValueError('inactive Stomach Blow requires its exact consumed expiry receipt')
                expired.append(proofs[0].attack_id)
        else:
            raise ValueError('stationary context excludes other Wound entries')
    actual = injury.active_wound_effects
    if not legs or len(actual) != len(expected) or set(actual) != expected:
        raise ValueError('stationary context requires exactly canonical terrain and active Stomach Blow effects')
    if injury.conditions.has(Condition.DRAINED) is not bool(active):
        raise ValueError('Drained must match exactly the active Stomach Blow causes')
    return (tuple(e for e in actual if isinstance(e, WoundRestrictionEffect)),
            tuple(e for e in actual if isinstance(e, WoundConditionEffect)), tuple(expired))


def stationary_wound_scope_supported(state: NpcRosterCastingState, actor_id: str) -> bool:
    """Classify canonical injury scope; phase/permission remain request guards."""
    from towr.domain.npc_roster_casting_models import NpcRosterCastingState
    if not isinstance(state, NpcRosterCastingState) or not isinstance(actor_id, str):
        raise TypeError('stationary scope requires typed full state and actor ID')
    if actor_id != state.wizard.actor_id:
        return False
    injury = state.roster.participant(actor_id).state.injury
    if (injury.dead or not injury.conditions.conditions <= {Condition.STAGGERED, Condition.DRAINED}):
        return False
    try:
        _parts(state, actor_id)
    except ValueError:
        return False
    return True


@dataclass(frozen=True, slots=True)
class NpcStationaryWoundContext:
    state: NpcRosterCastingState
    actor_id: str
    no_external_condition_sources: bool

    def __post_init__(self) -> None:
        # Local imports keep the root/Champion child model dependency finite.
        from towr.domain.npc_roster_turn_models import _identifier, _validate_phase_source
        _identifier(self.actor_id)
        _validate_phase_source(self.state)
        if type(self.no_external_condition_sources) is not bool:
            raise TypeError('no_external_condition_sources must be an explicit boolean')
        if not self.no_external_condition_sources:
            raise ValueError('stationary context requires confirmed absence of external Condition causes')
        if self.actor_id != self.state.wizard.actor_id:
            raise ValueError('stationary context requires the owner Wizard')
        injury = self.injury
        if (not isinstance(injury, CharacterInjuryState) or injury.dead
                or not injury.conditions.conditions <= {Condition.STAGGERED, Condition.DRAINED}):
            raise ValueError('stationary context requires living Wizard with Staggered/Drained only')
        _parts(self.state, self.actor_id)

    @property
    def injury(self) -> CharacterInjuryState:
        return self.state.roster.participant(self.actor_id).state.injury

    @property
    def terrain_effects(self) -> tuple[WoundRestrictionEffect, ...]:
        return _parts(self.state, self.actor_id)[0]

    @property
    def condition_effects(self) -> tuple[WoundConditionEffect, ...]:
        return _parts(self.state, self.actor_id)[1]

    @property
    def active_stomach_blows(self) -> tuple[NpcStomachBlowExpiry, ...]:
        return self.state.wound_expiries

    @property
    def expired_stomach_blow_attack_ids(self) -> tuple[str, ...]:
        return _parts(self.state, self.actor_id)[2]

    @property
    def can_give_ground(self) -> bool:
        return False

    def validate_source(self, state: NpcRosterCastingState, actor_id: str) -> None:
        from towr.domain.npc_roster_casting_models import NpcRosterCastingState
        if not isinstance(state, NpcRosterCastingState) or not isinstance(actor_id, str):
            raise TypeError('stationary source requires typed full state and actor ID')
        replace(self)
        if state != self.state or actor_id != self.actor_id:
            raise ValueError('stationary context belongs to another full source or actor role')
