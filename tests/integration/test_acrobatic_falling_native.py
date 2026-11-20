"""Actual PC/NPC Pegasus dismounts retain Acrobatic's real fall source."""
from dataclasses import replace
import unittest

from tests.integration.test_pc_falling_native import falling_source
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import free_talent
from towr.domain.armour_models import ArmourLoadout, BodyArmour, ITHILMAR_ENVIRONMENT_RULE_ID
from towr.domain.pc_battlefield_models import PcAirspaceSpec, PcBattlefieldSpec, battlefield_is_midair
from towr.domain.pc_falling_models import PcFallingProof
from towr.domain.pc_melee_result_models import PcMeleeStep, initial_pc_melee_state
from towr.domain.pc_mount_models import CombatMount, RiderKind
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.talent_catalog import TalentId
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


class NativeAcrobaticFallingTests(unittest.TestCase):
    def assert_replay(self, result):
        state = initial_pc_melee_state(result.source)
        for step in result.steps:
            state = apply_pc_melee_step(state, step)
        self.assertEqual(state, result.state)

    def test_pc_rating_zero_still_rolls_actual_athletics_after_real_leg_spasm_dismount(self):
        source = falling_source()
        member = replace(source.party[0], talents=(free_talent(TalentId.ACROBATIC),))
        source = replace(source, party=(member,), battlefield=replace(source.battlefield,
            airspace=replace(source.battlefield.airspace, fall_hazard_rating=1)))
        # The original gunshot causes real Wound9 and its forced dismount.
        # The final10 is the real failed Athletics Test, not a skipped Hazard0.
        rng = ScriptedD10([10, 10] + [1]*6 + [10, 9, 10])
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        self.assertIsNone(result.unsupported)
        fall, = tuple(step for step in result.steps if type(step.proof) is PcFallingProof)
        exposure = fall.proof.request.exposure
        self.assertEqual((exposure.acrobatic_fall.base_rating, exposure.rating), (1, 0))
        self.assertEqual(exposure.acrobatic_fall.source.talent, member.talents[0])
        self.assertEqual(fall.proof.test.trace.initial_values, (10,))
        self.assertEqual((fall.proof.test.successes, fall.proof.result.shortfall), (0, 0))
        self.assertTrue(fall.proof.result.avoided)
        self.assertIsNone(fall.state.pending_wound)
        self.assertEqual(tuple(wound.table_total for wound in result.state.participant('pc1').injury.wounds), (9,))
        self.assertEqual(result.state.participant('pc1').fate, member.fate)
        self.assertTrue(battlefield_is_midair(fall.source.battlefield, 'pc1'))
        self.assertFalse(battlefield_is_midair(fall.state.battlefield, 'pc1'))
        self.assertEqual(fall.source.round_state, fall.state.round_state)
        self.assertEqual(result.executed_actions, 2)
        self.assert_replay(result)
        with self.assertRaises(ValueError):
            PcMeleeStep(fall.state, fall.proof)

    def test_npc_rating_three_halves_to_one_after_actual_airborne_charge_with_ithilmar(self):
        from tests.integration.test_pc_weighted_net_native import pc_net_scene
        source = pc_net_scene(rounds=2)
        member = replace(source.party[0], mount=CombatMount.PEGASUS, rider_kind=RiderKind.HUMAN,
            pc=replace(source.party[0].pc, ballistic_skill=3, brawn=None))
        npc = falling_source().enemies[0].definition.generated_components
        npc = replace(npc, armour=ArmourLoadout((BodyArmour.ITHILMAR,), BodyArmour.ITHILMAR),
            mount=CombatMount.PEGASUS, rider_kind=RiderKind.HUMAN,
            talents=(free_talent(TalentId.ACROBATIC),))
        source = replace(source, party=(member,), enemies=(npc.participant('minion1'),),
            npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc, 'minion1'),),
            facts=replace(source.facts, unmounted=False),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT, RangedWeaponRange.LONG,
                airspace=PcAirspaceSpec(3, True)))
        rng = ScriptedD10([1]*21)
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        self.assertIsNone(result.unsupported)
        fall, = tuple(step for step in result.steps if type(step.proof) is PcFallingProof)
        request = fall.proof.request
        exposure = request.exposure
        self.assertEqual(request.actor_id, 'minion1')
        self.assertEqual((exposure.acrobatic_fall.base_rating, exposure.rating), (3, 1))
        self.assertEqual(exposure.acrobatic_fall.source.talent, npc.talents[0])
        self.assertEqual(tuple(mod.amount for mod in request.avoidance_test.dice_modifiers
            if mod.rule_id == ITHILMAR_ENVIRONMENT_RULE_ID), (1,))
        self.assertEqual((fall.proof.test.trace.rolled_dice, fall.proof.test.successes), (2, 2))
        self.assertTrue(fall.proof.result.avoided)
        self.assertIsNone(fall.proof.fate_decline)
        self.assertIsNone(fall.proof.glorious)
        self.assertIsNone(fall.proof.npc_disposition)
        self.assertFalse(fall.state.enemy('minion1').state.injury.defeated)
        self.assertEqual(fall.source.round_state, fall.state.round_state)
        self.assert_replay(result)
        for changed in (replace(exposure, acrobatic_fall=None),
                replace(exposure, acrobatic_fall=replace(exposure.acrobatic_fall, base_rating=2))):
            with self.subTest(exposure=changed), self.assertRaises(ValueError):
                PcMeleeStep(fall.source, replace(fall.proof, request=replace(request, exposure=changed)))
        with self.assertRaises(ValueError):
            PcMeleeStep(fall.state, fall.proof)


if __name__ == '__main__':
    unittest.main()
