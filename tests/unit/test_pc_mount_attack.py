"""Mount Abilities retain their source independently of the rider's equipment."""
from dataclasses import replace
import unittest

from tests.unit.test_pc_demigryph import reserved
from towr.domain.armour_models import ArmourLoadout, BodyArmour
from towr.domain.pc_mount_attack_models import (
    PcMountedAttackMode, PcMountAttackAbility, build_pc_mounted_attack_intent,
    pc_mount_attack_profile, pc_mounted_attack_test, prepare_pc_mounted_attack,
)
from towr.domain.pc_mount_models import CombatMount
from towr.domain.test_models import InlineProfile


class PcMountedAttackTests(unittest.TestCase):
    def test_all_six_mounts_use_their_printed_natural_attack(self):
        for mount in CombatMount:
            with self.subTest(mount=mount):
                ability, profile, damage = pc_mount_attack_profile(mount)
                if mount is CombatMount.DEMIGRYPH:
                    self.assertEqual((ability, profile, damage.base),
                        (PcMountAttackAbility.WICKED_CLAWS, InlineProfile(4, 4, 8), 5))
                else:
                    self.assertEqual((ability, profile, damage.base),
                        (PcMountAttackAbility.HOOVES, InlineProfile(3, 3, 6), 3))

    def test_mount_abilities_do_not_receive_rider_sword_or_agilulf_ratings(self):
        loadout=ArmourLoadout((BodyArmour.AGILULF,), BodyArmour.AGILULF)
        state=reserved(mount=CombatMount.HORSE,armour=loadout)
        test=pc_mounted_attack_test(state,'pc1','minion1','mount:test')
        self.assertEqual(test.profile,InlineProfile(3,3,6))
        self.assertFalse(any('sword' in item.rule_id or 'agilulf' in item.rule_id for item in test.dice_modifiers))
        kernel,_=prepare_pc_mounted_attack(state,'pc1','minion1','mount')
        self.assertEqual(kernel.attack.impact_spec.damage.base,3)
        self.assertEqual(kernel.attack.impact_spec.damage_modifiers,())
        self.assertFalse(kernel.attack.impact_spec.ignores_armour)

    def test_retained_primary_intent_has_actual_mount_actor_target_and_clock(self):
        state=reserved(mount=CombatMount.HORSE)
        intent=build_pc_mounted_attack_intent(state,'pc1','minion1')
        self.assertIs(intent.mode,PcMountedAttackMode.MOUNT)
        self.assertEqual(intent.weapon_instance_id,'pc1:mount:horse:hooves')
        self.assertEqual(intent.source_round,state.round_state)
        with self.assertRaises(ValueError):
            replace(intent,actor_id='minion1')
        with self.assertRaises(ValueError):
            replace(intent,target_id='pc1')
        with self.assertRaises(ValueError):
            _=replace(intent,mode=PcMountedAttackMode.RIDER).weapon_instance_id


if __name__=='__main__':unittest.main()
