"""Pure source/policy checks for ADR-0037 journals; no reducers or Tests.

PG1.4 Rules pp112,114,119,122; Magic pp156-157,162. GM1.1 pp91-92.
These checks bind recorded choices to supplied facts, not a general rules engine.
"""
from towr.domain.condition_models import Condition
from towr.domain.movement_models import FreeMovementRequest
from towr.domain.npc_broken_recover_models import NpcBrokenRecoverResult
from towr.domain.npc_broken_run_models import NpcBrokenRunResult
from towr.domain.npc_magic_scenario_models import NpcMagicScenario
from towr.domain.npc_magic_scene_models import NpcMagicBrokenPlanKind, NpcMagicSceneKey, NpcMagicSceneFrame, NpcMagicRouteFacts
from towr.domain.npc_magic_step_models import NpcMagicStep
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingState
from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionResult
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_dead_champion_models import NpcRosterDeadChampionExclusionResult
from towr.domain.npc_roster_minion_attack_models import NpcRosterMinionAttackResult
from towr.domain.npc_roster_minion_defeat_models import NpcRosterMinionDefeatResult
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartResult
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndResult
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange as Range
from towr.domain.resolution_models import CowardlyFlightMovementCompletion, GiveGroundResolutionRequest
from towr.domain.test_models import Skill, TestRequest
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind, ImproviseKind, ManoeuvreKind


def magic_live_ids(state: NpcRosterCastingState) -> tuple[str, ...]:
    return tuple(p.state.actor_id for p in state.roster.participants
                 if not (p.state.injury.dead if p.state.actor_id == state.wizard.actor_id else p.state.injury.defeated))


def magic_scene_key(state: NpcRosterCastingState) -> NpcMagicSceneKey:
    return NpcMagicSceneKey(state.spatial_state.placements, magic_live_ids(state))


def magic_next_actor(scenario: NpcMagicScenario, state: NpcRosterCastingState) -> str | None:
    combat = state.round_state
    return next((i for i in scenario.activation_order if i in magic_live_ids(state)
                 and i not in (*combat.completed_turn_entity_ids, *combat.excluded_turn_entity_ids)
                 and state.roster.participant(i).state.side is combat.next_side), None)


def magic_dead_champion_exclusion_attack(previous: NpcMagicStep | None) -> NpcRosterChampionAttackResult | None:
    """Identify the owed death phase; its request validates the full completion.

    A completed Wizard turn remains completed. Other mandatory Attack effects
    retain their existing pending consumer/stop instead of being erased here.
    """
    if previous is not None and not isinstance(previous, NpcMagicStep):
        raise TypeError('death continuation requires a typed previous magic step')
    if previous is None or not isinstance(previous.result, NpcRosterChampionAttackResult):
        return None
    attack = previous.result
    target_id = attack.attack.execution.target_id
    combat = attack.attack.execution.state
    # The bound Attack projects these exact injury/round snapshots. Read them
    # directly instead of rebuilding a full owner for each ordinary hit/miss.
    if (attack.attack.pending_follow_ups or not attack.attack.resolution.target_state.dead
            or target_id != attack.source.state.wizard.actor_id
            or target_id in (*combat.completed_turn_entity_ids, *combat.excluded_turn_entity_ids)):
        return None
    return attack


def validate_magic_step_predecessor(previous: NpcMagicStep | None, step: NpcMagicStep | None) -> None:
    """Require both directions of Attack -> death exclusion, including tail.

    State equality alone cannot bind two Attack witnesses with different dice
    traces that happen to project to the same full post-state.
    """
    if step is not None and not isinstance(step, NpcMagicStep):
        raise TypeError('death continuation requires a typed next magic step')
    attack = magic_dead_champion_exclusion_attack(previous)
    exclusion = step.result if step is not None else None
    if attack is not None:
        if not isinstance(exclusion, NpcRosterDeadChampionExclusionResult) or exclusion.source.attack != attack:
            raise ValueError('completed lethal Attack requires its matching immediate dead Champion exclusion')
    elif isinstance(exclusion, NpcRosterDeadChampionExclusionResult):
        raise ValueError('dead Champion exclusion requires its immediate lethal Attack predecessor')


def magic_target(scenario: NpcMagicScenario, state: NpcRosterCastingState,
                 actor_id: str, frame: NpcMagicSceneFrame) -> str | None:
    """Recorded policy's first reachable Zone/actor; injuries do not hide a target."""
    actor = state.roster.participant(actor_id)
    policy = scenario.policy_for(actor_id)
    live = magic_live_ids(state)
    if actor_id == state.wizard.actor_id:
        zones = {z.zone_id: z.target_range for z in frame.zone_ranges}
        return next((z for z in policy.zone_priorities if zones[z] is not Range.EXTREME
                     and any(p.state.actor_id in live and p.state.side is not actor.state.side
                             and state.spatial_state.placement_for(p.state.actor_id).zone_id == z
                             for p in state.roster.participants)), None)
    pairs = tuple(p for p in frame.pair_ranges if actor_id in (p.first_actor_id, p.second_actor_id))
    if any(p.target_range is Range.CLOSE for p in pairs):
        return None
    profile = actor.definition.attacks[0]
    for target in policy.target_actor_ids:
        if target not in live:
            continue
        pair = next(p for p in pairs if target in (p.first_actor_id, p.second_actor_id))
        approval = pair.first_range_approved_by_gm if pair.first_actor_id == actor_id else pair.second_range_approved_by_gm
        if (pair.target_range is not Range.EXTREME and (profile.hands is RangedWeaponHands.ONE_HANDED
                or tuple(Range).index(pair.target_range) <= tuple(Range).index(profile.range_max) or approval)):
            return target
    return None


