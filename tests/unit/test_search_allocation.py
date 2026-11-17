"""Deterministic statistical identities, exact path sums and budget invariants."""
from math import floor, prod
import unittest

from tools.search_allocation import (
    ArmSpec, ArmTruth, Counts, Fixture, Oracle, Plan, Trial, bernoulli_cs,
    evaluate, fixtures, racing_next, run_search, target_loss_bounds,
)
from tools.benchmark_search_allocation import benchmark, summarize


def alternating(arm, stage, index):
    return Trial('win' if index%2 else 'loss',5)


def pool(n=6):
    return tuple(ArmSpec(f'arm:{i:02}') for i in range(n))


class SequentialBoundsTests(unittest.TestCase):
    def test_zero_samples_and_closed_form_all_success_endpoints(self):
        self.assertEqual(bernoulli_cs(0,0,.05),(0,1))
        for n in (1,8,32):
            mass = prod((i+.5)/(i+1) for i in range(n))
            expected = (.05*mass)**(1/n)
            lower,upper = bernoulli_cs(n,n,.05)
            self.assertAlmostEqual(lower,expected,places=12)
            self.assertEqual(upper,1)
            lower,upper = bernoulli_cs(n,0,.05)
            self.assertEqual(lower,0)
            self.assertAlmostEqual(upper,1-expected,places=12)

    def test_bounds_are_symmetric_and_contain_empirical_mean(self):
        for n in (1,4,19):
            for successes in range(n+1):
                lower,upper = bernoulli_cs(n,successes,.01)
                opposite = bernoulli_cs(n,n-successes,.01)
                self.assertLessEqual(lower,successes/n)
                self.assertGreaterEqual(upper,successes/n)
                self.assertAlmostEqual(lower,1-opposite[1])
                self.assertAlmostEqual(upper,1-opposite[0])

    def test_exact_probability_of_any_crossing_over_all_binary_paths_is_bounded(self):
        # Sum EVERY path probability through n=12, retaining only paths that
        # have not crossed. This is exact finite enumeration, not a MC test.
        for probability in (.05,.3,.5,.9):
            alive = {0:1.}
            crossed = 0.
            for n in range(1,13):
                next_alive = {}
                for previous,mass in alive.items():
                    for increment,chance in ((0,1-probability),(1,probability)):
                        successes = previous+increment
                        lower,upper = bernoulli_cs(n,successes,.1)
                        path_mass = mass*chance
                        if not lower <= probability <= upper:
                            crossed += path_mass
                        else:
                            next_alive[successes] = next_alive.get(successes,0)+path_mass
                alive = next_alive
            self.assertAlmostEqual(crossed+sum(alive.values()),1.)
            self.assertLessEqual(crossed,.1+1e-12)

    def test_invalid_counts_and_alpha_rejected(self):
        bernoulli_cs(1,0,.05)  # A warm cache must not bypass exact-type guards.
        for args in ((-1,0,.05),(3,4,.05),(True,0,.05),(1,0,0),(1,0,float('nan'))):
            with self.subTest(args=args), self.assertRaises(ValueError):
                bernoulli_cs(*args)

    def test_informative_unknown_bounds_never_use_complete_case_denominator(self):
        counts = Counts(n=100,wins=20,unknown=60)
        lower,upper = counts.interval(.001)
        self.assertLessEqual(lower,.2)
        self.assertGreaterEqual(upper,.8)
        self.assertEqual(Counts(n=1000,wins=0,unknown=1000).interval(.001),(0.,1.))

    def test_target_distance_uses_entire_interval(self):
        lower,upper = target_loss_bounds((.2,.8),.5)
        self.assertEqual(lower,0.)
        self.assertAlmostEqual(upper,.3)
        lower,upper = target_loss_bounds((.2,.7),.8)
        self.assertAlmostEqual(lower,.1)
        self.assertAlmostEqual(upper,.6)

    def test_arm_reactivates_after_previous_leader_becomes_unsupported(self):
        arms = pool(2)
        counts = {arms[0].id:Counts(n=10000,wins=5000),arms[1].id:Counts(n=10000,wins=8000)}
        self.assertEqual(racing_next(arms,counts,.5,.001,10),arms[0])
        counts[arms[0].id].add(Trial('unknown',2))
        self.assertEqual(racing_next(arms,counts,.5,.001,10),arms[1])


