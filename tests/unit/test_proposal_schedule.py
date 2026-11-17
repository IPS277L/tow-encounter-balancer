"""Proposal operations preserve their boundaries independently of scheduling."""
from random import Random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from towr.application.dynamic_encounter import (
    NpcSearchSpace, _ProposalOperation as Op, _propose, _select_proposal_operation,
)


def request(**changes):
    return SimpleNamespace(**(dict(minimum_npcs=1,maximum_npcs=10,target_win_rate=.5,
        target_rounds=5,top_k=2,space=NpcSearchSpace())|changes))


def observation(composition,win=.75,unsupported=0):
    return SimpleNamespace(composition=composition,win_rate=win,mean_started_rounds=5,
        summary=SimpleNamespace(outcome_counts=SimpleNamespace(unsupported_path=unsupported)))


class ProposalGenerationTests(unittest.TestCase):
    def setUp(self):
        self.source=request()
        self.members=tuple(self.source.space.sample(Random(i)) for i in range(3))

    def test_restart_preserves_legacy_draws_and_complete_rng_state(self):
        a,b=Random(42),Random(42)
        expected=tuple(self.source.space.sample(a) for _ in range(a.randint(1,10)))
        result=_propose(self.source,[],b,Op.RESTART)
        self.assertEqual(result.requested,Op.RESTART)
        self.assertEqual(result.applied,Op.RESTART)
        self.assertEqual(result.composition,expected)
        self.assertEqual(a.getstate(),b.getstate())

    def test_component_preserves_the_old_single_member_mutation_rng(self):
        observations=[observation(self.members)]
        a,b=Random(42),Random(42)
        expected=list(a.choice(observations).composition)
        index=a.randrange(len(expected))
        expected[index]=self.source.space.mutate(expected[index],a)
        result=_propose(self.source,observations,b,Op.COMPONENT)
        self.assertEqual(result.composition,tuple(expected))
        self.assertEqual(a.getstate(),b.getstate())
        self.assertEqual(result.applied,Op.COMPONENT)
        self.assertEqual(sum(x!=y for x,y in zip(self.members,result.composition)),1)

    def test_count_grows_by_one_preserving_existing_profiles_and_order(self):
        result=_propose(self.source,[observation(self.members)],Random(42),Op.COUNT)
        self.assertEqual(result.applied,Op.COUNT)
        self.assertEqual(result.composition[:-1],self.members)
        self.assertEqual(len(result.composition),4)
        self.assertTrue(self.source.space.contains(result.composition[-1]))

    def test_count_shrink_removes_one_member_preserving_the_rest(self):
        result=_propose(self.source,[observation(self.members,win=.25)],Random(42),Op.COUNT)
        self.assertEqual(result.applied,Op.COUNT)
        self.assertTrue(any(self.members[:i]+self.members[i+1:]==result.composition for i in range(3)))

    def test_unavailable_count_is_reported_as_component_without_wrong_direction(self):
        for source,obs in (
                (request(minimum_npcs=3,maximum_npcs=3),observation(self.members)),
                (request(maximum_npcs=3),observation(self.members)),
                (self.source,observation(self.members,win=.5)),
                (self.source,observation(self.members,unsupported=1))):
            result=_propose(source,[obs],Random(42),Op.COUNT)
            self.assertEqual(result.requested,Op.COUNT)
            self.assertEqual(result.applied,Op.COMPONENT)
            self.assertEqual(len(result.composition),3)
            self.assertEqual(sum(a!=b for a,b in zip(self.members,result.composition)),1)

    def test_adaptive_operation_requires_observations_and_typed_operation(self):
        with self.assertRaises(ValueError):_propose(self.source,[],Random(42),Op.COMPONENT)
        with self.assertRaises(TypeError):_propose(self.source,[],Random(42),'restart')


class LegacyProposalSelectionTests(unittest.TestCase):
    def test_first_proposal_consumes_no_selection_rng(self):
        rng=Random(42)
        with patch.object(rng,'random',side_effect=AssertionError('unexpected draw')):
            self.assertIs(_select_proposal_operation(request(),0,1,rng),Op.RESTART)

    def test_old_random_choice_and_count_parity_are_preserved(self):
        rng=Random(42)
        with patch.object(rng,'random',return_value=.5):
            self.assertIs(_select_proposal_operation(request(),1,2,rng),Op.COUNT)
            self.assertIs(_select_proposal_operation(request(),2,3,rng),Op.COMPONENT)
            self.assertIs(_select_proposal_operation(request(minimum_npcs=3,maximum_npcs=3),1,2,rng),Op.COMPONENT)
        with patch.object(rng,'random',return_value=.8):
            self.assertIs(_select_proposal_operation(request(),1,2,rng),Op.RESTART)


if __name__=='__main__':unittest.main()
