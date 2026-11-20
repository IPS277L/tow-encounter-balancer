"""Public generation preserves the book's paid Agility requirement."""
from dataclasses import replace
from random import Random
from unittest import TestCase, main

from tests.unit.test_generated_npc_talent_generation import FixedChoices
from towr.application.dynamic_encounter import NpcSearchSpace
from towr.domain.generated_npc_models import GeneratedWeapon
from towr.domain.pc_mount_models import CombatMount, RiderKind
from towr.domain.talent_actor_models import GENERATED_TALENT_POOL
from towr.domain.talent_catalog import TalentId


def space(agility):
    return NpcSearchSpace(agility=agility,weapon=(GeneratedWeapon.STAFF,),weapon_count=(1,),
        armour=(None,),shield=(None,),mount=(CombatMount.HORSE,),rider_kind=(RiderKind.HUMAN,),
        allowed_talents=(TalentId.BACK_IN_THE_SADDLE,))


class BackInSaddleGenerationTests(TestCase):
    def test_paid_purchase_requires_agility_four_and_has_a_real_mount_source(self):
        npc=space((4,)).sample(FixedChoices(1))
        self.assertEqual(tuple(row.id for row in npc.talents),(TalentId.BACK_IN_THE_SADDLE,))
        self.assertIs(npc.mount,CombatMount.HORSE)
        self.assertTrue(space((4,)).contains(npc))
        self.assertIn(TalentId.BACK_IN_THE_SADDLE,GENERATED_TALENT_POOL)
        with self.assertRaises(ValueError): replace(npc,agility=3)
        self.assertEqual(space((3,)).sample(FixedChoices(1)).talents,())

    def test_numeric_resampling_keeps_the_actual_purchase_and_its_prerequisite(self):
        npc=space((4,)).sample(FixedChoices(1))
        changed=space((3,4)).resample_numeric((npc,),FixedChoices(0)).composition[0]
        self.assertEqual(changed.talents,npc.talents)
        self.assertEqual(changed.agility,4)
        self.assertTrue(space((3,4)).contains(changed))

    def test_component_mutation_cannot_leave_an_illegal_paid_talent(self):
        allowed=space((3,4))
        npc=space((4,)).sample(FixedChoices(1))
        for seed in range(8):
            with self.subTest(seed=seed):
                changed=allowed.mutate(npc,Random(seed))
                self.assertTrue(allowed.contains(changed))
                if any(row.id is TalentId.BACK_IN_THE_SADDLE for row in changed.talents):
                    self.assertGreaterEqual(changed.agility,4)


if __name__=='__main__': main()
