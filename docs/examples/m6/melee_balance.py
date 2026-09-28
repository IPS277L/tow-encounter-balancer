"""Explicit reserve -> public Melee generator -> staged evaluation; no wire format."""

from copy import deepcopy
from dataclasses import fields, replace
from fractions import Fraction
from multiprocessing import active_children
import random
import sys

from melee_scenario import build_scenario
from towr.application.melee_candidate_generation import generate_melee_candidates
from towr.application.melee_candidate_generation_errors import MeleeCandidateGenerationError
from towr.application.melee_candidate_generation_models import MeleeCandidateGenerationRequest, MeleeCompositionGroup
from towr.application.melee_staged_evaluation_errors import MeleeStagedEvaluationError
from towr.application.melee_staged_evaluation_service import evaluate_melee_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.melee_staged_evaluation import melee_continuation_candidate_ids
from towr.balance.melee_staged_evaluation_models import MeleeBalanceStage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_melee_scenario_models import NpcMeleeActorPolicy, NpcMeleeScenarioFacts
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcParticipantSnapshot, NpcParticipantState, NpcRoster
from towr.domain.spatial_models import SpatialEntityPlacement


def build_request() -> MeleeCandidateGenerationRequest:
    # Reuse the public example's Footpad profile, not a tests/private builder.
    # GM1.1 Allies and Antagonists / Footpad p97: Lurker is outside battle.
    base = build_scenario()
    definition = base.initial.current.state.roster.participants[0].definition
    opposition = base.initial.current.state.roster.participants[-1].state.side
    # Author E3 as part of the input reserve. The generator only selects actors.
    extra = NpcParticipantSnapshot(definition, NpcParticipantState(
        "E3", definition.id, opposition, ProfileInjuryState(0, 1), ("dagger",),
        definition.resilience, True, False,
    ))
    roster = NpcRoster((*base.initial.current.state.roster.participants, extra))
    actor_ids = ("P1", "P2", "E1", "E2", "E3")
    current = replace(base.initial.current, id="example:melee:reserve", state=NpcRosterAttackState(roster),
                      round_state=replace(base.initial.current.round_state, participants=roster.turn_participants),
                      actor_order=actor_ids)
    spatial = replace(base.initial.spatial_state, placements=(
        *base.initial.spatial_state.placements, SpatialEntityPlacement("E3", opposition.value, "arena"),
    ))
    policies = []
    for actor in actor_ids:
        targets = ("E3", "E2", "E1") if actor in ("P1", "P2") else ("P1", "P2")
        # Authored for every composition/reachable state, not inferred from counts.
        # PG1.4 Rules / Attack Modifiers pp118-119; GM1.1 / Minions p91.
        policies.append(NpcMeleeActorPolicy(actor, targets, tuple(
            MinionDefeatDecision(actor, target, NpcDefeatDisposition.KNOCKED_OUT, gm_approved=True)
            for target in targets
        ), outnumbering_bonus_approved=actor != "P2"))
    template = replace(base, initial=replace(base.initial, current=current, spatial_state=spatial),
                       actor_policies=tuple(policies), objective=NpcDefeatObjective(("E3", "E2", "E1")))
    # Separate family assertions: omitted reserve actors are absent from that
    # battle. Sharing a Zone alone does not establish Close (PG1.4 Rules p114).
    facts = NpcMeleeScenarioFacts(
        zone_id="arena", all_opponents_in_close_range=True, targets_aware=True, clear_line_of_sight=True,
        stationary=True, all_zone_combatants_included=True, unmounted_combatants_only=True,
        no_higher_ground=True, no_additional_rules=True, no_other_test_modifiers=True, can_leave_zone=True,
    )
    return MeleeCandidateGenerationRequest(
        template, (MeleeCompositionGroup("A", ("E2", "E1"), 0, 2),
                   MeleeCompositionGroup("B", ("E3",), 0, 1)),
        facts, "footpads", 5, 42, (MeleeBalanceStage(8, 2), MeleeBalanceStage(32, 1)), 104,
        ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)),
    )


