"""Bash is sampled from numeric prerequisites, not a canonical NPC identity."""
from dataclasses import replace
import unittest

from tests.unit.test_generated_npc_talent_generation import FixedChoices
from towr.application.dynamic_encounter import NpcSearchSpace
from towr.domain.generated_npc_models import GeneratedWeapon
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_actor_models import GENERATED_TALENT_POOL


class BashGenerationTests(unittest.TestCase):
    def space(self,strength):
        return NpcSearchSpace(strength=(strength,),weapon=(GeneratedWeapon.SWORD,),weapon_count=(1,),
            armour=(None,),shield=(None,),allowed_talents=(TalentId.BASH_ATTACK,))

    def test_eligible_numeric_npc_can_gain_the_talent_and_retains_full_acquisition(self):
        space=self.space(5)
        npc=space.sample(FixedChoices(1))
        self.assertEqual(tuple(talent.id for talent in npc.talents),(TalentId.BASH_ATTACK,))
        self.assertTrue(npc.talents[0].acquisitions)
        self.assertTrue(space.contains(npc))
        self.assertIsNotNone(npc.brawn)
        self.assertIn(TalentId.BASH_ATTACK,GENERATED_TALENT_POOL)

    def test_insufficient_initial_strength_never_samples_bash(self):
        npc=self.space(4).sample(FixedChoices(1))
        self.assertEqual(npc.talents,())
        eligible=self.space(5).sample(FixedChoices(1))
        with self.assertRaises(ValueError):replace(eligible,strength=4)

    def test_numeric_resampling_keeps_valid_source_without_weakening_requirements(self):
        space=self.space(5)
        npc=space.sample(FixedChoices(1))
        sampled=space.resample_numeric((npc,),FixedChoices(0))
        changed=sampled.composition[0]
        self.assertEqual(changed.talents,npc.talents)
        self.assertEqual(changed.strength,5)
        self.assertTrue(space.contains(changed))


if __name__=='__main__':unittest.main()
