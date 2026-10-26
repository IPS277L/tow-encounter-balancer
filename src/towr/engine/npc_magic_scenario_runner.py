"""One bounded ADR-0037 encounter over existing full-owner transitions.

PG1.4 Rules pp112,118-119,122,190; Magic pp156-157,162. GM1.1 pp91-92.
No retry, guessed scene facts, Miscast preparation or new effect consumer.
"""
from dataclasses import dataclass, replace

from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.condition_models import Condition, StaggerChoice, StaggerRequest
from towr.domain.cowardly_flight_casting_models import CowardlyFlightCastingFacts
from towr.domain.cowardly_flight_casting_completion_models import CowardlyFlightCastingCompletionRequest
from towr.domain.injury_models import (
    WoundConditionSourceSnapshot, CharacterWoundRequest, WoundTableRoll, WoundNegationOption,
    MonstrosityImpactRequest, MonstrosityImpactChoice, DecisionOwner,
)
from towr.domain.movement_models import FreeMovementRequest
from towr.domain.npc_attack_preparation_models import NpcAttackPreparationRequest
from towr.domain.npc_broken_recover_models import NpcBrokenRecoverRequest
from towr.domain.npc_broken_run_models import NpcBrokenRunRequest
from towr.domain.npc_champion_attack_models import NpcChampionAttackRequest
from towr.domain.npc_magic_journal_policy import (
    magic_live_ids, magic_scene_key, magic_next_actor, magic_target,
    magic_movement_prefix, validate_magic_step_policy,
)
from towr.domain.npc_magic_scenario_models import NpcMagicScenario
from towr.domain.npc_magic_scenario_result_models import (
    NpcMagicScenarioResult, diagnose_npc_magic_unsupported, npc_magic_terminal_outcome,
)
from towr.domain.npc_magic_scene_models import NpcMagicBrokenPlanKind
from towr.domain.npc_magic_step_models import NpcMagicStep, NpcMagicStepResult
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionRequest
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingTargetContext, NpcRosterCastingState
from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionRequest, NpcRosterCastingCompletionResult
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest, NpcRosterChampionAttackResult
from towr.domain.npc_roster_minion_attack_models import NpcRosterMinionAttackRequest
from towr.domain.npc_roster_minion_defeat_models import NpcRosterMinionDefeatRequest
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest, NpcRosterRoundAdvanceRequest
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.protection_models import ProtectionPreparationRequest
from towr.domain.resolution_models import GiveGroundResolutionRequest, KernelAttackRequest
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind, ImproviseKind, ManoeuvreKind
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting, complete_cowardly_flight_casting
from towr.engine.npc_broken_recover import execute_npc_broken_recover
from towr.engine.npc_broken_run import execute_npc_broken_run
from towr.rules.cowardly_flight_resolution import complete_cowardly_flight_movement
from towr.rules.dice import RandomSource
from towr.rules.npc_attack_preparation import prepare_npc_attack, prepare_npc_attack_protection
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
from towr.rules.npc_roster_minion_defeat_resolution import acknowledge_npc_roster_minion_defeat
from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn, advance_npc_roster_round
from towr.rules.npc_wound_turn_end import end_npc_wound_turn
from towr.rules.spatial_resolution import resolve_give_ground
from towr.rules.test_resolution import KeepAllFailures


@dataclass(frozen=True, slots=True)
class _Decisions(KeepAllFailures):
    choice: StaggerChoice

    def choose_repeated_stagger(self, *, request: StaggerRequest,
                               allowed_choices: tuple[StaggerChoice, ...]) -> StaggerChoice:
        if self.choice not in allowed_choices:
            raise ValueError('scenario Staggered policy is unavailable')
        return self.choice

    def choose_wound_negation(self, *, request: CharacterWoundRequest, table_roll: WoundTableRoll,
                             options: tuple[WoundNegationOption, ...]) -> str | None:
        return None  # This admitted experiment excludes Fate/negation resources.

    def choose_monstrosity_impact(self, *, request: MonstrosityImpactRequest, owner: DecisionOwner,
                                 choices: tuple[MonstrosityImpactChoice, ...]) -> MonstrosityImpactChoice:
        raise ValueError('Monstrosity decisions are outside the magic scenario')


def _end_sources(state: NpcRosterCastingState, actor_id: str) -> tuple[WoundConditionSourceSnapshot, ...]:
    expiries = tuple(e for e in state.wound_expiries if e.actor_id == actor_id)
    removed = {e.effect for e in expiries}
    effects = getattr(state.roster.participant(actor_id).state.injury, 'active_wound_effects', ())
    conditions = tuple(dict.fromkeys(e.effect.condition for e in expiries))
    return tuple(WoundConditionSourceSnapshot(c, any(e not in removed and getattr(e, 'condition', None) is c
                                                   for e in effects)) for c in conditions)


