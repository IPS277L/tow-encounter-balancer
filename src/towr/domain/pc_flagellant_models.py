"""Bounded Feel No Pain causes and a real self-Recover healing receipt."""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    ProfileInjuryState, ProfileNpcType, ProfileStateChangeRequest, ProfileWoundRequest, ProfileWoundResult,
)
from towr.domain.magic_models import WizardMagicState
from towr.domain.pc_flagellant_policy_models import (
    FLAGELLANT_DEFINITION_IDS, FEEL_NO_PAIN_RULE_ID, FLAGELLANT_RECOVER_RULE_ID, PcFeelNoPainPolicy,
)
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.recover_models import (
    RecoverActionExecutionRequest, RecoverActionExecutionResult, RecoverConditionTarget,
    RecoverMode, RecoverStandardChoice,
)
from towr.domain.resolution_models import AttackerStaggerRequest, FirstStaggerWoundSpec


def flagellant_conditions(definition, conditions):
    """Unbreakable blocks only the Broken value, regardless of effect classification."""
    if definition.id not in FLAGELLANT_DEFINITION_IDS:
        return conditions
    validate_pc_book_npc_definition(definition)
    return conditions.without_condition(Condition.BROKEN)


def validate_pc_flagellant_conditions(state):
    for enemy in state.enemies:
        if flagellant_conditions(enemy.definition, enemy.state.injury.conditions) != enemy.state.injury.conditions:
            raise ValueError('Unbreakable Flagellant cannot retain Broken in its owner state')


def pc_flagellant_policy(source, actor_id):
    return next((p for p in source.npc_flagellant_policies if p.actor_id == actor_id), None)


def pc_flagellant_first_stagger_spec(state, actor_id):
    policy = pc_flagellant_policy(state.source, actor_id)
    if policy is None or policy.feel_no_pain is not PcFeelNoPainPolicy.WOUND_AT_ZERO:
        return None
    enemy = state.enemy(actor_id)
    validate_pc_book_npc_definition(enemy.definition)
    if enemy.definition.id not in FLAGELLANT_DEFINITION_IDS:
        raise ValueError('Feel No Pain requires its canonical Flagellant')
    injury = enemy.state.injury
    if injury.defeated or injury.wounds != 0 or injury.conditions.has(Condition.STAGGERED):
        return None
    return FirstStaggerWoundSpec(FEEL_NO_PAIN_RULE_ID)


def pc_flagellant_recover_selected(state, actor_id):
    policy = pc_flagellant_policy(state.source, actor_id)
    if policy is None or not policy.recover_when_wounded:
        return False
    enemy = state.enemy(actor_id)
    validate_pc_book_npc_definition(enemy.definition)
    if enemy.definition.id not in FLAGELLANT_DEFINITION_IDS:
        raise ValueError('Flagellant Recover requires its canonical source')
    return not enemy.state.injury.defeated and enemy.state.injury.wounds == 1 and actor_id not in state.exited_npc_ids


def build_pc_npc_recover(state):
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    turn = state.round_state.active_turn
    if turn is None or not pc_flagellant_recover_selected(state, turn.actor_id):
        raise ValueError('no selected wounded Flagellant can Recover')
    actor = turn.actor_id
    conditions = state.enemy(actor).state.injury.conditions
    target = lambda condition: (RecoverConditionTarget(actor, conditions, None)
        if conditions.has(condition) else None)
    return RecoverActionExecutionRequest(pc_melee_action_id(state, actor)+':npc-recover:execute',
        state.round_state, actor, conditions, True, 1, RecoverMode.STANDARD,
        RecoverStandardChoice(WizardMagicState(), staggered_target=target(Condition.STAGGERED),
            prone_target=target(Condition.PRONE)))


def flagellant_recovered_injury(before):
    if type(before) is not ProfileInjuryState:
        raise TypeError('Flagellant recovery requires its exact profile injury')
    replace(before)
    if (type(before.wounds) is not int or before.wounds != 1 or before.wound_limit != 2
            or before.defeated or before.defeat_cause is not None):
        raise ValueError('only a living wounded Flagellant heals one Wound')
    return replace(before, wounds=0,
        conditions=before.conditions.without_condition(Condition.STAGGERED).without_condition(Condition.PRONE))


