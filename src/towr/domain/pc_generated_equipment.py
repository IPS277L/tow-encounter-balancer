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
from towr.domain.test_models import DiceModifier,Skill,TestRequest,_expected_initial_roll_parameters

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeState


def generated_attack_modifiers(definition: NpcDefinition, conditions: ConditionState,
        target_conditions: ConditionState) -> tuple[DiceModifier,...]:
    components = definition.generated_components
    if components is None:
        return ()
    weapon = PcMeleeWeapon(components.weapon.value)
    return (pc_weapon_test_modifiers(weapon,Skill.MELEE,conditions)
        + pc_weapon_attack_modifiers(weapon,target_conditions))


def generated_damage_modifiers(definition: NpcDefinition,
        target_resilience: ResilienceProfile) -> tuple[DamageModifier,...]:
    components = definition.generated_components
    return (() if components is None else
        pc_weapon_damage_modifiers(PcMeleeWeapon(components.weapon.value),target_resilience))


def npc_protection_test(state: PcMeleeState, defender_id: str, attacker_id: str, test_id: str,
        profile: NpcProtectionProfile | None = None, *, attack_skill: Skill = Skill.MELEE
        ) -> tuple[NpcProtectionProfile,TestRequest]:
    """Select from actual prepared Tests; evaluating alternatives spends no RNG.

    Source order resolves an exact tie (generated Defence before Athletics).
    All contextual modifiers are shared with the real native Attack request.
    """
    from towr.domain.pc_npc_distraction_models import pc_npc_distraction_test_modifiers
    from towr.domain.pc_npc_grudge_models import pc_npc_grudge_melee_modifiers
    from towr.domain.pc_magic_models import magic_test_modifiers

    enemy = state.enemy(defender_id)
    components = enemy.definition.generated_components
    profiles = ((profile,) if profile is not None else enemy.definition.protection
        if components is not None else enemy.definition.protection[:1])
    if profile is None and components is not None and attack_skill is Skill.SHOOTING:
        from towr.domain.test_models import InlineProfile
        melee=NpcProtectionProfile('RULE-EQUIPMENT-004:generated-close-melee',Skill.MELEE,
            InlineProfile(components.weapon_skill,components.melee))
        profiles=((enemy.definition.protection[0],) if enemy.state.holds_shield else ())+(
            melee,enemy.definition.protection[1])
    tests = []
    for option in profiles:
        modifiers = list(pc_npc_distraction_test_modifiers(state,defender_id,attacker_id))
        if option.skill is Skill.MELEE:
            modifiers.extend(pc_npc_grudge_melee_modifiers(state,defender_id,attacker_id))
        if components is not None and enemy.state.wields_weapon:
            modifiers.extend(pc_weapon_test_modifiers(PcMeleeWeapon(components.weapon.value),
                option.skill,enemy.state.injury.conditions))
        modifiers.extend(magic_test_modifiers(state,defender_id,option.skill)[0])
        if enemy.state.injury.conditions.has(Condition.DRAINED):
            modifiers = [item for item in modifiers if item.amount <= 0]
        tests.append((option,TestRequest(test_id,option.test_profile,tuple(modifiers))))
    if len(tests) == 1 or enemy.state.injury.conditions.has(Condition.DEFENCELESS):
        return tests[0]
    def expected_successes_numerator(pair: tuple[NpcProtectionProfile,TestRequest]) -> int:
        # These ordinary NPC Protection Tests have only dice modifiers. Their
        # exact mean is dice*threshold/10; integer comparison preserves ties.
        parameters = _expected_initial_roll_parameters(pair[1])
        return parameters[5]*parameters[6]
    return max(tests,key=expected_successes_numerator)
