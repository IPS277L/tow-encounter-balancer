"""One typed M6 scenario through the public runner; stdout is not a wire format."""

from dataclasses import fields
from random import Random

from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import StaggerChoice
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_melee_scenario_models import NpcMeleeActorPolicy, NpcMeleeScenario, NpcMeleeScenarioFacts
from towr.domain.npc_melee_scenario_result_models import NpcMeleeScenarioResult
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult, NpcRosterAttackState
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster,
)
from towr.domain.npc_round_request_models import NpcRoundRequest
from towr.domain.npc_rounds_models import NpcRoundsRequest, NpcRoundsResult
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.engine.npc_melee_scenario_runner import run_npc_melee_scenario


SEED = 42
ROUND_BUDGET = 3


def build_scenario() -> NpcMeleeScenario:
    # GM Guide 1.1, Allies and Antagonists / Brigands & Footpads / Footpad, p97.
    # Lurker applies outside battle; this fixture explicitly starts aware.
    definition = NpcDefinition(
        "example:footpad", "RULE-PROFILE-TALABEC-005", TargetInjuryPolicy.MINION, 1, ResilienceProfile(3),
        (NpcAttackProfile(
            "dagger", "RULE-PROFILE-TALABEC-005:dagger", Skill.MELEE, InlineProfile(3, 3), DamageProfile(2),
            RangedWeaponRange.CLOSE, RangedWeaponRange.CLOSE, RangedWeaponHands.ONE_HANDED,
        ),),
        (NpcProtectionProfile("RULE-PROFILE-TALABEC-005:protection", Skill.ATHLETICS, InlineProfile(3, 3)),),
    )
    perspective, opposition = CombatSide.PLAYERS_AND_ALLIES, CombatSide.OPPOSITION
    # Side names do not turn these Minions into player characters.
    actors = (("P1", perspective), ("P2", perspective), ("E1", opposition), ("E2", opposition))
    roster = NpcRoster(tuple(NpcParticipantSnapshot(definition, NpcParticipantState(
        actor_id, definition.id, side, ProfileInjuryState(0, 1), ("dagger",), definition.resilience, True, False,
    )) for actor_id, side in actors))
    combat = CombatRoundState(1, roster.turn_participants, (perspective, opposition))
    current = NpcRoundRequest("example:melee", NpcRosterAttackState(roster), combat,
                              tuple(actor_id for actor_id, _ in actors), ())
    spatial = SpatialBattleState(
        ZoneGraph(("arena", "exit"), (ZoneConnection("arena", "exit"),)),
        tuple(SpatialEntityPlacement(actor_id, side.value, "arena") for actor_id, side in actors),
    )
    # PG 1.4 Rules / The Battlefield p114: a shared Zone alone does not establish Close.
    facts = NpcMeleeScenarioFacts(
        zone_id="arena", all_opponents_in_close_range=True, targets_aware=True, clear_line_of_sight=True,
        stationary=True, all_zone_combatants_included=True, unmounted_combatants_only=True,
        no_higher_ground=True, no_additional_rules=True, no_other_test_modifiers=True, can_leave_zone=True,
    )
    # Authored decisions, not inferred approvals. GM Guide 1.1 / Minions p91;
    # PG 1.4 / Attack Modifiers pp118-119 permits GM withholding of outnumbering.
    policies = tuple(NpcMeleeActorPolicy(
        actor_id, tuple(target for target, target_side in actors if target_side is not side),
        tuple(MinionDefeatDecision(actor_id, target, NpcDefeatDisposition.KNOCKED_OUT, gm_approved=True)
              for target, target_side in actors if target_side is not side),
        outnumbering_bonus_approved=True,
    ) for actor_id, side in actors)
    return NpcMeleeScenario(
        NpcRoundsRequest(current, spatial, ROUND_BUDGET), facts, policies,
        # Legal fixed tactic even with an escape path; PG 1.4 / Staggered p123.
        StaggerChoice.SUFFER_WOUND, perspective,
        NpcDefeatObjective(tuple(actor_id for actor_id, side in actors if side is opposition)),
    )


def print_report(result: NpcMeleeScenarioResult, *, seed: int) -> None:
    source, report = result.source_scenario, result.runner_report
    print(f"scenario: {source.initial.current.id}; seed: {seed}; round_budget: {source.initial.max_rounds}")
    print("profile: RULE-PROFILE-TALABEC-005; BOOK-GM-GUIDE 1.1 / Allies and Antagonists / Footpad p97")
    print("numeric: Dagger Close 3d/3 Dam2 1H; Athletics 3d/3; RES3; Minion")
    print("rules: BOOK-PLAYER-GUIDE 1.4 / Rules pp107,112,114,118-119,123; BOOK-GM-GUIDE 1.1 pp91,93,97")
    print(f"perspective: {source.perspective_side.value}; objective: {','.join(source.objective.target_actor_ids)}")
    print("side_order: " + ",".join(side.value for side in source.initial.current.round_state.side_order))
    print("actor_order: " + ",".join(source.initial.current.actor_order))
    print("facts: " + "; ".join(f"{field.name}={getattr(source.facts, field.name)}" for field in fields(source.facts)))
    print("repeated_stagger: " + source.repeated_stagger_choice.value)
    for policy in source.actor_policies:
        decisions = ",".join(f"{item.target_id}:{item.disposition.value}:approved={item.gm_approved}"
                             for item in policy.defeat_decisions)
        print(f"policy {policy.actor_id}: targets={','.join(policy.target_actor_ids)}; "
              f"outnumbering_approved={policy.outnumbering_bonus_approved}; defeats={decisions}")
    print("outcome: " + result.outcome.value)
    print(f"attacks: {report.executed_attack_count}; visited_rounds: {report.visited_round_count}; "
          f"completed_rounds: {report.newly_completed_round_count}")
    # The final runner observation may stop on pending defeat. The scenario's
    # terminal suffix resolves it without another Attack/turn/observation.
    print(f"last_runner_stop: {report.outcome.value}; runner_pending: {report.pending_follow_up_count}; "
          f"scenario_pending: {len(result.current.pending_follow_ups)}")
    print(f"defeat_acknowledgements: {len(result.defeat_acknowledgements)}; "
          f"terminal_acknowledgement: {result.terminal_acknowledgement is not None}")
    for call in report.source_steps:
        if not isinstance(call, NpcRoundsResult):
            continue
        for combat in call.rounds:
            for action in combat.steps:
                if not isinstance(action, NpcRosterAttackExecutionResult):
                    continue
                execution = action.execution
                trace = execution.resolution.attack.attacker_test.trace
                print(f"attack {execution.request_id}: {execution.actor_id}->{execution.target_id}; "
                      f"dice={trace.rolled_dice}; modifiers={','.join(trace.applied_rule_ids)}")
    for actor in result.current.state.roster.participants:
        injury = actor.state.injury
        print(f"actor {actor.state.actor_id}: wounds={injury.wounds}; defeated={injury.defeated}; "
              f"conditions={','.join(condition.value for condition in injury.conditions.conditions)}")


def main() -> None:
    scenario = build_scenario()
    print_report(run_npc_melee_scenario(scenario, Random(SEED)), seed=SEED)


if __name__ == "__main__":
    main()
