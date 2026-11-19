"""Scarab charges heal an actual recorded injury through one paid Recover."""
import unittest

from tests.support.magic_weapon_battles import magic_battle, run_native
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.injury_models import WoundEntryId
from towr.domain.pc_scarab_recover_models import PcScarabHealingProof
from towr.domain.recover_models import RecoverMode


class MagicWeaponHealingTests(unittest.TestCase):
    def test_automatic_scarab_heals_actual_crushed_rib_and_spends_only_its_three_charges(self):
        source = magic_battle('scarab_knife', rounds=2, initial_charges=3,
            pc_ws=1, npc_ws=6, pc_toughness=1)
        # Real first Attack/Protection use fourteen dice, then Wounds Table10.
        # The next PC turn pays Recover; the final enemy Attack causes another
        # genuine superficial Wound, with no untreated Rib bonus die left.
        rng = ScriptedD10([3] * 14 + [10] + [3] * 8)
        result = run_native(self, source, rng)
        rng.assert_exhausted()
        heal, = (step for step in result.steps if type(step.proof) is PcScarabHealingProof)
        before = heal.source.participant('pc')
        after = heal.state.participant('pc')
        proof = heal.proof
        self.assertIs(before.injury.wounds[0].entry_id, WoundEntryId.CRUSHED_RIB)
        self.assertFalse(before.injury.wounds[0].healed)
        self.assertTrue(after.injury.wounds[0].healed)
        self.assertTrue(after.injury.wounds[0].treated)
        self.assertFalse(any(effect.wound_sequence == 1 for effect in after.injury.active_wound_effects))
        self.assertIs(proof.request.mode, RecoverMode.STANDARD)
        self.assertEqual(proof.request.choice.object_interaction.object_id, proof.selection.item_id)
        self.assertEqual(proof.result.resolution.object_interaction_follow_up.object_id, proof.selection.item_id)
        self.assertEqual(proof.selection.wound_sequence, 1)
        self.assertEqual(before.weapon_inventory.item(proof.selection.item_id).charges, 3)
        self.assertEqual(after.weapon_inventory.item(proof.selection.item_id).charges, 0)
        self.assertEqual(after.weapon_inventory.item(proof.selection.item_id).source,
            before.weapon_inventory.item(proof.selection.item_id).source)
        self.assertEqual(after.weapon_inventory.item(proof.selection.item_id).location,
            before.weapon_inventory.item(proof.selection.item_id).location)
        self.assertTrue(proof.result.slot.executed)
        self.assertEqual(result.executed_actions, 4)
        self.assertEqual(result.state.participant('pc').daily_wounds.wound_count, 2)


if __name__ == '__main__':
    unittest.main()
