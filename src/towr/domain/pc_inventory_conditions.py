"""Independent PG1.4 IV92 Carrying causes from actual physical weapon units.

This owner changes only the Carrying contribution to Burdened. Item movement,
potions, wounds and the other Condition sources keep their existing owners.
"""
from __future__ import annotations

from dataclasses import dataclass,replace

from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.weapon_inventory_models import WeaponInventoryState,carrying_burden_rule_ids


def _actor(state,actor):
    if type(actor) is not str or not actor.strip():
        raise TypeError('inventory Conditions require an actual actor identifier')
    if actor not in (*state.source.pc_activation_order,*state.source.npc_activation_order):
        raise ValueError('inventory Conditions require an actual encounter actor')


def external_inventory_conditions(state,actor) -> frozenset[Condition]:
    """Query only current Carrying; no Strength is inferred from numeric NPC dice."""
    _actor(state,actor)
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_potion_models import pc_effective_definition
        inventory=state.participant(actor).weapon_inventory
        strength=pc_effective_definition(state,actor).strength
    else:
        npc=state.enemy(actor)
        inventory=npc.state.weapon_inventory
        components=npc.definition.generated_components
        if inventory is None or components is None:
            return frozenset()
        strength=components.strength
    if type(inventory) is not WeaponInventoryState:
        raise TypeError('carrying requires the actual common inventory')
    return (frozenset((Condition.BURDENED,))
        if carrying_burden_rule_ids(inventory,strength) else frozenset())


def initial_pc_inventory_injury(source,inventory,injury) -> CharacterInjuryState:
    """Add initial Carrying to the supplied healthy/armour-derived injury state."""
    from towr.domain.pc_melee_models import PcMeleeParticipant
    if type(source) is not PcMeleeParticipant:
        raise TypeError('initial carrying requires its actual PC source')
    if type(inventory) is not WeaponInventoryState:
        raise TypeError('initial carrying requires the actual common inventory')
    if type(injury) is not CharacterInjuryState:
        raise TypeError('initial carrying requires its exact character injury state')
    replace(injury)
    if not carrying_burden_rule_ids(inventory,source.pc.strength):
        return injury
    conditions=injury.conditions.with_condition(Condition.BURDENED)
    return injury if conditions==injury.conditions else replace(injury,conditions=conditions)


@dataclass(frozen=True,slots=True)
class _ProposedPartyView:
    """Read-only actor proposal for effective facts, without a fabricated journal."""
    previous: object
    party: tuple

    def participant(self,actor):
        return next(member for member in self.party if member.actor_id==actor)

    def __getattr__(self,name):
        return getattr(self.previous,name)


def reconcile_pc_inventory_burden(state,member):
    """Reconcile an owner's proposed member using its already updated gear/buffs.

    Removing the last Carrying cause cannot end a Net, ongoing Wound, Armour,
    magic or Briarroot source. If Carrying was absent, this owner removes nothing.
    """
    from towr.domain.pc_melee_result_models import PcMeleeParticipantState
    if type(member) is not PcMeleeParticipantState:
        raise TypeError('carrying reconciliation requires the actual typed PC member')
    replace(member)
    _actor(state,member.actor_id)
    if member.actor_id not in state.source.pc_activation_order:
        raise ValueError('PC carrying reconciliation requires a PC actor')
    view=_ProposedPartyView(state,tuple(member if old.actor_id==member.actor_id else old
        for old in state.party))
    before=external_inventory_conditions(state,member.actor_id)
    after=external_inventory_conditions(view,member.actor_id)
    conditions=member.injury.conditions
    if Condition.BURDENED in after:
        conditions=conditions.with_condition(Condition.BURDENED)
    elif Condition.BURDENED in before:
        from towr.domain.pc_armour_models import external_armour_conditions
        from towr.domain.pc_magic_models import external_magic_conditions
        from towr.domain.pc_briarroot_models import external_briarroot_conditions
        from towr.domain.pc_heavy_wound_models import has_ongoing_condition
        independent=(member.net_condition_sources
            or has_ongoing_condition(member.injury,Condition.BURDENED)
            or Condition.BURDENED in (external_armour_conditions(view,member.actor_id)
                | external_magic_conditions(view,member.actor_id)
                | external_briarroot_conditions(view,member.actor_id)))
        if not independent:
            conditions=conditions.without_condition(Condition.BURDENED)
    return member if conditions==member.injury.conditions else replace(member,
        injury=replace(member.injury,conditions=conditions))


def reconcile_npc_inventory_burden(state,enemy,*,weighted_nets=None):
    """Reconcile only Carrying after a real NPC throw/drop/pickup transition."""
    source=enemy.definition.generated_components
    if source is None or enemy.state.weapon_inventory is None:return enemy
    before=state.enemy(enemy.state.actor_id).state.weapon_inventory
    after=enemy.state.weapon_inventory
    conditions=enemy.state.injury.conditions
    if carrying_burden_rule_ids(after,source.strength):
        conditions=conditions.with_condition(Condition.BURDENED)
    elif before is not None and carrying_burden_rule_ids(before,source.strength):
        from towr.domain.armour_models import armour_burden_sources
        from towr.domain.pc_magic_models import external_magic_conditions
        from towr.domain.pc_briarroot_models import external_briarroot_conditions
        from towr.domain.pc_weighted_net_models import PcNetLocation
        bank=state.weighted_nets if weighted_nets is None else weighted_nets
        independent=(armour_burden_sources(source.armour,source.strength)
            or any(item.location is PcNetLocation.BOUND and item.bound_target_id==enemy.state.actor_id for item in bank)
            or Condition.BURDENED in (external_magic_conditions(state,enemy.state.actor_id)
                | external_briarroot_conditions(state,enemy.state.actor_id)))
        if not independent:conditions=conditions.without_condition(Condition.BURDENED)
    return enemy if conditions==enemy.state.injury.conditions else replace(enemy,
        state=replace(enemy.state,injury=replace(enemy.state.injury,conditions=conditions)))
