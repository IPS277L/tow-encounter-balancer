"""PG69 alternatives via real Tests, physical state, current JSON and replay."""
from dataclasses import replace
import unittest

from tests.support.brawn_displacement_battles import (
    pc_shove_scene, npc_shove_scene, pc_drag_scene, npc_drag_scene, npc_air_drag_scene,
)
from tests.support.magic_weapon_battles import run_native
from towr.domain.brawn_impact_models import BrawnAttackEffect
from towr.domain.condition_models import Condition
from towr.domain.pc_battlefield_models import battlefield_range, battlefield_is_midair
from towr.domain.pc_battlefield_movement_models import PcBattlefieldMoveProof
from towr.domain.pc_brawn_displacement_models import PcBrawnShoveProof, project_pc_brawn_shove
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_mount_models import (
    PcDismountProof, pc_is_mounted, mount_resilience_bonus, PEGASUS_KNIGHTS_RULE_ID,
)
from towr.domain.pc_falling_models import PcFallingProof
from towr.domain.test_models import Skill
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.weapon_catalog import WeaponKind
from towr.engine.pc_melee_runner import apply_pc_melee_step


class BrawnDisplacementExecutionTests(unittest.TestCase):
    def test_shove_changes_actual_close_to_short_and_later_ally_fires_in_both_roles(self):
        for builder, npc in ((pc_shove_scene, False), (npc_shove_scene, True)):
            with self.subTest(npc=npc):
                source = builder()
                result = run_native(self, source)
                shove, = (step for step in result.steps if type(step.proof) is PcBrawnShoveProof)
                proof = shove.proof
                actor = (source.enemy_activation_order if npc else source.pc_activation_order)[0]
                ally = (source.enemy_activation_order if npc else source.pc_activation_order)[1]
                target = (source.pc_activation_order if npc else source.enemy_activation_order)[0]
                self.assertEqual((proof.request.actor_id, proof.request.target_id), (actor, target))
                self.assertIs(proof.attack.weapon_intent.brawn_effect, BrawnAttackEffect.SHOVE)
                self.assertIs(proof.attack.weapon_intent.attack_use.kind, WeaponKind.UNARMED)
                self.assertIs(battlefield_range(proof.previous, actor, target), RangedWeaponRange.CLOSE)
                self.assertIs(battlefield_range(proof.state, actor, target), RangedWeaponRange.SHORT)
                self.assertEqual(proof.previous.spatial, proof.state.spatial)
                self.assertFalse(any(target in pair for pair in proof.state.close_pairs))
                self.assertEqual(shove.source.round_state, shove.state.round_state)
                self.assertNotIn(proof.request, shove.state.pending)
                core = proof.attack.execution.resolution
                self.assertIsNone(core.stagger)
                self.assertIsNone(core.character_wound)
                self.assertIsNone(core.profile_wound)
                shot = next(step.proof for step in result.steps[result.steps.index(shove)+1:]
                    if type(step.proof) is PcAttackProof and step.proof.request.actor_id == ally)
                self.assertIs(shot.weapon_intent.attack_use.kind, WeaponKind.SLING)
                self.assertFalse(shot.request.kernel_request.attack.is_close_range)
                self.assertEqual(result.executed_actions, 3 if npc else 2)
                with self.assertRaises((ValueError, TypeError)):
                    apply_pc_melee_step(shove.state, proof)
                with self.assertRaises((ValueError, TypeError)):
                    project_pc_brawn_shove(shove.source, replace(proof, state=proof.previous))

    def test_drag_removes_real_mount_without_fake_prone_or_wound_in_both_roles(self):
        for builder, npc in ((pc_drag_scene, False), (npc_drag_scene, True)):
            with self.subTest(npc=npc):
                source = builder()
                result = run_native(self, source)
                dismount, = (step for step in result.steps if type(step.proof) is PcDismountProof)
                proof = dismount.proof
                target = (source.pc_activation_order if npc else source.enemy_activation_order)[0]
                self.assertEqual(proof.actor_id, target)
                self.assertIsNotNone(proof.brawn_drag)
                self.assertIs(proof.brawn_drag.kind, BrawnAttackEffect.DISMOUNT)
                self.assertFalse(proof.source_injury.conditions.has(Condition.PRONE))
                self.assertTrue(pc_is_mounted(dismount.source, target))
                self.assertFalse(pc_is_mounted(dismount.state, target))
                self.assertEqual(mount_resilience_bonus(dismount.source, target), 1)
                self.assertEqual(mount_resilience_bonus(dismount.state, target), 0)
                self.assertNotIn(proof.brawn_drag, dismount.state.pending)
                self.assertEqual(dismount.source.round_state, dismount.state.round_state)
                attack = next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
                    and step.proof.request.kernel_request.id == proof.brawn_drag.resolution_id)
                self.assertIs(attack.weapon_intent.brawn_effect, BrawnAttackEffect.DISMOUNT)
                self.assertIsNone(attack.execution.resolution.character_wound)
                self.assertIsNone(attack.execution.resolution.profile_wound)
                self.assertIsNone(attack.execution.resolution.stagger)
                with self.assertRaises((ValueError, TypeError)):
                    replace(proof, brawn_drag=None)
                with self.assertRaises((ValueError, TypeError)):
                    apply_pc_melee_step(dismount.state, proof)

    def test_real_airborne_drag_runs_existing_falling_hazard_after_actual_flight(self):
        source = npc_air_drag_scene()
        result = run_native(self, source)
        actor, target = source.enemy_activation_order[0], source.pc_activation_order[0]
        self.assertTrue(any(type(step.proof) is PcBattlefieldMoveProof
            and step.proof.actor_id == target and battlefield_is_midair(step.state.battlefield, target)
            for step in result.steps))
        drag, = (step for step in result.steps if type(step.proof) is PcDismountProof)
        self.assertIsNotNone(drag.proof.brawn_drag)
        self.assertEqual((drag.proof.brawn_drag.actor_id, drag.proof.actor_id), (actor, target))
        self.assertTrue(battlefield_is_midair(drag.source.battlefield, target))
        attack = next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id == actor)
        self.assertIs(attack.weapon_intent.attack_skill, Skill.BRAWN)
        self.assertFalse(attack.weapon_intent.mount_attack)
        self.assertIs(attack.weapon_intent.attack_use.kind, WeaponKind.UNARMED)
        self.assertIs(attack.weapon_intent.brawn_effect, BrawnAttackEffect.DISMOUNT)
        self.assertIsNone(attack.execution.resolution.character_wound)
        self.assertIsNone(attack.execution.resolution.profile_wound)
        # Prone here is the real printed mounted Charge ability, rather than
        # an invented property of dragging. Ground Drag above has no Prone.
        self.assertEqual(attack.execution.resolution.applied_secondary_rule_ids, (PEGASUS_KNIGHTS_RULE_ID,))
        fall, = (step for step in result.steps if type(step.proof) is PcFallingProof)
        self.assertEqual(fall.proof.request.source_dismount, drag.proof)
        self.assertEqual(fall.proof.request.actor_id, target)
        self.assertEqual(fall.proof.request.exposure.rating, 2)
        self.assertTrue(fall.proof.result.avoided)
        self.assertTrue(battlefield_is_midair(fall.source.battlefield, target))
        self.assertFalse(battlefield_is_midair(fall.state.battlefield, target))
        self.assertFalse(pc_is_mounted(fall.state, target))
        self.assertEqual(result.executed_actions, 2)

    def test_crossbow_preparation_keeps_one_real_bonus_against_mounted_target_before_air_drag(self):
        source = npc_air_drag_scene(weapon='crossbow')
        result = run_native(self, source)
        shot = next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id == source.pc_activation_order[0])
        modifiers = tuple(mod for mod in shot.request.kernel_request.attack.impact_spec.damage_modifiers
            if mod.rule_id == 'RULE-EQUIPMENT-004:armoured-target-damage-bonus')
        self.assertEqual(len(modifiers), 1)
        self.assertEqual(modifiers[0].amount, 1)
        self.assertTrue(modifiers[0].armour_specific)
        self.assertFalse(modifiers[0].magical_source)
        self.assertIs(shot.weapon_intent.attack_use.kind, WeaponKind.CROSSBOW)
        self.assertTrue(any(type(step.proof) is PcDismountProof and step.proof.brawn_drag is not None
            for step in result.steps))
        item = result.state.participant(source.pc_activation_order[0]).weapon_inventory.active
        self.assertIs(item.kind, WeaponKind.CROSSBOW)
        self.assertFalse(item.reload.loaded)
        self.assertEqual(len(item.reload.reload_cycle_ids), 1)


if __name__ == '__main__':
    unittest.main()
