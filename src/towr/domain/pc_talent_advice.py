"""Finite prepared-Test advice for PC Talents and the existing Fate policy.

No initial rolls, receipts, RNG calls or resource spends are created here.
"""
from dataclasses import replace
from functools import lru_cache

from towr.domain.condition_models import Condition,ConditionState
from towr.domain.generated_npc_models import GeneratedTalent
from towr.domain.pc_melee_models import PcFatePolicy,PcMeleeWeapon
from towr.domain.pc_weapon_models import pc_weapon_test_modifiers
from towr.domain.pc_generated_talents import WILD_ATTACK_RULE_ID
from towr.domain.test_models import Skill,TestRequest,TestQuality,QualityModifier,_expected_initial_roll_parameters


def pc_has_combat_talent(state,actor: str,talent: GeneratedTalent) -> bool:
    return any(value.talent is talent for value in state.source.participant(actor).combat_talents)


def pc_wild_eligible(state,actor: str) -> bool:
    from towr.domain.pc_heavy_wound_models import usable_weapon_hand
    member=state.participant(actor)
    return (pc_has_combat_talent(state,actor,GeneratedTalent.WILD_ATTACK)
        and not member.injury.dead and not member.injury.conditions.has(Condition.DEFENCELESS)
        and not member.injury.conditions.has(Condition.STAGGERED)
        and not member.injury.conditions.has(Condition.DRAINED)
        and usable_weapon_hand(member) is not None)


def pc_wild_test_variant(request: TestRequest,weapon: PcMeleeWeapon,
        conditions: ConditionState) -> TestRequest:
    """Prepare a hypothetical next Melee Test after its voluntary price.

    Caller establishes eligibility. Only actor weapon modifiers change; actual
    target modifiers, Help, conditions and the ordinary dice cap are retained.
    """
    old=pc_weapon_test_modifiers(weapon,Skill.MELEE,conditions)
    after=conditions.with_condition(Condition.STAGGERED)
    new=pc_weapon_test_modifiers(weapon,Skill.MELEE,after)
    old_ids={modifier.rule_id for modifier in old}
    return replace(request,dice_modifiers=tuple(m for m in request.dice_modifiers
        if m.rule_id not in old_ids)+new,
        quality_modifiers=(*request.quality_modifiers,QualityModifier(WILD_ATTACK_RULE_ID,TestQuality.GLORIOUS)))


@lru_cache(maxsize=4096)
def _fated_distribution(dice: int,threshold: int,grim: bool,maximum_initial: int,delta: int):
    from towr.domain.pc_tactical_models import _binomial
    initial=_binomial(dice,threshold*10)
    values=[0.0]*(dice+1)
    for successes,chance in enumerate(initial):
        useful=successes>0 if grim else successes<dice
        spend=successes<=maximum_initial and useful
        if grim:
            # Fate cancels Grim before success rerolls; otherwise only the
            # originally successful dice can remain successes after reroll.
            conditional=((1.0,) if successes==0 else _binomial(successes,threshold*10))
            if spend:
                values[successes]+=chance
            else:
                for final,probability in enumerate(conditional):
                    values[final]+=chance*probability
        elif spend:
            for rerolled,probability in enumerate(_binomial(dice-successes,threshold*10)):
                values[successes+rerolled]+=chance*probability
        else:
            values[successes]+=chance
    if not delta:
        return tuple(values)
    shifted=[0.0]*(max(0,dice+delta)+1)
    for successes,chance in enumerate(values):
        shifted[max(0,successes+delta)]+=chance
    return tuple(shifted)


def pc_test_distribution(state,actor: str,skill: Skill,request: TestRequest,*,include_policy: bool=False):
    """Account for a legal selected future Fate window, never spend its budget.

    New combat-Talent actors use this comparison. Existing actors keep their
    original bounded advice. Reroll-lock contexts retain the established exact
    quality distribution rather than inventing a new lock-dependent policy.
    """
    from towr.domain.pc_tactical_models import _distribution
    source=state.source.participant(actor)
    policy=source.glorious_policy
    member=state.participant(actor)
    if ((not source.combat_talents and not include_policy) or source.fate_policy is not PcFatePolicy.CONFIGURED
            or policy is None or skill not in policy.skills or request.reroll_locks
            or any(item.quality is TestQuality.GLORIOUS for item in request.quality_modifiers)):
        return _distribution(request)
    cost=0 if member.fate.lucky_free_spend_available else 1
    if not member.fate.can_spend or member.fate.remaining_spends-cost<policy.minimum_remaining_spends:
        return _distribution(request)
    parameters=_expected_initial_roll_parameters(request)
    dice,threshold=parameters[5:7]
    grim=any(item.quality is TestQuality.GRIM for item in request.quality_modifiers)
    return _fated_distribution(dice,threshold,grim,policy.maximum_initial_successes,
        sum(item.amount for item in request.success_modifiers))
