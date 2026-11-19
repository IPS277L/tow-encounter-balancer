"""Actual alternate Recover to extinguish Ablaze, PG1.4 V118/122.

The Test removes only fire. Standard Recover benefits, item interactions and
healing do not accompany it. This owner prepares and authenticates one action;
the battle dispatcher owns selecting it and the later end-of-turn Hazard.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.fate_models import FateGloriousSpendResult
from towr.domain.recover_models import (
    RecoverActionExecutionRequest, RecoverActionExecutionResult, RecoverConditionRemovalChoice,
    RecoverConditionTarget, RecoverMode, _expected_recover_execution,
)
from towr.domain.test_models import QualityModifier, Skill, TestQuality, TestRequest
from towr.domain.turn_models import CombatActionKind
from towr.rules.recover_resolution import _complete_condition_removal_after_test

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcFateDecline, PcMeleeState


@dataclass(frozen=True, slots=True)
class PcExtinguishProof:
    request: RecoverActionExecutionRequest
    result: RecoverActionExecutionResult
    fate_decline: PcFateDecline | None = None
    glorious: FateGloriousSpendResult | None = None


def _injury(state,actor):
    return (state.participant(actor).injury if actor in state.source.pc_activation_order
        else state.enemy(actor).state.injury)


def pc_extinguish_selected(state):
    turn=state.round_state.active_turn
    if turn is None:return False
    actor=turn.actor_id
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_models import PcMeleePolicy
        from towr.domain.pc_tactical_models import select_pc_tactic
        return (state.source.participant(actor).policy is PcMeleePolicy.AUTOMATIC_COMBAT
            and select_pc_tactic(state,actor).reason=='extinguish_ablaze')
    if state.enemy(actor).definition.generated_components is None:return False
    from towr.domain.pc_npc_weapon_inventory import _utility
    return extinguish_value(state,actor)>max(0.0,_utility(state,actor))+1e-12


def _enemy_in_zone(state,actor):
    enemies=(tuple(enemy.state.actor_id for enemy in state.live_enemies)
        if actor in state.source.pc_activation_order else tuple(member.actor_id for member in state.live_party))
    if state.battlefield is None:
        return bool(enemies)
    spatial=state.battlefield.spatial
    zone=spatial.placement_for(actor).zone_id
    return any(spatial.placement_for(other).zone_id==zone for other in enemies)


def _can_extinguish(state,actor):
    injury=_injury(state,actor)
    if (not injury.conditions.has(Condition.ABLAZE) or injury.conditions.has(Condition.DEFENCELESS)
            or injury.conditions.has(Condition.BROKEN) and _enemy_in_zone(state,actor)):
        return False
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import has_ongoing_condition
        return not injury.dead and not has_ongoing_condition(injury,Condition.ABLAZE)
    return not injury.defeated and actor not in state.exited_npc_ids


def _extinguish_test(state,actor,test_id,skill,*,environmental=False):
    """Own body Test, with complete actual profile and applicable modifiers."""
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_result_models import _pc_test
        request=_pc_test(state,actor,test_id,skill)
        if environmental:
            from towr.domain.pc_armour_models import actor_armour_test_modifiers
            from towr.domain.armour_models import ITHILMAR_ENVIRONMENT_RULE_ID
            extra=tuple(modifier for modifier in actor_armour_test_modifiers(state,actor,skill,environmental=True)
                if modifier.rule_id==ITHILMAR_ENVIRONMENT_RULE_ID)
            if not state.participant(actor).injury.conditions.has(Condition.DRAINED):
                request=replace(request,dice_modifiers=(*request.dice_modifiers,*extra))
        return request
    enemy=state.enemy(actor)
    profile=next((option.test_profile for option in enemy.definition.protection if option.skill is skill),None)
    if profile is None:
        raise ValueError('NPC extinguishing advice requires its actual Athletics/Endurance profiles')
    from towr.domain.pc_armour_models import actor_armour_test_modifiers
    from towr.domain.pc_magic_models import magic_test_modifiers
    magic,quality=magic_test_modifiers(state,actor,skill)
    modifiers=(*magic,*actor_armour_test_modifiers(state,actor,skill,environmental=environmental))
    conditions=enemy.state.injury.conditions
    if conditions.has(Condition.DRAINED):
        modifiers=tuple(modifier for modifier in modifiers if modifier.amount<=0)
    if skill is Skill.ATHLETICS and conditions.has(Condition.BLINDED):
        quality=(*quality,QualityModifier('RULE-HEALTH-008:blinded',TestQuality.GRIM))
    return TestRequest(test_id,profile,modifiers,quality)


def build_pc_extinguish(state: PcMeleeState) -> RecoverActionExecutionRequest:
    turn=state.round_state.active_turn
    if (turn is None or not turn.action_slots or turn.action_slots[-1].executed
            or turn.action_slots[-1].declaration.kind is not CombatActionKind.RECOVER
            or state.pending or state.pending_wound is not None or state.magic_pending is not None):
        raise ValueError('extinguishing requires the actual unused Recover slot after mandatory consequences')
    actor=turn.actor_id
    if not _can_extinguish(state,actor):
        raise ValueError('extinguishing requires a living capable actor with removable Ablaze')
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    action_id=pc_melee_action_id(state,actor)+':extinguish'
    conditions=_injury(state,actor).conditions
    choice=RecoverConditionRemovalChoice(RecoverConditionTarget(actor,conditions,None),Condition.ABLAZE,
        _extinguish_test(state,actor,action_id+':athletics',Skill.ATHLETICS),Skill.ATHLETICS,True)
    return RecoverActionExecutionRequest(action_id,state.round_state,actor,conditions,
        _enemy_in_zone(state,actor),len(turn.action_slots),RecoverMode.REMOVE_CONDITION,choice)


def project_pc_extinguish(state: PcMeleeState,proof: PcExtinguishProof) -> dict:
    if type(proof) is not PcExtinguishProof:
        raise TypeError('extinguishing requires its exact typed proof')
    if type(proof.request) is not RecoverActionExecutionRequest or type(proof.result) is not RecoverActionExecutionResult:
        raise TypeError('extinguishing requires its exact Recover request and completed result')
    from towr.domain.pc_melee_result_models import (
        _party_update,_enemy_update,_test_result,pc_after_test,validate_pc_melee_source_types,
    )

    def same(actual,expected):
        if actual!=expected:
            raise ValueError('extinguishing changed its actual action, source Test or complete result')
        validate_pc_melee_source_types(actual,expected)

    request=build_pc_extinguish(state)
    same(proof.request,request)
    actor=request.actor_id
    actual=proof.result.resolution.test_result
    pc=actor in state.source.pc_activation_order
    if pc:
        from towr.domain.pc_fate_test_models import validate_pc_test_fate
        effective,fate=validate_pc_test_fate(state,actor,Skill.ATHLETICS,request.choice.test,
            actual,proof.fate_decline,proof.glorious)
    else:
        if proof.fate_decline is not None or proof.glorious is not None:
            raise ValueError('NPC extinguishing cannot invent a PC Fate resource')
        _test_result(request.choice.test,actual)
        effective=request.choice.test
    choice=replace(request.choice,test=effective)
    expected=_expected_recover_execution(replace(request,choice=choice),
        _complete_condition_removal_after_test(choice,actual))
    same(proof.result,expected)
    conditions=expected.resolution.conditions
    updates=dict(round_state=expected.round_state)
    if pc:
        from towr.domain.pc_heavy_wound_models import critical_for_action
        injury=pc_after_test(state,actor,critical_for_action(state.participant(actor),CombatActionKind.RECOVER))
        if injury.conditions.has(Condition.CRITICALLY_INJURED):
            conditions=conditions.with_condition(Condition.CRITICALLY_INJURED)
        updates['party']=_party_update(state,actor,injury=replace(injury,conditions=conditions),fate=fate)
    else:
        updates['enemies']=_enemy_update(state,actor,replace(_injury(state,actor),conditions=conditions))
    return updates


def extinguish_value(state: PcMeleeState,actor: str) -> float:
    """Two-turn fire shortfall avoided; exact finite Tests, no sampled futures.

    Only the immediate Athletics comparison may use current PC Fate policy.
    Future Endurance is valued without reusing that same finite Fate resource.
    """
    if actor not in (*state.source.pc_activation_order,*state.source.enemy_activation_order):
        raise ValueError('extinguishing advice requires an actual source actor')
    if not _can_extinguish(state,actor):
        return 0.0
    from towr.domain.pc_tactical_models import _distribution
    athletics=_extinguish_test(state,actor,'tactics:extinguish:'+actor,Skill.ATHLETICS)
    endurance=_extinguish_test(state,actor,'tactics:fire-risk:'+actor,Skill.ENDURANCE,environmental=True)
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_talent_advice import pc_test_distribution
        distribution=pc_test_distribution(state,actor,Skill.ATHLETICS,athletics,include_policy=True)
    else:
        distribution=_distribution(athletics)
    success=sum(chance for successes,chance in enumerate(distribution) if successes>0)
    shortfall=sum(max(0,2-successes)*chance for successes,chance in enumerate(_distribution(endurance)))
    return success*shortfall*2
