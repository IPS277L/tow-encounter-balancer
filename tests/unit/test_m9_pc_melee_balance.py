"""Deterministic aggregate/source/budget checks; no battle probability oracles."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
import unittest
from unittest.mock import Mock, patch

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.application.pc_melee_balance_models import (
    PcMeleeBalanceExecutionError, PcMeleeBalancePhase, PcMeleeBalanceRequest,
    PcMeleeBalanceResult, PcMeleeCompositionGroup, pc_melee_count_vectors,
    project_pc_melee_candidate, validate_pc_melee_balance_request, validate_pc_melee_balance_result,
)
from towr.balance.pc_melee_assessment import PcMeleeAssessmentStatus, PcMeleeCandidateAssessment
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.simulation.pc_melee_models import PcMeleeOutcomeCounts, PcMeleeSimulationRequest, PcNearMissBurnCount, PcGloriousSpendCount, PcHelpActionCount, PcAllyRecoverActionCount
from towr.simulation.pc_melee_summary_models import PcMeleeDefeatCount, PcMeleeSimulationSummary


WINDOW = ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4))


def request(*, enemies=3, trials=4, groups=None, template=None, window=WINDOW, top_k=3):
    template = template or make_pc_melee_scenario(enemy_count=enemies, max_rounds=3)
    if groups is None:
        groups = (PcMeleeCompositionGroup('ordinary',
            tuple(enemy.state.actor_id for enemy in template.enemies), 1, len(template.enemies)),)
    size = 1
    for group in groups:
        size *= group.maximum_count-group.minimum_count+1
    return PcMeleeBalanceRequest(template, groups, deepcopy(template.facts), 42, trials,
        size, size*trials, window, top_k)


def aggregate(source, *, wins=0, defeats=0, unsupported=0):
    """Arithmetic aggregate doubles; actual gameplay is tested in integration."""
    limited = source.trials-wins-defeats-unsupported
    started = source.trials*source.scenario.max_rounds
    completed = started-(source.trials-limited)
    return PcMeleeSimulationSummary(source, PcMeleeOutcomeCounts(wins, defeats, limited, unsupported),
        started, started, completed, defeats,
        tuple(PcMeleeDefeatCount(member.actor_id,defeats) for member in source.scenario.party),
        0, tuple(PcNearMissBurnCount(member.actor_id,0) for member in source.scenario.party),
        0, tuple(PcGloriousSpendCount(member.actor_id,0) for member in source.scenario.party),
        0, tuple(PcHelpActionCount(member.actor_id,0) for member in source.scenario.party),
        0, tuple(PcAllyRecoverActionCount(member.actor_id,0) for member in source.scenario.party))


class PcMeleeBalanceUnitTests(unittest.TestCase):
    def test_source_is_fixed_and_all_orders_are_filtered_without_reordering(self):
        original = make_pc_melee_scenario(enemy_count=3)
        priority = ('minion3', 'minion2', 'minion1')
        member = original.party[0]
        template = replace(original, enemy_activation_order=('minion2', 'minion3', 'minion1'),
            party=(replace(member,target_priority=priority,
                defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority)),))
        source = request(template=template, trials=1, groups=(
            PcMeleeCompositionGroup('a', ('minion3', 'minion1'), 1, 2),
            PcMeleeCompositionGroup('b', ('minion2',), 0, 1)))
        projected = project_pc_melee_candidate(source, (1, 1))
        scenario = projected.scenario
        self.assertEqual(scenario.id, 'pc-melee:counts:1,1')
        self.assertEqual(tuple(enemy.state.actor_id for enemy in scenario.enemies), ('minion2', 'minion3'))
        self.assertEqual(scenario.enemy_activation_order, ('minion2', 'minion3'))
        self.assertEqual(scenario.party[0].target_priority, ('minion3', 'minion2'))
        self.assertEqual(tuple(item.target_id for item in scenario.party[0].defeat_decisions), scenario.party[0].target_priority)
        self.assertIs(scenario.party[0].pc, template.party[0].pc)
        self.assertIs(scenario.party[0].fate, template.party[0].fate)
        self.assertEqual((projected.master_seed, projected.trials), (42, 1))
        self.assertIsNot(source.facts, template.facts)
        self.assertEqual(scenario.facts, source.facts)
        self.assertEqual(len(template.enemies), 3)

    def test_all_zero_is_excluded_from_count_and_cartesian_order(self):
        source = request(enemies=2, groups=(
            PcMeleeCompositionGroup('a', ('minion1',), 0, 1),
            PcMeleeCompositionGroup('b', ('minion2',), 0, 1)))
        self.assertEqual(source.candidate_count, 3)
        self.assertEqual(source.planned_trials, 12)
        self.assertEqual(tuple(pc_melee_count_vectors(source)), ((0, 1), (1, 0), (1, 1)))
        with self.assertRaises(ValueError):
            project_pc_melee_candidate(source, (0, 0))

    def test_billion_candidate_grid_is_rejected_arithmetically_without_materialization(self):
        template = make_pc_melee_scenario(enemy_count=30)
        groups = tuple(PcMeleeCompositionGroup(str(index), (enemy.state.actor_id,), 0, 1)
            for index, enemy in enumerate(template.enemies))
        with patch('towr.application.pc_melee_balance_models.product', side_effect=AssertionError('enumeration')),\
                patch('towr.application.pc_melee_balance_models.PcMeleeSimulationRequest',
                      side_effect=AssertionError('simulation requests')):
            with self.assertRaisesRegex(ValueError, 'max_candidates'):
                PcMeleeBalanceRequest(template, groups, template.facts, 42, 1, 10, 1 << 32, WINDOW, 1)

    def test_global_budget_is_checked_before_any_projection(self):
        source = request()
        with patch('towr.application.pc_melee_balance_models.product', side_effect=AssertionError('enumeration')):
            with self.assertRaisesRegex(ValueError, 'max_total_trials'):
                replace(source, max_total_trials=source.planned_trials-1)

    def test_group_partition_definition_and_bounds_are_strict(self):
        source = request(enemies=2)
        for groups in ((), (PcMeleeCompositionGroup('a', ('minion1',), 0, 1),),
                       (PcMeleeCompositionGroup('a', ('pc', 'minion2'), 0, 1),),
                       (PcMeleeCompositionGroup('a', ('minion1',), 0, 1),
                        PcMeleeCompositionGroup('b', ('minion1', 'minion2'), 0, 1))):
            with self.subTest(groups=groups), self.assertRaises(ValueError):
                replace(source, groups=groups)
        for count in (True, 1.0, '1'):
            with self.subTest(count=count), self.assertRaises(TypeError):
                PcMeleeCompositionGroup('a', ('minion1',), count, 1)
        for actors in ('minion1', {'minion1'}, iter(('minion1',))):
            with self.subTest(actors=actors), self.assertRaises(TypeError):
                PcMeleeCompositionGroup('a', actors, 0, 1)
        with self.assertRaises(ValueError):
            PcMeleeCompositionGroup('a', ('minion1',), 2, 1)
        # Identical numeric attack values do not make different definitions one group.
        last = source.template.enemies[-1]
        changed_definition = replace(last.definition, id='different', source_rule_id='different:source')
        changed = replace(last, definition=changed_definition,
            state=replace(last.state, definition_id=changed_definition.id))
        different = replace(source.template, enemies=(source.template.enemies[0], changed))
        with self.assertRaisesRegex(ValueError, 'complete profile NPC definitions'):
            replace(source, template=different)

    def test_request_and_transported_equal_aliases_are_readmitted(self):
        source = request()
        for name in ('master_seed', 'trials_per_candidate', 'max_candidates', 'max_total_trials', 'top_k'):
            with self.subTest(name=name), self.assertRaises(TypeError):
                replace(source, **{name: True})
        for changes in ({'master_seed': 1 << 64}, {'trials_per_candidate': 0}, {'top_k': 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(source, **changes)
        forged = deepcopy(source)
        object.__setattr__(forged.facts, 'can_leave_zone', 0)
        self.assertEqual(forged, source)
        with self.assertRaises(TypeError):
            validate_pc_melee_balance_request(forged)
        forged = deepcopy(source)
        object.__setattr__(forged.groups[0], 'minimum_count', True)
        self.assertEqual(forged, source)
        with self.assertRaises(TypeError):
            validate_pc_melee_balance_request(forged)

    def test_explicit_family_facts_must_match_source_without_inference(self):
        source = request()
        with self.assertRaisesRegex(ValueError, 'complete template facts'):
            replace(source, facts=replace(source.facts, outnumbering_bonus_approved=False))
        copied = replace(source, facts=deepcopy(source.facts))
        self.assertEqual(copied, source)

    def test_constructor_copies_ordered_lists_and_remains_frozen(self):
        source = request()
        groups = list(source.groups)
        copied = replace(source, groups=groups)
        groups.clear()
        self.assertEqual(copied.groups, source.groups)
        with self.assertRaises(FrozenInstanceError):
            copied.top_k = 1

    def test_one_unsupported_observation_blocks_selection_without_filtering_denominator(self):
        source = request()
        def simulate(candidate):
            count = len(candidate.scenario.enemies)
            return aggregate(candidate, wins={1: 1, 2: 2, 3: 2}[count], unsupported=int(count == 3))
        with patch('random.Random', side_effect=AssertionError('balance creates no RNG')):
            result = evaluate_pc_melee_balance(source, simulate)
        self.assertEqual(result.selected_candidate_ids, ('pc-melee:counts:2', 'pc-melee:counts:1'))
        rejected = result.candidates[-1].assessment
        self.assertEqual(rejected.objective_achieved_rate, Fraction(1, 2))
        self.assertEqual(rejected.unsupported_path_rate, Fraction(1, 4))
        self.assertEqual(rejected.round_limit_rate, Fraction(1, 4))
        self.assertIs(rejected.status, PcMeleeAssessmentStatus.UNSUPPORTED_OBSERVATIONS)
        self.assertIsNone(rejected.window_match)
        self.assertEqual((result.candidate_count, result.planned_trials, result.total_trials), (3, 12, 12))
        self.assertTrue(all(candidate.source_request.master_seed == 42 for candidate in result.candidates))

    def test_target_distance_ties_preserve_candidate_order_and_top_k(self):
        source = request(enemies=2, top_k=1)
        result = evaluate_pc_melee_balance(source,
            lambda candidate: aggregate(candidate, wins=1 if len(candidate.scenario.enemies) == 1 else 3))
        self.assertEqual(result.selected_candidate_ids, ('pc-melee:counts:1',))
        self.assertTrue(all(candidate.assessment.window_match for candidate in result.candidates))

    def test_outside_window_is_not_selected_and_complete_report_is_kept(self):
        source = request()
        result = evaluate_pc_melee_balance(source, lambda candidate: aggregate(candidate, wins=0))
        self.assertEqual(result.selected_candidate_ids, ())
        self.assertEqual(len(result.candidates), 3)
        self.assertTrue(all(candidate.assessment.status is PcMeleeAssessmentStatus.ELIGIBLE
            and candidate.assessment.window_match is False for candidate in result.candidates))

    def test_every_subset_is_admitted_before_first_simulation(self):
        from towr.application import pc_melee_balance as service
        original = service.project_pc_melee_candidate
        simulator = Mock(side_effect=AssertionError('must not execute a valid prefix'))
        def project(source, counts):
            if counts == (2,):
                raise ValueError('invalid late source projection')
            return original(source, counts)
        with patch.object(service, 'project_pc_melee_candidate', side_effect=project):
            with self.assertRaises(PcMeleeBalanceExecutionError) as caught:
                evaluate_pc_melee_balance(request(), simulator)
        simulator.assert_not_called()
        self.assertIs(caught.exception.phase, PcMeleeBalancePhase.GENERATION)
        self.assertEqual((caught.exception.candidate_id, caught.exception.candidate_index), ('pc-melee:counts:2', 1))
        self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_late_simulator_failure_keeps_context_and_no_partial_report(self):
        source = request()
        private = RuntimeError('private worker detail')
        calls = []
        def simulate(candidate):
            calls.append(candidate)
            if len(calls) == 2:
                raise private
            return aggregate(candidate)
        with self.assertRaises(PcMeleeBalanceExecutionError) as caught:
            evaluate_pc_melee_balance(source, simulate)
        self.assertEqual(len(calls), 2)
        error = caught.exception
        self.assertIs(error.phase, PcMeleeBalancePhase.EVALUATION)
        self.assertEqual((error.candidate_id, error.candidate_index), ('pc-melee:counts:2', 1))
        self.assertIs(error.__cause__, private)
        self.assertNotIn('private', str(error))

    def test_foreign_or_equal_corrupt_aggregate_is_rejected(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt):
                def simulate(source):
                    summary = aggregate(replace(source, master_seed=1))
                    if corrupt:
                        object.__setattr__(summary.source_request, 'master_seed', True)
                    return summary
                with self.assertRaises(PcMeleeBalanceExecutionError) as caught:
                    evaluate_pc_melee_balance(request(), simulate)
                self.assertIs(caught.exception.phase, PcMeleeBalancePhase.EVALUATION)
                self.assertIsInstance(caught.exception.__cause__, TypeError if corrupt else ValueError)
        with self.assertRaises(PcMeleeBalanceExecutionError) as caught:
            evaluate_pc_melee_balance(request(), lambda _: object())
        self.assertIsInstance(caught.exception.__cause__, TypeError)

    def test_result_cache_checks_full_source_order_counts_window_and_ranking(self):
        source = request()
        result = evaluate_pc_melee_balance(source, lambda candidate: aggregate(candidate, wins=2))
        for changes in ({'candidates': result.candidates[:-1]},
                        {'candidates': tuple(reversed(result.candidates))},
                        {'selected_candidate_ids': ()},
                        {'source_request': replace(source, window=ObjectiveRateWindow(Fraction(0), Fraction(0), Fraction(1)))}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(result, **changes)
        wrong = replace(result.candidates[0], counts=(2,))
        with self.assertRaises(ValueError):
            replace(result, candidates=(wrong, *result.candidates[1:]))
        forged = deepcopy(result)
        object.__setattr__(forged.candidates[0].summary.outcome_counts, 'unsupported_path', False)
        self.assertEqual(forged, result)
        with self.assertRaises(TypeError):
            replace(forged)
        forged = deepcopy(result)
        object.__setattr__(forged, 'selected_candidate_ids', list(forged.selected_candidate_ids))
        with self.assertRaises(TypeError):
            validate_pc_melee_balance_result(forged)

    def test_assessment_requires_the_exact_aggregate_source(self):
        source = PcMeleeSimulationRequest(make_pc_melee_scenario(), 1, 4)
        summary = aggregate(source, wins=2, defeats=1)
        assessment = PcMeleeCandidateAssessment(source, summary, WINDOW)
        self.assertEqual(assessment.party_defeated_rate, Fraction(1, 4))
        self.assertEqual(assessment.round_limit_rate, Fraction(1, 4))
        with self.assertRaises(ValueError):
            PcMeleeCandidateAssessment(replace(source, master_seed=2), summary, WINDOW)


if __name__ == '__main__':
    unittest.main()
