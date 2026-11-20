"""Whole-inventory actor preparation and unit-owned initial Shooting readiness."""
from dataclasses import fields,replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.application.encounter_inventory import WeaponItem,ItemLocation
from towr.domain.pc_combat_equipment_models import PcWeaponItem,PcItemLocation as L
from towr.domain.pc_melee_models import (
    PcMeleeWeapon as W,PcWeaponHand as H,PcMeleePolicy,PcRangedProfile,
    PcRangedReloadHandPolicy,PcRepeaterBonusPolicy,
)
from towr.domain.npc_roster_models import NpcProtectionProfile
from towr.domain.pc_melee_result_models import PcAttackProof,initial_pc_melee_state
from towr.domain.test_models import InlineProfile,Skill
from towr.domain.weapon_capability_models import weapon_ranged_requirements
from towr.domain.weapon_inventory_models import weapon_unit_id
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


def firearm_facts(*,repeater=False):
    return PcRangedProfile(4, 6,  True, True, True, PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS, repeater_bonus_policy=PcRepeaterBonusPolicy.AUTOMATIC if repeater else None)


def source(items,facts,*,initiative=3,awareness=None,dexterity=5,policy=PcMeleePolicy.AUTOMATIC_COMBAT,opening=False,rounds=1):
    scene=make_pc_melee_scenario(max_rounds=rounds)
    member=scene.party[0]
    primary=next(item for item in items if item.location is L.HELD)
    member=replace(member,pc=replace(member.pc,weapon=primary.weapon,ranged=facts,initiative=initiative,awareness=awareness,dexterity=dexterity,
        weapon_skill=1,melee=2,defence=2,toughness=20,strength=4),
        initial_weapon_hand=primary.hand,policy=policy,combat_equipment=items)
    enemies=tuple(replace(enemy,definition=replace(enemy.definition,
        protection=(NpcProtectionProfile('fixture:athletics',Skill.ATHLETICS,InlineProfile(2,4)),)))
        for enemy in scene.enemies)
    options={}
    if opening:
        from towr.domain.pc_battlefield_models import PcBattlefieldSpec
        from towr.domain.ranged_weapon_profiles import RangedWeaponRange
        options=dict(facts=replace(scene.facts,all_opponents_close=False,can_leave_zone=True),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT,RangedWeaponRange.LONG))
    return replace(scene,party=(member,),enemies=enemies,**options)


class ConstantTen:
    def randint(self,low,high):
        if (low,high)!=(1,10):raise AssertionError('unexpected die range')
        return 10


