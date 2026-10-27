"""Finite synthetic arithmetic for ADR-0041, not a staged evaluator.

Keep magic_simulation.py and magic_scenario.py beside this file. Existing
bounded models validate illustrative aggregates; no battles or RNG draws run.
"""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from multiprocessing import active_children
from random import getstate

from magic_simulation import authored_simulation_scenario
from towr.balance.magic_assessment import assess_magic_candidate
from towr.balance.magic_assessment_models import MagicAssessmentStatus
from towr.balance.magic_evaluation_models import (
    MagicBalanceCandidate, MagicBalanceCandidateResult, MagicBalanceEvaluationRequest,
    MagicBalanceEvaluationResult,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts
from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary


def main() -> None:
    rng_before = getstate()
    children_before = {child.pid for child in active_children()}
    scenario = authored_simulation_scenario()
    other = replace(scenario, actors=tuple(
        replace(actor, target_actor_ids=('wizard', 'ally')) if actor.actor_id == 'enemy' else actor
        for actor in scenario.actors))
    candidates = tuple(MagicBalanceCandidate(name, source) for name, source in
                       zip(('A', 'B', 'C', 'D'), (scenario, other, scenario, other), strict=True))
    window = ObjectiveRateWindow(F(9, 20), F(1, 2), F(11, 20))
    first_input = MagicBalanceEvaluationRequest(candidates, 42, 10, 40, window, 2)
    before = deepcopy(first_input)

    def report(source, goals, unsupported):
        rows = []
        for candidate, simulation, goal, unknown in zip(
                source.candidates, source.simulation_requests, goals, unsupported, strict=True):
            n = simulation.trials
            # Necessary aggregate bounds, not a claim that these histories ran.
            started = n * simulation.scenario.max_rounds
            completed = started - unknown
            summary = NpcMagicSimulationSummary(
                simulation, NpcMagicOutcomeCounts(goal, 0, n - goal - unknown, unknown),
                completed, started, completed,
            )
            rows.append(MagicBalanceCandidateResult(
                candidate.candidate_id, assess_magic_candidate(simulation, summary, source.window)))
        return MagicBalanceEvaluationResult(source, tuple(rows))

    def illustrative_continuation(observation):
        # Finite arithmetic only; production helper/type/chain guards are future work.
        eligible = (row for row in observation.candidates
                    if row.assessment.status is MagicAssessmentStatus.ELIGIBLE)
        ranked = sorted(eligible, key=lambda row: abs(
            row.assessment.objective_achieved_rate - observation.source_request.window.target))
        kept = {row.candidate_id for row in ranked[:observation.source_request.top_k]}
        return tuple(row.candidate_id for row in observation.candidates if row.candidate_id in kept)

    first = report(first_input, (4, 7, 5, 6), (0, 0, 1, 0))
    assert first.selected_candidate_ids == ()
    assert illustrative_continuation(first) == ('A', 'D')
    last_input = MagicBalanceEvaluationRequest((candidates[0], candidates[3]), 42, 100, 200, window, 1)
    final = report(last_input, (49, 51), (0, 0))
    assert final.selected_candidate_ids == ('A',)
    assert report(last_input, (45, 55), (0, 0)).selected_candidate_ids == ('A',)
    assert report(last_input, (40, 60), (0, 0)).selected_candidate_ids == ()
    assert first.total_trials + final.total_trials == 240
    assert 4 * 10 + min(4, 2) * 100 == 240 > 239
    assert 4 * 10 + min(4, 2) * (100 - 10) == 220  # Excluded incremental budget.
    assert 4 * 10 + 2 * 100 + min(2, 5) * 1000 == 2240
    # A closer D still returns in original input order with A, not ranking order.
    assert illustrative_continuation(report(first_input, (4, 7, 5, 5), (0, 0, 1, 0))) == ('A', 'D')
    assert illustrative_continuation(report(first_input, (4, 7, 5, 6), (0, 1, 1, 1))) == ('A',)
    single = replace(last_input, candidates=(candidates[0],), max_total_trials=100)
    assert first.total_trials + report(single, (49,), (0,)).total_trials == 140
    exhausted = report(first_input, (4, 7, 5, 6), (1, 1, 1, 1))
    assert illustrative_continuation(exhausted) == () and exhausted.total_trials == 40
    final_unsupported = report(last_input, (49, 51), (1, 1))
    assert illustrative_continuation(final_unsupported) == final_unsupported.selected_candidate_ids == ()
    all_limit = report(first_input, (0, 0, 0, 0), (0, 0, 0, 0))
    assert illustrative_continuation(all_limit) == ('A', 'B')
    assert report(replace(first_input, top_k=10), (4, 7, 5, 6), (0, 0, 0, 0)).selected_candidate_ids == ('C',)
    n = 2**60 + 1
    large = replace(last_input, trials_per_candidate=n, max_total_trials=2 * n)
    precise = report(large, (n // 2 - 1, n // 2), (0, 0))
    assert float(precise.candidates[0].assessment.objective_achieved_rate) == float(
        precise.candidates[1].assessment.objective_achieved_rate)
    assert illustrative_continuation(precise) == ('D',)
    assert all(first_input.simulation_requests[0].seed_for(index) == last_input.simulation_requests[0].seed_for(index)
               for index in range(10))
    assert tuple(row.assessment.source_request.scenario for row in final.candidates) == (scenario, other)
    zero_window = replace(first_input, window=ObjectiveRateWindow(F(0), F(0), F(0)))
    assert report(zero_window, (0, 0, 0, 0), (0, 0, 0, 0)).selected_candidate_ids == ('A', 'B')
    zero_unsupported = report(zero_window, (0, 0, 0, 0), (10, 10, 10, 10))
    assert illustrative_continuation(zero_unsupported) == zero_unsupported.selected_candidate_ids == ()
    zero_action = NpcMagicSimulationSummary(
        first_input.simulation_requests[0], NpcMagicOutcomeCounts(0, 0, 0, 10), 0, 10, 0)
    assert assess_magic_candidate(zero_action.source_request, zero_action, zero_window.window).window_match is None
    assert first_input == before and getstate() == rng_before
    assert {child.pid for child in active_children()} == children_before
    print('Magic staged contract: synthetic continuation A,D differs from empty bounded selection')
    print('Synthetic final selection/order/ties, inclusive and point-zero windows, unsupported/all-limit: OK')
    print('Complete-repeat budgets: planned=240 versus cap239; actual=240/140/40; three-stage upper bound=2240')
    print('Incremental budget220 excluded; large exact Fraction and unchanged indexed-seed prefix: OK')
    print('Native magic actions/started/completed bounds and zero-action unsupported: OK')
    print('Inputs/global RNG unchanged; child processes unchanged; no battle execution or RNG draws')
    print('No staged models/service, budget preflight, report-chain or stage-error guards are implemented by this probe')


if __name__ == '__main__':
    main()
