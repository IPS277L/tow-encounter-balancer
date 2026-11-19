"""Real finite item effects in both roles, with native source and step replay."""
from dataclasses import replace
import unittest

from tests.support.magic_weapon_battles import magic_battle,run_native,Threes
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_magic_weapon_models import PcScarabChargeProof
from towr.domain.weapon_inventory_models import WeaponItemLocation


class MagicWeaponEffectsTests(unittest.TestCase):
    def test_scarab_hit_without_wound_drains_without_a_charge_in_both_roles(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                source=magic_battle('scarab_knife',npc_magic=npc,pc_ws=6,
                    npc_ws=3 if npc else 1)
                if npc:
                    member=source.party[0]
                    source=replace(source,party=(replace(member,pc=replace(member.pc,
                        defence=1,athletics=1)),))
                result=run_native(self,source)
                actor='generated-npc:1' if npc else 'pc'
                attack=next(step.proof for step in result.steps
                    if type(step.proof) is PcAttackProof and step.proof.request.actor_id==actor)
                self.assertTrue(attack.execution.resolution.target_state.conditions.has(Condition.DRAINED))
                self.assertIsNone(attack.execution.resolution.character_wound)
                self.assertIsNone(attack.execution.resolution.profile_wound)
                inventory=(result.state.enemy(actor).state.weapon_inventory if npc
                    else result.state.participant(actor).weapon_inventory)
                self.assertEqual(inventory.items[0].charges,0)

    def test_scarab_actual_wound_charges_once_after_character_fate_window(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                source=magic_battle('scarab_knife',npc_magic=npc,pc_ws=1 if npc else 6,
                    npc_ws=6 if npc else 1,pc_toughness=1 if npc else 20,npc_toughness=20 if npc else 1)
                result=run_native(self,source)
                actor='generated-npc:1' if npc else 'pc'
                inventory=(result.state.enemy(actor).state.weapon_inventory if npc
                    else result.state.participant(actor).weapon_inventory)
                self.assertEqual(inventory.items[0].charges,1)
                charges=[step.proof for step in result.steps if type(step.proof) is PcScarabChargeProof]
                self.assertEqual(len(charges),int(npc))
                if npc:
                    proof=charges[0]
                    with self.assertRaises(ValueError):
                        from towr.domain.pc_magic_weapon_models import project_scarab_charge
                        project_scarab_charge(result.state,proof)

    def test_fracasse_disarms_one_actual_magic_item_and_paid_recover_returns_it(self):
        source=magic_battle('trickster_blade',npc_magic=True,
            pc_weapon='morning_star_of_fracasse',pc_ws=6,npc_ws=1)
        result=run_native(self,source)
        attack=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc')
        self.assertEqual(len(attack.proof.magic_weapon.drops),1)
        fallen=attack.state.enemy('generated-npc:1').state.weapon_inventory.items[0]
        self.assertIs(fallen.location,WeaponItemLocation.DROPPED)
        self.assertEqual(attack.state.briarroot_dropped_weapons[0].weapon_id,fallen.id)
        returned=result.state.enemy('generated-npc:1').state.weapon_inventory.items[0]
        self.assertEqual(returned.source,fallen.source)
        self.assertIs(returned.location,WeaponItemLocation.HELD)
        self.assertEqual(result.executed_actions,2)

    def test_dragon_fire_is_real_once_per_battle_resource_and_hazard(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                source=magic_battle('dragon_bow',npc_magic=npc,distance='medium',
                    pc_weapon='pistol' if npc else None,pc_ws=1 if npc else 6,npc_ws=6 if npc else 1)
                result=run_native(self,source)
                actor='generated-npc:1' if npc else 'pc'
                attack=next(step.proof for step in result.steps
                    if type(step.proof) is PcAttackProof and step.proof.request.actor_id==actor)
                self.assertTrue(attack.weapon_intent.dragon_fire)
                self.assertTrue(attack.magic_weapon.after_inventory.active.dragon_arrow_used)
                self.assertFalse(any(mod.amount<0 for mod in attack.request.kernel_request.attack.attacker_test.dice_modifiers))
                self.assertTrue(attack.execution.resolution.target_state.conditions.has(Condition.ABLAZE))

    def test_ogre_pistol_uses_holder_shooting_reload_and_fit(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                source=magic_battle('ogre_pistol',npc_magic=npc,rounds=3,
                    pc_ws=1 if npc else 6,npc_ws=6 if npc else 1)
                result=run_native(self,source)
                actor='generated-npc:1' if npc else 'pc'
                attack=next(step.proof for step in result.steps
                    if type(step.proof) is PcAttackProof and step.proof.request.actor_id==actor)
                spec=attack.request.kernel_request.attack.impact_spec
                self.assertEqual(spec.damage.base,5)
                self.assertTrue(spec.ignores_armour)
                self.assertEqual(attack.weapon_intent.attack_use.primary.source.gm_fit_confirmed,True)
                inventory=(result.state.enemy(actor).state.weapon_inventory if npc
                    else result.state.participant(actor).weapon_inventory)
                self.assertGreaterEqual(len(inventory.items[0].reload.reload_cycle_ids),1)


if __name__=='__main__':
    unittest.main()
