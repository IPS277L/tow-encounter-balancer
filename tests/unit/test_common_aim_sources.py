"""Aim source eligibility is separate from loaded Shooting/Reload readiness."""
from dataclasses import replace
from unittest import TestCase

from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from tests.support.pc_hochland_scenarios import make_pc_hochland_scenario
from tests.support.pc_shield_scenarios import shield_loadout
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.unit.test_pc_npc_aim import source as npc_source
from towr.domain.armour_models import ArmourLoadout, ShieldKind
from towr.domain.generated_npc_models import GeneratedWeapon
from towr.domain.pc_aim_source_models import actor_can_aim, actor_awareness_profile
from towr.domain.pc_melee_models import PcMeleePolicy, PcWeaponHand
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.ranged_weapon_profiles import RangedWeaponRange


class CommonAimSourceTests(TestCase):
    def test_player_close_pistol_shield_and_unloaded_inventory_can_aim(self):
        source=make_pc_pistol_scenario()
        member=source.party[0]
        member=replace(member,pc=replace(member.pc,awareness=4),shield=shield_loadout(PcWeaponHand.RIGHT),
            combat_equipment=tuple(replace(item,initially_loaded=False) for item in member.combat_equipment))
        state=initial_pc_melee_state(replace(source,party=(member,)))
        self.assertFalse(state.party[0].ranged.loaded)
        self.assertTrue(actor_can_aim(state,member.actor_id))
        self.assertEqual(actor_awareness_profile(state,member.actor_id),member.pc.awareness_profile)

    def test_generated_close_pistol_shield_and_unloaded_inventory_can_aim(self):
        source=npc_source(distance=RangedWeaponRange.CLOSE)
        npc=source.enemies[0].definition.generated_components
        npc=replace(npc,armour=ArmourLoadout(shield=ShieldKind.SHIELD),
            weapons=initial_generated_weapons(GeneratedWeapon.PISTOL,initially_loaded=False))
        state=initial_pc_melee_state(replace(source,enemies=(npc.participant('minion1'),)))
        self.assertTrue(state.enemies[0].state.holds_shield)
        self.assertTrue(actor_can_aim(state,'minion1'))
        self.assertEqual(actor_awareness_profile(state,'minion1').maximum_dice,2*npc.initiative)

    def test_a_close_enemy_still_blocks_a_non_close_shooting_implement(self):
        source=make_pc_hochland_scenario(use_second_action=False)
        member=replace(source.party[0],policy=PcMeleePolicy.AUTOMATIC_COMBAT)
        source=replace(source,party=(member,),short_range_opening=None,
            battlefield=PcBattlefieldSpec(RangedWeaponRange.CLOSE,RangedWeaponRange.LONG),
            facts=replace(source.facts,all_opponents_close=True,can_leave_zone=True))
        self.assertFalse(actor_can_aim(initial_pc_melee_state(source),member.actor_id))
