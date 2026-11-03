"""One source-bound standard Recover for Battered Leg Prone.

PG1.4 Rules / Recover p118, Prone p123, Wounds Table p190/5;
Interrupted Casting pp156-157. Recover's pool reduction precedes its skipped Test.
"""
from dataclasses import dataclass, replace

from towr.domain.action_execution_models import SkippedCastingTestAfterActionResult
from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState, WoundConditionEffect, WoundEffectDuration
from towr.domain.magic_models import MiscastPoolOutcome, WizardMagicState
from towr.domain.npc_action_interruption import validate_npc_casting_interruption
from towr.domain.npc_roster_battered_leg_models import (
    NpcBatteredLegCompletionWitness, _owner, _readmit, require_battered_leg_completion,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_roster_turn_models import _identifier, _validate_phase_source
from towr.domain.recover_models import (
    RecoverActionExecutionRequest, RecoverActionExecutionResult, RecoverConditionChange,
    RecoverConditionTarget, RecoverMode, RecoverStandardChoice, RecoverStandardResult,
)
from towr.domain.turn_models import ActionSlotGrant, CombatActionDeclaration, CombatActionKind


def _magic(state):
    if not isinstance(state, WizardMagicState):
        raise TypeError('Recover requires its typed magic state')
    for field in ('miscast_dice', 'casting_successes', 'latest_casting_roll_successes'):
        if type(getattr(state, field)) is not int:
            raise TypeError('Recover magic counts must retain strict integers')
    _readmit(state)


def _conditions(state):
    if (type(state.conditions) is not frozenset
            or not all(isinstance(value, Condition) for value in state.conditions)):
        raise TypeError('Recover Conditions must retain their typed frozenset')
    _readmit(state)


@dataclass(frozen=True, slots=True)
class NpcRosterBatteredLegRecoverRequest:
    id: str
    state: NpcRosterCastingState
    actor_id: str

    def __post_init__(self):
        _identifier(self.id)
        _identifier(self.actor_id)
        _owner(self.state)
        _validate_phase_source(self.state)
        state = self.state
        if self.actor_id != state.wizard.actor_id:
            raise ValueError('Battered Leg Recover requires the owner Wizard')
        if self.id in state.consumed_execution_ids:
            raise ValueError('Battered Leg Recover action was already consumed')
        turn = state.round_state.active_turn
        if (turn is None or turn.actor_id != self.actor_id or len(turn.action_slots) != 1
                or turn.action_slots[0].grant is not ActionSlotGrant.STANDARD
                or turn.action_slots[0].executed
                or turn.action_slots[0].declaration != CombatActionDeclaration(CombatActionKind.RECOVER)):
            raise ValueError('Battered Leg Recover requires one active unexecuted standard Recover slot')
        receipt = state.battered_leg_receipt
        if not isinstance(receipt, NpcBatteredLegCompletionWitness):
            raise ValueError('Battered Leg Recover requires its full Endurance witness')
        if receipt.prone_stand is not None or receipt.prone_recover is not None:
            raise ValueError('Battered Leg Prone removal was already consumed')
        require_battered_leg_completion(state)
        injury = state.roster.participant(self.actor_id).state.injury
        expected = WoundConditionEffect(1, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED)
        if (receipt.endurance.test_result.succeeded or not isinstance(injury, CharacterInjuryState)
                or injury.dead or injury.conditions.conditions != frozenset((Condition.PRONE,))
                or injury.active_wound_effects != (expected,)):
            raise ValueError('Battered Leg Recover requires only its failed-Test sourced Prone')
        self.recover_request

    @property
    def recover_request(self) -> RecoverActionExecutionRequest:
        state = self.state
        actor = state.roster.participant(self.actor_id)
        zone = state.spatial_state.placement_for(self.actor_id).zone_id
        enemy_in_zone = any(
            p.state.side is not actor.state.side
            and not (p.state.injury.dead if isinstance(p.state.injury, CharacterInjuryState)
                     else p.state.injury.defeated)
            and state.spatial_state.placement_for(p.state.actor_id).zone_id == zone
            for p in state.roster.participants)
        return RecoverActionExecutionRequest(self.id, state.round_state, self.actor_id,
            actor.state.injury.conditions, enemy_in_zone, 1, RecoverMode.STANDARD,
            RecoverStandardChoice(state.wizard.magic_state,
                prone_target=RecoverConditionTarget(self.actor_id, actor.state.injury.conditions, None)))


@dataclass(frozen=True, slots=True)
class NpcRosterBatteredLegRecoverResult:
    source: NpcRosterBatteredLegRecoverRequest
    recover: RecoverActionExecutionResult
    interruption: SkippedCastingTestAfterActionResult | None

    def __post_init__(self):
        if not isinstance(self.source, NpcRosterBatteredLegRecoverRequest):
            raise TypeError('Battered Leg Recover result requires its typed full source')
        _readmit(self.source)
        if not isinstance(self.recover, RecoverActionExecutionResult):
            raise TypeError('Battered Leg Recover requires its typed action result')
        recover = self.recover
        for value in (recover.source_request.choice, recover.source_request,
                      recover.resolution, recover.slot.declaration, recover.slot,
                      recover.slot.execution, recover.previous_round_state, recover.round_state, recover):
            _readmit(value)
        expected_request = self.source.recover_request
        if recover.source_request != expected_request or recover.source_request.mode is not RecoverMode.STANDARD:
            raise ValueError('Battered Leg Recover differs from its exact standard self source')
        if not isinstance(recover.resolution, RecoverStandardResult):
            raise TypeError('Battered Leg Recover requires the standard resolution')
        resolution = recover.resolution
        for magic in (resolution.source.magic_state, resolution.previous_magic_state, resolution.magic_state):
            _magic(magic)
        _conditions(recover.source_request.actor_conditions)
        _conditions(resolution.source.prone_target.conditions)
        if type(resolution.miscast_dice_removed) is not int or type(resolution.condition_changes) is not tuple:
            raise TypeError('Recover removal count and condition changes must retain their types')
        if recover.source_request.actor_has_enemy_in_zone is not expected_request.actor_has_enemy_in_zone:
            raise TypeError('Recover enemy fact must retain its boolean')
        if recover.slot.grant is not ActionSlotGrant.STANDARD or recover.slot.declaration.kind is not CombatActionKind.RECOVER:
            raise TypeError('Recover must retain its typed standard declaration')
        for value in (recover.previous_round_state, recover.round_state):
            if type(value.round_number) is not int:
                raise TypeError('Recover round indices must retain strict integers')
        if (type(recover.slot.execution.round_number) is not int
                or type(recover.slot.execution.slot_index) is not int):
            raise TypeError('Recover receipt indices must retain strict integers')
        for change in resolution.condition_changes:
            _readmit(change)
            _conditions(change.previous_conditions)
            _conditions(change.conditions)
            if type(change.removed_conditions) is not tuple:
                raise TypeError('Recover removed Conditions must retain a tuple')
        old_magic = self.source.state.wizard.magic_state
        removed = min(1, old_magic.miscast_dice)
        expected_resolution = RecoverStandardResult(expected_request.choice,
            (RecoverConditionChange(self.source.actor_id, expected_request.actor_conditions,
                expected_request.actor_conditions.without_condition(Condition.PRONE), (Condition.PRONE,)),),
            old_magic, replace(old_magic, miscast_dice=old_magic.miscast_dice - removed), removed, None, None)
        if resolution != expected_resolution or recover.applied_rule_ids != (expected_request.rule_id,):
            raise ValueError('Battered Leg Recover must remove only its Prone and one Miscast die')
        if self.interruption is not None:
            if not isinstance(self.interruption, SkippedCastingTestAfterActionResult):
                raise TypeError('Recover interruption must retain its typed result')
            for value in (self.interruption.source, self.interruption.miscast_pool,
                          self.interruption.state, self.interruption):
                _readmit(value)
            _magic(self.interruption.state)
            _magic(self.interruption.miscast_pool.state)
            if (type(self.interruption.source.amount) is not int
                    or type(self.interruption.miscast_pool.dice_added) is not int
                    or type(self.interruption.miscast_pool.previous_miscast_dice) is not int):
                raise TypeError('Recover interruption dice must retain strict integers')
            if not isinstance(self.interruption.miscast_pool.outcome, MiscastPoolOutcome):
                raise TypeError('Recover interruption must retain its typed outcome')
            roll = self.interruption.miscast_pool.roll_request
            if roll is not None:
                _readmit(roll)
                if type(roll.pool_dice_count) is not int:
                    raise TypeError('Recover Miscast roll must retain its strict pool count')
        intermediate = replace(self.source.state, wizard=replace(self.source.state.wizard,
            magic_state=resolution.magic_state))
        validate_npc_casting_interruption(intermediate, self.source.actor_id, self.source.id,
                                         recover.slot.execution, self.interruption)

    @property
    def completed_injury(self) -> CharacterInjuryState:
        injury = self.source.state.roster.participant(self.source.actor_id).state.injury
        return replace(injury, conditions=injury.conditions.without_condition(Condition.PRONE), active_wound_effects=())

    @property
    def state(self) -> NpcRosterCastingState:
        _readmit(self)
        old = self.source.state
        roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=self.completed_injury))
                                 if p.state.actor_id == self.source.actor_id else p
                                 for p in old.roster.participants))
        magic = self.recover.resolution.magic_state if self.interruption is None else self.interruption.state
        pending = (self.interruption if self.interruption is not None
                   and self.interruption.miscast_pool.roll_request is not None else None)
        return replace(old, roster=roster, wizard=replace(old.wizard, magic_state=magic),
            round_state=self.recover.round_state,
            champion_attack=replace(old.champion_attack, roster=roster, round_state=self.recover.round_state),
            minion_attack=None if old.minion_attack is None else replace(old.minion_attack, roster=roster),
            consumed_execution_ids=(*old.consumed_execution_ids, self.source.id),
            pending_interruption=pending,
            battered_leg_receipt=replace(old.battered_leg_receipt, prone_recover=self))
