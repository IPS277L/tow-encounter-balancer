"""An additional surgeon Test has its own once-only modifier window."""
from dataclasses import replace
from unittest import TestCase

from tests.helpers import SequenceRandom
from tests.unit.test_c24_medical_effective_consumers import _wounded_state,_append
from towr.domain.pc_medical_models import (build_medical_treatment,complete_medical_treatment,
    expected_medical_treatment_application,expected_medical_suppression,complete_medical_suppression,
    PcMedicalTreatmentProof,PcMedicalTreatmentApplicationProof,PcMedicalSuppressionProof)
from towr.domain.pc_magic_models import PcMagicModifier,PcMagicTaskKind
from towr.domain.pc_melee_result_models import PcMeleeStep,PcFateDecline
from towr.domain.pc_oath_models import oath_step_evidence
from towr.rules.recover_resolution import apply_recover_wound_treatment
from towr.rules.test_resolution import resolve_test


class MedicalTestConsumptionTests(TestCase):
    def test_anatomy_preserves_next_test_penalty_then_additional_recall_consumes_it(self):
        state,actor,target,_=_wounded_state()
        modifier=PcMagicModifier('medical:next-test',actor,PcMagicTaskKind.NEXT_TEST_PENALTY)
        state=replace(state,magic_modifiers=(modifier,))
        prepared=build_medical_treatment(state,target,1)
        self.assertIsNone(prepared.test)
        state=_append(state,PcMedicalTreatmentProof(prepared,complete_medical_treatment(prepared)))
        state=_append(state,PcMedicalTreatmentApplicationProof(apply_recover_wound_treatment(
            expected_medical_treatment_application(state))))
        self.assertEqual(state.magic_modifiers,(modifier,))
        request=expected_medical_suppression(state)
        test=resolve_test(request.recall_test,SequenceRandom([1]*20))
        self.assertIn(modifier.source_id,test.trace.applied_rule_ids)
        proof=PcMedicalSuppressionProof(request,complete_medical_suppression(request,test),
            PcFateDecline(actor,request.recall_test.id,'test',state.source.participant(actor).fate_policy))
        self.assertIn(test,oath_step_evidence(proof))
        after=PcMeleeStep(state,proof).state
        self.assertEqual(after.magic_modifiers,())
        with self.assertRaises(ValueError):PcMeleeStep(after,proof)
