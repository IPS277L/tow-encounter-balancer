"""PG1.4 III74: remove one's Staggered after a successful real Aim."""
from dataclasses import dataclass, replace

from towr.domain.aim_models import AimActionExecutionRequest, AimActionExecutionResult
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent
from towr.domain.talent_test_source import validate_completed_talent_test

CAREFUL_AIM_RULE_ID = 'RULE-TALENT-002:careful-aim'


@dataclass(frozen=True, slots=True)
class CarefulAimApplication:
    execution: AimActionExecutionResult
    talent: AcquiredTalent
    previous: ConditionState

    def __post_init__(self):
        if type(self.execution) is not AimActionExecutionResult:
            raise TypeError('Careful Aim requires its actual completed Aim')
        if type(self.execution.source_request) is not AimActionExecutionRequest:
            raise TypeError('Careful Aim requires its complete typed Aim source')
        replace(self.execution.source_request)
        replace(self.execution)
        validate_completed_talent_test(self.execution.source_request.awareness_test,
            self.execution.awareness_test_result)
        if not self.execution.awareness_test_result.succeeded:
            raise ValueError('a failed Aim cannot remove Staggered')
        if type(self.talent) is not AcquiredTalent or self.talent.id is not TalentId.CAREFUL_AIM:
            raise TypeError('Careful Aim requires its actual acquired Talent')
        replace(self.talent)
        if (type(self.previous) is not ConditionState
                or type(self.previous.conditions) is not frozenset):
            raise TypeError('Careful Aim requires its exact previous Conditions')
        replace(self.previous)
        if not self.previous.has(Condition.STAGGERED):
            raise ValueError('Careful Aim must remove an actual Staggered')

    @property
    def conditions(self):
        return self.previous.without_condition(Condition.STAGGERED)

    @property
    def rule_id(self):
        return CAREFUL_AIM_RULE_ID


def careful_aim_application(state, execution):
    """Always take a useful legal removal, after the final Awareness Test.

    The owner retains ongoing injury causes and applies only this removal to
    its post-Test injury; Critical hand-use and other new effects survive.
    """
    from towr.domain.pc_generated_talents import actor_conditions, actor_stagger_removable
    from towr.domain.talent_actor_models import actor_acquired_talents
    actor = execution.source_request.actor_id
    talent = next((entry for entry in actor_acquired_talents(state, actor)
        if entry.id is TalentId.CAREFUL_AIM), None)
    if (talent is None or not execution.awareness_test_result.succeeded
            or not actor_stagger_removable(state, actor)):
        return None
    return CarefulAimApplication(execution, talent, actor_conditions(state, actor))