class AllocationLaboratoryTests(unittest.TestCase):
    def test_uniform112_plan_matches_six_by_eight_plus_two_by32(self):
        result = run_search(pool(),alternating,Plan(112),policy='uniform')
        self.assertEqual([c.n for c in result.explored.values()],[8]*6)
        self.assertEqual([c.n for c in result.confirmed.values()],[32]*2)
        self.assertEqual((result.search_work,result.confirmation_work,result.spent_work),(48,64,112))

    def test_racing_exposes_same_pool_then_respects_cap_and_fresh_indices(self):
        calls = []
        def draw(arm,stage,index):
            calls.append((arm,stage,index))
            return alternating(arm,stage,index)
        result = run_search(pool(),draw,Plan(112),policy='racing')
        self.assertTrue(all(c.n >= 4 for c in result.explored.values()))
        self.assertLessEqual(result.spent_work,112)
        for stage,observations in (('explore',result.explored),('confirm',result.confirmed)):
            for arm,counts in observations.items():
                self.assertEqual([i for a,s,i in calls if a == arm and s == stage],list(range(counts.n)))
        self.assertEqual(len(result.confirmed),2)

    def test_variable_cost_escrow_and_unused_resource_accounting(self):
        arms = (ArmSpec('cheap',1),ArmSpec('expensive',4))
        for policy in ('uniform','racing'):
            result = run_search(arms,alternating,Plan(448),policy=policy)
            self.assertEqual(result.reserved_work,256)
            self.assertEqual(result.confirmation_work,160)
            self.assertLessEqual(result.search_work,192)
            self.assertLessEqual(result.spent_work,448)
            self.assertEqual(result.search_work,sum(c.n*a.cost for a,c in
                ((arm,result.explored[arm.id]) for arm in arms)))

    def test_invalid_plan_fails_before_first_oracle_observation(self):
        def forbidden(*args):
            self.fail('oracle must not run')
        with self.assertRaises(ValueError):
            run_search(pool(),forbidden,Plan(64),policy='racing')

    def test_unknown_in_confirmation_excludes_arm_but_preserves_all32_trials(self):
        def draw(arm,stage,index):
            return Trial('unknown',2) if arm == 'arm:00' and stage == 'confirm' and index == 3 else alternating(arm,stage,index)
        result = run_search(pool(2),draw,Plan(112),policy='uniform')
        self.assertEqual(result.confirmed['arm:00'].n,32)
        self.assertEqual(result.confirmed['arm:00'].unknown,1)
        self.assertEqual(result.selected,'arm:01')

    def test_all_unsupported_returns_no_recommendation_and_retains_reserve(self):
        result = run_search(pool(),lambda *args:Trial('unknown',2),Plan(112),policy='racing')
        self.assertIsNone(result.selected)
        self.assertFalse(result.confirmed)
        self.assertEqual(result.confirmation_work,0)
        self.assertGreaterEqual(112-result.spent_work,result.reserved_work)

    def test_oracle_tapes_are_paired_reproducible_and_call_order_independent(self):
        fixture = fixtures()[0]
        a,b = Oracle(fixture,42),Oracle(fixture,42)
        one,two = fixture.arms[15].spec.id,fixture.arms[16].spec.id
        later = a.draw(one,'explore',12)
        a.draw(two,'confirm',10)
        first = a.draw(one,'explore',0)
        self.assertEqual(first,b.draw(one,'explore',0))
        self.assertEqual(later,b.draw(one,'explore',12))
        a.draw(one,'confirm',12)
        self.assertNotEqual(a._rngs[(one,'explore')].getstate(),a._rngs[(one,'confirm')].getstate())

    def test_coverage_and_selection_failure_are_distinguished(self):
        fixture = Fixture('separate_errors',(ArmTruth(ArmSpec('good'),.5),ArmTruth(ArmSpec('bad'),.9)))
        def misleading(arm,stage,index):
            return Trial('win',5) if arm == 'good' else alternating(arm,stage,index)
        result = run_search(tuple(a.spec for a in fixture.arms),misleading,Plan(112),policy='uniform')
        metrics = evaluate(fixture,result)
        self.assertTrue(metrics['coverage_win'])
        self.assertFalse(metrics['final_win_hit'])
        self.assertAlmostEqual(metrics['selection_regret'],.4)
        missed = run_search((ArmSpec('bad'),),misleading,Plan(112),policy='uniform')
        missed_metrics = evaluate(fixture,missed)
        self.assertFalse(missed_metrics['coverage_win'])
        self.assertEqual(missed_metrics['selection_regret'],0.)

    def test_duration_conflict_does_not_silently_change_lexicographic_objective(self):
        fixture = Fixture('objectives',(ArmTruth(ArmSpec('p_first'),.5,11),ArmTruth(ArmSpec('joint'),.55,5)))
        def draw(arm,stage,index):
            probability = .5 if arm == 'p_first' else .55
            win = floor((index+1)*probability+1e-10) > floor(index*probability+1e-10)
            return Trial('win' if win else 'loss',11 if arm == 'p_first' else 5)
        result = run_search(tuple(a.spec for a in fixture.arms),draw,Plan(112),policy='uniform')
        metrics = evaluate(fixture,result)
        self.assertEqual(result.selected,'p_first')
        self.assertTrue(metrics['coverage_joint'])
        self.assertFalse(metrics['final_joint_hit'])

    def test_unknown_prefix_does_not_become_a_true_rounds_mean(self):
        truth = ArmTruth(ArmSpec('hidden'),1.,11.,unknown_if_win=1.)
        fixture = Fixture('hidden',(truth,))
        oracle = Oracle(fixture,0)
        self.assertEqual(oracle.draw('hidden','explore',0),Trial('unknown',2))
        self.assertEqual(truth.mean_rounds,11)
        result = run_search((truth.spec,),oracle.draw,Plan(112),policy='racing')
        metrics = evaluate(fixture,result)
        self.assertTrue(metrics['missing_recommendation'])
        self.assertEqual(metrics['penalized_error'],.5)

    def test_small_benchmark_is_complete_paired_and_reproducible(self):
        first = benchmark(seeds=(0,),budgets=(112,),pools=(6,))
        second = benchmark(seeds=(0,),budgets=(112,),pools=(6,))
        self.assertEqual(first['rows'],second['rows'])
        self.assertEqual(first['summary'],second['summary'])
        self.assertEqual(len(first['rows']),16)
        self.assertEqual(len(first['paired_uniform_to_racing']),8)
        self.assertTrue(all(r['search_work']+r['confirmation_work'] <= r['work_cap'] for r in first['rows']))
        summary,_ = summarize(first['rows'])
        self.assertTrue(all(s['runs'] == 1 for s in summary))


if __name__ == '__main__':
    unittest.main()
