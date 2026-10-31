"""Narrow M8 handoff checks; PG1.4 Rules / Dropping Prone120, Prone123."""
from towr.domain.condition_models import Condition
from towr.domain.npc_attack_preparation_models import NpcProtectedAttackPreparationResult
from towr.domain.npc_roster_models import NpcParticipantSnapshot
from towr.domain.resolution_models import KernelAttackRequest
from towr.domain.test_models import DiceModifier, Skill


PRONE_TARGET_RULE_ID = 'RULE-COMBAT-009:prone-target'


def _validate_prone_shooting(
    actor: NpcParticipantSnapshot, target: NpcParticipantSnapshot,
    prepared: NpcProtectedAttackPreparationResult, kernel: KernelAttackRequest,
) -> bool:
    """Check the full prepared evidence without projecting away Conditions."""
    target_prone = target.state.injury.conditions.has(Condition.PRONE)
    scoped = target_prone or actor.state.injury.conditions.has(Condition.PRONE)
    modifiers = prepared.npc_attack.source_request.dice_modifiers
    if not scoped:
        if any(m.rule_id == PRONE_TARGET_RULE_ID for m in modifiers):
            raise ValueError('Prone target modifier requires an actual Prone target')
        return False
    if prepared.npc_attack.selected_profile.skill is not Skill.SHOOTING:
        raise ValueError('Prone attack admission is scoped to Shooting')
    expected = (DiceModifier(PRONE_TARGET_RULE_ID, -1),) if target_prone else ()
    if modifiers != expected:
        raise ValueError('Prone Shooting requires exactly the state-derived target modifier')
    if target_prone and kernel.can_target_leave_zone is not False:
        raise ValueError('Prone target cannot leave its Zone')
    for option in prepared.protection.source_request.options:
        test = option.test
        if test.dice_modifiers or test.quality_modifiers or test.success_modifiers or test.reroll_locks:
            raise ValueError('scoped Prone Protection requires unchanged normal Tests')
    return True
