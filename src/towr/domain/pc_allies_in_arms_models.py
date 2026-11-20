"""Allies in Arms: one source-bound removal after a real Help Test, PG73/C7."""
from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.talent_actor_models import actor_acquired_talents
from towr.domain.talent_catalog import TalentId


def allies_in_arms_choice(state,helper,beneficiary,*,helper_stagger_added=False):
    """A bounded simulator preference, independent of dice and hidden outcomes.

    Removing the first Staggered is valued at .5, as in ordinary combat advice.
    Prefer an ally's still upcoming action on an equal value. This is tactics,
    not an extra restriction on the book effect.
    """
    from towr.domain.pc_generated_talents import actor_stagger_removable
    if not any(entry.id is TalentId.ALLIES_IN_ARMS for entry in actor_acquired_talents(state,helper)):
        return None,0.
    unavailable=(*state.round_state.completed_turn_entity_ids,*state.round_state.excluded_turn_entity_ids)
    choices=[]
    for actor in (beneficiary,helper):
        removable=actor_stagger_removable(state,actor)
        if actor==helper and helper_stagger_added:
            removable=True
        if removable:
            value=.5+(.1 if actor==beneficiary and actor not in unavailable else 0.)
            choices.append((actor,value))
    return max(choices,key=lambda choice:choice[1]) if choices else (None,0.)


def build_allies_in_arms_application(state,execution):
    from towr.domain.talent_allies_in_arms_models import AlliesInArmsApplication
    from towr.domain.pc_generated_talents import actor_conditions
    source=execution.source_request
    target,_=allies_in_arms_choice(state,source.actor_id,source.beneficiary_id)
    if target is None:
        return None
    talent=next(entry for entry in actor_acquired_talents(state,source.actor_id)
        if entry.id is TalentId.ALLIES_IN_ARMS)
    return AlliesInArmsApplication(execution,talent,target,actor_conditions(state,target))


def allies_in_arms_updates(state,application,updates):
    """Remove only Staggered; preserve the Help Test's new Critical effects."""
    if application is None:
        return updates
    actor=application.target_id
    updates=dict(updates)
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_weapon_inventory import replace_pc_member
        updates['party']=tuple(replace_pc_member(member,injury=replace(member.injury,
            conditions=member.injury.conditions.without_condition(Condition.STAGGERED)))
            if member.actor_id==actor else member for member in updates.get('party',state.party))
    else:
        updates['enemies']=tuple(replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=enemy.state.injury.conditions.without_condition(Condition.STAGGERED))))
            if enemy.state.actor_id==actor else enemy for enemy in updates.get('enemies',state.enemies))
    return updates
