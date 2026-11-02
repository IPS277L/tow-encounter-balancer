"""Finite full-owner Crushed Rib witnesses, ADR-0056 (PG1.4 pp108,118,123,190).

Current source compatibility is checked here; journal reachability remains the
authoritative caller's responsibility. No RNG or speculative execution occurs.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.crushed_rib_test_models import (
    CrushedRibTestResult, CrushedRibCastingResult, _injury, _identifier,
    _integer, _boolean, _ordered, _typed, _test, _magic,
)
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState, WoundRecord, WoundEntryId, WoundRecordOrigin
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.attack_models import ResilienceProfile
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import TestRequest, Skill
from towr.domain.ranged_weapon_profiles import RangedWeaponRange, RangedWeaponHands
from towr.domain.turn_models import CombatSide, ActionSlotGrant

if TYPE_CHECKING:
    from towr.domain.npc_roster_casting_models import NpcRosterCastingState, NpcRosterCastingResult
    from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult


def _roster(roster, wizard_id):
    from towr.domain.npc_roster_models import NpcRoster, NpcParticipantSnapshot, NpcParticipantState, NpcDefinition
    _typed(roster, NpcRoster)
    _ordered(roster.participants)
    for p in roster.participants:
        _typed(p, NpcParticipantSnapshot)
        _typed(p.state, NpcParticipantState)
        _typed(p.definition, NpcDefinition)
        _typed(p.state.injury, CharacterInjuryState if p.state.actor_id == wizard_id else ProfileInjuryState)
        if p.state.actor_id == wizard_id:
            _injury(p.state.injury, pending=None)
        _typed(p.state.injury.conditions, ConditionState)
        if type(p.state.injury.conditions.conditions) is not frozenset:
            raise TypeError('Crushed Rib owner Conditions must retain their original frozenset form')
        replace(p.state.injury.conditions)
        _typed(p.state.current_resilience, ResilienceProfile)
        _typed(p.definition.resilience, ResilienceProfile)
        _typed(p.state.side, CombatSide)
        _typed(p.definition.injury_policy, TargetInjuryPolicy)
        for condition in p.state.injury.conditions.conditions:
            _typed(condition, Condition)
        _boolean(p.state.wields_weapon)
        _boolean(p.state.holds_shield)
        _ordered(p.state.available_attack_ids)
        _ordered(p.definition.attacks)
        _ordered(p.definition.protection)
        for number in (p.state.current_resilience.toughness, p.state.current_resilience.bonus,
                       p.definition.resilience.toughness, p.definition.resilience.bonus):
            _integer(number)
        for profile in p.definition.protection:
            replace(profile)
            _test(TestRequest('crushed-rib:owner-profile', profile.test_profile))
        for attack in p.definition.attacks:
            _typed(attack.skill, Skill)
            _typed(attack.range_min, RangedWeaponRange)
            _typed(attack.range_max, RangedWeaponRange)
            _typed(attack.hands, RangedWeaponHands)
            _ordered(attack.secondary_effects)
            replace(attack)
            _test(TestRequest('crushed-rib:owner-attack-profile', attack.test_profile))
            _integer(attack.damage.base)
            _integer(attack.damage.success_multiplier)
            _boolean(attack.ignores_armour)
        if p.state.actor_id != wizard_id:
            _integer(p.state.injury.wounds)
            _integer(p.state.injury.wound_limit)
        replace(p.state.injury)
        replace(p.state)
        replace(p.definition)
        replace(p)
    replace(roster)


def _combat(combat):
    _integer(combat.round_number)
    for values in (combat.participants, combat.side_order, combat.completed_turn_entity_ids,
                   combat.excluded_turn_entity_ids):
        _ordered(values)
    for side in combat.side_order:
        _typed(side, CombatSide)
    for participant in combat.participants:
        _typed(participant.side, CombatSide)
        replace(participant)
    if combat.active_turn is not None:
        turn = combat.active_turn
        _typed(turn.side, CombatSide)
        _ordered(turn.action_slots)
        for slot in turn.action_slots:
            _integer(slot.index)
            _typed(slot.grant, ActionSlotGrant)
            replace(slot.declaration)
            if slot.execution is not None:
                _integer(slot.execution.slot_index)
                replace(slot.execution)
            replace(slot)
        replace(turn)
    replace(combat)


def _owner(state):
    """Re-admit original owner fields before comparisons can hide aliases."""
    from towr.domain.npc_roster_casting_models import NpcRosterCastingState, NpcCastingWizardState
    from towr.domain.npc_roster_models import NpcRoster
    from towr.domain.npc_champion_attack_models import NpcChampionAttackState
    from towr.domain.npc_roster_attack_models import NpcRosterAttackState
    from towr.domain.infection_models import DailyWoundState, DailyWoundReceipt
    from towr.domain.spatial_models import SpatialBattleState
    from towr.domain.turn_models import CombatRoundState
    _typed(state, NpcRosterCastingState)
    _typed(state.roster, NpcRoster)
    _typed(state.wizard, NpcCastingWizardState)
    _typed(state.round_state, CombatRoundState)
    _typed(state.spatial_state, SpatialBattleState)
    _ordered(state.roster.participants)
    _ordered(state.consumed_execution_ids)
    _ordered(state.wound_expiries)
    _ordered(state.wound_turn_end_receipts)
    for receipt in state.wound_turn_end_receipts:
        _integer(receipt.round_number)
        _ordered(receipt.expired_attack_ids)
        _ordered(receipt.expired_sources)
        replace(receipt)
    for identifier in state.consumed_execution_ids:
        _identifier(identifier)
    _roster(state.roster, state.wizard.actor_id)
    _combat(state.round_state)
    _integer(state.spatial_state.round_number)
    spatial = state.spatial_state
    for values in (spatial.placements, spatial.gave_ground_entity_ids,
                   spatial.free_move_used_entity_ids, spatial.difficult_terrain_tested_entity_ids,
                   spatial.graph.zone_ids, spatial.graph.connections):
        _ordered(values)
    for placement in spatial.placements:
        replace(placement)
    for connection in spatial.graph.connections:
        replace(connection)
    replace(spatial.graph)
    replace(state.spatial_state)
    _magic(state.wizard.magic_state)
    replace(state.wizard.caster)
    _test(TestRequest('crushed-rib:owner-casting-profile', state.wizard.caster.casting_profile))
    replace(state.wizard)
    for child, kind in ((state.champion_attack, NpcChampionAttackState),
                        (state.minion_attack, NpcRosterAttackState)):
        if child is not None:
            _typed(child, kind)
            _ordered(child.consumed_execution_ids)
            if child.roster is not state.roster:
                _roster(child.roster, state.wizard.actor_id)
            if isinstance(child, NpcChampionAttackState):
                _combat(child.round_state)
            replace(child)
    champion = state.champion_attack
    if champion is None:
        raise ValueError('Crushed Rib requires the bound Champion owner')
    _ordered(champion.consumed_wound_roll_ids)
    daily = champion.daily_wounds
    _typed(daily, DailyWoundState)
    _ordered(daily.receipts)
    for receipt in daily.receipts:
        _typed(receipt, DailyWoundReceipt)
        wound = receipt.wound
        _typed(wound, WoundRecord)
        _integer(wound.sequence)
        _integer(wound.table_total)
        _typed(wound.entry_id, WoundEntryId)
        _typed(wound.origin, WoundRecordOrigin)
        _ordered(wound.roll_values)
        for value in wound.roll_values:
            _integer(value)
            if not 1 <= value <= 10:
                raise ValueError('Crushed Rib daily Wound history requires actual d10 values')
        for flag in (wound.effect_resolved, wound.treated, wound.healed):
            _boolean(flag)
        replace(wound)
        replace(receipt)
    replace(daily)
    if daily.is_closed or daily.target_id != state.wizard.actor_id:
        raise ValueError('Crushed Rib requires the current open Wizard daily Wound owner')
    replace(state)


def _daily_source(state, injury):
    """Require the exact registered Wound10 and its consumed lifecycle roll."""
    champion = state.champion_attack
    wound = injury.wounds[-1]
    receipts = tuple(r for r in champion.daily_wounds.receipts if r.wound.sequence == wound.sequence)
    if len(receipts) != 1:
        raise ValueError('Crushed Rib requires its exact daily Wound receipt')
    receipt = receipts[0]
    replace(receipt)
    _integer(receipt.wound.sequence)
    _integer(receipt.wound.table_total)
    for flag in (receipt.wound.effect_resolved, receipt.wound.treated, receipt.wound.healed):
        _boolean(flag)
    # A daily receipt precedes effect resolution; only that flag differs.
    if replace(receipt.wound, effect_resolved=True) != wound:
        raise ValueError('Crushed Rib daily receipt differs from the original Wound')
    if receipt.source_request_id + '-lifecycle' not in champion.consumed_wound_roll_ids:
        raise ValueError('Crushed Rib loses its consumed lifecycle roll')


def _prefix(before, current):
    return current[:len(before)] == before


@dataclass(frozen=True, slots=True)
class NpcCrushedRibConsumptionWitness:
    result: NpcRosterChampionAttackResult | NpcRosterCastingResult
    consumption: CrushedRibTestResult | CrushedRibCastingResult

    def __post_init__(self):
        from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingRequest
        from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult, NpcRosterChampionAttackRequest
        if not isinstance(self.result, (NpcRosterChampionAttackResult, NpcRosterCastingResult)):
            raise TypeError('Crushed Rib requires a complete first consuming M8 result')
        if not isinstance(self.consumption, (CrushedRibTestResult, CrushedRibCastingResult)):
            raise TypeError('Crushed Rib requires a completed K1 receipt')
        parent = self.result.source
        _typed(parent, NpcRosterCastingRequest if isinstance(self.result, NpcRosterCastingResult)
               else NpcRosterChampionAttackRequest)
        context = parent.crushed_rib_context
        if not isinstance(context, NpcCrushedRibContext) or context.consumption is not None:
            raise ValueError('Crushed Rib witness must refer to the first pending-context result')
        # Test the finite edge before re-admission, rejecting cycles/late results.
        replace(context)
        replace(self.consumption)
        replace(parent)
        if isinstance(self.result, NpcRosterChampionAttackResult):
            replace(self.result.attack.source)
            replace(self.result.attack)
            actual = self.result.attack.crushed_rib
        else:
            replace(self.result.casting.source)
            replace(self.result.casting)
            actual = self.result.casting.crushed_rib
        replace(self.result)
        if actual is None or actual != self.consumption:
            raise ValueError('Crushed Rib receipt differs from its actual consuming M8 Test')
        source = self.consumption.source.source_request
        if source.actor_id != context.actor_id or source.state != context.injury:
            raise ValueError('Crushed Rib consumption differs from the full pending source')


@dataclass(frozen=True, slots=True)
class NpcCrushedRibContext:
    state: NpcRosterCastingState
    actor_id: str
    no_external_condition_sources: bool
    consumption: NpcCrushedRibConsumptionWitness | None = None

    def __post_init__(self):
        from towr.domain.npc_roster_turn_models import _validate_phase_source
        _identifier(self.actor_id)
        _boolean(self.no_external_condition_sources)
        if not self.no_external_condition_sources:
            raise ValueError('Crushed Rib requires confirmed absence of external Condition causes')
        _owner(self.state)
        _validate_phase_source(self.state)
        if self.actor_id != self.state.wizard.actor_id:
            raise ValueError('Crushed Rib context requires the owner Wizard')
        _injury(self.injury, pending=self.consumption is None)
        _daily_source(self.state, self.injury)
        if self.consumption is not None:
            _typed(self.consumption, NpcCrushedRibConsumptionWitness)
            replace(self.consumption)
            receipt = self.consumption.consumption
            if receipt.source.source_request.actor_id != self.actor_id or self.injury != receipt.state:
                raise ValueError('Crushed Rib consumed context requires the exact current receipt injury')
            previous = self.consumption.result.state
            _owner(previous)
            if self.injury != previous.roster.participant(self.actor_id).state.injury:
                raise ValueError('post-Test consequences exceed the consumed Crushed Rib injury scope')
            old = previous.champion_attack
            current = self.state.champion_attack
            if (self.state.wizard.caster != previous.wizard.caster
                    or tuple((p.definition, p.state.actor_id, p.state.side) for p in self.state.roster.participants)
                    != tuple((p.definition, p.state.actor_id, p.state.side) for p in previous.roster.participants)
                    or current.daily_wounds.day_id != old.daily_wounds.day_id
                    or not _prefix(previous.consumed_execution_ids, self.state.consumed_execution_ids)
                    or not _prefix(old.consumed_execution_ids, current.consumed_execution_ids)
                    or not _prefix(old.consumed_wound_roll_ids, current.consumed_wound_roll_ids)
                    or not _prefix(old.daily_wounds.receipts, current.daily_wounds.receipts)):
                raise ValueError('Crushed Rib current owner loses its first-result provenance/history')
            old_minion = previous.minion_attack
            new_minion = self.state.minion_attack
            if old_minion is not None and (new_minion is None or not _prefix(
                    old_minion.consumed_execution_ids, new_minion.consumed_execution_ids)):
                raise ValueError('Crushed Rib current owner loses its Minion child history')
            a, b = previous.round_state, self.state.round_state
            if (b.round_number < a.round_number or b.side_order != a.side_order
                    or b.round_number == a.round_number and (
                        not _prefix(a.completed_turn_entity_ids, b.completed_turn_entity_ids)
                        or not set(a.excluded_turn_entity_ids) <= set(b.excluded_turn_entity_ids))):
                raise ValueError('Crushed Rib current clock precedes the consuming result')

    @property
    def injury(self) -> CharacterInjuryState:
        return self.state.roster.participant(self.actor_id).state.injury

    def validate_source(self, state: NpcRosterCastingState, actor_id: str) -> None:
        _owner(state)
        _identifier(actor_id)
        replace(self)
        if state != self.state or actor_id != self.actor_id:
            raise ValueError('Crushed Rib context belongs to another full source or actor role')
