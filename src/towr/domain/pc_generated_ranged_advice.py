"""Prepared Close Protection and bounded shooting-mode advice (ADR-0124).

Only present source facts enter this finite forecast. No RNG, resource spends,
proofs or replacement runtime states are created while comparing alternatives.
"""
from dataclasses import replace
from functools import lru_cache

from towr.domain.condition_models import Condition
from towr.domain.ranged_weapon_profiles import (
    RangedWeaponId, REPEATER_SHOOTING_BONUS_RULE_ID, ranged_weapon_combat_profile,
    ranged_weapon_reload_profile,RangedReloadTrigger,RangedWeaponRange,
)
from towr.domain.test_models import DiceModifier, Skill, TestRequest


def pc_shooting_protection(state, target_id, attacker_id, test_id, *,
        conditions=None, extra_dice=0, enhancement=None):
    """Choose a legal actual prepared Test; ties prefer Defence, Melee, Athletics.

    The prospective arguments support Recover/Help/potion advice only. They do
    not modify the owner, its hand facts or a previously bound Help receipt.
    """
    from towr.domain.pc_backup_weapon_models import pc_active_weapon
    from towr.domain.pc_heavy_wound_models import usable_weapon_hand
    from towr.domain.pc_help_models import build_pc_test_help
    from towr.domain.pc_melee_result_models import _pc_test
    from towr.domain.pc_potion_models import pc_effective_definition
    from towr.domain.pc_shield_models import pc_has_working_shield
    from towr.domain.pc_talent_advice import pc_test_distribution
    from towr.domain.pc_weapon_models import pc_weapon_test_modifiers
    from towr.domain.pc_short_opening_models import pc_enemy_range

    member = state.participant(target_id)
    actual_conditions = member.injury.conditions
    conditions = actual_conditions if conditions is None else conditions
    close = pc_enemy_range(state,attacker_id,target_id) is RangedWeaponRange.CLOSE
    skills = (((Skill.DEFENCE,) if pc_has_working_shield(member) else ())
        + ((Skill.MELEE,) if close else ()) + (Skill.ATHLETICS,))
    candidates = []
    for skill in skills:
        modifiers = (DiceModifier('tactics:prospective-help', extra_dice),) if extra_dice else ()
        request = _pc_test(state, target_id, test_id, skill, modifiers)
        if conditions != actual_conditions and usable_weapon_hand(member) is not None:
            weapon = pc_active_weapon(state, target_id)
            old_ids = {modifier.rule_id for modifier in pc_weapon_test_modifiers(weapon, skill, actual_conditions)}
            new = pc_weapon_test_modifiers(weapon, skill, conditions)
            request = replace(request, dice_modifiers=tuple(m for m in request.dice_modifiers
                if m.rule_id not in old_ids) + new)
        if conditions.has(Condition.DRAINED):
            request = replace(request, dice_modifiers=tuple(m for m in request.dice_modifiers if m.amount <= 0))
        if enhancement is not None:
            pc = pc_effective_definition(state, target_id)
            pc = replace(pc, **{enhancement: getattr(pc, enhancement)+1})
            profile = {Skill.DEFENCE: pc.defence_profile, Skill.MELEE: pc.melee_profile,
                Skill.ATHLETICS: pc.athletics_profile}[skill]
            request = replace(request, profile=profile)
        request, _ = build_pc_test_help(state, target_id, skill, request)
        distribution = pc_test_distribution(state, target_id, skill, request, include_policy=True)
        mean = sum(successes*chance for successes, chance in enumerate(distribution))
        candidates.append((mean, skill, request))
    best = candidates[0]
    for candidate in candidates[1:]:
        if candidate[0] > best[0]+1e-12:
            best = candidate
    return best[1], best[2]


def pc_close_shooting_protection(state, target_id, attacker_id, test_id, **prospective):
    """Existing callers share the actual distance-aware Protection choice."""
    return pc_shooting_protection(state,target_id,attacker_id,test_id,**prospective)


@lru_cache(maxsize=4096)
def _repeater_choice(ordinary_value, bonus_value, reload_distribution, horizon,
        required_successes=3):
    """Exact finite action forecast with the actual required reload successes.

    loaded=0; positive values are remaining Exacting successes. On a loaded turn
    the actor may choose anew. A reload action has no immediate hit utility.
    """
    @lru_cache(maxsize=None)
    def value(turns, remaining):
        if turns <= 0:
            return 0.0
        if remaining:
            return sum(chance*value(turns-1,max(0,remaining-successes))
                for successes,chance in enumerate(reload_distribution))
        return max(ordinary_value+value(turns-1,0),
            bonus_value+value(turns-1,required_successes))
    ordinary = ordinary_value+value(horizon-1,0)
    bonus = bonus_value+value(horizon-1,required_successes)
    return bonus > ordinary+1e-12


def npc_repeater_bonus(state, actor_id, attacker: TestRequest,
        defender: TestRequest | None, target_id, *, target_conditions=None, resilience=None,
        defender_skill=None):
    """Select the optional mode before dice using the real prepared shot.

    ``attacker`` is the ordinary request, before the repeater bonus. Caller
    retains the returned mode in the actual source-bound preparation proof.
    """
    from towr.domain.pc_npc_ranged_models import npc_ranged_reload_test
    from towr.domain.pc_shield_models import pc_shield_resilience
    from towr.domain.pc_talent_advice import pc_test_distribution
    from towr.domain.pc_tactical_models import _distribution, _impact_value

    enemy = state.enemy(actor_id)
    components = enemy.definition.generated_components
    if components is None or components.ranged is None:
        return False
    weapon_id = RangedWeaponId(components.weapon.value)
    reload_profile = ranged_weapon_reload_profile(weapon_id)
    if reload_profile.trigger is not RangedReloadTrigger.AFTER_OPTIONAL_BONUS:
        return False
    if enemy.state.injury.conditions.has(Condition.DRAINED):
        return False
    bonus_dice = reload_profile.optional_shooting_bonus_dice
    boosted = replace(attacker,dice_modifiers=(*attacker.dice_modifiers,
        DiceModifier(REPEATER_SHOOTING_BONUS_RULE_ID,bonus_dice)))
    target = state.participant(target_id)
    conditions = target.injury.conditions if target_conditions is None else target_conditions
    resilience = pc_shield_resilience(state,target_id) if resilience is None else resilience
    profile = ranged_weapon_combat_profile(weapon_id)
    resistance = resilience.toughness if profile.ignores_armour else resilience.total
    attack_profile = enemy.definition.attacks[0]
    protection = ((1.0,) if defender is None else _distribution(defender) if defender_skill is None
        else pc_test_distribution(state,target_id,defender_skill,defender,include_policy=True))
    def utility(request):
        damage = attack_profile.damage.base + (profile.armoured_target_damage_bonus
            if resilience.is_armoured else 0)
        return _impact_value(_distribution(request),protection,damage,
            resistance,attack_profile.damage.success_multiplier,
            conditions.has(Condition.STAGGERED),conditions.has(Condition.DEFENCELESS))
    reload = npc_ranged_reload_test(state,actor_id,'tactics:reload')
    unavailable = (*state.round_state.completed_turn_entity_ids,*state.round_state.excluded_turn_entity_ids)
    horizon = min(3,max(0,state.source.max_rounds-state.round_state.round_number+1
        - int(actor_id in unavailable)))
    if not horizon:
        return False
    return _repeater_choice(utility(attacker),utility(boosted),_distribution(reload),horizon,
        reload_profile.required_successes)
