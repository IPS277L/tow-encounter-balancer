"""Prepared explicit held-weapon strikes, with no fake combat action slots."""
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.generated_weapon_sources import initial_generated_weapons
from towr.domain.armour_models import ArmourLoadout
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.pc_melee_result_models import initial_pc_melee_state,prepare_pc_weapon_kernel
from towr.domain.pc_weapon_inventory import pc_weapon_inventory_view
from towr.domain.pc_npc_weapon_inventory import _NpcInventoryView
from towr.domain.pc_weapon_intent_models import build_pc_explicit_attack_weapon_intent
from towr.domain.weapon_use_models import build_weapon_use
from towr.domain.test_models import Skill
from towr.domain.attack_models import DamageImpactSpec


class ExplicitWeaponKernelTests(unittest.TestCase):
    def test_prepared_pc_can_use_a_real_held_weapon_independently_of_unarmed_active_choice(self):
        source=make_pc_melee_scenario(max_rounds=1)
        member=replace(source.party[0],pc=replace(source.party[0].pc,brawn=4))
        state=initial_pc_melee_state(replace(source,party=(member,)))
        # The existing tactical view selects Unarmed without moving the held
        # Staff. This is a preparation boundary, not a fabricated full journal.
        view=pc_weapon_inventory_view(state,'pc',None)
        inventory=view.participant('pc').weapon_inventory
        self.assertIsNone(inventory.active_item_id)
        use=build_weapon_use('pc',inventory,inventory.items[0].id)
        self.assertIs(use.skill,Skill.MELEE)
        action='prepared:pc:immediate'
        intent=build_pc_explicit_attack_weapon_intent(view,'pc','minion1',action,weapon_use=use)
        kernel,protection=prepare_pc_weapon_kernel(view,intent,action)
        self.assertEqual(kernel.attack.attacker_test.profile,member.pc.melee_profile)
        self.assertIs(type(kernel.attack.impact_spec),DamageImpactSpec)
        self.assertEqual(kernel.attack.impact_spec.damage.base,member.pc.strength)
        self.assertIs(protection.attack_skill,Skill.MELEE)
        self.assertEqual(view.round_state,state.round_state)
        self.assertIsNone(state.round_state.active_turn)
        with self.assertRaises(ValueError):prepare_pc_weapon_kernel(view,intent,'foreign:action')

    def test_prepared_generated_npc_uses_the_selected_melee_profile_instead_of_its_active_brawn(self):
        source=make_pc_melee_scenario(max_rounds=1)
        npc=GeneratedNpc(3,3,20,2,5,4,initial_generated_weapons(GeneratedWeapon.SWORD),
            ArmourLoadout(),defence=4,brawn=2)
        state=initial_pc_melee_state(replace(source,enemies=(npc.participant('minion1'),)))
        enemy=state.enemy('minion1')
        inventory=replace(enemy.state.weapon_inventory,active_item_id=None)
        view=_NpcInventoryView(state,(replace(enemy,state=replace(enemy.state,weapon_inventory=inventory)),))
        use=build_weapon_use('minion1',inventory,inventory.items[0].id)
        action='prepared:npc:immediate'
        intent=build_pc_explicit_attack_weapon_intent(view,'minion1','pc',action,weapon_use=use)
        kernel,protection=prepare_pc_weapon_kernel(view,intent,action)
        self.assertEqual((kernel.attack.attacker_test.profile.base_dice,
            kernel.attack.attacker_test.profile.threshold),(3,5))
        self.assertIs(protection.attack_skill,Skill.MELEE)
        self.assertIs(type(kernel.attack.impact_spec),DamageImpactSpec)
        self.assertEqual(view.round_state,state.round_state)
        self.assertIsNone(state.round_state.active_turn)


if __name__=='__main__':unittest.main()
