"""Two authored Melee candidates through the public evaluator; no wire format."""

from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from multiprocessing import active_children
import random

from melee_scenario import build_scenario
from towr.application.melee_evaluation_errors import MeleeBalanceEvaluationError
from towr.application.melee_evaluation_service import evaluate_melee_candidates
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.melee_evaluation_models import (
    MeleeBalanceCandidate, MeleeBalanceEvaluationRequest, MeleeBalanceEvaluationResult,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.npc_melee_scenario_models import NpcMeleeScenario
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_round_request_models import NpcRoundRequest
from towr.domain.npc_rounds_models import NpcRoundsRequest
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.turn_models import CombatRoundState


def build_two_against_one() -> NpcMeleeScenario:
    """Author exactly P1/P2 versus E1, not a general composition generator."""
    original = build_scenario()
    actor_ids = ("P1", "P2", "E1")
    roster = NpcRoster(tuple(actor for actor in original.initial.current.state.roster.participants
                             if actor.state.actor_id in actor_ids))
    combat = CombatRoundState(1, roster.turn_participants, original.initial.current.round_state.side_order)
    current = NpcRoundRequest("example:melee:2x1", NpcRosterAttackState(roster), combat, actor_ids, ())
    spatial = SpatialBattleState(original.initial.spatial_state.graph, tuple(
        placement for placement in original.initial.spatial_state.placements if placement.entity_id in actor_ids))
    policies = tuple(replace(
        policy,
        target_actor_ids=tuple(target for target in policy.target_actor_ids if target in actor_ids),
        defeat_decisions=tuple(decision for decision in policy.defeat_decisions if decision.target_id in actor_ids),
    ) for policy in original.actor_policies if policy.actor_id in actor_ids)
    # These authored facts and GM decisions apply to this scenario too:
    # all enemy pairs are Close/aware, all Zone combatants are included;
    # ordinary outnumbering is approved and defeat means knocked out.
    # PG 1.4 Rules / The Battlefield p114, Attack Modifiers pp118-119;
    # GM 1.1 Allies and Antagonists / Minions p91, Footpad p97.
    return NpcMeleeScenario(
        NpcRoundsRequest(current, spatial, original.initial.max_rounds), original.facts, policies,
        original.repeated_stagger_choice, original.perspective_side, NpcDefeatObjective(("E1",)),
    )


def build_request() -> MeleeBalanceEvaluationRequest:
    return MeleeBalanceEvaluationRequest(
        candidates=(MeleeBalanceCandidate("footpads:2x1", build_two_against_one()),
                    MeleeBalanceCandidate("footpads:2x2", build_scenario())),
        master_seed=42, trials_per_candidate=16, max_total_trials=32,
        window=ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)), top_k=1,
    )


def print_report(report: MeleeBalanceEvaluationResult) -> None:
    source = report.source_request
    print("profile: Footpad; BOOK-GM-GUIDE 1.1 / Allies and Antagonists / Footpad p97")
    print("rules: BOOK-PLAYER-GUIDE 1.4 / Rules pp112,114,118-119,123; BOOK-GM-GUIDE 1.1 / Minions p91")
    print("facts/policies: stationary aware Minions, explicit Close, all Zone actors included; "
          "outnumbering approved; repeated Staggered -> Wound; defeat -> knocked out")
    print(f"seed: {source.master_seed}; seed_scheme: {report.seed_scheme}; trials_per_candidate: {source.trials_per_candidate}")
    print(f"window: min={source.window.minimum}, target={source.window.target}, max={source.window.maximum}; top_k: {source.top_k}")
    print(f"budget per evaluation: planned={source.planned_trials}; actual={report.total_trials}; max={source.max_total_trials}")
    for row in report.candidates:
        assessment = row.assessment
        scenario = assessment.source_request.scenario
        counts = assessment.summary.outcome_counts
        print(f"candidate: {row.candidate_id}; round_budget: {scenario.initial.max_rounds}; "
              f"perspective: {scenario.perspective_side.value}; objective: {','.join(scenario.objective.target_actor_ids)}")
        print(f"  counts goal/defeated/limit/unsupported: {counts.objective_achieved}/"
              f"{counts.side_defeated}/{counts.round_limit}/{counts.unsupported_path}")
        print(f"  rates goal/defeated/limit/unsupported: {assessment.objective_achieved_rate}, "
              f"{assessment.side_defeated_rate}, {assessment.round_limit_rate}, {assessment.unsupported_path_rate}")
        print(f"  attacks: {assessment.summary.total_attack_count}; visited_rounds: "
              f"{assessment.summary.total_visited_round_count}; status: {assessment.status.value}; "
              f"window_match: {assessment.window_match}")
    print(f"selected: {report.selected_candidate_ids}")


def main() -> None:
    source = build_request()
    before = deepcopy(source)
    rng_before = random.getstate()
    children_before = {child.pid for child in active_children()}
    sequential = evaluate_melee_candidates(source, SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL))
    process = evaluate_melee_candidates(
        source, SimulationExecutionOptions(SimulationExecutionMode.PROCESS, workers=2, batch_size=5))
    # Compare full reports, not a hard-coded Monte Carlo rate or winner.
    assert sequential == process
    assert sequential.selected_candidate_ids == process.selected_candidate_ids
    assert sequential.source_request is source and process.source_request is source
    assert sequential.total_trials == process.total_trials == source.planned_trials
    assert source == before and random.getstate() == rng_before
    assert {child.pid for child in active_children()} == children_before
    print_report(sequential)
    print("sequential/process reports and selected IDs: equal; process workers=2 batch_size=5")
    print(f"demonstration runs two complete evaluations: {2 * source.planned_trials} total trials")
    print("input/global RNG unchanged; no remaining child processes")


if __name__ == "__main__":
    try:
        main()
    except MeleeBalanceEvaluationError as error:
        print(f"candidate failed: {error.candidate_id}; cause: {type(error.__cause__).__name__}: {error.__cause__}")
        raise  # Preserve the cause/worker notes and return failure, without a partial report.
