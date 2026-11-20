"""One Allies in Arms removal from a completed ordinary Help, PG1.4 III73.

The accepted C7 timing is after the final Help Test, including zero successes.
The encounter owner supplies the actual removable target and consumes the Help
receipt once. This source model cannot decide whether an ongoing Wound still
applies Staggered, nor grant a new action or another Test.
"""
from dataclasses import dataclass, replace

from towr.domain.talent_test_source import validate_completed_talent_test
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.help_models import (
    HelpActionExecutionRequest, HelpActionExecutionResult, HelpBonusSnapshot, _expected_help_execution,
)
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent

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
        validate_completed_talent_test(source.help_test, self.execution.help_test_result)
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
