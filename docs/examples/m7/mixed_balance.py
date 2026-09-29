"""Explicit reserve -> public Mixed generator -> staged evaluation; no wire format."""

from copy import deepcopy
from dataclasses import fields, replace
from fractions import Fraction
from multiprocessing import active_children
import random
import sys

from mixed_scenario import build_scenario
from towr.application.mixed_candidate_generation import generate_mixed_candidates
from towr.application.mixed_candidate_generation_errors import MixedCandidateGenerationError
from towr.application.mixed_candidate_generation_models import MixedCandidateGenerationRequest, MixedCompositionGroup
from towr.application.mixed_staged_evaluation_errors import MixedStagedEvaluationError
from towr.application.mixed_staged_evaluation_service import evaluate_mixed_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.mixed_staged_evaluation import mixed_continuation_candidate_ids
from towr.balance.mixed_staged_evaluation_models import MixedBalanceStage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_mixed_scenario_models import NpcMixedActorPolicy, NpcMixedPairRange, NpcMixedScenarioFacts
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.turn_models import CombatSide
from towr.domain.spatial_models import SpatialEntityPlacement


def build_request() -> MixedCandidateGenerationRequest:
    # Public example's numeric Footpad Dagger / Brigand Warbow projections:
    # GM1.1 Allies and Antagonists pp91,93,97. No Axe/Craven Melee branch.
    base = build_scenario()
    current = base.initial.current
    bow = current.state.roster.participant("Pbow")
    opposition = CombatSide.OPPOSITION
    # Author the extra actor before generation; the generator selects a reserve.
    extra = replace(bow, state=replace(bow.state, actor_id="E3", side=opposition))
    roster = NpcRoster((*current.state.roster.participants, extra))
    actor_ids = ("Pbow", "P1", "P2", "E1", "E2", "E3")
    current = replace(current, id="example:mixed:reserve", state=NpcRosterAttackState(roster),
                      round_state=replace(current.round_state, participants=roster.turn_participants),
                      actor_order=actor_ids)
    spatial = replace(base.initial.spatial_state, placements=(
        *base.initial.spatial_state.placements, SpatialEntityPlacement("E3", opposition.value, "far"),
    ))
    policies = []
    for actor in actor_ids:
        targets = ("E3", "E2", "E1") if actor in ("Pbow", "P1", "P2") else ("Pbow", "P1", "P2")
        # Authored for every composition/reachable state, not inferred from counts.
        policies.append(NpcMixedActorPolicy(actor, targets, tuple(
            MinionDefeatDecision(actor, target, NpcDefeatDisposition.KNOCKED_OUT, gm_approved=True)
            for target in targets
        ), outnumbering_bonus_approved=actor != "P2", can_leave_zone=actor == "P2"))
    template = replace(
        base, initial=replace(base.initial, current=current, spatial_state=spatial),
        pair_ranges=(*base.pair_ranges, *(NpcMixedPairRange(actor, "E3", Range.MEDIUM)
                                        for actor in ("Pbow", "P1", "P2"))),
        actor_policies=tuple(policies), objective=NpcDefeatObjective(("E3", "E2", "E1")),
    )
    # Separate family assertions; omitted actors are absent from each battle.
    # Close is explicit, never inferred from a shared Zone (PG1.4 Rules p114).
    facts = NpcMixedScenarioFacts(
        targets_aware=True, clear_line_of_sight=True, stationary=True,
        all_zone_combatants_included=True, unmounted_combatants_only=True, no_higher_ground=True,
        no_additional_rules=True, no_other_test_modifiers=True,
        ammunition_sufficient=True, requires_reload_action=False,
    )
    pairs = tuple(replace(p) for p in template.pair_ranges)
    return MixedCandidateGenerationRequest(
        template, (MixedCompositionGroup("A", ("E2", "E1"), 1, 2),
                   MixedCompositionGroup("B", ("E3",), 0, 1)),
        facts, pairs, "mixed", 4, 42, (MixedBalanceStage(8, 2), MixedBalanceStage(32, 1)), 96,
        ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)),
    )


