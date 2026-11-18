"""Finite item identity, hands, independent resource states and PG92 burdens."""
from dataclasses import FrozenInstanceError, replace
import unittest

from tests.support.weapon_reload import execute_scripted_weapon_reload as actual_reload
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.reload_models import ReloadableWeaponState, begin_reload_cycle, create_initial_ranged_weapon_reload_state
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_inventory_models import (
    TWO_HANDED_COUNT_BURDEN_RULE_ID, WEAPON_COUNT_BURDEN_RULE_ID,
    WeaponGrip as G, WeaponItemLocation as L, WeaponItemSource, WeaponInventoryState,
    WeaponUnitState, carrying_burden_rule_ids,
    initial_weapon_inventory, weapon_reload_target, weapon_unit_id, weapon_reload_cycle_id,
)


def source(identifier='sword',kind=W.SWORD,*,location=L.CARRIED,grip=None,**kwargs):
    return WeaponItemSource(identifier,kind,location,grip,**kwargs)


class WeaponInventoryModelsTests(unittest.TestCase):
    def test_empty_source_supports_an_external_unarmed_mode_without_a_fake_item(self):
        inventory=initial_weapon_inventory('pc',())
        self.assertEqual(inventory,WeaponInventoryState())
        self.assertEqual(inventory.items,())
        self.assertIsNone(inventory.active)
        self.assertEqual(carrying_burden_rule_ids(inventory,1),())
        with self.assertRaises(ValueError):source(kind=W.UNARMED)

    def test_held_throwing_stack_expands_one_held_unit_and_actual_carried_spares(self):
        original=source('spears',W.THROWING_SPEAR,location=L.HELD,grip=G.LEFT,quantity=3)
        inventory=initial_weapon_inventory('pc',(original,))
        self.assertEqual(tuple(item.location for item in inventory.items),(L.HELD,L.CARRIED,L.CARRIED))
        self.assertEqual(tuple(item.grip for item in inventory.items),(G.LEFT,None,None))
        self.assertEqual(tuple(item.unit_index for item in inventory.items),(0,1,2))
        self.assertEqual(len({item.id for item in inventory.items}),3)
        self.assertTrue(all(item.source is original and item.source_item_id=='spears' for item in inventory.items))
        self.assertIsNone(inventory.active_item_id)  # Holding does not preselect an Attack.
        self.assertEqual(carrying_burden_rule_ids(inventory,2),(WEAPON_COUNT_BURDEN_RULE_ID,))

    def test_multiple_nets_and_knife_sets_are_separate_finite_physical_units(self):
        inventory=initial_weapon_inventory('pc',(
            source('nets',W.WEIGHTED_NET,location=L.HELD,grip=G.BOTH,quantity=2),
            source('knife-sets',W.THROWING_KNIVES,quantity=2)))
        self.assertEqual(tuple(item.location for item in inventory.items),(L.HELD,L.CARRIED,L.CARRIED,L.CARRIED))
        self.assertEqual(len(inventory.items),4)
        self.assertEqual(carrying_burden_rule_ids(inventory,3),
            (WEAPON_COUNT_BURDEN_RULE_ID,TWO_HANDED_COUNT_BURDEN_RULE_ID))
        single_set=initial_weapon_inventory('pc',(source('set',W.THROWING_KNIVES),))
        self.assertEqual(len(single_set.items),1)
        self.assertEqual(carrying_burden_rule_ids(single_set,1),())

    def test_melee_and_guns_need_explicit_instances_instead_of_quantity_stacks(self):
        for kind,kwargs in ((W.SWORD,{}),(W.PISTOL,dict(initially_loaded=True)),
                (W.SCARAB_KNIFE,{}),(W.DUELLIST_BLADES,{})):
            with self.subTest(kind=kind),self.assertRaises(ValueError):source(kind=kind,quantity=2,**kwargs)

    def test_canonical_unit_ids_preserve_origin_and_cannot_alias_colon_names(self):
        self.assertEqual(weapon_unit_id('pc','knife',0),'weapon-unit:2:pc:5:knife:0')
        self.assertNotEqual(weapon_unit_id('a:b','c',0),weapon_unit_id('a','b:c',0))
        self.assertNotEqual(weapon_unit_id('pc','knife',0),weapon_unit_id('npc','knife',0))
        self.assertNotEqual(weapon_unit_id('pc','knife',0),weapon_unit_id('pc','knife',1))
        with self.assertRaises(ValueError):initial_weapon_inventory('pc',(source('same'),source('same',W.AXE)))
        unit=initial_weapon_inventory('pc',(source('knife',W.THROWING_KNIVES,quantity=2),)).items[0]
        for fields in (dict(id='invented'),dict(source_item_id='other'),dict(unit_index=2),dict(initial_actor_id='other')):
            with self.subTest(fields=fields),self.assertRaises(ValueError):replace(unit,**fields)

    def test_foreign_item_keeps_its_initial_actor_namespace_without_owner_restrictions(self):
        foreign=initial_weapon_inventory('npc:original',(source('sword'),)).items[0]
        recipient=WeaponInventoryState((replace(foreign,location=L.HELD,grip=G.RIGHT),),foreign.id)
        self.assertEqual(recipient.active.id,foreign.id)
        self.assertEqual(recipient.active.initial_actor_id,'npc:original')
        self.assertIs(recipient.active.source,foreign.source)
        self.assertEqual(recipient.active.source_item_id,'sword')

    def test_two_held_weapons_require_distinct_hands_and_do_not_imply_dual_attack(self):
        inventory=initial_weapon_inventory('pc',(
            source('star',W.MORNING_STAR,location=L.HELD,grip=G.LEFT),
            source('sword',location=L.HELD,grip=G.RIGHT)))
        self.assertEqual(len(inventory.items),2)  # Morning Star bans Dual Wield, not holding two items.
        self.assertIsNone(inventory.active)
        with self.assertRaises(ValueError):initial_weapon_inventory('pc',(
            source('left',location=L.HELD,grip=G.LEFT),source('also-left',W.AXE,location=L.HELD,grip=G.LEFT)))
        with self.assertRaises(ValueError):initial_weapon_inventory('pc',(
            source('glaive',W.GLAIVE,location=L.HELD,grip=G.BOTH),
            source('dagger',W.DAGGER,location=L.HELD,grip=G.RIGHT)))

    def test_actual_shield_hand_conflicts_with_one_or_two_handed_weapons(self):
        inventory=initial_weapon_inventory('pc',(source(location=L.HELD,grip=G.LEFT),),shield_hand=G.RIGHT)
        self.assertEqual(inventory.shield_hand,G.RIGHT)
        self.assertEqual(carrying_burden_rule_ids(inventory,1),())  # Shield is not a weapon unit.
        with self.assertRaises(ValueError):initial_weapon_inventory('pc',(
            source(location=L.HELD,grip=G.LEFT),),shield_hand=G.LEFT)
        with self.assertRaises(ValueError):initial_weapon_inventory('pc',(
            source(kind=W.DUELLIST_BLADES,location=L.HELD,grip=G.BOTH),),shield_hand=G.RIGHT)
        with self.assertRaises(ValueError):WeaponInventoryState(shield_hand=G.BOTH)

    def test_printed_hands_variable_grip_and_the_confirmed_rock_hand_rule(self):
        for grip in (G.LEFT,G.RIGHT,G.BOTH):
            self.assertEqual(source(kind=W.FOOT_SPEAR,location=L.HELD,grip=grip).initial_grip,grip)
        self.assertEqual(source(kind=W.ROCK,location=L.HELD,grip=G.LEFT).initial_grip,G.LEFT)
        with self.assertRaises(ValueError):source(kind=W.ROCK,location=L.HELD,grip=G.BOTH)
        with self.assertRaises(ValueError):source(kind=W.SWORD,location=L.HELD,grip=G.BOTH)
        with self.assertRaises(ValueError):source(kind=W.GREATSWORD,location=L.HELD,grip=G.LEFT)
        with self.assertRaises(ValueError):source(location=L.HELD,grip=None)
        with self.assertRaises(ValueError):source(location=L.CARRIED,grip=G.LEFT)

    def test_initial_selection_requires_held_but_runtime_selection_survives_drop(self):
        unit_id=weapon_unit_id('pc','sword',0)
        inventory=initial_weapon_inventory('pc',(source(location=L.HELD,grip=G.LEFT),),active_item_id=unit_id)
        self.assertIs(inventory.active,inventory.items[0])
        self.assertIs(inventory.item(unit_id),inventory.items[0])
        with self.assertRaises(ValueError):initial_weapon_inventory('pc',(source(),),active_item_id=unit_id)
        with self.assertRaises(ValueError):WeaponInventoryState(active_item_id='absent')
        with self.assertRaises(KeyError):inventory.item('absent')
        dropped=inventory.with_item(replace(inventory.active,location=L.DROPPED,grip=None))
        self.assertEqual(dropped.active_item_id,unit_id)
        self.assertIs(dropped.active.location,L.DROPPED)
        self.assertEqual(inventory.active_item_id,unit_id)
        for location in (L.CARRIED,L.DEPLOYED,L.STUCK,L.SPENT):
            selected=dropped.with_item(replace(dropped.active,location=location))
            self.assertEqual(selected.active_item_id,unit_id)
            self.assertIs(selected.active.location,location)

    def test_free_reload_sources_have_no_persistent_loaded_flag(self):
        for kind in (W.SWORD,W.SLING,W.SHORTBOW,W.WARBOW,W.LONGBOW,W.DRAGON_BOW,W.THROWING_KNIVES):
            with self.subTest(kind=kind):
                item=source(kind=kind)
                self.assertIsNone(weapon_reload_target(kind))
                self.assertIsNone(initial_weapon_inventory('pc',(item,)).items[0].reload)
                with self.assertRaises(ValueError):source(kind=kind,initially_loaded=True)

    def test_exacting_and_repeater_targets_belong_to_each_real_item(self):
        expected=((W.CROSSBOW,2),(W.PISTOL,3),(W.OGRE_PISTOL,3),(W.HANDGUN,3),
            (W.BLUNDERBUSS,3),(W.HOCHLAND_LONG_RIFLE,4),(W.REPEATER_HANDBOW,3),
            (W.REPEATER_CROSSBOW,3),(W.REPEATER_PISTOL,3),(W.REPEATER_HANDGUN,5))
        for kind,target in expected:
            with self.subTest(kind=kind):
                fit=dict(gm_fit_confirmed=True) if kind is W.OGRE_PISTOL else {}
                with self.assertRaises(ValueError):source(kind=kind,**fit)
                loaded=initial_weapon_inventory('pc',(source(kind=kind,initially_loaded=True,**fit),)).items[0]
                empty=initial_weapon_inventory('pc',(source(kind=kind,initially_loaded=False,**fit),)).items[0]
                self.assertIs(type(loaded.reload),ReloadableWeaponState)
                self.assertEqual(loaded.reload,create_initial_ranged_weapon_reload_state(
                    loaded.id,RangedWeaponId(kind.value)))
                self.assertEqual(empty.reload,begin_reload_cycle(loaded.reload,weapon_reload_cycle_id(loaded.id,1)))
                self.assertEqual(empty.reload.exacting.contributions,())
                self.assertEqual(empty.reload.required_successes,target)
                self.assertEqual(weapon_reload_target(kind),target)

    def test_two_pistols_keep_separate_cycles_progress_and_loaded_flags(self):
        inventory=initial_weapon_inventory('pc',(
            source('first',W.PISTOL,location=L.HELD,grip=G.LEFT,initially_loaded=True),
            source('second',W.PISTOL,location=L.HELD,grip=G.RIGHT,initially_loaded=False)))
        first,second=inventory.items
        partial_result=actual_reload(second.reload,(1,1))
        partial=inventory.with_item(replace(second,reload=partial_result.state))
        complete_result=actual_reload(partial_result.state,(1,),round_number=2)
        loaded=partial.with_item(replace(partial.item(second.id),reload=complete_result.state))
        self.assertEqual(loaded.item(first.id),first)
        self.assertIs(loaded.item(second.id).reload,complete_result.state)
        empty_first=begin_reload_cycle(first.reload,weapon_reload_cycle_id(first.id,1))
        fired=loaded.with_item(replace(loaded.item(first.id),reload=empty_first))
        self.assertEqual(fired.item(second.id),loaded.item(second.id))
        moved=fired.with_item(replace(fired.item(first.id),location=L.DROPPED,grip=None))
        self.assertIs(moved.item(first.id).reload,empty_first)
        recovered=moved.with_item(replace(moved.item(first.id),location=L.HELD,grip=G.LEFT))
        self.assertEqual(recovered.item(first.id).reload,fired.item(first.id).reload)
        with self.assertRaises(ValueError):partial.with_item(second)
        with self.assertRaises(ValueError):fired.with_item(first)  # Reusing the original source is not a reload.
        with self.assertRaises(ValueError):fired.with_item(replace(fired.item(first.id),reload=
            begin_reload_cycle(first.reload,weapon_reload_cycle_id(first.id,2))))

    def test_zero_success_work_and_complete_k1_history_cannot_be_replaced_during_transfer(self):
        before=initial_weapon_inventory('original',(source('gun',W.PISTOL,initially_loaded=False),))
        item,=before.items
        first=actual_reload(item.reload,(10,10))
        current=before.with_item(replace(item,reload=first.state))
        other=actual_reload(item.reload,(10,10),round_number=2)
        self.assertEqual(first.state.exacting.accumulated_successes,other.state.exacting.accumulated_successes)
        with self.assertRaises(ValueError):current.with_item(replace(item,reload=other.state))
        with self.assertRaises(ValueError):current.with_item(item)
        recipient=WeaponInventoryState((replace(current.items[0],location=L.HELD,grip=G.RIGHT),),item.id)
        self.assertIs(recipient.active.reload,first.state)
        self.assertEqual(recipient.active.reload.exacting.contributions,(first.exacting.contribution,))
        self.assertEqual(recipient.active.initial_actor_id,'original')

    def test_reload_cycle_ids_are_injective_and_follow_the_actual_physical_unit(self):
        item=initial_weapon_inventory('pc',(source('gun',W.PISTOL,initially_loaded=False),)).items[0]
        cycle=weapon_reload_cycle_id(item.id,1)
        self.assertEqual(cycle,'weapon-reload-cycle:'+str(len(item.id))+':'+item.id+':1')
        self.assertNotEqual(weapon_reload_cycle_id('a:1',2),weapon_reload_cycle_id('a',12))
        with self.assertRaises(TypeError):weapon_reload_cycle_id(item.id,True)
        with self.assertRaises(ValueError):weapon_reload_cycle_id(item.id,0)
        other=begin_reload_cycle(create_initial_ranged_weapon_reload_state(item.id,RangedWeaponId.PISTOL),'foreign-cycle')
        with self.assertRaises(ValueError):replace(item,reload=other)
        foreign=create_initial_ranged_weapon_reload_state('foreign',RangedWeaponId.PISTOL)
        with self.assertRaises(ValueError):replace(item,reload=foreign)

    def test_scarab_charges_and_dragon_use_stay_with_the_same_unit_across_movement(self):
        inventory=initial_weapon_inventory('pc',(
            source('knife',W.SCARAB_KNIFE,initial_charges=3),source('bow',W.DRAGON_BOW)))
        knife,bow=inventory.items
        spent=inventory.with_item(replace(knife,charges=0))
        changed=spent.with_item(replace(spent.item(knife.id),location=L.HELD,grip=G.LEFT))
        self.assertEqual(changed.item(knife.id).charges,0)
        self.assertEqual(changed.item(knife.id).source.initial_charges,3)
        self.assertEqual(changed.item(bow.id),bow)
        activated=changed.with_item(replace(bow,dragon_arrow_used=True))
        dropped=activated.with_item(replace(activated.item(bow.id),location=L.DROPPED))
        self.assertTrue(dropped.item(bow.id).dragon_arrow_used)
        with self.assertRaises(ValueError):dropped.with_item(replace(dropped.item(bow.id),dragon_arrow_used=False))
        with self.assertRaises(ValueError):source(kind=W.SWORD,initial_charges=1)
        with self.assertRaises(ValueError):replace(knife,dragon_arrow_used=True)
        with self.assertRaises(ValueError):replace(bow,charges=1)

    def test_spent_unit_never_refills_and_does_not_consume_its_carried_spare(self):
        selected=weapon_unit_id('pc','oil',0)
        inventory=initial_weapon_inventory('pc',(
            source('oil',W.OIL_FLASK,location=L.HELD,grip=G.LEFT,quantity=2),),active_item_id=selected)
        first,spare=inventory.items
        used=inventory.with_item(replace(first,location=L.SPENT,grip=None))
        self.assertEqual(used.items[1],spare)
        self.assertEqual(len(used.items),2)
        self.assertEqual(used.items[0].source.quantity,2)
        self.assertEqual(used.active.id,first.id)
        self.assertIs(used.active.location,L.SPENT)
        self.assertEqual(carrying_burden_rule_ids(used,1),())
        with self.assertRaises(ValueError):used.with_item(first)
        with self.assertRaises(KeyError):used.with_item(initial_weapon_inventory('pc',(source('other'),)).items[0])

    def test_updating_a_unit_cannot_replace_its_source_kind_or_source_facts(self):
        inventory=initial_weapon_inventory('pc',(source('one'),))
        unit=inventory.items[0]
        forged=replace(unit,source=source('one',W.AXE))
        with self.assertRaises(ValueError):inventory.with_item(forged)
        forged=replace(unit,source=source('one',location=L.HELD,grip=G.LEFT))
        with self.assertRaises(ValueError):inventory.with_item(forged)
        with self.assertRaises(ValueError):WeaponInventoryState((unit,unit))

    def test_pg92_carrying_counts_physical_units_and_only_printed_two_handed_items(self):
        inventory=initial_weapon_inventory('pc',(
            source('sword:left',location=L.HELD,grip=G.LEFT),
            source('sword:right',location=L.HELD,grip=G.RIGHT),source('glaive',W.GLAIVE)))
        self.assertEqual(carrying_burden_rule_ids(inventory,2),(WEAPON_COUNT_BURDEN_RULE_ID,))
        self.assertEqual(carrying_burden_rule_ids(inventory,3),())
        printed_two=initial_weapon_inventory('pc',(source('pair',W.DUELLIST_BLADES),source('glaive',W.GLAIVE)))
        self.assertEqual(carrying_burden_rule_ids(printed_two,5),(TWO_HANDED_COUNT_BURDEN_RULE_ID,))
        variable=initial_weapon_inventory('pc',(
            source('spear',W.FOOT_SPEAR,location=L.HELD,grip=G.BOTH),source('glaive',W.GLAIVE)))
        self.assertEqual(carrying_burden_rule_ids(variable,2),())
        self.assertEqual(len(initial_weapon_inventory('pc',(source('pair',W.DUELLIST_BLADES),)).items),1)

    def test_ground_deployed_stuck_and_spent_items_are_not_carried_burdens(self):
        inventory=initial_weapon_inventory('pc',(
            source('glaive',W.GLAIVE),source('hammer',W.GROTARGGS_HAMMER),
            source('net',W.WEIGHTED_NET),source('oil',W.OIL_FLASK)))
        self.assertEqual(carrying_burden_rule_ids(inventory,1),
            (WEAPON_COUNT_BURDEN_RULE_ID,TWO_HANDED_COUNT_BURDEN_RULE_ID))
        for unit,location in zip(inventory.items,(L.DROPPED,L.STUCK,L.DEPLOYED,L.SPENT),strict=True):
            inventory=inventory.with_item(replace(unit,location=location))
        self.assertEqual(carrying_burden_rule_ids(inventory,1),())
        recovered=inventory.with_item(replace(inventory.items[0],location=L.CARRIED))
        self.assertEqual(carrying_burden_rule_ids(recovered,1),())

    def test_ogre_fit_is_an_explicit_initial_fact_without_an_owner_id_dispatch(self):
        for fit in (None,False):
            with self.subTest(fit=fit),self.assertRaises(ValueError):
                source(kind=W.OGRE_PISTOL,initially_loaded=True,gm_fit_confirmed=fit)
        ogre=source(kind=W.OGRE_PISTOL,initially_loaded=True,gm_fit_confirmed=True)
        inventory=initial_weapon_inventory('human:any-name',(ogre,))
        self.assertTrue(inventory.items[0].source.gm_fit_confirmed)
        with self.assertRaises(ValueError):source(gm_fit_confirmed=True)

    def test_exact_scalar_types_invalid_locations_and_resource_shapes_are_rejected(self):
        for fields in (dict(id=''),dict(kind='sword'),dict(quantity=True),dict(initial_location='held'),
                dict(initial_grip='left'),dict(initially_loaded=1),dict(initial_charges=True),dict(gm_fit_confirmed=1)):
            with self.subTest(fields=fields),self.assertRaises((TypeError,ValueError)):
                replace(source(),**fields)
        for location in (L.DROPPED,L.DEPLOYED,L.STUCK,L.SPENT):
            with self.subTest(location=location),self.assertRaises(ValueError):source(location=location)
        gun=initial_weapon_inventory('pc',(source('gun',W.PISTOL,initially_loaded=False),)).items[0]
        for fields in (dict(loaded=1),dict(required_successes=True),dict(reload_cycle_ids=[]),
                dict(required_successes=4),dict(loaded=True),dict(reload_cycle_id=None),
                dict(weapon_id='pistol')):
            with self.subTest(fields=fields),self.assertRaises((TypeError,ValueError)):
                replace(gun,reload=replace(gun.reload,**fields))
        corrupted=replace(gun.reload.exacting)
        object.__setattr__(corrupted,'contributions',('forged',))
        corrupted_reload=replace(gun.reload)
        object.__setattr__(corrupted_reload,'exacting',corrupted)
        with self.assertRaises(TypeError):replace(gun,reload=corrupted_reload)
        with self.assertRaises(TypeError):replace(gun,reload={})
        unit=initial_weapon_inventory('pc',(source(),)).items[0]
        for fields in (dict(location='carried'),dict(unit_index=True),dict(charges=True),dict(dragon_arrow_used=1)):
            with self.subTest(fields=fields),self.assertRaises((TypeError,ValueError)):replace(unit,**fields)
        with self.assertRaises(TypeError):WeaponInventoryState([unit])
        with self.assertRaises(TypeError):WeaponInventoryState(shield_hand='left')
        with self.assertRaises(TypeError):initial_weapon_inventory('pc',[source()])
        with self.assertRaises(TypeError):carrying_burden_rule_ids(WeaponInventoryState(),True)
        with self.assertRaises(ValueError):carrying_burden_rule_ids(WeaponInventoryState(),0)

    def test_initial_sources_and_units_are_frozen_independent_battle_values(self):
        original=source()
        first=initial_weapon_inventory('pc',(original,))
        second=initial_weapon_inventory('pc',(original,))
        self.assertEqual(first,second)
        self.assertIsNot(first,second)
        self.assertIsNot(first.items[0],second.items[0])
        self.assertIs(first.items[0].source,original)
        for item,attribute,value in ((original,'quantity',5),(first.items[0],'location',L.SPENT),(first,'items',())):
            with self.subTest(item=type(item)),self.assertRaises(FrozenInstanceError):setattr(item,attribute,value)


if __name__=='__main__':unittest.main()
