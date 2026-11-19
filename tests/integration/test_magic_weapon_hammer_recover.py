"""A genuinely missed higher-ground strike embeds the same finite Hammer."""
from dataclasses import replace
import unittest

from tests.support.magic_weapon_battles import (
    magic_battle, pc_after_horse_charge_source, run_native, Threes,
)
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition
from towr.domain.pc_hammer_recover_models import (
    PcHammerRetrievalProof, hammer_retrieval_option, project_pc_hammer_retrieval,
)
from towr.domain.pc_melee_models import PcMeleePolicy
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_npc_catalog import create_pc_book_npc, PcBookNpcProfile
from towr.domain.recover_models import RecoverMode
from towr.domain.test_models import Skill
from towr.domain.weapon_inventory_models import WeaponItemLocation
from towr.domain.weapon_magic_lifecycle import GROTARGG_RETRIEVE_RULE_ID
from towr.engine.pc_melee_runner import apply_pc_melee_step


def npc_hammer_source():
    source = magic_battle('grotarggs_hammer', npc_magic=True, count=2,
        pc_ws=1, npc_ws=6, rounds=3)
    bear = create_pc_book_npc(PcBookNpcProfile.BEAR_CRUSHING_WEIGHT,
        source.enemy_activation_order[0])
    member = replace(source.party[0], policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF)
    return replace(source, party=(member,), enemies=(bear, source.enemies[1]),
        battlefield=None, facts=replace(source.facts, all_opponents_close=True, can_leave_zone=False))


class NpcHammerMiss(Threes):
    def __init__(self):
        self.calls = 0

    def randint(self, low, high):
        self.calls += 1
        # Real first PC HIT avoids a miss-Stagger; Bear then knocks the PC
        # Prone, and the eight-die higher-ground Grotargg Test/rerolls miss.
        return 10 if 2 <= self.calls <= 4 or 10 <= self.calls <= 25 else super().randint(low, high)


class MagicWeaponHammerRecoverTests(unittest.TestCase):
    def test_pc_paid_retrieval_restores_same_unit_and_marker_only_after_real_success(self):
        source = pc_after_horse_charge_source('grotarggs_hammer', count=2, rounds=3)
        rng = ScriptedD10([3] * 8 + [10] * 12 + [3] * 30)
        result = run_native(self, source, rng)
        rng.assert_exhausted()
        recover, = (step for step in result.steps if type(step.proof) is PcHammerRetrievalProof)
        proof = recover.proof
        actor = source.pc_activation_order[1]
        self.assertEqual(proof.actor_id, actor)
        self.assertEqual(hammer_retrieval_option(recover.source, actor), proof.weapon_id)
        self.assertIs(proof.request.mode, RecoverMode.RETRIEVE_HAMMER)
        self.assertIs(proof.request.choice.test_skill, Skill.BRAWN)
        self.assertTrue(proof.result.resolution.succeeded)
        self.assertEqual(tuple(mod.amount for mod in proof.effective.choice.test.dice_modifiers
            if mod.rule_id == GROTARGG_RETRIEVE_RULE_ID), (-2,))
        self.assertEqual(proof.result.resolution.test_result.trace.initial_values, (3,))
        old = recover.source.participant(actor).weapon_inventory.item(proof.weapon_id)
        after = recover.state.participant(actor).weapon_inventory.item(proof.weapon_id)
        self.assertIs(old.location, WeaponItemLocation.STUCK)
        self.assertIs(after.location, WeaponItemLocation.HELD)
        self.assertEqual(old.source, after.source)
        self.assertEqual(old.id, after.id)
        self.assertIsNotNone(proof.previous_item.ground)
        self.assertIsNone(proof.item.ground)
        self.assertTrue(any(placement.entity_id == proof.previous_item.marker_id
            for placement in proof.previous.spatial.placements))
        self.assertFalse(any(placement.entity_id == proof.item.marker_id
            for placement in proof.state.spatial.placements))
        self.assertTrue(recover.source.participant(actor).injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(recover.state.participant(actor).injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(hasattr(proof.result.resolution, 'condition_changes'))
        self.assertEqual(result.executed_actions, 8)
        with self.assertRaises((ValueError, TypeError)):
            apply_pc_melee_step(recover.state, proof)
        with self.assertRaises((ValueError, TypeError)):
            project_pc_hammer_retrieval(recover.source, replace(proof, item=proof.previous_item))
        with self.assertRaises((ValueError, TypeError)):
            project_pc_hammer_retrieval(recover.source, replace(proof,
                request=replace(proof.request, choice=replace(proof.request.choice,
                    item_id='foreign-unit'))))

    def test_failed_pc_recover_spends_action_and_keeps_the_actual_hammer_embedded(self):
        source = pc_after_horse_charge_source('grotarggs_hammer', count=2, rounds=3)
        # Same real battle; only the extraction Test at index37 fails.
        rng = ScriptedD10([3] * 8 + [10] * 12 + [3] * 16 + [10] + [3] * 13)
        result = run_native(self, source, rng)
        rng.assert_exhausted()
        recover, = (step for step in result.steps if type(step.proof) is PcHammerRetrievalProof)
        proof = recover.proof
        self.assertFalse(proof.result.resolution.succeeded)
        self.assertTrue(proof.result.slot.executed)
        self.assertEqual(proof.result.resolution.test_result.trace.initial_values, (10,))
        self.assertEqual(proof.previous_item, proof.item)
        self.assertEqual(proof.previous, proof.state)
        self.assertEqual(proof.resources.previous_inventory, proof.resources.after_inventory)
        self.assertIs(recover.state.participant(proof.actor_id).weapon_inventory.item(proof.weapon_id).location,
            WeaponItemLocation.STUCK)
        self.assertIsNotNone(proof.item.ground)
        self.assertEqual(result.executed_actions, 8)

    def test_generated_npc_uses_own_brawn_and_same_recover_without_any_pc_fate(self):
        source = npc_hammer_source()
        result = run_native(self, source, NpcHammerMiss())
        recover, = (step for step in result.steps if type(step.proof) is PcHammerRetrievalProof)
        proof = recover.proof
        actor = source.enemy_activation_order[1]
        self.assertEqual(proof.actor_id, actor)
        self.assertIs(proof.request.mode, RecoverMode.RETRIEVE_HAMMER)
        self.assertTrue(proof.result.resolution.succeeded)
        self.assertEqual(proof.effective.choice.test.profile.threshold, 4)
        self.assertEqual(proof.result.resolution.test_result.trace.rolled_dice, 1)
        self.assertIsNone(proof.fate_decline)
        self.assertIsNone(proof.glorious)
        self.assertEqual(proof.resources.previous_inventory.item(proof.weapon_id).source,
            proof.resources.after_inventory.item(proof.weapon_id).source)
        self.assertIs(proof.resources.after_inventory.item(proof.weapon_id).location, WeaponItemLocation.HELD)
        self.assertIsNone(proof.item.ground)
        self.assertTrue(recover.state.enemy(actor).state.wields_weapon)


if __name__ == '__main__':
    unittest.main()
