"""Item-derived armour context shared by both sides of an encounter."""
from __future__ import annotations

from dataclasses import replace

from towr.domain.armour_models import (
    ArmourLoadout,BodyArmour,active_agilulf,armour_burden_sources,armour_test_modifiers,
    armour_quality_modifiers,armour_allows_near_miss,
    protects_against_mundane_armour_effects,
)
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.test_models import Skill


def actor_armour(state,actor: str) -> ArmourLoadout | None:
    if actor in state.source.pc_activation_order:
        return state.source.participant(actor).armour
    if actor in state.source.npc_activation_order:
        components=state.enemy(actor).definition.generated_components
        return components.armour if components is not None else None
    from towr.domain.pc_actor_models import pc_companion
    row = pc_companion(state, actor)
    if row is not None:
        from towr.domain.pc_companion_effect_models import companion_profile
        return companion_profile(state, actor).armour
    raise ValueError('armour query requires an actual encounter actor')


def actor_armour_test_modifiers(state,actor,skill,*,oppose_attack=False,
        control_mount=False,environmental=False):
    from towr.domain.pc_mount_models import mounted_armour_test_exemptions,mounted_test_modifiers
    equipment=actor_armour(state,actor)
    exemptions=mounted_armour_test_exemptions(state,actor,skill,
        oppose_attack=oppose_attack,control_mount=control_mount)
    modifiers=(armour_test_modifiers(equipment,skill,environmental=environmental,**exemptions)
        if equipment is not None else ()) + mounted_test_modifiers(state,actor,skill,
            oppose_attack=oppose_attack,control_mount=control_mount)
    from towr.domain.pc_medical_models import effective_medical_injury
    injury=effective_medical_injury(state,actor)
    return tuple(modifier for modifier in modifiers if modifier.amount<=0) if injury.conditions.has(
        Condition.DRAINED) else modifiers


def actor_armour_quality_modifiers(state,actor,*,charge_attack=False,tracking_or_pursuit=False):
    equipment=actor_armour(state,actor)
    from towr.domain.pc_medical_models import effective_medical_injury
    injury=effective_medical_injury(state,actor)
    if injury.conditions.has(Condition.DRAINED):
        return ()  # Item-granted Glorious is not the explicit Fate exception.
    return (() if equipment is None else armour_quality_modifiers(equipment,
        charge_attack=charge_attack,tracking_or_pursuit=tracking_or_pursuit))


def actor_armour_allows_near_miss(state,actor):
    equipment=actor_armour(state,actor)
    return equipment is None or armour_allows_near_miss(equipment)


def actor_bound_to_chivalric_combat(state,actor):
    equipment=actor_armour(state,actor)
    return equipment is not None and BodyArmour.AGILULF in equipment.body


def validate_agilulf_defeat_policies(source):
    """A GM availability fact cannot authorise an explicitly forbidden surrender."""
    from towr.domain.minion_defeat_models import NpcDefeatDisposition
    bound={enemy.state.actor_id for enemy in source.npc_sources
        if enemy.definition.generated_components is not None
        and BodyArmour.AGILULF in enemy.definition.generated_components.armour.body}
    if any(decision.target_id in bound
            and decision.disposition is NpcDefeatDisposition.DISARMED_AND_SURRENDERED
            for member in source.party for decision in member.defeat_decisions):
        raise ValueError('Agilulf chivalric armour forbids a surrendered/captive defeat disposition')


def actor_has_mundane_armour_ward(state,actor):
    equipment=actor_armour(state,actor)
    return equipment is not None and protects_against_mundane_armour_effects(equipment)


def advised_damage_modifiers(modifiers,resilience):
    from towr.domain.attack_models import DamageImpactSpec,DamageProfile,effective_damage_modifiers
    return effective_damage_modifiers(DamageImpactSpec(DamageProfile(0),resilience,
        damage_modifiers=tuple(modifiers)))


def advised_weapon_damage_modifiers(weapon,resilience):
    from towr.domain.pc_weapon_models import pc_weapon_damage_modifiers
    return advised_damage_modifiers(pc_weapon_damage_modifiers(weapon,resilience),resilience)


def initial_pc_armour_injury(source):
    burdened=source.armour is not None and armour_burden_sources(source.armour,source.pc.strength)
    return CharacterInjuryState(conditions=ConditionState(
        frozenset((Condition.BURDENED,)) if burdened else frozenset()))


def external_armour_conditions(state,actor):
    equipment=actor_armour(state,actor)
    if equipment is None:
        return frozenset()
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_potion_models import pc_effective_definition
        strength=pc_effective_definition(state,actor).strength
    else:
        strength=state.enemy(actor).definition.generated_components.strength
    return frozenset((Condition.BURDENED,)) if armour_burden_sources(equipment,strength) else frozenset()


def pc_effective_armour_ratings(source,pc):
    return replace(pc,weapon_skill=5,melee=5,defence=5) if (
        source.armour is not None and active_agilulf(source.armour)) else pc


def pc_after_armour_enhancement(state,actor,member):
    """Re-evaluate only the weight source; keep wounds, Nets and magic causes."""
    source=state.source.participant(actor)
    if source.armour is None:
        return member
    strength=source.pc.strength+int('strength' in member.enhancements)
    conditions=member.injury.conditions
    if armour_burden_sources(source.armour,strength):
        conditions=conditions.with_condition(Condition.BURDENED)
    elif external_armour_conditions(state,actor):
        from towr.domain.pc_heavy_wound_models import has_ongoing_condition
        from towr.domain.pc_magic_models import external_magic_conditions
        from towr.domain.pc_briarroot_models import external_briarroot_conditions
        from towr.domain.pc_inventory_conditions import external_inventory_conditions,_ProposedPartyView
        proposal=_ProposedPartyView(state,tuple(member if old.actor_id==actor else old for old in state.party))
        other=(member.net_condition_sources or has_ongoing_condition(member.injury,Condition.BURDENED)
            or Condition.BURDENED in (external_magic_conditions(state,actor)
                | external_briarroot_conditions(state,actor)
                | external_inventory_conditions(proposal,actor)))
        if not other:
            conditions=conditions.without_condition(Condition.BURDENED)
    return replace(member,injury=replace(member.injury,conditions=conditions))
