"""Item Glorious executes its native tactic without bypassing locked dice."""
from pathlib import Path
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request
from towr.application.dynamic_encounter import search_dynamic_encounter
from towr.domain.pc_melee_result_models import _test_result
from towr.domain.test_models import InlineProfile, QualityModifier, TestQuality, TestRequest
from towr.engine.pc_melee_runner import _Decisions
from towr.rules.miscast_pool_resolution import rule_of_nine_reroll_lock
from towr.rules.test_resolution import resolve_test


class PcArmourGloriousIntegrationTests(unittest.TestCase):
    def test_published_armour_request_runs_its_actual_seeded_search(self):
        source=Path('docs/examples/dynamic/armour.request.json').read_text(encoding='utf-8')
        request=parse_dynamic_encounter_request(source).request
        result=search_dynamic_encounter(request)
        self.assertIs(result.source,request)
        self.assertTrue(result.explored)
        self.assertTrue(result.validations)
        self.assertGreater(result.total_trials,0)

    def test_native_glorious_rerolls_failures_but_preserves_rule_of_nine(self):
        request=TestRequest('native:glorious:locked',InlineProfile(3,5),quality_modifiers=(
            QualityModifier('authored:glorious',TestQuality.GLORIOUS),),
            reroll_locks=(rule_of_nine_reroll_lock(),))
        rng=ScriptedD10([9,10,2,1])
        result=resolve_test(request,rng,decisions=_Decisions())
        rng.assert_exhausted()
        self.assertEqual(result.trace.initial_values,(9,10,2))
        self.assertEqual(result.trace.final_values,(9,1,2))
        self.assertEqual(tuple(r.index for r in result.trace.rerolls),(1,))
        self.assertEqual(result.successes,2)
        _test_result(request,result)
        # Explicit PC scenario decisions other than Test rerolls stay present.
        self.assertIsNone(_Decisions().choose_wound_negation(request=None,table_roll=None,options=()))


if __name__=='__main__':unittest.main()
