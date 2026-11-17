"""Proposal steering is not a game rule or a claim of monotonic difficulty."""
from types import SimpleNamespace
import unittest

from towr.application.dynamic_encounter import _directed_count_parent


def observation(count,win,*,rounds=5,unsupported=0):
    return SimpleNamespace(composition=(None,)*count,win_rate=win,mean_started_rounds=rounds,
        summary=SimpleNamespace(outcome_counts=SimpleNamespace(unsupported_path=unsupported)))


class DirectedCountProposalTests(unittest.TestCase):
    def setUp(self):
        self.request=SimpleNamespace(minimum_npcs=1,maximum_npcs=10,
            target_win_rate=.5,target_rounds=5)

    def test_easy_plateau_advances_even_when_rounds_prefer_earlier_parent(self):
        earlier,later=observation(6,1),observation(7,1,rounds=8)
        self.assertIs(_directed_count_parent(self.request,[earlier,later]),later)

    def test_hard_plateau_advances_toward_fewer_opponents(self):
        earlier,later=observation(6,0),observation(5,0,rounds=8)
        self.assertIs(_directed_count_parent(self.request,[earlier,later]),later)

    def test_closest_observed_win_rate_precedes_count_frontier(self):
        promising=observation(6,.75)
        self.assertIs(_directed_count_parent(self.request,
            [observation(9,1),promising]),promising)

    def test_boundaries_and_exact_target_do_not_force_opposite_direction(self):
        for candidate in (observation(10,1),observation(1,0),observation(6,.5)):
            self.assertIsNone(_directed_count_parent(self.request,[candidate]))

    def test_unsupported_observations_never_direct_a_resize(self):
        self.assertIsNone(_directed_count_parent(self.request,[observation(5,1,unsupported=1)]))
        valid=observation(4,.25)
        self.assertIs(_directed_count_parent(self.request,
            [observation(5,.5,unsupported=1),valid]),valid)

    def test_equal_error_keeps_existing_rounds_tie_break_between_win_rates(self):
        easy,hard=observation(6,.75),observation(5,.25,rounds=8)
        self.assertIs(_directed_count_parent(self.request,[easy,hard]),easy)


if __name__=='__main__':
    unittest.main()
