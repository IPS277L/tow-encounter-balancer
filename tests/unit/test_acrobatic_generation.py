"""Acrobatic is selected from actual initial Agility and preserved on resampling."""
from dataclasses import replace
import unittest

from tests.unit.test_generated_npc_talent_generation import FixedChoices
from towr.application.dynamic_encounter import NpcSearchSpace
from towr.domain.generated_npc_models import GeneratedWeapon,generated_talent_requirements_met
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_actor_models import GENERATED_TALENT_POOL


class AcrobaticGenerationTests(unittest.TestCase):
    def space(self,agility):
        return NpcSearchSpace(agility=agility,weapon=(GeneratedWeapon.STAFF,),weapon_count=(1,),
            armour=(None,),shield=(None,),allowed_talents=(TalentId.ACROBATIC,))

    def test_actual_initial_agility_controls_sampling_and_loaded_source_admission(self):
        npc=self.space((4,)).sample(FixedChoices(1))
        self.assertEqual(tuple(entry.id for entry in npc.talents),(TalentId.ACROBATIC,))
        self.assertTrue(self.space((4,)).contains(npc))
        self.assertIn(TalentId.ACROBATIC,GENERATED_TALENT_POOL)
        with self.assertRaises(ValueError):replace(npc,agility=3)
        self.assertEqual(self.space((3,)).sample(FixedChoices(1)).talents,())

    def test_missing_or_insufficient_agility_never_implies_a_paid_requirement(self):
        for value in (None,3):
            with self.subTest(agility=value):
                self.assertFalse(generated_talent_requirements_met(TalentId.ACROBATIC,
                    weapon_skill=4,strength=4,agility=value))
        self.assertTrue(generated_talent_requirements_met(TalentId.ACROBATIC,
            weapon_skill=4,strength=4,agility=4))

    def test_numeric_resampling_preserves_purchase_and_filters_illegal_agility(self):
        space=self.space((3,4))
        npc=self.space((4,)).sample(FixedChoices(1))
        changed=space.resample_numeric((npc,),FixedChoices(0)).composition[0]
        self.assertEqual(changed.talents,npc.talents)
        self.assertEqual(changed.agility,4)
        self.assertTrue(space.contains(changed))


if __name__=='__main__':unittest.main()
