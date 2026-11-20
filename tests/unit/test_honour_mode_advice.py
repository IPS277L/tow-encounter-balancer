"""Exact small mode comparisons are preparation, never dice or resource use."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.support.pc_tactics_fixtures import automatic_source
from tests.support.oath_sources import with_native_outcome_owner
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.pc_oath_models import honour_quality_modifiers, prepare_pc_honour_test, actor_oath
from towr.domain.honour_bound_models import HONOUR_BOUND_GLORIOUS_RULE_ID
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import TestProfile, TestRequest, TestQuality, QualityModifier, RerollLock


def prepared(profile, *, lucky=False, grim=False, locks=()):
    source=automatic_source(pc_count=1,enemy_count=1)
    member=replace(source.party[0],pc=replace(source.party[0].pc,
        weapon_skill=profile.characteristic,melee=profile.skill))
    source=with_native_outcome_owner(replace(source,party=(member,)),fate=0 if lucky else 1,lucky=lucky)
    state=initial_pc_melee_state(source)
    actor=source.pc_activation_order[0]
    qualities=(*honour_quality_modifiers(state,actor),
        *((QualityModifier('actual:grim',TestQuality.GRIM),) if grim else ()))
    return state,actor,TestRequest('prepared:actual',profile,quality_modifiers=qualities,reroll_locks=locks)


def has_free_mode(test):
    return any(quality.rule_id==HONOUR_BOUND_GLORIOUS_RULE_ID for quality in test.quality_modifiers)


class HonourModeAdviceTests(unittest.TestCase):

    def test_high_quality_pool_uses_free_glorious_without_funding(self):
        state,actor,test=prepared(TestProfile(4,6))
        result=prepare_pc_honour_test(state,actor,test)
        self.assertEqual(result,test)
        self.assertTrue(has_free_mode(result))
        self.assertEqual(state.participant(actor).fate.spends,())

    def test_weak_pool_reserves_the_paid_mode_without_consuming_it(self):
        state,actor,test=prepared(TestProfile(2,2))
        before=deepcopy(state)
        result=prepare_pc_honour_test(state,actor,test)
        self.assertFalse(has_free_mode(result))
        self.assertTrue(has_free_mode(test))
        self.assertEqual(state,before)
        self.assertTrue(actor_oath(state,actor).honour.available)
        self.assertEqual(actor_oath(state,actor).honour_uses,())

    def test_actual_lucky_free_funding_changes_the_choice_on_a_grim_pool(self):
        normal,actor,test=prepared(TestProfile(4,5),grim=True)
        self.assertTrue(has_free_mode(prepare_pc_honour_test(normal,actor,test)))
        lucky,lucky_actor,lucky_test=prepared(TestProfile(4,5),grim=True,lucky=True)
        self.assertFalse(has_free_mode(prepare_pc_honour_test(lucky,lucky_actor,lucky_test)))
        self.assertTrue(lucky.participant(lucky_actor).fate.lucky_free_spend_available)
        self.assertEqual(lucky.participant(lucky_actor).fate.rating,0)

    def test_rule_of_nine_known_before_casting_changes_comparison_without_fake_rolls(self):
        state,actor,test=prepared(TestProfile(4,3))
        with patch('towr.rules.test_resolution.roll_test_initial',side_effect=AssertionError('advice must not roll')):
            free=prepare_pc_honour_test(state,actor,test)
            casting=prepare_pc_honour_test(state,actor,test,rule_of_nine=True)
        self.assertTrue(has_free_mode(free))
        self.assertFalse(has_free_mode(casting))
        self.assertEqual(casting.reroll_locks,test.reroll_locks)  # Physical Casting guard is installed by its owner.
        self.assertEqual(state.participant(actor).fate.spends,())

    def test_preparation_retains_independent_modifiers_and_reroll_locks(self):
        lock=RerollLock('actual:locked-ten',10)
        state,actor,test=prepared(TestProfile(2,2),grim=True,locks=(lock,))
        before=deepcopy(state)
        with patch('towr.rules.test_resolution.resolve_test',side_effect=AssertionError('advice must not execute')):
            result=prepare_pc_honour_test(state,actor,test)
        self.assertEqual(result.reroll_locks,(lock,))
        self.assertIn(QualityModifier('actual:grim',TestQuality.GRIM),result.quality_modifiers)
        self.assertEqual(result.profile,test.profile)
        self.assertEqual(result.id,test.id)
        self.assertEqual(state,before)


if __name__=='__main__':
    unittest.main()
