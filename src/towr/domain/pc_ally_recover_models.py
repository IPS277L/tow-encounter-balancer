"""Bounded standard Recover choices and exact multi-PC consequences; no RNG."""
from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionEffect, WoundEffectDuration, WoundRestriction
from towr.domain.pc_heavy_wound_models import (
    add_critical, critical_for_action, has_ongoing_condition,
    restriction_sources,
)
from towr.domain.recover_models import (
    RecoverConditionTarget, RecoverStandardChoice, RecoverStandardResult,
    _expected_standard_changes,
)
from towr.domain.turn_models import CombatActionKind


def pc_recover_removable(member, condition):
    return (not member.injury.dead and member.injury.conditions.has(condition)
        and not has_ongoing_condition(member.injury,condition))


def pc_ally_recover_beneficiary(state):
    actor = state.round_state.active_turn.actor_id
    strategy = state.source.participant(actor).ally_recover_policy
    if strategy is None:
        return None
    member = state.participant(actor)
    ally = state.participant(strategy.beneficiary_id)
    if member.injury.dead or member.injury.conditions.has(Condition.DEFENCELESS):
        return None
    if any(pc_recover_removable(ally,condition) for condition in (Condition.STAGGERED,Condition.PRONE)):
        return ally.actor_id
    return None


def pc_recover_targets(state):
    """Self-required turns stay self-first; otherwise the explicit ally is first."""
    from towr.domain.pc_melee_result_models import _pc_recover_needed
    actor = state.round_state.active_turn.actor_id
    member = state.participant(actor)
    ally_id = pc_ally_recover_beneficiary(state)
    ally = state.participant(ally_id) if ally_id is not None else None
    candidates = ((member,ally) if _pc_recover_needed(member) else (ally,member))
    result = []
    for condition in (Condition.STAGGERED,Condition.PRONE):
        selected = next((candidate for candidate in candidates
            if candidate is not None and pc_recover_removable(candidate,condition)),None)
        result.append(None if selected is None else RecoverConditionTarget(selected.actor_id,
            selected.injury.conditions,None if selected.actor_id==actor else True))
    return tuple(result)


def expected_pc_standard_recover(request):
    """Build the complete K1 receipt from canonical choices, without executing."""
    from towr.domain.recover_models import _expected_recover_execution
    choice = request.choice
    if type(choice) is not RecoverStandardChoice:
        raise TypeError('bounded PC Recover requires standard choices')
    removed = min(1,choice.magic_state.miscast_dice)
    resolution = RecoverStandardResult(choice,_expected_standard_changes(choice),choice.magic_state,
        replace(choice.magic_state,miscast_dice=choice.magic_state.miscast_dice-removed),removed,
        choice.mount,choice.object_interaction)
    return _expected_recover_execution(request,resolution)


def pc_after_standard_recover(state, request, result):
    """Only actual recipients lose effects; receiving aid is not their action."""
    actor = request.actor_id
    updated = {}
    for change in result.resolution.condition_changes:
        member = state.participant(change.entity_id)
        effects = tuple(effect for effect in member.injury.active_wound_effects
            if not (isinstance(effect,WoundConditionEffect)
                and effect.condition in change.removed_conditions
                and effect.duration is WoundEffectDuration.UNTIL_REMOVED))
        injury = replace(member.injury,conditions=change.conditions,active_wound_effects=effects)
        if member.actor_id != actor and Condition.PRONE in change.removed_conditions:
            injury = add_critical(injury,restriction_sources(injury,
                WoundRestriction.REMOVING_PRONE_CAUSES_CRITICAL))
        updated[member.actor_id] = injury
    member = state.participant(actor)
    from towr.domain.pc_backup_weapon_models import pc_preferred_weapon_hand
    hand = (pc_preferred_weapon_hand(state,actor)
        if request.choice.object_interaction is not None else member.weapon_hand)
    injury = updated.get(actor,member.injury)
    updated[actor] = critical_for_action(replace(member,injury=injury),CombatActionKind.RECOVER,
        removes_prone=(request.choice.prone_target is not None
            and request.choice.prone_target.entity_id==actor),
        used_hand=hand if request.choice.object_interaction is not None else None)
    return tuple(replace(member,injury=updated.get(member.actor_id,member.injury),
        weapon_hand=hand if member.actor_id==actor else member.weapon_hand) for member in state.party)