class PcInventorySourceContractTests(unittest.TestCase):
    def test_manual_two_handed_melee_backup_ignores_an_unused_loaded_firearm(self):
        from tests.support.pc_melee_scripted import ScriptedD10
        from tests.unit.test_m12_pc_heavy_wounds import heavy_prefix
        from towr.domain.pc_melee_models import PcBackupWeaponPolicy,PcTwoHandedGrip
        from towr.domain.pc_melee_result_models import PcBackupWeaponDrawProof
        from towr.domain.pc_ranged_models import PcRangedReloadProof
        scene=make_pc_melee_scenario(weapon=W.PICKAXE,enemy_count=5,max_rounds=2)
        member=scene.party[0]
        items=(PcWeaponItem('pick',W.PICKAXE,L.HELD,PcTwoHandedGrip.BOTH),
            PcWeaponItem('spare',W.SWORD,L.CARRIED,None),
            PcWeaponItem('unused-gun',W.PISTOL,L.CARRIED,None,initially_loaded=True))
        member=replace(member,pc=replace(member.pc,ranged=firearm_facts()),
            combat_equipment=items,backup_weapon_policy=PcBackupWeaponPolicy(W.SWORD,H.LEFT))
        enemies=tuple(replace(enemy,definition=replace(enemy.definition,
            protection=(replace(enemy.definition.protection[0],skill=Skill.ATHLETICS),)))
            for enemy in scene.enemies)
        scene=replace(scene,party=(member,),enemies=enemies)
        rng=ScriptedD10([1]*3+[10]*2+heavy_prefix(16)[5:]
            +[10]*3+[1]*3+[1]*3+[10]*2+[1]*3+[10,10,10,1,1,1,1]*3)
        result=run_pc_melee_scenario(scene,rng)
        rng.assert_exhausted()
        self.assertIsNone(result.unsupported)
        self.assertEqual(sum(type(step.proof) is PcBackupWeaponDrawProof for step in result.steps),1)
        self.assertFalse(any(type(step.proof) is PcRangedReloadProof for step in result.steps))
        inventory=result.state.participant('pc').weapon_inventory
        self.assertEqual(inventory.active.source_item_id,'spare')
        self.assertEqual(inventory.active.grip.value,'right')
        self.assertTrue(inventory.item(weapon_unit_id('pc','unused-gun',0)).reload.loaded)

    def test_manual_melee_action_ignores_a_carried_pistols_charge(self):
        from towr.domain.pc_ranged_models import PcRangedReloadProof
        for loaded in (False,True):
            with self.subTest(loaded=loaded):
                items=(PcWeaponItem('sword',W.SWORD,L.HELD,H.LEFT),
                    PcWeaponItem('gun',W.PISTOL,L.CARRIED,None,initially_loaded=loaded))
                scene=source(items,firearm_facts(),policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF)
                result=run_pc_melee_scenario(scene,ConstantTen())
                self.assertIsNone(result.unsupported)
                self.assertTrue(any(type(step.proof) is PcAttackProof
                    and step.proof.request.actor_id=='pc' for step in result.steps))
                self.assertFalse(any(type(step.proof) is PcRangedReloadProof for step in result.steps))
                inventory=result.state.participant('pc').weapon_inventory
                self.assertEqual(inventory.active.source_item_id,'sword')
                gun=inventory.item(weapon_unit_id('pc','gun',0))
                self.assertEqual(gun.location,L.CARRIED)
                self.assertIs(gun.reload.loaded,loaded)

    def test_carried_bow_does_not_offer_an_illegal_shot_in_a_stationary_close_scene(self):
        items=(PcWeaponItem('sword',W.SWORD,L.HELD,H.LEFT),
            PcWeaponItem('bow',W.SHORTBOW,L.CARRIED,None))
        facts=PcRangedProfile(5,6,ammunition_supply_confirmed=True)
        scene=source(items,facts)
        result=run_pc_melee_scenario(scene,ConstantTen())
        self.assertIsNone(result.unsupported)
        self.assertEqual(result.state.participant('pc').weapon_inventory.active.source_item_id,'sword')
        self.assertTrue(any(type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc' for step in result.steps))
        self.assertFalse(any(type(step.proof).__name__=='PcRangedShotProof' for step in result.steps))

    def test_actor_preparation_has_no_shared_initial_charge(self):
        self.assertNotIn('initially_loaded',{f.name for f in fields(PcRangedProfile)})
        with self.assertRaises(TypeError):
            PcRangedProfile(3,4,initially_loaded=True)

    def test_every_exacting_item_needs_its_own_exact_initial_bool(self):
        for kind in (W.PISTOL,W.REPEATER_HANDBOW,W.CROSSBOW,W.HANDGUN):
            for loaded in (True,False):
                with self.subTest(kind=kind,loaded=loaded):
                    self.assertIs(PcWeaponItem('gun',kind,L.CARRIED,None,
                        initially_loaded=loaded).initially_loaded,loaded)
                    self.assertIs(WeaponItem('gun',kind,ItemLocation.CARRIED,
                        initially_loaded=loaded).initially_loaded,loaded)
            for bad in (None,0,1,'true'):
                with self.subTest(kind=kind,bad=bad),self.assertRaises((TypeError,ValueError)):
                    PcWeaponItem('gun',kind,L.CARRIED,None,initially_loaded=bad)
        with self.assertRaises(ValueError):
            PcWeaponItem('sword',W.SWORD,L.HELD,H.LEFT,initially_loaded=False)

    def test_melee_primary_and_carried_empty_pistol_have_complete_shared_actor_facts(self):
        items=(PcWeaponItem('sword',W.SWORD,L.HELD,H.LEFT),
            PcWeaponItem('gun',W.PISTOL,L.CARRIED,None,initially_loaded=False))
        scene=source(items,firearm_facts())
        member=initial_pc_melee_state(scene).participant('pc')
        self.assertEqual(member.weapon_inventory.active.source_item_id,'sword')
        gun=member.weapon_inventory.item(weapon_unit_id('pc','gun',0))
        self.assertFalse(gun.reload.loaded)
        self.assertEqual(gun.reload.exacting.contributions,())
        self.assertEqual(scene.party[0].pc.weapon,W.SWORD)
        with self.assertRaises((TypeError,ValueError)):
            source(items,None)

    def test_bow_primary_and_carried_firearm_require_the_union_of_preparation(self):
        from towr.domain.pc_melee_models import PcTwoHandedGrip
        items=(PcWeaponItem('bow',W.SHORTBOW,L.HELD,PcTwoHandedGrip.BOTH),
            PcWeaponItem('gun',W.PISTOL,L.CARRIED,None,initially_loaded=True))
        member=source(items,firearm_facts(),opening=True).party[0]
        self.assertEqual(member.pc.dexterity,5)
        free=PcRangedProfile(4,6,ammunition_supply_confirmed=True)
        with self.assertRaises(ValueError):source(items,free)

    def test_pistol_and_repeater_handbow_share_facts_without_sharing_readiness(self):
        items=(PcWeaponItem('gun',W.PISTOL,L.HELD,H.LEFT,initially_loaded=False),
            PcWeaponItem('handbow',W.REPEATER_HANDBOW,L.HELD,H.RIGHT,initially_loaded=True))
        scene=source(items,firearm_facts(repeater=True))
        inventory=initial_pc_melee_state(scene).participant('pc').weapon_inventory
        self.assertEqual(tuple(item.reload.loaded for item in inventory.items),(False,True))
        with self.assertRaises((TypeError,ValueError)):source(items,firearm_facts())
        with self.assertRaises(ValueError):source((items[0],),firearm_facts(repeater=True))

    def test_manual_shooter_also_requires_items_and_can_begin_empty(self):
        items=(PcWeaponItem('gun',W.PISTOL,L.HELD,H.LEFT,initially_loaded=False),)
        member=source(items,firearm_facts(),policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF).party[0]
        with self.assertRaises(ValueError):replace(member,combat_equipment=None)
        inventory=initial_pc_melee_state(source(items,firearm_facts(),
            policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF)).participant('pc').weapon_inventory
        self.assertFalse(inventory.active.reload.loaded)

    def test_requirement_union_uses_traits_and_does_not_make_catalog_presence_executable(self):
        requirements=weapon_ranged_requirements((W.SWORD,W.DRAGON_BOW,W.PISTOL,W.REPEATER_HANDBOW))
        self.assertEqual(requirements.weapon_kinds,(W.DRAGON_BOW,W.PISTOL,W.REPEATER_HANDBOW))
        self.assertTrue(requirements.exacting)
        self.assertTrue(requirements.firearm)
        self.assertTrue(requirements.repeater)
        self.assertFalse(requirements.requires_aim)
        self.assertTrue(weapon_ranged_requirements((W.HOCHLAND_LONG_RIFLE,)).requires_aim)
        with self.assertRaises(ValueError):
            source((PcWeaponItem('dragon',W.DRAGON_BOW,L.CARRIED,None),
                PcWeaponItem('sword',W.SWORD,L.HELD,H.LEFT)),firearm_facts())

    def test_native_melee_primary_can_draw_and_fire_its_carried_pistol(self):
        scene=source((PcWeaponItem('sword',W.SWORD,L.HELD,H.LEFT),
            PcWeaponItem('gun',W.PISTOL,L.CARRIED,None,initially_loaded=True)),firearm_facts())
        result=run_pc_melee_scenario(scene,ConstantTen())
        self.assertIsNone(result.unsupported)
        shot,=(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc')
        self.assertIsNotNone(shot.proof.ranged_shot)
        self.assertEqual(shot.proof.ranged_shot.execution.weapon_state.weapon_instance_id,
            weapon_unit_id('pc','gun',0))
        self.assertFalse(result.state.participant('pc').weapon_inventory.active.reload.loaded)
        replay=initial_pc_melee_state(scene)
        for step in result.steps:replay=apply_pc_melee_step(replay,step)
        self.assertEqual(replay,result.state)

    def test_carried_firearm_cannot_bypass_agilulf_chivalric_attack_restriction(self):
        from towr.domain.armour_models import ArmourLoadout,BodyArmour
        from towr.domain.pc_weapon_inventory import pc_weapon_inventory_view,pc_attack_weapon_use
        scene=source((PcWeaponItem('sword',W.SWORD,L.HELD,H.LEFT),
            PcWeaponItem('gun',W.PISTOL,L.CARRIED,None,initially_loaded=True)),firearm_facts())
        member=scene.party[0]
        armour=ArmourLoadout(body=(BodyArmour.AGILULF,),benefit=BodyArmour.AGILULF)
        member=replace(member,pc=replace(member.pc,armour_bonus=2),armour=armour,
            armour_worn=True,agilulf_code_confirmed=True)
        state=initial_pc_melee_state(replace(scene,party=(member,)))
        view=pc_weapon_inventory_view(state,'pc',weapon_unit_id('pc','gun',0))
        self.assertIsNotNone(view)
        self.assertIsNone(pc_attack_weapon_use(view,'pc','minion1'))

    def test_fixed_reload_stows_other_ready_gun_without_spending_its_charge(self):
        from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
        from towr.domain.pc_ranged_models import PcRangedReloadProof
        scene=source((PcWeaponItem('left',W.PISTOL,L.HELD,H.LEFT,initially_loaded=True),
            PcWeaponItem('right',W.PISTOL,L.HELD,H.RIGHT,initially_loaded=True)),firearm_facts(),
            policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF,rounds=3)
        result=run_pc_melee_scenario(scene,ConstantTen())
        self.assertIsNone(result.unsupported)
        swap,=(step for step in result.steps if type(step.proof) is PcWeaponSwapProof)
        reloads=tuple(step for step in result.steps if type(step.proof) is PcRangedReloadProof)
        self.assertEqual(len(reloads),2)
        self.assertEqual(swap.proof.intent.reason,'prepare_fixed_reload_hands')
        for reload in reloads:
            other=reload.state.participant('pc').weapon_inventory.item(weapon_unit_id('pc','right',0))
            self.assertIs(other.location,L.CARRIED)
            self.assertTrue(other.reload.loaded)
            self.assertEqual(other.reload.reload_cycle_ids,())
            self.assertEqual(reload.proof.result.previous_state.weapon_instance_id,weapon_unit_id('pc','left',0))
        replay=initial_pc_melee_state(scene)
        for step in result.steps:replay=apply_pc_melee_step(replay,step)
        self.assertEqual(replay,result.state)

    def test_automatic_bow_to_melee_uses_actual_single_hand_without_a_fixed_backup_policy(self):
        from towr.domain.pc_melee_models import PcTwoHandedGrip
        from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
        scene=source((PcWeaponItem('bow',W.SHORTBOW,L.HELD,PcTwoHandedGrip.BOTH),
            PcWeaponItem('sword',W.SWORD,L.CARRIED,None)),
            PcRangedProfile(1,2,ammunition_supply_confirmed=True),opening=True,rounds=3)
        member=scene.party[0]
        scene=replace(scene,party=(replace(member,pc=replace(member.pc,weapon_skill=5,melee=6)),))
        self.assertIsNone(scene.party[0].backup_weapon_policy)
        result=run_pc_melee_scenario(scene,ConstantTen())
        self.assertIsNone(result.unsupported)
        draws=tuple(step for step in result.steps if type(step.proof) is PcWeaponSwapProof
            and step.proof.state.active.kind is W.SWORD)
        self.assertTrue(draws)
        self.assertIn(draws[0].state.participant('pc').weapon_hand,(H.LEFT,H.RIGHT))
        sword_attacks=tuple(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc'
            and step.source.participant('pc').weapon_inventory.active.kind is W.SWORD)
        self.assertTrue(sword_attacks)
        replay=initial_pc_melee_state(scene)
        for step in result.steps:replay=apply_pc_melee_step(replay,step)
        self.assertEqual(replay,result.state)


if __name__=='__main__':unittest.main()