def run_npc_magic_scenario(scenario: NpcMagicScenario, rng: RandomSource) -> NpcMagicScenarioResult:
    """Use one caller RNG until objective, perspective defeat, budget or exact stop."""
    if not isinstance(scenario, NpcMagicScenario):
        raise TypeError('magic runner requires a validated NpcMagicScenario')
    replace(scenario)  # Recheck complete admission before bootstrap or any RNG.
    if not callable(getattr(rng, 'randint', None)):
        raise TypeError('magic runner requires an injected randint source')
    current = scenario.initial_runtime_state
    steps: list[NpcMagicStep] = []
    decisions = _Decisions(scenario.repeated_stagger_choice)

    def identifier(label: str) -> str:
        return f'{scenario.id}:{len(steps)}:{label}'

    def publish(result: NpcMagicStepResult, expected_source: object) -> None:
        nonlocal current
        step = NpcMagicStep(result)
        if result.source != expected_source or step.before != current:
            raise ValueError('executor returned a result for another full source')
        validate_magic_step_policy(scenario, step)
        current = step.after
        steps.append(step)

    # Each iteration publishes a phase/action or returns. Each round has at most
    # one turn per actor, one action per turn, and finite pending movements.
    while True:
        if npc_magic_terminal_outcome(scenario, current) is not None:
            return NpcMagicScenarioResult(scenario, tuple(steps))
        last_id = steps[-1].id if steps else scenario.id
        stop = diagnose_npc_magic_unsupported(scenario, current, last_id)
        if stop is not None:
            return NpcMagicScenarioResult(scenario, tuple(steps), stop)
        if current.pending_movement is not None:
            pending = current.pending_movement
            movements = ()
            spatial = pending.source.spatial_state
            for follow_up in pending.zone.movement_follow_ups:
                stop = diagnose_npc_magic_unsupported(scenario, current, last_id, movements)
                if stop is not None:
                    return NpcMagicScenarioResult(scenario, tuple(steps), stop)
                frame = scenario.frame_for(magic_movement_prefix(scenario, current, movements))
                plan = next(p for p in frame.give_ground_plans if p.actor_id == follow_up.target_id)
                target = next(t for t in pending.source.targets if t.actor_id == follow_up.target_id)
                moved = resolve_give_ground(GiveGroundResolutionRequest(
                    follow_up.request, spatial, target.actor_id, plan.destination_zone_id, target.injury.conditions,
                    path_entity_ids=plan.route.path_entity_ids, crosses_obstacle=plan.route.crosses_obstacle,
                    crosses_difficult_terrain=plan.route.crosses_difficult_terrain,
                    away_from_entity_id=pending.source.actor_id))
                movements = (*movements, complete_cowardly_flight_movement(follow_up, moved))
                spatial = moved.state
            source = NpcRosterCastingCompletionRequest(current,
                CowardlyFlightCastingCompletionRequest(pending, movements, spatial))
            publish(NpcRosterCastingCompletionResult(source, complete_cowardly_flight_casting(source.completion, rng)), source)
            continue
        if current.pending_minion_attack is not None:
            attack = current.pending_minion_attack
            decision = next(d for d in scenario.policy_for(attack.execution.actor_id).defeat_decisions
                            if d.target_id == attack.execution.target_id)
            source = NpcRosterMinionDefeatRequest(identifier('defeat'), current, decision)
            publish(acknowledge_npc_roster_minion_defeat(source), source)
            continue
        turn = current.round_state.active_turn
        if turn is None:
            if current.round_state.round_complete:
                source = NpcRosterRoundAdvanceRequest(identifier('advance'), current)
                publish(advance_npc_roster_round(source), source)
                continue
            actor_id = magic_next_actor(scenario, current)
            injury = current.roster.participant(actor_id).state.injury
            if injury.conditions.has(Condition.BROKEN):
                frame = scenario.frame_for(magic_scene_key(current))
                plan = next((p for p in frame.broken_plans if p.actor_id == actor_id), None) if frame else None
                declaration = (CombatActionDeclaration(CombatActionKind.MANOEUVRE, manoeuvre=ManoeuvreKind.RUN)
                    if plan is not None and plan.kind is NpcMagicBrokenPlanKind.FREE_MOVE_RUN else
                    CombatActionDeclaration(CombatActionKind.RECOVER))
            else:
                declaration = (CombatActionDeclaration(CombatActionKind.IMPROVISE, improvise_kind=ImproviseKind.SPELL,
                    improvise_approach_id=scenario.spell.lore_id) if actor_id == current.wizard.actor_id else
                    CombatActionDeclaration(CombatActionKind.ATTACK))
            source = NpcRosterTurnStartRequest(identifier('turn'), current, actor_id, declaration)
            publish(start_npc_roster_turn(source), source)
            continue
        actor_id = turn.actor_id
        if turn.action_slots[0].executed:
            source = NpcWoundTurnEndRequest(identifier('end'), current, actor_id, _end_sources(current, actor_id))
            publish(end_npc_wound_turn(source), source)
            continue
        frame = scenario.frame_for(magic_scene_key(current))
        actor = current.roster.participant(actor_id)
        policy = scenario.policy_for(actor_id)
        action_id = identifier('action')
        if actor.state.injury.conditions.has(Condition.BROKEN):
            plan = next(p for p in frame.broken_plans if p.actor_id == actor_id)
            movement = (None if plan.kind is NpcMagicBrokenPlanKind.SAFE_RECOVER else FreeMovementRequest(
                action_id + ':free-move', current.round_state, current.spatial_state, actor_id, policy.speed,
                actor.state.injury.conditions, plan.free_move_zone_ids, plan.free_move_route.path_entity_ids,
                plan.free_move_route.crosses_obstacle, plan.free_move_route.crosses_difficult_terrain))
            if plan.kind is NpcMagicBrokenPlanKind.FREE_MOVE_RUN:
                source = NpcBrokenRunRequest(action_id, current, actor_id, movement,
                    plan.run_destination_zone_id, plan.run_route.path_entity_ids,
                    plan.run_route.crosses_obstacle, plan.run_route.crosses_difficult_terrain, plan.fastest_route_confirmed)
                publish(execute_npc_broken_run(source), source)
            else:
                source = NpcBrokenRecoverRequest(action_id, current, actor_id,
                    policy.willpower_profile, movement, plan.fastest_route_confirmed, True)
                publish(execute_npc_broken_recover(source, rng), source)
            continue
        target_id = magic_target(scenario, current, actor_id, frame)
        if actor_id == current.wizard.actor_id:
            plans = {p.actor_id: p for p in frame.give_ground_plans}
            targets = tuple(NpcRosterCastingTargetContext(i, scenario.policy_for(i).willpower_profile,
                plans[i].can_leave_zone and not plans[i].impossible_confirmed)
                for i in magic_live_ids(current) if current.roster.participant(i).state.side is not actor.state.side
                and current.spatial_state.placement_for(i).zone_id == target_id)
            source = prepare_npc_roster_casting(request_id=action_id, state=current, selected_zone_id=target_id,
                targets=targets, facts=CowardlyFlightCastingFacts(
                    caster_can_cast=True, knows_battle_magic=scenario.facts.knows_battle_magic,
                    spell_memorised=scenario.facts.spell_memorised, caster_unarmoured=True,
                    no_bulky_items=scenario.facts.no_bulky_items, no_casting_opposition=scenario.facts.no_casting_opposition,
                    no_mixing_winds=scenario.facts.no_mixing_winds, no_other_test_modifiers=scenario.facts.no_other_test_modifiers,
                    no_potency_modifiers=scenario.facts.no_potency_modifiers, no_effect_immunities=scenario.facts.no_effect_immunities,
                    all_zone_enemies_included=True, target_zone_within_long_range=True), policy=policy.casting_policy)
            publish(NpcRosterCastingResult(source, execute_cowardly_flight_casting(source.casting, rng)), source)
            continue
        target = current.roster.participant(target_id)
        pair = next(p for p in frame.pair_ranges if {p.first_actor_id, p.second_actor_id} == {actor_id, target_id})
        approval = pair.first_range_approved_by_gm if pair.first_actor_id == actor_id else pair.second_range_approved_by_gm
        prepared = prepare_npc_attack(NpcAttackPreparationRequest(
            action_id + ':prepare', action_id + ':attack', action_id + ':attacker-test', actor.attack_snapshot(action_id + ':snapshot'),
            policy.attack_id, target_id, pair.target_range, target.state.current_resilience, False,
            actor.state.injury.conditions.has(Condition.STAGGERED), approval))
        protected = prepare_npc_attack_protection(prepared, ProtectionPreparationRequest(
            action_id + ':protect', target_id, prepared.attack, Skill.SHOOTING, scenario.facts.targets_aware, False,
            target.state.wields_weapon, target.state.holds_shield, Skill.ATHLETICS,
            target.protection_options(action_id + ':protection-test')))
        departure = next(d for d in frame.attack_departures if d.actor_id == target_id)
        execution = AttackActionExecutionRequest(action_id, current.round_state, actor_id, target_id, 1,
            KernelAttackRequest(action_id + ':kernel', target_id, protected.attack, target.definition.injury_policy,
                target.state.injury, departure.can_leave_zone, target_id in current.spatial_state.gave_ground_entity_ids))
        if target_id == current.wizard.actor_id:
            source = NpcRosterChampionAttackRequest(current, NpcChampionAttackRequest(current.champion_attack, protected, execution))
            publish(NpcRosterChampionAttackResult(source, execute_npc_champion_attack(source.attack, rng, decisions=decisions)), source)
        else:
            source = NpcRosterMinionAttackRequest(current, NpcRosterAttackExecutionRequest(current.minion_attack, protected, execution))
            publish(execute_npc_roster_minion_attack(source, rng, decisions=decisions), source)