def _frame(scenario: NpcMagicScenario, state: NpcRosterCastingState) -> NpcMagicSceneFrame:
    frame = scenario.frame_for(magic_scene_key(state))
    if frame is None:
        raise ValueError('journal action requires its supplied current scene frame')
    return frame


def _route(actual: GiveGroundResolutionRequest | FreeMovementRequest, expected: NpcMagicRouteFacts) -> bool:
    return (actual.path_entity_ids == expected.path_entity_ids
            and actual.crosses_obstacle is expected.crosses_obstacle
            and actual.crosses_difficult_terrain is expected.crosses_difficult_terrain)


def magic_movement_prefix(scenario: NpcMagicScenario, state: NpcRosterCastingState,
                          movements: tuple[CowardlyFlightMovementCompletion, ...]) -> NpcMagicSceneKey:
    """Check staged Curse prefix without publishing its spatial state to root."""
    pending = state.pending_movement
    if pending is None:
        raise ValueError('staged movements require full pending Curse')
    follow_ups = pending.zone.movement_follow_ups
    if len(movements) > len(follow_ups):
        raise ValueError('staged movement prefix exceeds pending chain')
    spatial = pending.source.spatial_state
    for index, completion in enumerate(movements):
        if completion.source != follow_ups[index]:
            raise ValueError('staged movements differ from the ordered pending prefix')
        positions = {p.entity_id: p for p in spatial.placements}
        key = NpcMagicSceneKey(tuple(positions.get(p.entity_id, p) for p in state.spatial_state.placements),
                               magic_live_ids(state))
        frame = scenario.frame_for(key)
        if frame is None:
            raise ValueError('staged movement has crossed a missing scene frame')
        mover = completion.source.target_id
        plan = next(p for p in frame.give_ground_plans if p.actor_id == mover)
        request = completion.resolution.source_request
        target = next(t for t in pending.source.targets if t.actor_id == mover)
        if (request is None or request.state != spatial or request.source != completion.source.request
                or request.mover_id != mover or request.mover_conditions != target.injury.conditions
                or request.away_from_entity_id != pending.source.actor_id
                or plan.destination_zone_id is None or not plan.can_leave_zone
                or request.destination_zone_id != plan.destination_zone_id or not _route(request, plan.route)):
            raise ValueError('recorded Give Ground differs from its complete source/scene route')
        expected_rules = tuple(dict.fromkeys((request.source.rule_id,
            'RULE-COMBAT-011:zones-and-ranges', 'RULE-COMBAT-015:give-ground')))
        if completion.resolution.applied_rule_ids != expected_rules:
            raise ValueError('staged Give Ground trace differs from its bound source')
        spatial = completion.resolution.state
    positions = {p.entity_id: p for p in spatial.placements}
    return NpcMagicSceneKey(tuple(positions.get(p.entity_id, p) for p in state.spatial_state.placements),
                           magic_live_ids(state))


