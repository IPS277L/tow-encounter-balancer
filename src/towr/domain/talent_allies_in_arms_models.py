"""One Allies in Arms removal from a completed ordinary Help, PG1.4 III73.

The accepted C7 timing is after the final Help Test, including zero successes.
The encounter owner supplies the actual removable target and consumes the Help
receipt once. This source model cannot decide whether an ongoing Wound still
applies Staggered, nor grant a new action or another Test.
"""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.help_models import (
    HelpActionExecutionRequest, HelpActionExecutionResult, HelpBonusSnapshot, _expected_help_execution,
)
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent
from towr.domain.test_models import (
    DiceModifier,InlineProfile,QualityModifier,RerollLock,SuccessModifier,TestProfile,
    RollTrace, RerollTrace, TestQuality, TestRequest, TestResult,
    _expected_initial_roll_parameters,
)
from towr.domain.turn_models import (
    ActionExecutionReceipt, CombatActionSlot, CombatRoundState, CombatSide,CombatTurnParticipant,CombatTurnState,
)


ALLIES_IN_ARMS_RULE_ID = 'RULE-TALENT-002:allies-in-arms'


def _conditions(value):
    if type(value) is not ConditionState or type(value.conditions) is not frozenset:
        raise TypeError('Allies in Arms requires an exact immutable ConditionState')
    replace(value)


def _round(value):
    if type(value) is not CombatRoundState:
        raise TypeError('Allies in Arms requires the complete Help round source')
    for field in ('participants', 'side_order', 'completed_turn_entity_ids', 'excluded_turn_entity_ids'):
        if type(getattr(value, field)) is not tuple:
            raise TypeError('Help round source collections must remain canonical tuples')
    for participant in value.participants:
        if type(participant) is not CombatTurnParticipant:
            raise TypeError('Help round requires its exact typed participants')
        replace(participant)
    if any(type(side) is not CombatSide for side in value.side_order):
        raise TypeError('Help round side order must retain its exact typed sides')
    turn = value.active_turn
    if type(turn) is not CombatTurnState or type(turn.action_slots) is not tuple:
        raise TypeError('Allies in Arms requires the actual immutable Help turn')
    for slot in turn.action_slots:
        if type(slot) is not CombatActionSlot:
            raise TypeError('Help source action slots must retain their exact type')
        replace(slot.declaration)
        replace(slot)
        if slot.execution is not None:
            if type(slot.execution) is not ActionExecutionReceipt:
                raise TypeError('Help execution must retain its actual typed receipt')
            replace(slot.execution)
    replace(turn)
    replace(value)


