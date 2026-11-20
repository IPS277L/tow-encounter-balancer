"""Component-owned PG93 equipment and automatic Protection for generated NPCs.

No actor/catalog ID selects a weapon trait. Ordinary named/numeric definitions
keep their existing single Protection and printed modifiers.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from towr.domain.attack_models import DamageModifier,ResilienceProfile
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.npc_roster_models import NpcDefinition, NpcProtectionProfile
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_weapon_models import (
    pc_weapon_test_modifiers, pc_weapon_attack_modifiers, pc_weapon_damage_modifiers,
)
from towr.domain.test_models import DiceModifier,Skill,TestRequest,TestQuality,_expected_initial_roll_parameters

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeState

_SELECT_USE = object()


def generated_attack_modifiers(definition: NpcDefinition, conditions: ConditionState,
        target_conditions: ConditionState, *, target_mounted: bool = False,weapon_use=None,
        actor_mounted: bool = False,charging: bool = False) -> tuple[DiceModifier,...]:
    components = definition.generated_components
    if components is None:
        return ()
    if weapon_use is not None:
        from towr.domain.weapon_effect_preparation import weapon_test_modifiers
        return weapon_test_modifiers(weapon_use,conditions,target_conditions=target_conditions,
            target_mounted=target_mounted,actor_mounted=actor_mounted,charging=charging,
            talents=components.talents).modifiers
    weapon = PcMeleeWeapon(components.weapon.value)
    return (pc_weapon_test_modifiers(weapon,Skill.MELEE,conditions)
        + pc_weapon_attack_modifiers(weapon,target_conditions,target_mounted=target_mounted))


def generated_damage_modifiers(definition: NpcDefinition,
        target_resilience: ResilienceProfile,*,weapon_use=None) -> tuple[DamageModifier,...]:
    components = definition.generated_components
    if components is not None and weapon_use is not None:
        from towr.domain.weapon_effect_preparation import weapon_damage_preparation
        return weapon_damage_preparation(weapon_use,components.strength,target_resilience).modifiers
    return (() if components is None else
        pc_weapon_damage_modifiers(PcMeleeWeapon(components.weapon.value),target_resilience))


def npc_protection_test(state: PcMeleeState, defender_id: str, attacker_id: str, test_id: str,
        profile: NpcProtectionProfile | None = None, *, attack_skill: Skill = Skill.MELEE,
        weapon_use=_SELECT_USE
        ) -> tuple[NpcProtectionProfile,TestRequest]:
    """Select from actual prepared Tests; evaluating alternatives spends no RNG.

    Source order resolves an exact tie (generated Defence before Athletics).
    All contextual modifiers are shared with the real native Attack request.
    """
    from towr.domain.pc_npc_distraction_models import pc_npc_distraction_test_modifiers
    from towr.domain.pc_npc_grudge_models import pc_npc_grudge_melee_modifiers
    from towr.domain.pc_magic_models import magic_test_modifiers

    if defender_id not in state.source.npc_activation_order:
        from towr.domain.pc_actor_models import pc_actor_npc_snapshot
        from towr.domain.pc_companion_effect_models import companion_test_request
        snapshot = pc_actor_npc_snapshot(state, defender_id)
        options = ((Skill.ENDURANCE, Skill.ATHLETICS) if attack_skill is Skill.BRAWN else (Skill.ATHLETICS,))
        candidates = []
        for candidate in options:
            test = companion_test_request(state, defender_id, test_id, candidate)
            from dataclasses import replace
            from towr.domain.pc_deep_formation_models import deep_formation_modifiers
            from towr.domain.pc_actor_models import pc_actor_injury
            support=deep_formation_modifiers(state,defender_id,attacker_id,attack_skill)
            if not pc_actor_injury(state,defender_id).conditions.has(Condition.DRAINED):
                test=replace(test,dice_modifiers=(*test.dice_modifiers,*support))
            prepared = NpcProtectionProfile(snapshot.definition.source_rule_id, candidate, test.profile)
            if profile is not None and profile != prepared:
                continue
            parameters = _expected_initial_roll_parameters(test)
            candidates.append((parameters[5]*parameters[6], prepared, test))
        if not candidates:
            raise ValueError('companion Protection changed its actual natural Skill source')
        _, selected, test = max(candidates, key=lambda row: row[0])
        return selected, test
    enemy = state.enemy(defender_id)
    from towr.domain.pc_medical_models import effective_medical_injury
    injury=effective_medical_injury(state,defender_id)
    components = enemy.definition.generated_components
    from towr.domain.pc_npc_weapon_inventory import npc_has_working_shield
    working_shield=npc_has_working_shield(state,defender_id)
    profiles = ((profile,) if profile is not None else enemy.definition.protection
        if components is not None else enemy.definition.protection[:1])
    if attack_skill is Skill.BRAWN:
        profiles=tuple(option for option in (enemy.definition.protection if profile is None else (profile,))
            if option.skill in (Skill.ATHLETICS,Skill.ENDURANCE))
    elif profile is None:
        profiles=tuple(option for option in profiles if option.skill is not Skill.ENDURANCE)
    if profile is None and components is not None and attack_skill in (Skill.SHOOTING,Skill.THROWING):
        from towr.domain.pc_short_opening_models import pc_enemy_range
        from towr.domain.ranged_weapon_profiles import RangedWeaponRange
        from towr.domain.test_models import InlineProfile
        from towr.domain.generated_npc_models import generated_npc_combat_ratings
        weapon_skill,melee_rating,_=generated_npc_combat_ratings(components)
        melee=NpcProtectionProfile('RULE-EQUIPMENT-004:generated-close-melee',Skill.MELEE,
            InlineProfile(weapon_skill,melee_rating))
        profiles=((*((enemy.definition.protection[0],) if working_shield else ()),
            *((melee,) if pc_enemy_range(state,attacker_id,defender_id) is RangedWeaponRange.CLOSE else ()),
            enemy.definition.protection[1]))
    profiles=tuple(option for option in profiles if option.skill is not Skill.DEFENCE
        or working_shield or attack_skill not in (Skill.SHOOTING,Skill.THROWING) and enemy.state.wields_weapon)
    tests = []
    from towr.domain.pc_battlefield_manoeuvre_models import current_pc_charge
    charge=current_pc_charge(state,attacker_id)
    against_charge=charge is not None and charge.target_id == defender_id
    for option in profiles:
        from towr.domain.pc_npc_weapon_inventory import npc_protection_weapon_use
        actual_use=((npc_protection_weapon_use(state,defender_id,option.skill,attack_skill)
            if components is not None and option.skill in (Skill.DEFENCE,Skill.MELEE) else None)
            if weapon_use is _SELECT_USE else weapon_use)
        if (components is not None and option.skill is Skill.DEFENCE and actual_use is None
                and not injury.conditions.has(Condition.DEFENCELESS)):
            continue
        modifiers = list(pc_npc_distraction_test_modifiers(state,defender_id,attacker_id))
        if option.skill is Skill.MELEE:
            modifiers.extend(pc_npc_grudge_melee_modifiers(state,defender_id,attacker_id))
        if actual_use is not None:
            from towr.domain.weapon_effect_preparation import weapon_test_modifiers
            modifiers.extend(weapon_test_modifiers(actual_use,injury.conditions,
                against_charge=against_charge,talents=components.talents).modifiers)
        modifiers.extend(magic_test_modifiers(state,defender_id,option.skill)[0])
        from towr.domain.pc_armour_models import actor_armour_test_modifiers
        modifiers.extend(actor_armour_test_modifiers(state,defender_id,option.skill,oppose_attack=True))
        from towr.domain.pc_deep_formation_models import deep_formation_modifiers
        modifiers.extend(deep_formation_modifiers(state,defender_id,attacker_id,attack_skill))
        if injury.conditions.has(Condition.DRAINED):
            modifiers = [item for item in modifiers if item.amount <= 0]
        from towr.domain.pc_help_models import build_pc_test_help
        from towr.domain.pc_npc_champion_models import npc_champion_test_modifiers
        body_dice,body_quality=npc_champion_test_modifiers(state,defender_id,option.skill)
        modifiers.extend(body_dice)
        test=TestRequest(test_id,option.test_profile,tuple(modifiers),tuple(dict.fromkeys(
            (*magic_test_modifiers(state,defender_id,option.skill)[1],*body_quality))))
        if injury.conditions.has(Condition.DRAINED):
            from dataclasses import replace
            test=replace(test,quality_modifiers=tuple(q for q in test.quality_modifiers
                if q.quality is not TestQuality.GLORIOUS))
        test,_=build_pc_test_help(state,defender_id,option.skill,test)
        tests.append((option,test))
    if not tests:
        raise ValueError('the target has no actual eligible Protection profile for this Attack Skill')
    if len(tests) == 1 or injury.conditions.has(Condition.DEFENCELESS):
        return tests[0]
    def expected_successes_numerator(pair: tuple[NpcProtectionProfile,TestRequest]) -> int:
        # These ordinary NPC Protection Tests have only dice modifiers. Their
        # exact mean is dice*threshold/10; integer comparison preserves ties.
        parameters = _expected_initial_roll_parameters(pair[1])
        return parameters[5]*parameters[6]
    return max(tests,key=expected_successes_numerator)
