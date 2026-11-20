"""Native ground foundation, with the unfinished public Talent cap kept closed.

Only fixture admission is widened. Attack, injury, dismount, retention,
ordinary Recover, remount and every replay step use the actual owners.
"""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import paid_talent
from tests.support.generated_weapon_sources import initial_generated_weapons
from towr.domain import talent_actor_models
from towr.domain.armour_models import ArmourLoadout
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.pc_back_in_saddle_models import PcBackInSaddleRecoverProof, PcBackInSaddleMoveProof
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_battlefield_movement_models import PcBattlefieldRecoverProof
from towr.domain.pc_melee_models import PcMeleePolicy
from towr.domain.pc_melee_result_models import (
    PcMeleeStep, PcAttackProof, PcRecoverProof, initial_pc_melee_state,
)
from towr.domain.pc_mount_models import CombatMount, PcDismountProof
from towr.domain.pc_mount_retention_models import PcMountRetentionProof
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.talent_catalog import TalentId
from towr.domain.turn_models import CombatSide
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step


def pc_ground_source():
    source = make_pc_melee_party_scenario(pc_count=1, enemy_count=1, max_rounds=2)
    member = replace(source.party[0], pc=replace(source.party[0].pc, toughness=3,
        agility=4, athletics=1), mount=CombatMount.HORSE, policy=PcMeleePolicy.AUTOMATIC_COMBAT,
        talents=(paid_talent(TalentId.BACK_IN_THE_SADDLE),))
    enemy = GeneratedNpc(3, 5, 20, 1, 5, 2, initial_generated_weapons(GeneratedWeapon.STAFF),
        ArmourLoadout(), defence=2)
    return replace(source, party=(member,), enemies=(enemy.participant('minion1'),),
        battlefield=PcBattlefieldSpec(RangedWeaponRange.CLOSE, RangedWeaponRange.LONG),
        facts=replace(source.facts, unmounted=False, can_leave_zone=True, outnumbering_bonus_approved=False))


def npc_ground_source():
    source = make_pc_melee_party_scenario(pc_count=1, enemy_count=1, max_rounds=1)
    member = replace(source.party[0], mount=CombatMount.HORSE, policy=PcMeleePolicy.AUTOMATIC_COMBAT)
    enemy = GeneratedNpc(3, 3, 20, 4, 4, 2, initial_generated_weapons(GeneratedWeapon.STAFF),
        ArmourLoadout(), defence=2, mount=CombatMount.HORSE,
        talents=(paid_talent(TalentId.BACK_IN_THE_SADDLE),))
    return replace(source, party=(member,), enemies=(enemy.participant('minion1'),),
        battlefield=PcBattlefieldSpec(RangedWeaponRange.MEDIUM, RangedWeaponRange.LONG),
        facts=replace(source.facts, all_opponents_close=False, unmounted=False,
            can_leave_zone=True, outnumbering_bonus_approved=False))