def main() -> None:
    source = build_request()
    before = deepcopy(source)
    rng_before = random.getstate()
    children_before = {child.pid for child in active_children()}
    try:
        generated = generate_mixed_candidates(source)
        evaluation = generated.evaluation_request
        sequential = evaluate_mixed_candidates_staged(evaluation, SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL))
        process = evaluate_mixed_candidates_staged(
            evaluation, SimulationExecutionOptions(SimulationExecutionMode.PROCESS, workers=2, batch_size=5))
    except MixedCandidateGenerationError as error:
        print(f"generation failed: candidate={error.candidate_id}; counts={error.counts}; cause={error.__cause__}", file=sys.stderr)
        raise
    except MixedStagedEvaluationError as error:
        print(f"evaluation failed: stage={error.stage_index}; candidate={error.candidate_id}; cause={error.__cause__}", file=sys.stderr)
        raise
    # No hard-coded Monte Carlo percentage, survivor or winner.
    assert sequential == process
    assert sequential.selected_candidate_ids == process.selected_candidate_ids
    assert generated.source_request is source
    assert sequential.source_request is evaluation and process.source_request is evaluation
    assert len(evaluation.candidates) == source.candidate_count == 4
    assert sequential.total_trials <= sequential.planned_trials == source.planned_trials == source.max_total_trials == 96
    assert source == before and random.getstate() == rng_before
    assert {child.pid for child in active_children()} == children_before

    print("profiles: Footpad Dagger / Brigand Warbow; BOOK-GM-GUIDE 1.1 / Allies and Antagonists pp91,93,97")
    print("numeric: Dagger Close 3d/3 Dam2 1H RES3 Athletics 3d/3; Warbow Medium-Long 3d/3 Dam3 2H RES4 Athletics 3d/2")
    print("rules: BOOK-PLAYER-GUIDE 1.4 / Equipment p94; Rules pp112,114,118-119,123; BOOK-GM-GUIDE 1.1 pp91,93,97")
    print(f"reserve: {source.template_scenario.initial.current.actor_order}; fixed perspective: {source.template_scenario.perspective_side.value}")
    print(f"seed: {source.master_seed}; seed_scheme: {sequential.seed_scheme}; round_budget: {source.template_scenario.initial.max_rounds}")
    print(f"window: min={source.window.minimum}, target={source.window.target}, max={source.window.maximum}")
    print("family facts: " + "; ".join(f"{f.name}={getattr(source.facts, f.name)}" for f in fields(source.facts)))
    print("placements: Pbow@rear; P1/P2/E1/E2@arena; E3@far; all actors are Minions")
    print("family pairs: " + str(tuple((p.first_actor_id, p.second_actor_id, p.target_range.value) for p in source.pair_ranges)))
    print("no movement/weapon switching; no available target -> unsupported_path, not defeat")
    print("omitted reserve actors are absent from each battle; graph: rear/arena/far triangle; repeated Staggered -> Wound")
    for group in source.groups:
        print(f"group {group.group_id}: reserve={group.actor_ids}; counts={group.minimum_count}..{group.maximum_count}")
    for policy in source.template_scenario.actor_policies:
        decisions = tuple((d.target_id, d.disposition.value, d.gm_approved) for d in policy.defeat_decisions)
        print(f"policy {policy.actor_id}: targets={policy.target_actor_ids}; outnumbering_approved={policy.outnumbering_bonus_approved}; "
              f"can_leave_zone={policy.can_leave_zone}; defeats={decisions}")
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
            print(f"  continuation (original candidate order): {mixed_continuation_candidate_ids(report)}")
    print(f"staged status: {sequential.status.value}; final selected: {sequential.selected_candidate_ids}")
    print("sequential/process full reports and selected IDs: equal; workers=2 batch_size=5")
    print(f"two complete evaluations: {sequential.total_trials + process.total_trials} trials; each stage reruns its full batch from index 0")
    print("input/global RNG unchanged; no remaining child processes; output is an observation, not a difficulty preset")


if __name__ == "__main__":
    main()
