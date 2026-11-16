import unittest
from towr.domain.pc_tactical_models import _distribution
from towr.domain.test_models import TestRequest,InlineProfile,QualityModifier,TestQuality
from towr.rules.miscast_pool_resolution import rule_of_nine_reroll_lock


class CastingProbabilityTests(unittest.TestCase):
    def test_locked_nine_changes_both_grim_success_and_glorious_failure_rerolls(self):
        grim=TestRequest('grim-nine',InlineProfile(1,9),
            quality_modifiers=(QualityModifier('armour',TestQuality.GRIM),),
            reroll_locks=(rule_of_nine_reroll_lock(),))
        glorious=TestRequest('glorious-nine',InlineProfile(1,5),
            quality_modifiers=(QualityModifier('fate',TestQuality.GLORIOUS),),
            reroll_locks=(rule_of_nine_reroll_lock(),))
        self.assertAlmostEqual(_distribution(grim)[1],0.82)
        self.assertAlmostEqual(_distribution(glorious)[1],0.70)


if __name__=='__main__':
    unittest.main()