class BackInSaddleGroundNativeTests(unittest.TestCase):
    def setUp(self):
        # Explicit foundation-only admission, not a public/runtime capability claim.
        for name in ('PC_EXECUTABLE_TALENTS', 'NPC_EXECUTABLE_TALENTS'):
            self.enterContext(patch.object(talent_actor_models, name,
                getattr(talent_actor_models, name) | {TalentId.BACK_IN_THE_SADDLE}))

    def test_pc_real_prone_dismount_then_paid_recover_remount_preserves_wound_and_replays(self):
        source = pc_ground_source()
        # PC misses; generated NPC hits and real Wound9 knocks the rider Prone.
        # Next round PC pays Recover to stand/remount; the NPC then misses.
        rng = ScriptedD10([10]*3 + [1]*3 + [1]*3 + [10]*3 + [9] + [10]*3 + [1]*3)
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        self.assertIsNone(result.unsupported)
        dismount, = tuple(step for step in result.steps if type(step.proof) is PcDismountProof)
        retained, = tuple(step for step in result.steps if type(step.proof) is PcMountRetentionProof)
        recovery, = tuple(step for step in result.steps if type(step.proof) is PcRecoverProof)
        remount, = tuple(step for step in result.steps if type(step.proof) is PcBackInSaddleRecoverProof)
        self.assertLess(result.steps.index(dismount), result.steps.index(retained))
        self.assertLess(result.steps.index(retained), result.steps.index(recovery))
        self.assertEqual(result.steps.index(recovery)+1, result.steps.index(remount))
        self.assertTrue(dismount.source.mounts[0].mounted)
        self.assertFalse(retained.state.mounts[0].mounted)
        self.assertTrue(retained.state.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertTrue(remount.state.mounts[0].mounted)
        self.assertFalse(remount.state.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertEqual(remount.proof.previous_body.snapshot, remount.proof.body.snapshot)
        self.assertEqual(len(retained.state.participant('pc1').injury.wounds), 1)
        self.assertEqual(result.state.participant('pc1').injury.wounds,
            retained.state.participant('pc1').injury.wounds)
        self.assertEqual(remount.proof.recovery, recovery.proof.result)
        self.assertEqual(remount.source.round_state.active_turn.action_slots,
            remount.state.round_state.active_turn.action_slots)
        self.assertEqual(len(remount.state.round_state.active_turn.action_slots), 1)
        self.assertFalse(any(type(step.proof) is PcBackInSaddleMoveProof for step in result.steps))
        self.assertEqual(len(tuple(step for step in result.steps if type(step.proof) is PcAttackProof)), 3)
        self.assertEqual(result.executed_actions, 4)
        state = initial_pc_melee_state(source)
        for step in result.steps:
            state = apply_pc_melee_step(state, step)
        self.assertEqual(state, result.state)
        for step in (retained, remount):
            with self.subTest(proof=type(step.proof).__name__), self.assertRaises(ValueError):
                PcMeleeStep(step.state, step.proof)

    def test_generated_npc_real_horse_charge_prone_then_paid_recover_remount_replays_without_fate(self):
        source = npc_ground_source()
        # The mounted PC Charges. Four Attack successes tie four Athletics
        # successes; the Horse inflicts Prone before the first Staggered.
        rng = ScriptedD10([1]*8)
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        self.assertIsNone(result.unsupported)
        retained, = tuple(step for step in result.steps if type(step.proof) is PcMountRetentionProof)
        recovery, = tuple(step for step in result.steps if type(step.proof) is PcBattlefieldRecoverProof)
        remount, = tuple(step for step in result.steps if type(step.proof) is PcBackInSaddleRecoverProof)
        self.assertEqual(retained.proof.source.actor_id, 'minion1')
        self.assertEqual(remount.proof.source.actor_id, 'minion1')
        self.assertLess(result.steps.index(retained), result.steps.index(recovery))
        self.assertEqual(result.steps.index(recovery)+1, result.steps.index(remount))
        self.assertTrue(retained.state.enemy('minion1').state.injury.conditions.has(Condition.PRONE))
        self.assertTrue(retained.state.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(remount.state.enemy('minion1').state.injury.conditions.has(Condition.PRONE))
        self.assertEqual(remount.proof.previous_body.snapshot, remount.proof.body.snapshot)
        self.assertEqual(remount.proof.body.snapshot.state.injury.wounds, 0)
        self.assertIs(remount.proof.body.snapshot.state.side, CombatSide.OPPOSITION)
        self.assertFalse(hasattr(remount.proof.body.snapshot.state, 'fate'))
        self.assertFalse(hasattr(result.state.enemy('minion1').state, 'fate'))
        self.assertEqual(tuple(row.state.actor_id for row in result.state.enemies), ('minion1',))
        self.assertTrue(next(row for row in result.state.mounts if row.actor_id == 'minion1').mounted)
        self.assertEqual(remount.proof.recovery, recovery.proof.result)
        self.assertEqual(remount.source.round_state.active_turn.action_slots,
            remount.state.round_state.active_turn.action_slots)
        self.assertEqual(len(remount.state.round_state.active_turn.action_slots), 1)
        self.assertFalse(any(type(step.proof) is PcBackInSaddleMoveProof for step in result.steps))
        self.assertEqual(result.executed_actions, 2)
        replay = initial_pc_melee_state(source)
        for step in result.steps:
            replay = apply_pc_melee_step(replay, step)
        self.assertEqual(replay, result.state)
        with self.assertRaises(ValueError):
            PcMeleeStep(remount.state, remount.proof)


if __name__ == '__main__':
    unittest.main()
