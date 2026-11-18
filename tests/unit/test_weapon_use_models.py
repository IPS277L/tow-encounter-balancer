"""Actual selected implements, distinct hands and immutable Test sources."""
from dataclasses import FrozenInstanceError, replace
import unittest

from towr.domain.test_models import Skill
from towr.domain.weapon_catalog import WeaponKind as W, weapon_printed_damage, weapon_profile
from towr.domain.weapon_inventory_models import (
    WeaponGrip as G, WeaponInventoryState, WeaponItemLocation as L,
    WeaponItemSource, initial_weapon_inventory,
)
from towr.domain.weapon_use_models import (
    WeaponProtectionUse, WeaponUse, build_weapon_protection_use, build_weapon_use,
)


def item(identifier,kind,grip,**kwargs):
    return WeaponItemSource(identifier,kind,L.HELD,grip,**kwargs)


def paired(left=W.SWORD,right=W.WARHAMMER,*,origin='pc',left_facts=None,right_facts=None):
    return initial_weapon_inventory(origin,(
        item('left',left,G.LEFT,**(left_facts or {})),
        item('right',right,G.RIGHT,**(right_facts or {}))))


class WeaponUseModelsTests(unittest.TestCase):
    def test_unarmed_is_a_brawn_source_without_physical_items_or_required_hands(self):
        inventory=WeaponInventoryState()
        use=build_weapon_use('pc',inventory,None,usable_hands=())
        self.assertIs(type(use),WeaponUse)
        self.assertIs(use.kind,W.UNARMED)
        self.assertIs(use.skill,Skill.BRAWN)
        self.assertIsNone(use.primary)
        self.assertIsNone(use.primary_grip)
        self.assertIs(use.primary_profile,weapon_profile(W.UNARMED))
        self.assertEqual((use.contributors,use.item_ids,use.used_hands),((),(),()))
        held=paired()
        self.assertEqual(build_weapon_use('pc',held,None,usable_hands=()).used_hands,())

    def test_explicit_primary_is_used_without_selecting_from_active_item(self):
        inventory=paired()
        left,right=inventory.items
        self.assertIsNone(inventory.active_item_id)
        use=build_weapon_use('pc',inventory,right.id)
        self.assertIs(use.primary,right)
        self.assertIs(use.kind,W.WARHAMMER)
        self.assertIs(use.skill,Skill.MELEE)
        self.assertEqual(use.item_ids,(right.id,))
        self.assertEqual(use.primary_grip,G.RIGHT)
        self.assertEqual(use.used_hands,(G.RIGHT,))
        selected=replace(inventory,active_item_id=left.id)
        self.assertIs(build_weapon_use('pc',selected,right.id).kind,W.WARHAMMER)
        self.assertIs(build_weapon_use('pc',selected,None).kind,W.UNARMED)

    def test_two_swords_and_different_mixed_melee_items_retain_individual_sources(self):
        inventory=paired(W.SWORD,W.SWORD)
        left,right=inventory.items
        use=build_weapon_use('pc',inventory,right.id,(left.id,),usable_hands=(G.RIGHT,G.LEFT))
        self.assertEqual(use.item_ids,(right.id,left.id))
        self.assertEqual(use.contributors,(left,))
        self.assertEqual(use.used_hands,(G.LEFT,G.RIGHT))
        self.assertIs(use.primary_profile,weapon_profile(W.SWORD))
        mixed=paired(W.DAGGER,W.MORNING_STAR_OF_FRACASSE)
        use=build_weapon_use('pc',mixed,mixed.items[0].id,(mixed.items[1].id,))
        self.assertIs(use.kind,W.DAGGER)
        self.assertEqual(use.primary_profile.damage_value,-1)
        self.assertEqual(weapon_printed_damage(use.kind,strength=4),3)
        reverse=build_weapon_use('pc',mixed,mixed.items[1].id,(mixed.items[0].id,))
        self.assertIs(reverse.kind,W.MORNING_STAR_OF_FRACASSE)
        self.assertEqual(reverse.primary_profile.damage_value,3)
        self.assertEqual(weapon_printed_damage(reverse.kind,strength=4),7)

    def test_knuckledusters_keep_the_primary_brawn_skill_when_a_sword_contributes(self):
        inventory=paired(W.KNUCKLEDUSTERS,W.SWORD)
        use=build_weapon_use('pc',inventory,inventory.items[0].id,(inventory.items[1].id,))
        self.assertIs(use.kind,W.KNUCKLEDUSTERS)
        self.assertIs(use.skill,Skill.BRAWN)
        self.assertEqual(use.primary_profile.damage_value,-1)

    def test_two_hand_and_variable_grips_use_every_actual_required_hand(self):
        for kind in (W.GLAIVE,W.FOOT_SPEAR,W.DUELLIST_BLADES):
            with self.subTest(kind=kind):
                inventory=initial_weapon_inventory('pc',(item('held',kind,G.BOTH),))
                use=build_weapon_use('pc',inventory,inventory.items[0].id)
                self.assertIs(use.primary_grip,G.BOTH)
                self.assertEqual(use.used_hands,(G.LEFT,G.RIGHT))
                with self.assertRaises(ValueError):build_weapon_use('pc',inventory,inventory.items[0].id,usable_hands=(G.LEFT,))
        inventory=initial_weapon_inventory('pc',(item('spear',W.FOOT_SPEAR,G.RIGHT),))
        self.assertEqual(build_weapon_use('pc',inventory,inventory.items[0].id,usable_hands=(G.RIGHT,)).used_hands,(G.RIGHT,))

    def test_single_shooting_or_throwing_items_are_valid_sources_without_combined_attacks(self):
        for kind,facts in ((W.PISTOL,dict(initially_loaded=True)),(W.SLING,{}),
                (W.THROWING_AXE,{}),(W.ROCK,{})):
            with self.subTest(kind=kind):
                inventory=initial_weapon_inventory('pc',(item('held',kind,G.LEFT,**facts),))
                use=build_weapon_use('pc',inventory,inventory.items[0].id,usable_hands=(G.LEFT,))
                self.assertIs(use.skill,weapon_profile(kind).skill)
                self.assertEqual(use.used_hands,(G.LEFT,))
        for left,right,facts in ((W.PISTOL,W.PISTOL,dict(initially_loaded=True)),
                (W.THROWING_SPEAR,W.THROWING_AXE,{}),(W.PISTOL,W.SWORD,dict(initially_loaded=True))):
            inventory=paired(left,right,left_facts=facts,
                right_facts=facts if right is W.PISTOL else {})
            with self.subTest(left=left,right=right),self.assertRaises(ValueError):
                build_weapon_use('pc',inventory,inventory.items[0].id,(inventory.items[1].id,))

    def test_morning_star_and_lance_ban_the_combined_use_not_the_held_inventory(self):
        for kind in (W.MORNING_STAR,W.LANCE):
            inventory=paired(kind,W.SWORD)
            left,right=inventory.items
            self.assertIs(build_weapon_use('pc',inventory,left.id).kind,kind)
            self.assertIs(build_weapon_use('pc',inventory,right.id).kind,W.SWORD)
            for primary,contributor in ((left,right),(right,left)):
                with self.subTest(kind=kind,primary=primary.kind),self.assertRaises(ValueError):
                    build_weapon_use('pc',inventory,primary.id,(contributor.id,))

    def test_unusable_selected_hand_and_unheld_or_missing_sources_are_rejected(self):
        inventory=paired()
        left,right=inventory.items
        with self.assertRaises(ValueError):build_weapon_use('pc',inventory,left.id,usable_hands=(G.RIGHT,))
        with self.assertRaises(ValueError):build_weapon_use('pc',inventory,right.id,(left.id,),usable_hands=(G.RIGHT,))
        with self.assertRaises(ValueError):build_weapon_use('pc',inventory,'missing')
        with self.assertRaises(ValueError):build_weapon_use('pc',inventory,None,(left.id,))
        with self.assertRaises(ValueError):build_weapon_use('pc',inventory,left.id,(left.id,))
        with self.assertRaises(ValueError):build_weapon_use('pc',inventory,left.id,(right.id,right.id))
        for location in (L.CARRIED,L.DROPPED,L.DEPLOYED,L.STUCK,L.SPENT):
            changed=inventory.with_item(replace(left,location=location,grip=None))
            with self.subTest(location=location),self.assertRaises(ValueError):build_weapon_use('pc',changed,left.id)
            with self.subTest(contributor_location=location),self.assertRaises(ValueError):
                build_weapon_use('pc',changed,right.id,(left.id,))

    def test_defence_requires_an_actual_usable_implement_or_shield(self):
        empty=WeaponInventoryState()
        with self.assertRaises(ValueError):build_weapon_protection_use('pc',empty,Skill.DEFENCE)
        with self.assertRaises(ValueError):build_weapon_protection_use('pc',empty,Skill.DEFENCE,shield_used=True)
        shield=WeaponInventoryState(shield_hand=G.LEFT)
        use=build_weapon_protection_use('pc',shield,Skill.DEFENCE,shield_used=True,usable_hands=(G.LEFT,))
        self.assertIs(type(use),WeaponProtectionUse)
        self.assertEqual((use.implements,use.item_ids,use.used_hands),((),(),(G.LEFT,)))
        with self.assertRaises(ValueError):build_weapon_protection_use('pc',shield,Skill.DEFENCE,shield_used=True,usable_hands=())

    def test_knuckles_cannot_supply_defence_but_another_held_sword_or_shield_can(self):
        inventory=paired(W.KNUCKLEDUSTERS,W.SWORD)
        knuckles,sword=inventory.items
        with self.assertRaises(ValueError):build_weapon_protection_use('pc',inventory,Skill.DEFENCE,(knuckles.id,))
        with self.assertRaises(ValueError):build_weapon_protection_use('pc',inventory,Skill.DEFENCE,(knuckles.id,sword.id))
        use=build_weapon_protection_use('pc',inventory,Skill.DEFENCE,(sword.id,),usable_hands=(G.RIGHT,))
        self.assertEqual(use.implements,(sword,))
        self.assertEqual(use.used_hands,(G.RIGHT,))
        shield=initial_weapon_inventory('pc',(item('knuckles',W.KNUCKLEDUSTERS,G.RIGHT),),shield_hand=G.LEFT)
        self.assertEqual(build_weapon_protection_use('pc',shield,Skill.DEFENCE,shield_used=True).used_hands,(G.LEFT,))

    def test_defence_can_use_a_printed_shooting_or_throwing_implement(self):
        for kind,grip,facts in ((W.PISTOL,G.LEFT,dict(initially_loaded=False)),
                (W.HANDGUN,G.BOTH,dict(initially_loaded=True)),(W.THROWING_AXE,G.RIGHT,{}),
                (W.WEIGHTED_NET,G.BOTH,{}),(W.ROCK,G.LEFT,{})):
            with self.subTest(kind=kind):
                inventory=initial_weapon_inventory('pc',(item('held',kind,grip,**facts),))
                use=build_weapon_protection_use('pc',inventory,Skill.DEFENCE,(inventory.items[0].id,))
                self.assertEqual(use.implements,inventory.items)
                self.assertEqual(use.used_hands,(G.LEFT,G.RIGHT) if grip is G.BOTH else (grip,))

    def test_two_swords_can_supply_defence_but_no_shield_can_share_their_hands(self):
        inventory=paired(W.SWORD,W.SWORD)
        ids=tuple(item.id for item in inventory.items)
        use=build_weapon_protection_use('pc',inventory,Skill.DEFENCE,ids)
        self.assertEqual(use.implements,inventory.items)
        self.assertEqual(use.used_hands,(G.LEFT,G.RIGHT))
        with self.assertRaises(ValueError):replace(inventory,shield_hand=G.RIGHT)
        one=initial_weapon_inventory('pc',(item('sword',W.SWORD,G.LEFT),),shield_hand=G.RIGHT)
        combined=build_weapon_protection_use('pc',one,Skill.DEFENCE,(one.items[0].id,),shield_used=True)
        self.assertEqual(combined.used_hands,(G.LEFT,G.RIGHT))
        for kind,facts in ((W.LANCE,{}),(W.MORNING_STAR,{}),(W.PISTOL,dict(initially_loaded=True)),(W.THROWING_AXE,{})):
            inventory=paired(W.SWORD,kind,right_facts=facts)
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                build_weapon_protection_use('pc',inventory,Skill.DEFENCE,tuple(item.id for item in inventory.items))

    def test_melee_counter_can_be_empty_and_handless_independently_of_attack_sources(self):
        use=build_weapon_protection_use('pc',WeaponInventoryState(),Skill.MELEE,usable_hands=())
        self.assertEqual((use.implements,use.used_hands),((),()))
        inventory=paired(W.KNUCKLEDUSTERS,W.SWORD)
        attack=build_weapon_use('pc',inventory,inventory.items[0].id)
        protection=build_weapon_protection_use('pc',inventory,Skill.MELEE,usable_hands=())
        self.assertIs(attack.skill,Skill.BRAWN)
        self.assertIs(protection.skill,Skill.MELEE)
        self.assertEqual(protection.item_ids,())
        self.assertEqual(protection.used_hands,())
        with self.assertRaises(ValueError):build_weapon_protection_use('pc',inventory,Skill.MELEE,(inventory.items[0].id,),usable_hands=())

    def test_both_attack_and_protection_accept_an_item_with_another_initial_origin(self):
        inventory=paired(origin='npc:initial')
        sword=inventory.items[0]
        attack=build_weapon_use('pc:recipient',inventory,sword.id)
        defence=build_weapon_protection_use('pc:recipient',inventory,Skill.DEFENCE,(sword.id,))
        self.assertEqual(attack.actor_id,'pc:recipient')
        self.assertEqual(defence.actor_id,'pc:recipient')
        self.assertEqual(attack.primary.initial_actor_id,'npc:initial')
        self.assertIs(attack.primary,defence.implements[0])

    def test_frozen_sources_retain_old_snapshot_but_cannot_be_rebound_to_a_removed_item(self):
        inventory=paired()
        left,right=inventory.items
        inventory=replace(inventory,active_item_id=left.id)
        attack=build_weapon_use('pc',inventory,left.id,(right.id,))
        defence=build_weapon_protection_use('pc',inventory,Skill.DEFENCE,(left.id,))
        dropped=inventory.with_item(replace(left,location=L.DROPPED,grip=None))
        self.assertEqual(dropped.active_item_id,left.id)
        self.assertIs(dropped.active.location,L.DROPPED)
        self.assertIs(attack.primary,left)
        self.assertEqual(attack.inventory,inventory)
        with self.assertRaises(ValueError):replace(attack,inventory=dropped)
        with self.assertRaises(ValueError):replace(defence,inventory=dropped)
        self.assertIs(build_weapon_use('pc',dropped,right.id).primary,right)
        with self.assertRaises(FrozenInstanceError):attack.primary_item_id=right.id
        with self.assertRaises(FrozenInstanceError):defence.shield_used=True

    def test_invalid_scalar_collections_skills_and_hand_facts_are_rejected(self):
        inventory=paired()
        primary=inventory.items[0].id
        for facts in (dict(actor_id=''),dict(actor_id=True),dict(inventory=()),dict(primary_item_id=True),
                dict(contributor_item_ids=[]),dict(contributor_item_ids=(True,)),dict(usable_hands=[]),
                dict(usable_hands=('left',)),dict(usable_hands=(G.BOTH,)),dict(usable_hands=(G.LEFT,G.LEFT))):
            with self.subTest(facts=facts),self.assertRaises((TypeError,ValueError)):
                replace(build_weapon_use('pc',inventory,primary),**facts)
        valid=build_weapon_protection_use('pc',inventory,Skill.DEFENCE,(primary,))
        for facts in (dict(skill='defence'),dict(skill=Skill.ATHLETICS),dict(skill=Skill.BRAWN),
                dict(item_ids=[]),dict(item_ids=(primary,primary)),dict(shield_used=1),dict(usable_hands=(G.BOTH,))):
            with self.subTest(facts=facts),self.assertRaises((TypeError,ValueError)):replace(valid,**facts)


if __name__=='__main__':unittest.main()
