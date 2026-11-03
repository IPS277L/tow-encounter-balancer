"""Full-owner Battered Leg completion and bounded later Prone removal evidence."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from towr.domain.npc_roster_battered_leg_prone_models import NpcRosterBatteredLegProneStandResult
    from towr.domain.npc_roster_battered_leg_recover_models import NpcRosterBatteredLegRecoverResult

from towr.domain.attack_models import AttackOutcome, ImpactOutcome
from towr.domain.battered_leg_models import (
    BatteredLegEnduranceTestRequest, BatteredLegEnduranceTestResult,
)
from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState, CharacterWoundType, WoundEntryId
from towr.domain.npc_champion_attack_models import (
    _actual_attack, _normal_attack_source, _normal_test_result, _strict_injury_snapshot,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.test_models import InlineProfile, TestRequest
from towr.domain.turn_models import ActionSlotGrant, CombatSide
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleOutcome


def _true(value, name):
    if type(value) is not bool:
        raise TypeError(f'{name} must be an explicit boolean')
    if not value:
        raise ValueError(f'{name} must be confirmed')


def _readmit(value):
    if replace(value) != value:
        raise ValueError('Battered Leg source must not require normalization')


def _owner(state):
    if not isinstance(state, NpcRosterCastingState):
        raise TypeError('Battered Leg requires the complete Casting owner')
    for name in ('consumed_execution_ids', 'wound_expiries', 'wound_turn_end_receipts'):
        if type(getattr(state, name)) is not tuple:
            raise TypeError('owner histories must retain tuples')
    for value in (state.wizard.caster, state.wizard.magic_state, state.wizard,
                  state.spatial_state.graph, state.spatial_state, state.round_state):
        _readmit(value)
    if type(state.round_state.round_number) is not int:
        raise TypeError('round number must be a strict integer')
    if not all(isinstance(side, CombatSide) for side in state.round_state.side_order):
        raise TypeError('round sides must retain typed enums')
    rosters = [state.roster]
    for child in (state.champion_attack, state.minion_attack):
        if child is not None:
            _readmit(child)
            rosters.append(child.roster)
    # Read original detached projections before equality can hide 0 == False
    # or a str enum alias in a child that happens to equal the root roster.
    for roster in rosters:
        if type(roster.participants) is not tuple:
            raise TypeError('owner rosters must retain tuple snapshots')
        for participant in roster.participants:
            _readmit(participant.definition)
            _readmit(participant.state)
            _readmit(participant)
            if not isinstance(participant.state.side, CombatSide):
                raise TypeError('actor side must retain its enum')
            for flag in (participant.state.wields_weapon, participant.state.holds_shield):
                if type(flag) is not bool:
                    raise TypeError('equipment flags must be strict booleans')
            if isinstance(participant.state.injury, CharacterInjuryState):
                _strict_injury_snapshot(participant.state.injury)
            else:
                _readmit(participant.state.injury)
        _readmit(roster)
    if state.champion_attack is None:
        raise ValueError('Battered Leg requires its Champion child owner')
    if type(state.champion_attack.daily_wounds.receipts) is not tuple:
        raise TypeError('daily Wound receipts must retain tuple snapshots')
    for receipt in state.champion_attack.daily_wounds.receipts:
        wound = receipt.wound
        _readmit(wound)
        for flag in (wound.treated, wound.effect_resolved, wound.healed):
            if type(flag) is not bool:
                raise TypeError('daily Wound flags must retain strict booleans')
        _readmit(receipt)
    _readmit(state.champion_attack.daily_wounds)
    _readmit(state.champion_attack)
    if state.minion_attack is not None:
        _readmit(state.minion_attack)
    _readmit(state)


def _attack_source(attack):
    if not isinstance(attack, NpcRosterChampionAttackResult):
        raise TypeError('Battered Leg requires its full bound Attack result')
    before = attack.source.state
    if before.battered_leg_receipt is not None:
        raise ValueError('Battered Leg first-Wound source cannot contain a prior receipt')
    _owner(before)
    lower = attack.attack
    if (attack.source.crushed_rib_context is not None
            or lower.source.stationary_wounds is not None
            or lower.source.crushed_rib_preparation is not None
            or lower.source.crushed_rib_consumption is not None):
        raise ValueError('Battered Leg excludes other Wound contexts')
    for value in (lower.source.preparation.npc_attack.source_request,
                  lower.source.preparation.npc_attack, lower.source.preparation.protection.source_request,
                  lower.source.preparation.protection, lower.source.preparation,
                  lower.source.execution.kernel_request, lower.source.execution,
                  lower.source, attack.source):
        _readmit(value)
    original = lower.source.execution.kernel_request.attack
    actual = lower.execution.resolution.attack
    _normal_attack_source(original)
    if original.defender_test is None or actual.defender_test is None:
        raise ValueError('Battered Leg source requires an actual opposed Attack')
    _normal_test_result(original.defender_test, actual.defender_test)
    _actual_attack(original, actual)
    if actual.outcome is not AttackOutcome.HIT or actual.impact is not ImpactOutcome.WOUND:
        raise ValueError('Battered Leg bridge requires an ordinary wounding hit')
    final_attack = lower.resolution.attack
    if final_attack.defender_test is None:
        raise ValueError('completed Attack must preserve its Protection Test')
    _normal_test_result(original.defender_test, final_attack.defender_test)
    _actual_attack(original, final_attack)
    completion = lower.completion
    if completion is None or completion.outcome is not CharacterWoundLifecycleOutcome.ACCEPTED:
        raise ValueError('Battered Leg requires an accepted Wound completion')
    if completion.daily_registration is None or completion.wound_effect is None:
        raise ValueError('Battered Leg completion must retain registration and effect')
    roll = completion.source_request.roll
    for value in (roll.wound_result.table_roll.entry, roll.wound_result.table_roll,
                  roll.source_request.wound, roll.source_request, roll,
                  completion.source_request, completion.daily_registration.source_request,
                  completion.daily_registration, completion):
        _readmit(value)
    if (roll.wound_result.subject_type is not CharacterWoundType.CHAMPION
            or roll.near_miss_eligible is not False
            or completion.wound_effect is None
            or completion.wound_effect.request.entry_id is not WoundEntryId.BATTERED_LEG
            or lower.execution.target_id != before.wizard.actor_id):
        raise ValueError('Battered Leg completion must belong to the owner Wizard')
    _readmit(lower.execution)
    _readmit(lower)
    _readmit(attack)
    after = attack.state
    _owner(after)
    turn = after.round_state.active_turn
    if (turn is None or turn.actor_id != lower.execution.actor_id
            or len(turn.action_slots) != 1
            or turn.action_slots[0].grant is not ActionSlotGrant.STANDARD
            or not turn.action_slots[0].executed
            or after.champion_attack.pending != lower
            or lower.pending_follow_ups != completion.wound_effect.follow_ups
            or len(lower.pending_follow_ups) != 1):
        raise ValueError('Battered Leg requires the immediate pending completed Attack')
    return after


def _k1(attack, profile, identifier, unmounted):
    state = attack.state
    effect = attack.attack.completion.wound_effect
    follow_up = effect.follow_ups[0]
    return BatteredLegEnduranceTestRequest(
        identifier, state.wizard.actor_id,
        state.roster.participant(state.wizard.actor_id).state.injury,
        effect, follow_up, TestRequest(follow_up.test_id, profile), unmounted,
    )


@dataclass(frozen=True, slots=True)
class NpcBatteredLegCompletionWitness:
    attack: NpcRosterChampionAttackResult
    endurance: BatteredLegEnduranceTestResult
    no_external_condition_sources: bool
    prone_stand: NpcRosterBatteredLegProneStandResult | None = None
    prone_recover: NpcRosterBatteredLegRecoverResult | None = None

    def __post_init__(self):
        _true(self.no_external_condition_sources, 'no_external_condition_sources')
        _attack_source(self.attack)
        if not isinstance(self.endurance, BatteredLegEnduranceTestResult):
            raise TypeError('Battered Leg receipt requires its K1 completion')
        _readmit(self.endurance)
        supplied = self.endurance.request
        if not isinstance(supplied.endurance_test.profile, InlineProfile):
            raise TypeError('M8 Endurance receipt requires its authored InlineProfile')
        expected = _k1(self.attack, supplied.endurance_test.profile, supplied.id, supplied.unmounted)
        if supplied != expected:
            raise ValueError('Battered Leg receipt differs from its full Attack source')
        if self.prone_stand is not None and self.prone_recover is not None:
            raise ValueError('Battered Leg Prone can be removed only once, by stand or Recover')
        if self.prone_stand is not None:
            from towr.domain.npc_roster_battered_leg_prone_models import NpcRosterBatteredLegProneStandResult
            if not isinstance(self.prone_stand, NpcRosterBatteredLegProneStandResult):
                raise TypeError('Battered Leg receipt requires its typed full self-stand result')
            _readmit(self.prone_stand)
            if self.prone_stand.source.state.battered_leg_receipt != replace(self, prone_stand=None, prone_recover=None):
                raise ValueError('Battered Leg self-stand belongs to another Endurance completion')
        if self.prone_recover is not None:
            from towr.domain.npc_roster_battered_leg_recover_models import NpcRosterBatteredLegRecoverResult
            if not isinstance(self.prone_recover, NpcRosterBatteredLegRecoverResult):
                raise TypeError('Battered Leg receipt requires its typed full Recover result')
            _readmit(self.prone_recover)
            if self.prone_recover.source.state.battered_leg_receipt != replace(self, prone_stand=None, prone_recover=None):
                raise ValueError('Battered Leg Recover belongs to another Endurance completion')

    @property
    def completed_injury(self):
        if self.prone_recover is not None:
            return self.prone_recover.completed_injury
        return (self.endurance.wound_result.state if self.prone_stand is None
                else self.prone_stand.completed_injury)

    def validate_storage(self, state):
        """Retain historical evidence without claiming arbitrary reachability."""
        after = self.attack.state if self.prone_stand is None else self.prone_stand.source.state
        if self.prone_recover is not None:
            after = self.prone_recover.source.state
        actor_id = after.wizard.actor_id
        old = after.roster.participant(actor_id)
        current = state.roster.participant(actor_id)
        identity = lambda wound: (wound.sequence, wound.entry_id, wound.table_total,
                                  wound.roll_values, wound.origin)
        if (state.wizard.actor_id != actor_id or state.wizard.caster != after.wizard.caster
                or tuple((p.definition, p.state.actor_id, p.state.side) for p in state.roster.participants)
                != tuple((p.definition, p.state.actor_id, p.state.side) for p in after.roster.participants)
                or not current.state.injury.wounds
                or identity(current.state.injury.wounds[0]) != identity(old.state.injury.wounds[0])
                or state.round_state.round_number < after.round_state.round_number):
            raise ValueError('Battered Leg receipt has foreign actor/Wound/profile anchors')
        if state.spatial_state.graph != after.spatial_state.graph:
            raise ValueError('Battered Leg receipt belongs to another scene graph')
        if state.champion_attack is None:
            raise ValueError('Battered Leg receipt lost its Champion history')
        if (state.champion_attack.daily_wounds.day_id != after.champion_attack.daily_wounds.day_id
                or state.champion_attack.daily_wounds.target_id != actor_id):
            raise ValueError('Battered Leg receipt belongs to another daily Wound owner')
        pairs = (
            (after.consumed_execution_ids, state.consumed_execution_ids),
            (after.champion_attack.consumed_execution_ids, state.champion_attack.consumed_execution_ids),
            (after.champion_attack.consumed_wound_roll_ids, state.champion_attack.consumed_wound_roll_ids),
            (after.champion_attack.daily_wounds.receipts, state.champion_attack.daily_wounds.receipts),
            (after.wound_turn_end_receipts, state.wound_turn_end_receipts),
        )
        if any(current[:len(old)] != old for old, current in pairs):
            raise ValueError('Battered Leg receipt lost its ordered source histories')
        if self.prone_recover is not None:
            required = (*after.consumed_execution_ids, self.prone_recover.source.id)
            if state.consumed_execution_ids[:len(required)] != required:
                raise ValueError('Battered Leg receipt lost its consumed Recover action')
        if after.minion_attack is not None:
            if state.minion_attack is None:
                raise ValueError('Battered Leg receipt lost its Minion child owner')
            for name in ('consumed_execution_ids', 'acknowledged_defeat_execution_ids',
                         'consumed_give_ground_execution_ids', 'consumed_nearby_stagger_sources',
                         'acknowledged_nearby_defeats', 'consumed_nearby_give_ground',
                         'completed_nearby_stagger_sources'):
                old_ids = getattr(after.minion_attack, name)
                if getattr(state.minion_attack, name)[:len(old_ids)] != old_ids:
                    raise ValueError('Battered Leg receipt lost its Minion child history')
        if state.round_state.round_number == after.round_state.round_number:
            old_ids = after.round_state.completed_turn_entity_ids
            if state.round_state.completed_turn_entity_ids[:len(old_ids)] != old_ids:
                raise ValueError('Battered Leg receipt cannot regress completed turns')
            if not set(after.round_state.excluded_turn_entity_ids) <= set(state.round_state.excluded_turn_entity_ids):
                raise ValueError('Battered Leg receipt cannot restore excluded turns')
            for name in ('gave_ground_entity_ids', 'free_move_used_entity_ids',
                         'difficult_terrain_tested_entity_ids'):
                if not set(getattr(after.spatial_state, name)) <= set(getattr(state.spatial_state, name)):
                    raise ValueError('Battered Leg receipt cannot reset same-round spatial usage')
            if (self.prone_stand is not None
                    and actor_id not in state.spatial_state.free_move_used_entity_ids):
                raise ValueError('Battered Leg receipt cannot reset its same-round self-stand free move')
            if self.prone_recover is not None:
                turn = state.round_state.active_turn
                if turn is not None and turn.actor_id == actor_id:
                    recorded = tuple(s.execution for s in turn.action_slots
                                     if s.execution is not None and s.execution.id == self.prone_recover.source.id)
                    if len(recorded) != 1:
                        raise ValueError('Battered Leg receipt lost its same-turn Recover action proof')
                    action = recorded[0]
                    if type(action.round_number) is not int or type(action.slot_index) is not int:
                        raise TypeError('Recover action proof must retain strict integer indices')
                    _readmit(action)
                    if action != self.prone_recover.recover.slot.execution:
                        raise ValueError('Battered Leg receipt has another Recover action proof')
                elif actor_id not in state.round_state.completed_turn_entity_ids:
                    raise ValueError('Battered Leg receipt cannot forget its completed Recover turn')


def require_battered_leg_completion(state):
    """Execution admission, separate from storage of unsupported snapshots."""
    injury = state.roster.participant(state.wizard.actor_id).state.injury
    if not any(w.entry_id == WoundEntryId.BATTERED_LEG for w in injury.wounds):
        return
    _strict_injury_snapshot(injury)
    receipt = state.battered_leg_receipt
    if not isinstance(receipt, NpcBatteredLegCompletionWitness):
        raise ValueError('Battered Leg requires its completed Endurance witness')
    _readmit(receipt)
    receipt.validate_storage(state)
    if injury != receipt.completed_injury:
        raise ValueError('Battered Leg current injury is outside the completed Test scope')


@dataclass(frozen=True, slots=True)
class NpcRosterBatteredLegRequest:
    id: str
    state: NpcRosterCastingState
    attack: NpcRosterChampionAttackResult
    endurance_profile: InlineProfile
    unmounted: bool
    no_external_condition_sources: bool

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError('Battered Leg request requires a nonblank id')
        _true(self.unmounted, 'unmounted')
        _true(self.no_external_condition_sources, 'no_external_condition_sources')
        if not isinstance(self.endurance_profile, InlineProfile):
            raise TypeError('Wizard Endurance requires an authored InlineProfile')
        _readmit(self.endurance_profile)
        after = _attack_source(self.attack)
        _owner(self.state)
        if self.state.battered_leg_receipt is not None or self.state != after:
            raise ValueError('Battered Leg Test requires the exact current pending owner')
        self.k1_request

    @property
    def k1_request(self):
        return _k1(self.attack, self.endurance_profile, self.id, self.unmounted)


@dataclass(frozen=True, slots=True)
class NpcRosterBatteredLegResult:
    source: NpcRosterBatteredLegRequest
    endurance: BatteredLegEnduranceTestResult

    def __post_init__(self):
        if not isinstance(self.source, NpcRosterBatteredLegRequest):
            raise TypeError('Battered Leg result requires its full source')
        _readmit(self.source)
        if not isinstance(self.endurance, BatteredLegEnduranceTestResult):
            raise TypeError('Battered Leg result requires its K1 completion')
        _readmit(self.endurance)
        if self.endurance.request != self.source.k1_request:
            raise ValueError('Battered Leg Test differs from its authored full source')

    @property
    def state(self):
        _readmit(self.source)
        _readmit(self.endurance)
        old = self.source.state
        actor_id = old.wizard.actor_id
        injury = self.endurance.wound_result.state
        roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=injury))
                                 if p.state.actor_id == actor_id else p for p in old.roster.participants))
        return replace(old, roster=roster,
            champion_attack=replace(old.champion_attack, roster=roster, pending=None),
            minion_attack=None if old.minion_attack is None else replace(old.minion_attack, roster=roster),
            battered_leg_receipt=NpcBatteredLegCompletionWitness(
                self.source.attack, self.endurance, self.source.no_external_condition_sources))