def validate_magic_step_policy(scenario: NpcMagicScenario, step: NpcMagicStep) -> None:
    result, state = step.result, step.before
    actor_id = step.actor_id
    if isinstance(result, NpcRosterTurnStartResult):
        if actor_id != magic_next_actor(scenario, state):
            raise ValueError('journal activation differs from scenario order')
        injury = state.roster.participant(actor_id).state.injury
        if injury.conditions.has(Condition.BROKEN):
            frame = scenario.frame_for(magic_scene_key(state))
            plan = next((p for p in frame.broken_plans if p.actor_id == actor_id), None) if frame else None
            declarations = (CombatActionDeclaration(CombatActionKind.RECOVER),
                            CombatActionDeclaration(CombatActionKind.MANOEUVRE, manoeuvre=ManoeuvreKind.RUN))
            if plan:
                declarations = (declarations[plan.kind is NpcMagicBrokenPlanKind.FREE_MOVE_RUN],)
        else:
            declarations = ((CombatActionDeclaration(CombatActionKind.IMPROVISE, improvise_kind=ImproviseKind.SPELL,
                improvise_approach_id=scenario.spell.lore_id),) if actor_id == state.wizard.actor_id
                else (CombatActionDeclaration(CombatActionKind.ATTACK),))
        if result.source.declaration not in declarations:
            raise ValueError('journal declaration differs from actor policy')
    elif isinstance(result, NpcRosterCastingResult):
        frame = _frame(scenario, state)
        casting = result.source.casting
        if (casting.selected_zone_id != magic_target(scenario, state, actor_id, frame)
                or casting.policy is not scenario.policy_for(actor_id).casting_policy):
            raise ValueError('journal Casting differs from Zone/Casting policy')
        plans = {p.actor_id: p for p in frame.give_ground_plans}
        for target in casting.targets:
            plan = plans[target.actor_id]
            can_move = plan.can_leave_zone and not plan.impossible_confirmed
            if (target.willpower_profile != scenario.policy_for(target.actor_id).willpower_profile
                    or target.can_give_ground is not can_move):
                raise ValueError('journal Casting target facts differ from actor/scene policy')
    elif isinstance(result, NpcRosterCastingCompletionResult):
        magic_movement_prefix(scenario, state, result.source.completion.movement_completions)
    elif isinstance(result, (NpcRosterMinionAttackResult, NpcRosterChampionAttackResult)):
        frame = _frame(scenario, state)
        attack = result.source.attack
        execution = attack.execution
        target_id = magic_target(scenario, state, actor_id, frame)
        if execution.target_id != target_id:
            raise ValueError('journal Attack differs from available target priority')
        source = attack.preparation.npc_attack.source_request
        pair = next(p for p in frame.pair_ranges if {p.first_actor_id, p.second_actor_id} == {actor_id, target_id})
        approval = pair.first_range_approved_by_gm if pair.first_actor_id == actor_id else pair.second_range_approved_by_gm
        protection = attack.preparation.protection.source_request
        departure = next((d for d in frame.attack_departures if d.actor_id == target_id), None)
        if departure is not None and execution.kernel_request.can_target_leave_zone is not departure.can_leave_zone:
            raise ValueError('journal Attack departure differs from supplied scene fact')
        if (source.selected_attack_id != scenario.policy_for(actor_id).attack_id
                or source.target_range is not pair.target_range or source.range_approved_by_gm is not approval
                or source.has_enemy_in_close_range or source.dice_modifiers
                or not protection.defender_is_aware or protection.defender_is_defenceless
                or protection.selected_skill is not Skill.ATHLETICS
                or any(option.test != TestRequest(option.test.id, option.test.profile) for option in protection.options)
                or execution.kernel_request.target_has_given_ground_this_round != (
                    target_id in state.spatial_state.gave_ground_entity_ids)):
            raise ValueError('journal Attack facts differ from scenario/scene policy')
        resolution = (result.attack.resolution if isinstance(result, NpcRosterChampionAttackResult)
                      else result.attack.execution.resolution)
        if (resolution.stagger is not None and resolution.stagger.selected_choice is not None
                and resolution.stagger.selected_choice is not scenario.repeated_stagger_choice):
            raise ValueError('journal repeated Staggered choice differs from scenario policy')
    elif isinstance(result, NpcRosterMinionDefeatResult):
        decision = result.source.decision
        expected = next(d for d in scenario.policy_for(decision.attacker_id).defeat_decisions
                        if d.target_id == decision.target_id)
        if decision != expected:
            raise ValueError('journal defeat decision differs from supplied GM policy')
    elif isinstance(result, (NpcBrokenRecoverResult, NpcBrokenRunResult)):
        frame = _frame(scenario, state)
        plan = next((p for p in frame.broken_plans if p.actor_id == actor_id), None)
        if plan is None:
            raise ValueError('journal Broken action requires supplied route policy')
        source, movement = result.source, result.source.movement
        run = isinstance(result, NpcBrokenRunResult)
        if run != (plan.kind is NpcMagicBrokenPlanKind.FREE_MOVE_RUN):
            raise ValueError('journal Broken action differs from route kind')
        if (source.fastest_route_confirmed is not plan.fastest_route_confirmed
                or (movement is None) != (plan.kind is NpcMagicBrokenPlanKind.SAFE_RECOVER)):
            raise ValueError('journal Broken action differs from fastest/free movement facts')
        if movement is not None and (movement.traversed_zone_ids != plan.free_move_zone_ids
                or movement.speed is not scenario.policy_for(actor_id).speed
                or not _route(movement, plan.free_move_route)):
            raise ValueError('journal Broken free movement differs from supplied route/Speed')
        if run:
            if (source.run_destination_zone_id != plan.run_destination_zone_id
                    or source.run_path_entity_ids != plan.run_route.path_entity_ids
                    or source.run_crosses_obstacle is not plan.run_route.crosses_obstacle
                    or source.run_crosses_difficult_terrain is not plan.run_route.crosses_difficult_terrain):
                raise ValueError('journal Broken Run differs from supplied route')
        elif source.willpower_profile != scenario.policy_for(actor_id).willpower_profile:
            raise ValueError('journal Recover differs from supplied Willpower')
    elif isinstance(result, NpcWoundTurnEndResult):
        source = result.source
        removed = {e.effect for e in source.expiries}
        injury = state.roster.participant(actor_id).state.injury
        effects = getattr(injury, 'active_wound_effects', ())
        for snapshot in source.condition_sources:
            other = any(e not in removed and getattr(e, 'condition', None) is snapshot.condition for e in effects)
            if snapshot.has_other_active_source is not other:
                raise ValueError('journal expiry cannot invent external Condition sources in a closed scene')
