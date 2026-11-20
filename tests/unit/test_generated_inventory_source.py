"""Whole generated inventory source, item/grip profiles and strict readmission."""
from tests.support.talent_sources import paid_talent
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from enum import Enum
import pickle
import unittest

from towr.domain.armour_models import ArmourLoadout,BodyArmour,ShieldKind
from towr.domain.generated_npc_models import (
    GeneratedAbility,GeneratedNpc,GeneratedRangedFacts,TalentId,GeneratedWeapon,
    generated_initial_weapon_inventory,generated_npc_profiles,
    generated_weapon_attack_id,generated_weapon_attack_profile,
)
from towr.domain.pc_mount_models import CombatMount
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.test_models import Skill
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_inventory_models import (
    WeaponGrip as G,WeaponItemLocation as L,WeaponItemSource,
    WEAPON_COUNT_BURDEN_RULE_ID,TWO_HANDED_COUNT_BURDEN_RULE_ID,carrying_burden_rule_ids,weapon_unit_id,
)


def item(kind=W.SWORD,*,id='weapon',location=L.HELD,grip=G.LEFT,loaded=None,quantity=1):
    return WeaponItemSource(id,kind,location,grip,quantity,initially_loaded=loaded)


def source(items=None,*,dexterity=4,**changes):
    return GeneratedNpc(3,3,3,3,4,4,(item(),) if items is None else items,
        changes.pop('armour',ArmourLoadout()),defence=4,initiative=changes.pop('initiative',3),dexterity=dexterity,**changes)


def firearm_facts():
    return GeneratedRangedFacts(3, 4,  True, True, True)


