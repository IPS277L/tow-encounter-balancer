"""Independent current Condition sources for treatment and medical views.

A raw Condition flag alone cannot erase its independent weapon, magic, Net,
armour or carrying source when a Wound's effects are temporarily suppressed.
"""
from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState,WoundConditionEffect


def medical_external_conditions(state,actor):
    from towr.domain.pc_actor_models import pc_actor_injury
    from towr.domain.pc_magic_models import external_magic_conditions
    from towr.domain.pc_armour_models import external_armour_conditions
    from towr.domain.pc_briarroot_models import external_briarroot_conditions
    from towr.domain.pc_inventory_conditions import external_inventory_conditions
    from towr.domain.pc_weighted_net_models import weighted_net_condition_sources
    injury=pc_actor_injury(state,actor)
    if type(injury) is not CharacterInjuryState:
        raise TypeError('medical effect views require a real Character Wound patient')
    wound_conditions=frozenset(effect.condition for effect in injury.active_wound_effects
        if type(effect) is WoundConditionEffect)
    external=injury.conditions.conditions-wound_conditions
    external|=external_magic_conditions(state,actor)
    external|=external_armour_conditions(state,actor)
    external|=external_briarroot_conditions(state,actor)
    external|=external_inventory_conditions(state,actor)
    if weighted_net_condition_sources(state,actor): external|=frozenset((Condition.BURDENED,))
    if actor in state.source.pc_activation_order and state.participant(actor).hit_condition_sources:
        external|=frozenset((Condition.DRAINED,))
    return frozenset(external)
