"""Two authored magic candidates through public ADR-0040 APIs.

Keep magic_simulation.py and magic_scenario.py beside this file. Numeric
profiles and GM facts retain the audited single-run scope; no generation or CLI.
"""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from multiprocessing import active_children
from random import getstate
import sys

from magic_simulation import authored_simulation_scenario
from towr.application.magic_evaluation_errors import MagicBalanceEvaluationError
from towr.application.magic_evaluation_service import evaluate_magic_candidates
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.magic_evaluation_models import (
    MagicBalanceCandidate, MagicBalanceEvaluationRequest, MagicBalanceEvaluationResult,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow


def build_request() -> MagicBalanceEvaluationRequest:
    ally_first = authored_simulation_scenario()
    wizard_first = replace(ally_first, actors=tuple(
        replace(actor, target_actor_ids=('wizard', 'ally')) if actor.actor_id == 'enemy' else actor
        for actor in ally_first.actors))
    return MagicBalanceEvaluationRequest(
        candidates=(MagicBalanceCandidate('ally-first', ally_first),
                    MagicBalanceCandidate('wizard-first', wizard_first)),
        master_seed=42, trials_per_candidate=8, max_total_trials=16,
        window=ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)), top_k=2,
    )


def print_report(report: MagicBalanceEvaluationResult) -> None:
    source = report.source_request
    print('profiles: authored Champion-Wizard Level2 Casting/Willpower3d/3 RES4; Shooting Minions3d/3 Dam3 RES3')
    print('rules: BOOK-PLAYER-GUIDE 1.4 / Combat p112; Broken p122; Magic pp156-157,162; Wounds pp190-191')
    print('NPC injury policies: BOOK-GM-GUIDE 1.1 / Allies and Antagonists pp91-92')
    print('facts/policies: explicit ranges, scene frames, departures, Curse Give Ground and Broken Recover; '
          'repeated Staggered -> Wound; Minion defeat -> GM-approved knocked out')
    print('alternatives change enemy target priority only; unsupported remains in ALL trials, not defeat/draw')
    print(f'seed: {source.master_seed}; seed_scheme: {report.seed_scheme}; trials_per_candidate: {source.trials_per_candidate}')
    print(f'window: min={source.window.minimum}, target={source.window.target}, max={source.window.maximum}; top_k: {source.top_k}')
    print(f'budget per evaluation: planned={source.planned_trials}; actual={report.total_trials}; max={source.max_total_trials}')
    for row in report.candidates:
        assessment = row.assessment
        scenario = assessment.source_request.scenario
        summary = assessment.summary
        counts = summary.outcome_counts
        print(f'candidate: {row.candidate_id}; round_budget: {scenario.max_rounds}; '
              f'perspective: {scenario.perspective_side.value}; objective: {",".join(scenario.objective.target_actor_ids)}')
        print(f'  counts goal/perspective_defeated/round_limit_reached/unsupported: {counts.objective_achieved}/'
              f'{counts.perspective_defeated}/{counts.round_limit_reached}/{counts.unsupported_path}')
        print(f'  rates goal/perspective_defeated/round_limit/unsupported: {assessment.objective_achieved_rate}, '
              f'{assessment.perspective_defeated_rate}, {assessment.round_limit_rate}, {assessment.unsupported_path_rate}')
        print(f'  actions: {summary.total_action_count}; started/completed rounds: '
              f'{summary.total_started_round_count}/{summary.total_completed_round_count}; '
              f'status: {assessment.status.value}; window_match: {assessment.window_match}')
    print(f'selected: {report.selected_candidate_ids}')


def main() -> None:
    source = build_request()
    before, rng_before = deepcopy(source), getstate()
    children_before = {child.pid for child in active_children()}
    sequential = evaluate_magic_candidates(source, SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL))
    process = evaluate_magic_candidates(
        source, SimulationExecutionOptions(SimulationExecutionMode.PROCESS, workers=2, batch_size=3))
    # Compare the complete report, without requiring a Monte Carlo percentage or winner.
    assert sequential == process
    assert sequential.selected_candidate_ids == process.selected_candidate_ids
    assert sequential.source_request is process.source_request is source
    assert sequential.total_trials == process.total_trials == source.planned_trials
    for report in (sequential, process):
        for row, expected in zip(report.candidates, source.simulation_requests):
            assert row.assessment.source_request is row.assessment.summary.source_request is expected
            assert row.assessment.window is source.window
    assert source == before and getstate() == rng_before
    assert {child.pid for child in active_children()} == children_before
    # Publish only after both complete evaluations and every consistency check.
    print_report(sequential)
    print('sequential/process full reports and selected IDs: equal; process workers=2 batch_size=3')
    print(f'demonstration runs two complete evaluations: {2 * source.planned_trials} total trials')
    print('input/global RNG unchanged; no remaining child processes')
    print('finite seeded observations only; eligibility is not tactical completeness or a difficulty guarantee')


if __name__ == '__main__':
    try:
        main()
    except MagicBalanceEvaluationError as error:
        print(f'candidate failed: {error.candidate_id}; cause: {type(error.__cause__).__name__}: {error.__cause__}',
              file=sys.stderr)
        raise  # Keep original cause/notes and fail without a partial stdout report.
