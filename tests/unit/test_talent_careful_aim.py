"""Careful Aim uses the final real Aim and changes only Staggered, PG74."""
from copy import deepcopy
from dataclasses import replace
from unittest import TestCase

from tests.unit.test_k1_aim_resolution import completed_aim
from tests.support.talent_sources import paid_talent
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_careful_aim_models import CarefulAimApplication


class CarefulAimTests(TestCase):
    def setUp(self):
        self.execution = completed_aim()
        self.talent = paid_talent(TalentId.CAREFUL_AIM)
        self.conditions = ConditionState(frozenset((Condition.STAGGERED, Condition.DRAINED,
            Condition.CRITICALLY_INJURED)))

    def test_success_keeps_the_actual_roll_bonus_action_and_other_conditions(self):
        before = deepcopy(self.execution)
        application = CarefulAimApplication(self.execution, self.talent, self.conditions)
        self.assertEqual(application.execution, before)
        self.assertEqual(application.conditions.conditions,
            frozenset((Condition.DRAINED, Condition.CRITICALLY_INJURED)))
        self.assertEqual(application.execution.slot, before.slot)
        self.assertEqual(application.execution.bonus, before.bonus)
        self.assertEqual(replace(application), application)

    def test_failure_does_not_authorize_a_removal(self):
        failed = completed_aim(values=(10, 10, 10))
        with self.assertRaises(ValueError):
            CarefulAimApplication(failed, self.talent, self.conditions)

    def test_other_talent_and_absent_stagger_cannot_authorize_it(self):
        with self.assertRaises(TypeError):
            CarefulAimApplication(self.execution, paid_talent(TalentId.ACROBATIC), self.conditions)
        with self.assertRaises(ValueError):
            CarefulAimApplication(self.execution, self.talent, ConditionState())

    def test_forged_trace_is_rejected_even_when_bonus_and_slot_are_unchanged(self):
        malformed = deepcopy(self.execution)
        object.__setattr__(malformed.awareness_test_result.trace, 'threshold', 10)
        with self.assertRaises(ValueError):
            CarefulAimApplication(malformed, self.talent, self.conditions)

    def test_mutated_nested_source_and_noncanonical_counter_are_rejected(self):
        malformed = deepcopy(self.execution)
        object.__setattr__(malformed.awareness_test_result.trace, 'rolled_successes', True)
        with self.assertRaises(TypeError):
            CarefulAimApplication(malformed, self.talent, self.conditions)
        malformed = deepcopy(self.execution)
        object.__setattr__(malformed.source_request, 'actor_id', 'another')
        with self.assertRaises(ValueError):
            CarefulAimApplication(malformed, self.talent, self.conditions)
