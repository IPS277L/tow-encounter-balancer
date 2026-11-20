"""Real failed surgery receipts and explicit GM weights, PG122/C24."""
from dataclasses import replace
from unittest import TestCase

from tests.helpers import SequenceRandom
from tests.unit.test_k1_combat_surgeon_battle_surgery import surgical_state,surgery_request
from towr.domain.injury_models import DecisionOwner
from towr.domain.surgery_failure_resolution_models import (
    SurgeryRiskPolicy,SurgeryFailureOutcome,SurgeryFailureResolutionRequest,
)
from towr.rules.combat_surgeon_surgery_resolution import execute_combat_surgeon_battle_surgery_action
from towr.rules.surgery_failure_resolution import resolve_surgery_failure


def failed_surgery():
    return execute_combat_surgeon_battle_surgery_action(
        surgery_request(1,surgical_state()),SequenceRandom([10,10,10]))


class SurgeryFailureResolutionTests(TestCase):
    def request(self,policy=None):
        source=failed_surgery()
        return SurgeryFailureResolutionRequest('risk:resolve',source,policy or
            SurgeryRiskPolicy('gm:scene',2,3,1,'A permanent surgical scar'),source.state)

    def test_each_explicit_weight_interval_and_boundary(self):
        request=self.request()
        for draw,outcome in ((1,SurgeryFailureOutcome.NO_COMPLICATION),(2,SurgeryFailureOutcome.NO_COMPLICATION),
                (3,SurgeryFailureOutcome.PERMANENT_DISFIGUREMENT),(5,SurgeryFailureOutcome.PERMANENT_DISFIGUREMENT),
                (6,SurgeryFailureOutcome.DEATH)):
            with self.subTest(draw=draw):
                result=resolve_surgery_failure(request,SequenceRandom([draw]))
                self.assertIs(result.outcome,outcome)
                self.assertEqual(result.state.wounds,request.injury_state.wounds)
                self.assertEqual(result.state.active_wound_effects,request.injury_state.active_wound_effects)
                self.assertEqual(result.state.dead,outcome is SurgeryFailureOutcome.DEATH)
                self.assertEqual(result.consumed_risk_ids,(request.surgery.failure_risk.id,))
                replace(result)

    def test_disfigurement_is_a_real_persistent_fact_without_invented_wound_or_penalty(self):
        request=self.request()
        result=resolve_surgery_failure(request,SequenceRandom([3]))
        fact=result.disfigurement
        self.assertEqual((fact.risk_id,fact.target_id,fact.wound),
            (request.surgery.failure_risk.id,'surgeon',request.injury_state.wounds[0]))
        self.assertEqual(fact.description,request.policy.disfigurement_description)
        self.assertEqual(result.state,request.injury_state)
        self.assertIsNone(request.surgery.proof)
        self.assertEqual(request.surgery.progress.exacting.accumulated_successes,0)

    def test_death_does_not_manufacture_a_table_roll_fate_window_or_an_action(self):
        request=self.request(SurgeryRiskPolicy('gm:danger',0,0,1))
        result=resolve_surgery_failure(request,SequenceRandom([1]))
        self.assertTrue(result.state.dead)
        self.assertIsNone(result.disfigurement)
        self.assertEqual(sum(slot.executed for slot in request.surgery.round_state.active_turn.action_slots),1)
        self.assertEqual(result.state,replace(request.injury_state,dead=True))

    def test_same_failed_test_cannot_be_consumed_twice(self):
        request=self.request()
        result=resolve_surgery_failure(request,SequenceRandom([1]))
        with self.assertRaises(ValueError):
            replace(request,consumed_risk_ids=result.consumed_risk_ids)
        with self.assertRaises(ValueError):
            replace(request,consumed_risk_ids=('older','older'))

    def test_successful_surgery_contribution_does_not_offer_risk(self):
        request=self.request()
        success=execute_combat_surgeon_battle_surgery_action(
            surgery_request(1,surgical_state()),SequenceRandom([1,1,1]))
        self.assertIsNone(success.failure_risk)
        with self.assertRaises(ValueError): replace(request,surgery=success)

    def test_stale_or_dead_patient_is_not_replaced_by_recorded_old_state(self):
        request=self.request()
        with self.assertRaises(ValueError): replace(request,injury_state=replace(request.injury_state,dead=True))
        with self.assertRaises(ValueError): replace(request,injury_state=replace(request.injury_state,active_wound_effects=()))

    def test_bad_gm_policy_has_no_implicit_default_or_probability(self):
        for weights in ((0,0,0),(True,1,1),(-1,1,1),(1.0,1,1)):
            with self.subTest(weights=weights), self.assertRaises((TypeError,ValueError)):
                SurgeryRiskPolicy('gm:bad',*weights,disfigurement_description='scar')
        with self.assertRaises((TypeError,ValueError)): SurgeryRiskPolicy('gm:bad',1,1,1)
        with self.assertRaises(ValueError): SurgeryRiskPolicy('gm:bad',1,0,0,owner=DecisionOwner.ACTOR)
        with self.assertRaises(ValueError): SurgeryRiskPolicy('gm:bad',1,0,0,'unused effect')

    def test_forged_draw_outcome_patient_and_ledger_are_rejected(self):
        request=self.request()
        result=resolve_surgery_failure(request,SequenceRandom([1]))
        for change in ({'draw':True},{'draw':7},{'outcome':SurgeryFailureOutcome.DEATH},
                {'state':replace(result.state,dead=True)},{'consumed_risk_ids':()},
                {'consumed_risk_ids':list(result.consumed_risk_ids)}):
            with self.subTest(change=change), self.assertRaises((TypeError,ValueError)):
                replace(result,**change)

    def test_downtime_failure_uses_the_same_explicit_owner(self):
        from tests.unit.test_k1_downtime_surgery import surgery_request as downtime_request
        from towr.rules.surgery_resolution import resolve_downtime_surgery
        source=resolve_downtime_surgery(downtime_request(surgical_state()),SequenceRandom([10,10,10]))
        request=SurgeryFailureResolutionRequest('downtime:risk',source,SurgeryRiskPolicy('gm:quiet',1,0,0),source.state)
        result=resolve_surgery_failure(request,SequenceRandom([1]))
        self.assertIs(result.outcome,SurgeryFailureOutcome.NO_COMPLICATION)
        self.assertEqual(result.state,source.state)