def main() -> None:
    source = build_request()
    before = deepcopy(source)
    rng_before = random.getstate()
    children_before = {child.pid for child in active_children()}
    try:
        generated = generate_melee_candidates(source)
        evaluation = generated.evaluation_request
        sequential = evaluate_melee_candidates_staged(evaluation, SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL))
        process = evaluate_melee_candidates_staged(
            evaluation, SimulationExecutionOptions(SimulationExecutionMode.PROCESS, workers=2, batch_size=5))
    except MeleeCandidateGenerationError as error:
        print(f"generation failed: candidate={error.candidate_id}; counts={error.counts}; cause={error.__cause__}", file=sys.stderr)
        raise
    except MeleeStagedEvaluationError as error:
        print(f"evaluation failed: stage={error.stage_index}; candidate={error.candidate_id}; cause={error.__cause__}", file=sys.stderr)
        raise
    # No hard-coded Monte Carlo percentage, survivor or winner.
    assert sequential == process
    assert sequential.selected_candidate_ids == process.selected_candidate_ids
    assert generated.source_request is source
    assert sequential.source_request is evaluation and process.source_request is evaluation
    assert len(evaluation.candidates) == source.candidate_count == 5
    assert sequential.total_trials <= sequential.planned_trials == source.planned_trials == source.max_total_trials == 104
    assert source == before and random.getstate() == rng_before
    assert {child.pid for child in active_children()} == children_before

    print("profile: RULE-PROFILE-TALABEC-005; BOOK-GM-GUIDE 1.1 / Allies and Antagonists / Footpad p97")
    print("numeric: Dagger Close 3d/3 Dam2 1H; Athletics 3d/3; RES3; Minion; aware battle")
    print("rules: BOOK-PLAYER-GUIDE 1.4 / Rules pp112,114,118-119,123; BOOK-GM-GUIDE 1.1 pp91,93,97")
    print(f"reserve: {source.template_scenario.initial.current.actor_order}; fixed perspective: {source.template_scenario.perspective_side.value}")
    print(f"seed: {source.master_seed}; seed_scheme: {sequential.seed_scheme}; round_budget: {source.template_scenario.initial.max_rounds}")
    print(f"window: min={source.window.minimum}, target={source.window.target}, max={source.window.maximum}")
    print("family facts: " + "; ".join(f"{f.name}={getattr(source.facts, f.name)}" for f in fields(source.facts)))
    print("omitted reserve actors are absent from each battle; graph: arena <-> exit; repeated Staggered -> Wound")
    for group in source.groups:
        print(f"group {group.group_id}: reserve={group.actor_ids}; counts={group.minimum_count}..{group.maximum_count}")
    for policy in source.template_scenario.actor_policies:
        decisions = tuple((d.target_id, d.disposition.value, d.gm_approved) for d in policy.defeat_decisions)
        print(f"policy {policy.actor_id}: targets={policy.target_actor_ids}; outnumbering_approved={policy.outnumbering_bonus_approved}; defeats={decisions}")
    print(f"generated: {source.candidate_count}; max_candidates: {source.max_candidates}")
    for candidate in evaluation.candidates:
        scenario = candidate.scenario
        print(f"candidate: {candidate.candidate_id}; initial: {scenario.initial.current.id}; "
              f"actors={scenario.initial.current.actor_order}; objective={scenario.objective.target_actor_ids}")
    print("stages (full trials per candidate, keep): " + str(tuple((s.trials_per_candidate, s.keep) for s in source.stages)))
    print(f"staged budget per evaluation: planned={sequential.planned_trials}; actual={sequential.total_trials}; max={source.max_total_trials}")
    for index, report in enumerate(sequential.stage_reports):
        print(f"stage index: {index}; trials per candidate: {report.source_request.trials_per_candidate}; actual trials: {report.total_trials}")
        for row in report.candidates:
            a = row.assessment
            c = a.summary.outcome_counts
            print(f"  {row.candidate_id}: counts goal/defeated/limit/unsupported={c.objective_achieved}/{c.side_defeated}/{c.round_limit}/{c.unsupported_path}; "
                  f"rates={a.objective_achieved_rate},{a.side_defeated_rate},{a.round_limit_rate},{a.unsupported_path_rate}; "
                  f"attacks={a.summary.total_attack_count}; visited_rounds={a.summary.total_visited_round_count}; "
                  f"status={a.status.value}; window_match={a.window_match}")
        print(f"  local selected: {report.selected_candidate_ids}")
        if index < len(sequential.stage_reports) - 1:
            print(f"  continuation (original candidate order): {melee_continuation_candidate_ids(report)}")
    print(f"staged status: {sequential.status.value}; final selected: {sequential.selected_candidate_ids}")
    print("sequential/process full reports and selected IDs: equal; workers=2 batch_size=5")
    print(f"two complete evaluations: {sequential.total_trials + process.total_trials} trials; each stage reruns its full batch from index 0")
    print("input/global RNG unchanged; no remaining child processes; output is an observation, not a difficulty preset")


if __name__ == "__main__":
    main()
