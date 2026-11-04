"""Actual PC encounters enter the balance boundary only as aggregate summaries."""
from copy import deepcopy
from fractions import Fraction
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.application.pc_melee_balance_models import (
    PcMeleeBalanceExecutionError, PcMeleeBalancePhase, PcMeleeBalanceRequest, PcMeleeCompositionGroup,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
from towr.simulation.pc_melee_summary_models import PcMeleeSimulationSummary


def source(*, fixed=False, trials=2):
    template = make_pc_melee_scenario(enemy_count=2, max_rounds=2)
    return PcMeleeBalanceRequest(template,
        (PcMeleeCompositionGroup('minions', ('minion2', 'minion1'), 2 if fixed else 1, 2),),
        deepcopy(template.facts), 82, trials, 1 if fixed else 2, trials*(1 if fixed else 2),
        ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1)), 2)


class PcMeleeBalanceIntegrationTests(unittest.TestCase):
    def test_actual_candidate_batches_keep_full_pc_fate_and_aggregate_only_report(self):
        request = source()
        original = deepcopy(request)
        observed = []
        def simulate(candidate):
            result = run_pc_melee_simulation(candidate)
            summary = summarize_pc_melee_simulation(result)
            observed.append((candidate, summary))
            return summary
        result = evaluate_pc_melee_balance(request, simulate)
        self.assertEqual(request, original)
        self.assertEqual(len(observed), 2)
        self.assertEqual((result.candidate_count, result.planned_trials, result.total_trials), (2, 4, 4))
        self.assertEqual(tuple(item.counts for item in result.candidates), ((1,), (2,)))
        self.assertEqual(tuple(enemy.state.actor_id for enemy in result.candidates[0].source_request.scenario.enemies),
                         ('minion2',))
        for candidate, (executed, summary) in zip(result.candidates, observed):
            self.assertIs(candidate.source_request, executed)
            self.assertIs(candidate.summary, summary)
            self.assertIsInstance(candidate.summary, PcMeleeSimulationSummary)
            self.assertEqual(candidate.source_request.scenario.party[0].pc, request.template.party[0].pc)
            self.assertEqual(candidate.source_request.scenario.party[0].fate, request.template.party[0].fate)
            self.assertFalse(hasattr(candidate.summary, 'records'))
            self.assertFalse(hasattr(candidate.summary, 'steps'))
            self.assertFalse(hasattr(candidate.summary, 'state'))
            counts = candidate.summary.outcome_counts
            self.assertEqual(sum(getattr(counts, name) for name in counts.__dataclass_fields__), 2)

    def test_one_real_spawn_candidate_has_the_same_complete_report_as_sequential(self):
        request = source(fixed=True, trials=3)
        sequential = evaluate_pc_melee_balance(request,
            lambda candidate: summarize_pc_melee_simulation(run_pc_melee_simulation(candidate)))
        process = evaluate_pc_melee_balance(request,
            lambda candidate: summarize_pc_melee_simulation(run_pc_melee_simulation_parallel(
                candidate, workers=1, batch_size=2)))
        self.assertEqual(process, sequential)
        self.assertEqual(request.template.party[0].fate.rating, 3)
        self.assertEqual(request.template.party[0].fate.spends, ())

    def test_failure_after_a_real_completed_candidate_returns_only_contextual_error(self):
        request = source(trials=1)
        original = deepcopy(request)
        calls = 0
        cause = RuntimeError('worker private cause')
        def simulate(candidate):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise cause
            return summarize_pc_melee_simulation(run_pc_melee_simulation(candidate))
        with self.assertRaises(PcMeleeBalanceExecutionError) as caught:
            evaluate_pc_melee_balance(request, simulate)
        self.assertEqual(request, original)
        self.assertEqual(calls, 2)
        self.assertIs(caught.exception.phase, PcMeleeBalancePhase.EVALUATION)
        self.assertEqual((caught.exception.candidate_id, caught.exception.candidate_index), ('pc-melee:counts:2', 1))
        self.assertIs(caught.exception.__cause__, cause)


if __name__ == '__main__':
    unittest.main()