@dataclass(frozen=True, slots=True)
class PcNpcRecoverProof:
    request: RecoverActionExecutionRequest
    execution: RecoverActionExecutionResult
    previous_injury: ProfileInjuryState
    injury: ProfileInjuryState
    rule_id: str = FLAGELLANT_RECOVER_RULE_ID

    @property
    def actor_id(self):
        return self.request.actor_id

    def __post_init__(self):
        if type(self.rule_id) is not str or self.rule_id != FLAGELLANT_RECOVER_RULE_ID:
            raise ValueError('NPC Recover healing requires its Feel No Pain rule')
        if type(self.request) is not RecoverActionExecutionRequest or type(self.execution) is not RecoverActionExecutionResult:
            raise TypeError('NPC Recover requires its actual request and execution')
        if type(self.previous_injury) is not ProfileInjuryState or type(self.injury) is not ProfileInjuryState:
            raise TypeError('NPC Recover requires exact before/after profile injuries')
        replace(self.request)
        replace(self.execution)
        if self.execution.source_request != self.request or self.request.actor_conditions != self.previous_injury.conditions:
            raise ValueError('NPC Recover is detached from its source or actor Conditions')
        if self.injury != flagellant_recovered_injury(self.previous_injury):
            raise ValueError('NPC Recover changed its single-Wound heal or standard self benefits')


def build_pc_flagellant_miss_wound(state):
    """Resolve this actor's actual pending miss, not the target's last incoming hit."""
    if (state.pending_wound is not None or not state.pending
            or type(state.pending[0]) is not AttackerStaggerRequest
            or state.round_state.active_turn is None):
        return None
    actor = state.round_state.active_turn.actor_id
    if actor not in state.source.enemy_activation_order or pc_flagellant_first_stagger_spec(state, actor) is None:
        return None
    return ProfileWoundRequest(state.pending[0].attack_id+':feel-no-pain:wound', ProfileNpcType.BRUTE,
        state.enemy(actor).state.injury)


def expected_flagellant_miss_wound(request):
    """The complete single-Wound witness for this bounded replacement."""
    return ProfileWoundResult(request.id,
        replace(request.state,wounds=1,conditions=request.state.conditions.without_condition(Condition.STAGGERED)),
        1,1,ProfileStateChangeRequest(ProfileNpcType.BRUTE,0,1,False),())


@dataclass(frozen=True, slots=True)
class PcFlagellantMissWoundProof:
    actor_id: str
    source: AttackerStaggerRequest
    previous_injury: ProfileInjuryState
    wound: ProfileWoundResult
    rule_id: str = FEEL_NO_PAIN_RULE_ID

    def __post_init__(self):
        if type(self.rule_id) is not str or self.rule_id != FEEL_NO_PAIN_RULE_ID:
            raise ValueError('miss Wound replacement requires its Feel No Pain rule')
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('miss Feel No Pain requires its exact actor ID')
        if type(self.source) is not AttackerStaggerRequest or type(self.wound) is not ProfileWoundResult:
            raise TypeError('miss Feel No Pain requires its typed miss and profile-Wound result')
        if type(self.previous_injury) is not ProfileInjuryState:
            raise TypeError('miss Feel No Pain requires its exact previous injury')
        replace(self.previous_injury)
        before = self.previous_injury
        if (before.wounds != 0 or before.wound_limit != 2 or before.defeated
                or before.conditions.has(Condition.STAGGERED)):
            raise ValueError('selected miss Feel No Pain requires a healthy unstaggered Flagellant')
        expected = expected_flagellant_miss_wound(ProfileWoundRequest(
            self.source.attack_id+':feel-no-pain:wound',ProfileNpcType.BRUTE,before))
        if self.wound != expected:
            raise ValueError('miss Feel No Pain changed its single accepted profile Wound/ACK')