class GeneratedInventorySourceTests(unittest.TestCase):
    def test_initial_views_follow_first_held_not_first_carried_and_are_readonly(self):
        npc=source((item(W.PISTOL,id='gun',location=L.CARRIED,grip=None,loaded=False),
            item(W.FOOT_SPEAR,id='spear',grip=G.RIGHT)),ranged=firearm_facts())
        self.assertIs(npc.weapon,GeneratedWeapon.FOOT_SPEAR)
        self.assertIs(npc.weapon_grip,RangedWeaponHands.ONE_HANDED)
        self.assertNotIn('weapon',{field.name for field in fields(npc)})
        self.assertNotIn('weapon_grip',{field.name for field in fields(npc)})
        self.assertNotIn('initially_loaded',{field.name for field in fields(npc.ranged)})
        with self.assertRaises((FrozenInstanceError,TypeError)):
            npc.weapon=GeneratedWeapon.PISTOL
        current=generated_initial_weapon_inventory(npc,'npc')
        self.assertEqual(current.active_item_id,weapon_unit_id('npc','spear',0))
        self.assertEqual(tuple(unit.source_item_id for unit in current.items),('gun','spear'))
        self.assertEqual(pickle.loads(pickle.dumps(npc)),npc)

    def test_source_tuple_membership_subset_and_held_primary_are_exact(self):
        for items in ([],(),(object(),),(item(location=L.CARRIED,grip=None),),
                (item(id='same'),item(W.DAGGER,id='same',location=L.CARRIED,grip=None)),
                (item(W.ROCK),)):
            with self.subTest(items=items),self.assertRaises((TypeError,ValueError)):
                source(items)
        with self.assertRaises(TypeError):
            GeneratedNpc(3,3,3,3,4,4,GeneratedWeapon.SWORD,ArmourLoadout(),defence=4)

    def test_initial_hands_and_actual_shield_are_proved_by_shared_inventory(self):
        for grip,shield_hand in ((G.LEFT,G.RIGHT),(G.RIGHT,G.LEFT)):
            npc=source((item(grip=grip),),armour=ArmourLoadout(shield=ShieldKind.SHIELD))
            current=generated_initial_weapon_inventory(npc,'npc')
            self.assertIs(current.shield_hand,shield_hand)
            self.assertIs(current.active.grip,grip)
        two=(item(),item(W.DAGGER,id='other',grip=G.RIGHT))
        self.assertEqual(len(generated_initial_weapon_inventory(source(two),'npc').items),2)
        for items in (two,(item(W.GLAIVE,grip=G.BOTH),),
                (item(),item(W.DAGGER,id='same-hand'))):
            with self.subTest(items=items),self.assertRaises(ValueError):
                source(items,armour=ArmourLoadout(shield=ShieldKind.SHIELD))

    def test_each_exacting_item_retains_its_own_explicit_charge(self):
        npc=source((item(W.PISTOL,id='left',loaded=True),
            item(W.PISTOL,id='right',grip=G.RIGHT,loaded=False)),ranged=firearm_facts())
        current=generated_initial_weapon_inventory(npc,'npc')
        self.assertEqual(tuple(unit.reload.loaded for unit in current.items),(True,False))
        self.assertEqual(tuple(unit.reload.weapon_instance_id for unit in current.items),
            tuple(unit.id for unit in current.items))
        self.assertEqual(current.items[0].reload.reload_cycle_ids,())
        self.assertEqual(len(current.items[1].reload.reload_cycle_ids),1)
        for invalid in (None,1,'true'):
            with self.subTest(invalid=invalid),self.assertRaises((TypeError,ValueError)):
                item(W.PISTOL,loaded=invalid)

    def test_whole_inventory_requires_reload_and_blackpowder_facts_even_if_carried(self):
        items=(item(),item(W.PISTOL,id='gun',location=L.CARRIED,grip=None,loaded=False))
        self.assertIs(source(items,ranged=firearm_facts()).weapon,GeneratedWeapon.SWORD)
        with self.assertRaises(ValueError):source(items,ranged=firearm_facts(),initiative=None)
        for facts in (None,
                                replace(firearm_facts(),has_blackpowder_kit=None),
                replace(firearm_facts(),has_blackpowder_lore=None)):
            with self.subTest(facts=facts),self.assertRaises((TypeError,ValueError)):
                source(items,ranged=facts)
        with self.assertRaises(ValueError):source(ranged=firearm_facts())
        handbow=(item(W.REPEATER_HANDBOW,loaded=True),)
        with self.assertRaises(ValueError):source(handbow,ranged=firearm_facts())
        self.assertIsNotNone(source(handbow,ranged=GeneratedRangedFacts(3, 4,  True, None, None), initiative=3))

    def test_free_bow_has_no_exacting_dexterity_but_keeps_actual_two_hand_aim(self):
        items=(item(W.SHORTBOW,grip=G.BOTH),)
        facts=GeneratedRangedFacts(3, 4,  True, None, None)
        npc=source(items,ranged=facts,awareness=4,dexterity=None)
        self.assertIsNone(generated_initial_weapon_inventory(npc,'npc').active.reload)
        self.assertEqual(source(items,ranged=facts,dexterity=4,awareness=4).dexterity,4)
        mixed=items+(item(W.PISTOL,id='gun',location=L.CARRIED,grip=None,loaded=True),)
        with self.assertRaises(ValueError):source(items,ranged=facts,awareness=None)
        with self.assertRaises(ValueError):source(items,ranged=facts,initiative=None,awareness=4)
        self.assertIsNotNone(source(mixed,ranged=firearm_facts(),awareness=4))
        with self.assertRaises(ValueError):item(W.SHORTBOW,grip=G.BOTH,loaded=True)

    def test_shooting_and_net_share_ballistic_skill_and_net_requires_throwing(self):
        items=(item(),item(W.PISTOL,id='gun',location=L.CARRIED,grip=None,loaded=True),
            item(W.WEIGHTED_NET,id='net',location=L.CARRIED,grip=None,quantity=2))
        for bs in (None,3):
            npc=source(items,ranged=firearm_facts(),throwing=4,ballistic_skill=bs)
            net=generated_weapon_attack_profile(npc,'net',G.BOTH)
            self.assertIs(net.skill,Skill.THROWING)
            self.assertEqual(net.test_profile.dice,3)
        with self.assertRaises(ValueError):source(items,ranged=firearm_facts(),throwing=4,ballistic_skill=2)
        with self.assertRaises(ValueError):source(items,ranged=firearm_facts())
        with self.assertRaises(ValueError):source(ballistic_skill=3)
        with self.assertRaises(ValueError):source(throwing=4)
        nets=(item(W.WEIGHTED_NET,grip=G.BOTH),)
        with self.assertRaises(ValueError):source(nets,throwing=4)
        self.assertIsNotNone(source(nets,throwing=4,ballistic_skill=3))

    def test_net_units_expand_once_and_carrying_remains_a_real_independent_cause(self):
        npc=source((item(W.WEIGHTED_NET,grip=G.BOTH,quantity=4),),throwing=4,ballistic_skill=3)
        current=generated_initial_weapon_inventory(npc,'npc:with:colons')
        self.assertEqual(tuple(unit.location for unit in current.items),(L.HELD,L.CARRIED,L.CARRIED,L.CARRIED))
        self.assertEqual(tuple(unit.unit_index for unit in current.items),(0,1,2,3))
        self.assertEqual(len({unit.id for unit in current.items}),4)
        self.assertEqual(carrying_burden_rule_ids(current,3),(WEAPON_COUNT_BURDEN_RULE_ID,TWO_HANDED_COUNT_BURDEN_RULE_ID))
        self.assertEqual(len(generated_npc_profiles(npc)[1]),1)

    def test_all_source_item_grip_profiles_retain_distinct_injective_ids(self):
        npc=source((item(id='a:left'),item(id='a',grip=G.RIGHT),
            item(W.GLAIVE,id='glaive',location=L.CARRIED,grip=None)))
        _,profiles,_=generated_npc_profiles(npc)
        self.assertEqual(len(profiles),5)
        self.assertEqual(len({profile.id for profile in profiles}),5)
        for item_id,grips in (('a:left',(G.LEFT,G.RIGHT)),('a',(G.LEFT,G.RIGHT)),('glaive',(G.BOTH,))):
            for grip in grips:
                actual=generated_weapon_attack_profile(npc,item_id,grip)
                self.assertEqual(actual.id,generated_weapon_attack_id(item_id,grip))
                self.assertIn(actual,profiles)
        self.assertNotEqual(generated_weapon_attack_id('a:left',G.RIGHT),generated_weapon_attack_id('a',G.LEFT))

    def test_variable_grips_rederive_damage_without_adding_other_items_damage(self):
        npc=source((item(W.FOOT_SPEAR,id='spear'),
            item(W.POLEARM,id='polearm',location=L.CARRIED,grip=None)))
        self.assertIs(npc.weapon_grip,RangedWeaponHands.ONE_HANDED)
        self.assertEqual(len(generated_npc_profiles(npc)[1]),6)
        for item_id,offset in (('spear',1),('polearm',2)):
            one=generated_weapon_attack_profile(npc,item_id,G.LEFT)
            two=generated_weapon_attack_profile(npc,item_id,G.BOTH)
            self.assertEqual(one.damage.base,3)
            self.assertEqual(two.damage.base,3+offset)
        two_handed=replace(npc,weapons=(replace(npc.weapons[0],initial_grip=G.BOTH),npc.weapons[1]))
        self.assertIs(two_handed.weapon_grip,RangedWeaponHands.TWO_HANDED)

    def test_damage_abilities_never_leak_into_net_condition_profiles(self):
        npc=source((item(W.WEIGHTED_NET,id='net',grip=G.BOTH),
            item(W.SWORD,id='sword',location=L.CARRIED,grip=None)),
            throwing=4,ballistic_skill=3,abilities=(GeneratedAbility.DRAINED_ON_HIT,))
        net=generated_weapon_attack_profile(npc,'net',G.BOTH)
        sword=generated_weapon_attack_profile(npc,'sword',G.RIGHT)
        self.assertIsNone(net.damage)
        self.assertIsNotNone(net.condition_impact)
        self.assertEqual(net.secondary_effects,())
        self.assertEqual(len(sword.secondary_effects),1)

    def test_agilulf_allows_carried_gun_but_not_initial_ranged_attack(self):
        armour=ArmourLoadout((BodyArmour.AGILULF,),BodyArmour.AGILULF)
        gun=item(W.PISTOL,id='gun',location=L.CARRIED,grip=None,loaded=True)
        npc=source((item(),gun),armour=armour,agilulf_code_confirmed=True,ranged=firearm_facts())
        melee=generated_weapon_attack_profile(npc,'weapon',G.LEFT)
        shooting=generated_weapon_attack_profile(npc,'gun',G.RIGHT)
        self.assertEqual((melee.test_profile.dice,melee.test_profile.threshold),(5,5))
        self.assertEqual((shooting.test_profile.dice,shooting.test_profile.threshold),(3,4))
        with self.assertRaises(ValueError):replace(npc,weapons=(replace(gun,initial_location=L.HELD,initial_grip=G.LEFT),))
        with self.assertRaises(ValueError):replace(npc,agilulf_code_confirmed=None)
        horse=source(armour=ArmourLoadout(barding=True),mount=CombatMount.HORSE,
            talents=(paid_talent(TalentId.MAGIC_RESISTANCE),))
        self.assertEqual(horse.participant('npc').definition.resilience.bonus,2)
        self.assertEqual(horse.talents,(paid_talent(TalentId.MAGIC_RESISTANCE),))

    def test_profiles_reject_foreign_items_grips_and_nested_source_forgery(self):
        class Alias(str,Enum):LEFT='left'
        npc=source((item(),item(W.GLAIVE,id='glaive',location=L.CARRIED,grip=None)))
        for identifier,grip in (('other',G.LEFT),('glaive',G.LEFT),('weapon',G.BOTH),
                ('weapon','left'),('weapon',Alias.LEFT),(1,G.LEFT)):
            with self.subTest(identifier=identifier,grip=grip),self.assertRaises((TypeError,ValueError)):
                generated_weapon_attack_profile(npc,identifier,grip)
        forged=deepcopy(source((item(W.PISTOL,loaded=True),),ranged=firearm_facts()))
        object.__setattr__(forged.weapons[0],'initially_loaded',1)
        with self.assertRaises(TypeError):generated_npc_profiles(forged)

    def test_definition_and_available_profiles_are_full_sources_not_primary_id_shortcuts(self):
        npc=source((item(),item(W.DAGGER,id='spare',location=L.CARRIED,grip=None)))
        actor=npc.participant('npc')
        _,profiles,_=generated_npc_profiles(npc)
        self.assertEqual(actor.definition.attacks,profiles)
        self.assertEqual(actor.state.available_attack_ids,tuple(profile.id for profile in profiles))
        self.assertIsNone(actor.state.weapon_inventory)
        changed=replace(profiles[0],id='primary')
        with self.assertRaises(ValueError):replace(actor.definition,attacks=(changed,*profiles[1:]))
        changed=replace(profiles[0],test_profile=replace(profiles[0].test_profile,dice=9))
        with self.assertRaises(ValueError):replace(actor.definition,attacks=(changed,*profiles[1:]))
        with self.assertRaises(ValueError):replace(actor.definition,attacks=profiles[:1])


if __name__=='__main__':unittest.main()
