"""Fixed-sample coverage identities and pre-outcome resource planning."""
from math import comb, sqrt, log
import unittest
from unittest.mock import patch

import tools.search_allocation as lab
from tools.search_allocation import (
    ArmSpec, Counts, Plan, Trial, bernoulli_fixed, freeze_confirmation,
    precision_reserve, precision_sample_size, run_search,
)


def pool(n):
    return tuple(ArmSpec(f'a:{i}') for i in range(n))


def alternating(arm,stage,index):
    return Trial('win' if index%2 else 'loss',5)


class FixedSampleBoundsTests(unittest.TestCase):
    def test_closed_form_endpoints_and_zero_sample(self):
        self.assertEqual(bernoulli_fixed(0,0,.01),(0.,1.))
        for n in (1,8,32,220):
            lower,upper = bernoulli_fixed(n,n,.0125)
            self.assertAlmostEqual(lower,.0125**(1/n),places=12)
            self.assertEqual(upper,1.)
            lower,upper = bernoulli_fixed(n,0,.0125)
            self.assertEqual(lower,0.)
            self.assertAlmostEqual(upper,1-.0125**(1/n),places=12)

    def test_each_one_sided_error_is_bounded_by_exact_binomial_sum(self):
        for n in (8,16,32):
            for p in (.02,.2,.5,.8,.98):
                lower_error = upper_error = 0.
                for s in range(n+1):
                    mass = comb(n,s)*p**s*(1-p)**(n-s)
                    lower,upper = bernoulli_fixed(n,s,.025)
                    lower_error += mass*(lower > p)
                    upper_error += mass*(upper < p)
                self.assertLessEqual(lower_error,.025+1e-12)
                self.assertLessEqual(upper_error,.025+1e-12)

    def test_requested_size_bounds_radius_for_every_observable_count(self):
        n = precision_sample_size(2,.05,.1)
        self.assertEqual(n,220)
        for s in range(n+1):
            lower,upper = bernoulli_fixed(n,s,.05/4)
            self.assertLessEqual(s/n-lower,.1+1e-12)
            self.assertLessEqual(upper-s/n,.1+1e-12)

    def test_informative_unknown_keeps_two_bounding_streams(self):
        frozen = freeze_confirmation(pool(2),440,220,.05,.1)
        counts = Counts(n=220,wins=22,unknown=176)
        lower,upper = frozen.interval(counts)
        self.assertLessEqual(lower,.1)
        self.assertGreaterEqual(upper,.9)
        self.assertLessEqual(upper-lower,176/220+2*frozen.nominal_half_width+1e-12)

    def test_fixed_intervals_require_entire_frozen_sample(self):
        frozen = freeze_confirmation(pool(2),440,220,.05,.1)
        for n in (0,219,221):
            with self.assertRaises(ValueError):
                frozen.interval(Counts(n=n,wins=n//2))

    def test_invalid_requests_fail_and_warm_cache_preserves_type_checks(self):
        bernoulli_fixed(1,0,.025)
        for values in ((True,0,.025),(2,3,.025),(1,0,0),(1,0,float('nan'))):
            with self.assertRaises(ValueError):bernoulli_fixed(*values)
        for values in ((0,.05,.1),(2,.05,0),(2,.05,True),(2,1,.1)):
            with self.assertRaises(ValueError):precision_sample_size(*values)


class ConfirmationResourceTests(unittest.TestCase):
    def test_budget_plan_degrades_precision_explicitly(self):
        for budget,expected_n in ((112,44),(256,116),(512,220)):
            reserved,n = precision_reserve(pool(6),Plan(budget),.1)
            self.assertEqual(n,expected_n)
            self.assertLessEqual(reserved+24,budget)
            frozen = freeze_confirmation(pool(2),reserved,n,.05,.1)
            self.assertEqual(frozen.n,expected_n)
            self.assertEqual(frozen.budget_limited,budget<512)
            self.assertAlmostEqual(frozen.nominal_half_width,sqrt(log(80)/(2*expected_n)))

    def test_wide_pool_does_not_hide_minimum_search_cost(self):
        reserve,n = precision_reserve(pool(24),Plan(112),.1)
        self.assertEqual((reserve,n),(16,8))
        with self.assertRaisesRegex(ValueError,'insufficient budget'):
            run_search(pool(24),lambda *a:self.fail('oracle ran'),Plan(97),policy='uniform',precision=.1)

    def test_actual_finalists_and_costs_may_release_capacity_before_observations(self):
        reserve,n = precision_reserve((ArmSpec('cheap',1),ArmSpec('costly',4)),Plan(512),.1)
        single = freeze_confirmation((ArmSpec('cheap',1),),reserve,n,.05,.1)
        self.assertEqual(single.finalist_ids,('cheap',))
        self.assertEqual(single.n_requested,185)
        self.assertEqual(single.n,185)
        self.assertLessEqual(single.n,reserve)
        empty = freeze_confirmation((),reserve,n,.05,.1)
        self.assertEqual((empty.n,empty.finalist_ids),(0,()))

    def test_plan_is_frozen_before_any_final_observation_and_not_revised_after_unknown(self):
        frozen = []
        original = lab.freeze_confirmation
        def freeze(*args):
            result = original(*args)
            frozen.append(result)
            return result
        calls = []
        def draw(arm,stage,index):
            if stage == 'confirm':
                self.assertEqual(len(frozen),1)
                self.assertIn(arm,frozen[0].finalist_ids)
                self.assertLess(index,frozen[0].n)
                calls.append((arm,index))
                if arm == 'a:0' and index == 0:return Trial('unknown',2)
            return alternating(arm,stage,index)
        with patch.object(lab,'freeze_confirmation',side_effect=freeze):
            result = run_search(pool(6),draw,Plan(512),policy='uniform',precision=.1)
        self.assertIs(result.final_plan,frozen[0])
        self.assertEqual(len(result.final_plan.finalist_ids),2)
        self.assertEqual(len(result.confirmed),2)
        self.assertTrue(all(c.n==220 for c in result.confirmed.values()))
        self.assertEqual(result.selected,'a:1')
        self.assertEqual(len(calls),440)

    def test_same_work_cap_is_preserved_for_both_protocols_and_variable_cost(self):
        arms = (ArmSpec('a',1),ArmSpec('b',4),ArmSpec('c',2))
        for precision in (None,.1):
            result = run_search(arms,alternating,Plan(448),policy='uniform',precision=precision)
            self.assertLessEqual(result.spent_work,448)
            self.assertLessEqual(result.search_work+result.reserved_work,448)
            self.assertEqual(result.search_work,sum(result.explored[a.id].n*a.cost for a in arms))
            if precision is not None:self.assertTrue(all(c.n>=4 for c in result.explored.values()))

    def test_all_unsupported_has_no_final_precision_claim(self):
        result = run_search(pool(6),lambda *a:Trial('unknown',2),Plan(112),policy='uniform',precision=.1)
        self.assertIsNone(result.selected)
        self.assertEqual(result.final_plan.finalist_ids,())
        self.assertEqual(result.final_plan.n,0)
        self.assertIsNone(result.final_plan.nominal_half_width)
        self.assertEqual(result.confirmation_work,0)

    def test_benchmark_smoke_has_both_protocols_and_fixed_final_plans(self):
        from tools.benchmark_confirmation_planning import benchmark
        artifact = benchmark(seeds=(0,),budgets=(512,),pools=(6,))
        self.assertEqual(len(artifact['rows']),16)
        self.assertEqual({r['protocol'] for r in artifact['rows']},{'cs32','fixed_precision'})
        for row in artifact['rows']:
            self.assertLessEqual(row['search_work']+row['confirmation_work'],row['work_cap'])
            if row['protocol']=='fixed_precision':
                plan=row['confirmation_plan']
                self.assertEqual(len(plan['finalist_ids']),2)
                self.assertEqual(plan['n'],220)
                self.assertTrue(row['requested_precision_feasible'])
            else:self.assertIsNone(row['confirmation_plan'])


if __name__=='__main__':
    unittest.main()
