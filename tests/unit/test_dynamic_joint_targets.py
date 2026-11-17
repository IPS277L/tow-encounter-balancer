"""Both target bands matter at admission, ranking and validation selection."""
from types import SimpleNamespace
import unittest

from towr.application.dynamic_encounter import (
    DynamicEncounterResult, DynamicTargetStatus as Status,
    assess_dynamic_targets, assess_dynamic_candidate, _score,
)


def request(win=.5,rounds=5):
    return SimpleNamespace(target_win_rate=win,target_rounds=rounds)


def candidate(win,rounds,unknown=0):
    return SimpleNamespace(win_rate=win,mean_started_rounds=rounds,
        summary=SimpleNamespace(outcome_counts=SimpleNamespace(unsupported_path=unknown)))


class JointTargetTests(unittest.TestCase):
    def test_joint_match_beats_perfect_probability_with_bad_duration(self):
        source=request()
        ideal_win=candidate(.5,11)
        joint=candidate(.55,5)
        self.assertIs(assess_dynamic_candidate(source,ideal_win).status,Status.OUTSIDE_TARGETS)
        self.assertIs(assess_dynamic_candidate(source,joint).status,Status.WITHIN_TARGETS)
        self.assertLess(_score(source,joint),_score(source,ideal_win))

    def test_inclusive_four_corners_and_just_outside(self):
        for win in (.4,.6):
            for rounds in (4,6):
                self.assertIs(assess_dynamic_targets(.5,5,win,rounds,0).status,Status.WITHIN_TARGETS)
        for win,rounds in ((.3999,5),(.6001,5),(.5,3.9999),(.5,6.0001)):
            self.assertIs(assess_dynamic_targets(.5,5,win,rounds,0).status,Status.OUTSIDE_TARGETS)

    def test_numerical_boundary_is_shared_by_score_and_status(self):
        source=request()
        inside=candidate(.60000000000001,6.)
        outside=candidate(.5,6.000000000002)
        self.assertIs(assess_dynamic_candidate(source,inside).status,Status.WITHIN_TARGETS)
        self.assertIs(assess_dynamic_candidate(source,outside).status,Status.OUTSIDE_TARGETS)
        self.assertLess(_score(source,inside),_score(source,outside))
        self.assertEqual(_score(source,candidate(.4,5)),_score(source,candidate(.6,5)))

    def test_minimax_then_total_normalized_deviation(self):
        source=request()
        compensated=candidate(.5,7.5)  # max2.5, sum2.5
        balanced=candidate(.7,7)  # max2, sum4
        same_max_better_total=candidate(.7,5)  # max2, sum2
        self.assertLess(_score(source,balanced),_score(source,compensated))
        self.assertLess(_score(source,same_max_better_total),_score(source,balanced))

    def test_stable_order_for_equal_scores(self):
        a,b=candidate(.4,6),candidate(.6,4)
        self.assertEqual(_score(request(),a),_score(request(),b))
        self.assertEqual(sorted((b,a),key=lambda c:_score(request(),c)),[b,a])

    def test_unsupported_never_qualifies_even_with_both_axis_flags(self):
        source=request()
        unknown=candidate(.5,5,1)
        assessment=assess_dynamic_candidate(source,unknown)
        self.assertTrue(assessment.win_rate_in_range)
        self.assertTrue(assessment.started_rounds_in_range)
        self.assertIs(assessment.status,Status.UNSUPPORTED)
        self.assertLess(_score(source,candidate(1,15)),_score(source,unknown))

    def test_probability_edges_and_minimum_round_target(self):
        for target,observed in ((0,.1),(1,.9)):
            self.assertIs(assess_dynamic_targets(target,1,observed,1,0).status,Status.WITHIN_TARGETS)
        self.assertIs(assess_dynamic_targets(.5,15,.5,14,0).status,Status.WITHIN_TARGETS)

    def test_match_flag_ignores_exploration_and_unsupported_validation(self):
        source=request()
        found=candidate(.5,5)
        outside=candidate(.5,10)
        unknown=candidate(.5,5,1)
        result=DynamicEncounterResult(source,(found,),(outside,unknown),1,1,False)
        self.assertFalse(result.target_match_found)
        result=DynamicEncounterResult(source,(outside,),(found,unknown),1,1,False)
        self.assertTrue(result.target_match_found)
        self.assertEqual(result.finalists,(found,))

    def test_invalid_aggregate_rejected(self):
        for values in ((.5,5,float('nan'),5,0),(.5,5,.5,float('inf'),0),
                (.5,5,.5,5,True),(.5,5,True,5,0),(-.1,5,.5,5,0),(.5,0,.5,5,0),(.5,5,.5,5,-1)):
            with self.subTest(values=values),self.assertRaises(ValueError):
                assess_dynamic_targets(*values)


if __name__=='__main__':unittest.main()