def _help_test(request, result):
    """Check recorded dice against the bound final Test, without RNG or policy.

    Glorious permits any legal subset of failures; Grim requires every eligible
    success. A Talent consumer cannot silently replace those recorded choices.
    """
    if type(request) is not TestRequest or type(result) is not TestResult or type(result.trace) is not RollTrace:
        raise TypeError('Allies in Arms requires its exact final Help Test and trace')
    if type(request.profile) not in (TestProfile,InlineProfile):
        raise TypeError('Help Test requires its exact typed roll profile')
    replace(request.profile)
    for field,kind in (('dice_modifiers',DiceModifier),('quality_modifiers',QualityModifier),
            ('success_modifiers',SuccessModifier),('reroll_locks',RerollLock)):
        values = getattr(request, field)
        if type(values) is not tuple or any(type(value) is not kind for value in values):
            raise TypeError('Help Test source modifiers must remain canonical tuples')
        for value in values:
            replace(value)
            if kind is DiceModifier and type(value.bypasses_pool_cap) is not bool:
                raise TypeError('Help dice modifier cap bypass requires an exact boolean')
    replace(request)
    trace = result.trace
    for field in ('base_dice', 'pool_cap', 'regular_dice_delta', 'cap_bypassing_dice',
            'dice_before_minimum', 'rolled_dice', 'threshold', 'rolled_successes', 'success_delta', 'successes'):
        if type(getattr(trace, field)) is not int:
            raise TypeError('Help trace counters must be exact integers')
    if type(trace.minimum_die_rule_applied) is not bool or type(trace.quality) is not TestQuality:
        raise TypeError('Help trace must retain its exact minimum flag and quality')
    for values in (trace.initial_values, trace.final_values):
        if type(values) is not tuple or any(type(value) is not int or not 1 <= value <= 10 for value in values):
            raise TypeError('Help trace must retain exact d10 tuples')
    if type(trace.rerolls) is not tuple or any(type(value) is not RerollTrace for value in trace.rerolls):
        raise TypeError('Help trace must retain typed reroll tuples')
    if type(trace.applied_rule_ids) is not tuple or any(type(value) is not str for value in trace.applied_rule_ids):
        raise TypeError('Help trace must retain exact rule identifiers')
    parameters = _expected_initial_roll_parameters(request)
    if len(trace.initial_values) != parameters[5] or len(trace.final_values) != parameters[5]:
        raise ValueError('Help trace changed its actual dice pool')
    qualities = {modifier.quality for modifier in request.quality_modifiers}
    quality = (next(iter(qualities)) if len(qualities) == 1 else TestQuality.NORMAL)
    locked = {lock.value for lock in request.reroll_locks}
    eligible = tuple(index for index, value in enumerate(trace.initial_values)
        if value not in locked and (value <= parameters[6] if quality is TestQuality.GRIM else value > parameters[6]))
    indices = tuple(value.index for value in trace.rerolls)
    if any(type(index) is not int for index in indices) or indices != tuple(sorted(set(indices))):
        raise ValueError('Help reroll choices must be exact unique ordered indices')
    if (quality is TestQuality.NORMAL and indices
            or quality is TestQuality.GRIM and indices != eligible
            or quality is TestQuality.GLORIOUS and not set(indices) <= set(eligible)):
        raise ValueError('Help trace changed its legal final reroll choices')
    final = list(trace.initial_values)
    for reroll in trace.rerolls:
        if (any(type(value) is not int for value in (reroll.original, reroll.replacement))
                or not 1 <= reroll.replacement <= 10 or reroll.original != final[reroll.index]):
            raise ValueError('Help trace changed an actual rerolled die')
        final[reroll.index] = reroll.replacement
    successes = sum(value <= parameters[6] for value in final)
    delta = sum(modifier.amount for modifier in request.success_modifiers)
    rules = tuple(modifier.rule_id for values in (request.dice_modifiers, request.quality_modifiers,
        request.success_modifiers, request.reroll_locks) for modifier in values)
    expected = RollTrace(request.id, *parameters[:6], parameters[6], parameters[7], quality,
        trace.initial_values, trace.rerolls, tuple(final), successes, delta, max(0, successes+delta), rules)
    if trace != expected or type(trace.request_id) is not str:
        raise ValueError('Help trace is not canonical for its complete final Test source')


@dataclass(frozen=True, slots=True)
class AlliesInArmsApplication:
    execution: HelpActionExecutionResult
    talent: AcquiredTalent
    target_id: str
    previous: ConditionState

    def __post_init__(self):
        if type(self.execution) is not HelpActionExecutionResult:
            raise TypeError('Allies in Arms requires the actual completed ordinary Help')
        source = self.execution.source_request
        if type(source) is not HelpActionExecutionRequest or type(self.execution.bonus) is not HelpBonusSnapshot:
            raise TypeError('Allies in Arms requires exact Help request and bonus source types')
        _conditions(source.actor_conditions)
        _round(source.round_state)
        _round(self.execution.previous_round_state)
        _round(self.execution.round_state)
        replace(source)
        _help_test(source.help_test, self.execution.help_test_result)
        replace(self.execution.bonus)
        replace(self.execution)
        if self.execution != _expected_help_execution(source, self.execution.help_test_result):
            raise ValueError('Allies in Arms changed its full Help execution or receipt')
        if type(self.talent) is not AcquiredTalent:
            raise TypeError('Allies in Arms requires its actual acquired Talent source')
        replace(self.talent)
        if self.talent.id is not TalentId.ALLIES_IN_ARMS:
            raise ValueError('another Talent cannot authorize Allies in Arms')
        if type(self.target_id) is not str or self.target_id not in (source.actor_id, source.beneficiary_id):
            raise ValueError('Allies in Arms removes Staggered from its helper or that one beneficiary')
        _conditions(self.previous)
        if not self.previous.has(Condition.STAGGERED):
            raise ValueError('Allies in Arms requires an actual Staggered removal')
        if self.target_id == source.actor_id and self.previous != source.actor_conditions:
            raise ValueError('helper removal must retain its actual pre-Test Condition source')

    @property
    def conditions(self) -> ConditionState:
        """Baseline removal, not a replacement for post-Test consequences.

        The encounter owner removes only Staggered from its current state. In
        particular it must retain Critically Injured newly caused by Help.
        """
        return self.previous.without_condition(Condition.STAGGERED)
