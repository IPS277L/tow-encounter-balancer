"""Scene facts consumed by real movement and attacks, with native replay."""
from dataclasses import replace
import unittest

from tests.support.magic_weapon_battles import magic_battle,run_native
from towr.domain.pc_terrain_models import PcTerrainTraversalProof
from towr.domain.pc_battlefield_manoeuvre_models import PcBattlefieldCarefulProof
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_scene_feature_models import PcZoneFeatures,PcVisibilityFact,SCENE_COVER_RULE_ID
from towr.domain.weapon_effect_preparation import STAFF_TERRAIN_RULE_ID
from towr.domain.test_models import TestQuality


class SceneFeatureNativeTests(unittest.TestCase):
    def test_low_athletics_selects_real_move_carefully_for_both_roles(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                source=magic_battle('staff',npc_magic=npc,pc_weapon='warbow' if npc else None,distance='medium')
                actor='generated-npc:1' if npc else 'pc'
                if npc:
                    opponent=replace(source.enemies[0].definition.generated_components,agility=2,athletics=2)
                    source=replace(source,enemies=(opponent.participant(actor),))
                else:
                    member=source.party[0]
                    source=replace(source,party=(replace(member,pc=replace(member.pc,agility=2,athletics=2)),))
                # Ag2 + the actual Staff gives 3d/2: P(no successes)=0.8**3=0.512.
                source=replace(source,battlefield=replace(source.battlefield,
                    zone_features=(PcZoneFeatures(0,difficult_terrain=True),PcZoneFeatures(1,difficult_terrain=True))))
                result=run_native(self,source)
                careful=[step for step in result.steps if type(step.proof) is PcBattlefieldCarefulProof
                    and step.proof.actor_id==actor]
                self.assertEqual(len(careful),1)
                step=careful[0]
                self.assertTrue(step.state.round_state.active_turn.action_slots[-1].executed)
                self.assertIn(actor,step.state.battlefield.spatial.free_move_used_entity_ids)
                self.assertNotIn(actor,step.state.battlefield.spatial.difficult_terrain_tested_entity_ids)
                self.assertIsNone(step.proof.result.awareness_test_result)
                self.assertFalse(any(type(item.proof) is PcTerrainTraversalProof
                    and item.proof.request.actor_id==actor for item in result.steps))
                self.assertEqual(result.executed_actions,2)

    def test_actual_staff_terrain_crossing_in_both_roles_uses_one_test_and_no_extra_action(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                source=magic_battle('staff',npc_magic=npc,pc_weapon='pistol' if npc else None,distance='short')
                source=replace(source,battlefield=replace(source.battlefield,
                    zone_features=(PcZoneFeatures(0,difficult_terrain=True),)))
                result=run_native(self,source)
                actor='generated-npc:1' if npc else 'pc'
                crossing=[step for step in result.steps if type(step.proof) is PcTerrainTraversalProof
                    and step.proof.request.actor_id==actor]
                self.assertEqual(len(crossing),1)
                proof=crossing[0].proof
                self.assertIsNotNone(proof.request.staff_use)
                self.assertEqual([m.amount for m in proof.request.athletics_test.dice_modifiers
                    if m.rule_id==STAFF_TERRAIN_RULE_ID],[1])
                self.assertIn(actor,proof.result.state.difficult_terrain_tested_entity_ids)
                self.assertEqual(proof.request.previous.spatial.placements,proof.result.state.placements)
                self.assertEqual(crossing[0].source.round_state,crossing[0].state.round_state)

    def test_dragon_removes_cover_penalty_while_pistol_retains_it(self):
        for weapon in ('dragon_bow','pistol'):
            with self.subTest(weapon=weapon):
                source=magic_battle(weapon,distance='medium')
                source=replace(source,battlefield=replace(source.battlefield,
                    zone_features=(PcZoneFeatures(1,cover=True,concealment=True),)))
                result=run_native(self,source)
                shot=next(step.proof for step in result.steps
                    if type(step.proof) is PcAttackProof and step.proof.request.actor_id=='pc')
                modifiers=[m.amount for m in shot.request.kernel_request.attack.attacker_test.dice_modifiers
                    if m.rule_id==SCENE_COVER_RULE_ID]
                self.assertEqual(modifiers,[] if weapon=='dragon_bow' else [-1])

    def test_unseen_pistol_is_grim_and_dragon_never_attacks_an_unseen_target(self):
        for weapon in ('pistol','dragon_bow'):
            with self.subTest(weapon=weapon):
                source=magic_battle(weapon,distance='medium')
                source=replace(source,battlefield=replace(source.battlefield,
                    visibility=(PcVisibilityFact('pc','generated-npc:1',False),)))
                result=run_native(self,source)
                shots=[step.proof for step in result.steps
                    if type(step.proof) is PcAttackProof and step.proof.request.actor_id=='pc']
                if weapon=='dragon_bow':
                    self.assertFalse(shots)
                    self.assertFalse(result.state.participant('pc').weapon_inventory.items[0].dragon_arrow_used)
                else:
                    self.assertTrue(shots)
                    self.assertIs(shots[0].execution.resolution.attack.attacker_test.trace.quality,TestQuality.GRIM)


if __name__=='__main__':
    unittest.main()
