"""NPC item admission and K1 resource views, without inventing a battle journal."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest

from tests.support.weapon_reload import execute_scripted_weapon_reload
from towr.domain.armour_models import ArmourLoadout, ShieldKind
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedRangedFacts, GeneratedWeapon
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc
from towr.domain.pc_npc_ranged_models import (
    initial_pc_npc_weapon_inventories, npc_ranged_inventory_update,
    npc_ranged_inventory_update_enemies, npc_ranged_weapon_from_unit,
    pc_npc_ranged_weapon, validate_pc_npc_ranged_weapons,
)
from towr.domain.pc_npc_ranged_source_models import (
    PcNpcRangedPolicy, PcNpcRangedReloadHandPolicy, pc_npc_ranged_policy_for_generated,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponId
from towr.domain.reload_models import (
    FreeReloadWeaponState, begin_reload_cycle, create_initial_ranged_weapon_reload_state,
)
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import (
    WeaponGrip, WeaponItemLocation, WeaponItemSource, initial_weapon_inventory,
    weapon_reload_cycle_id, weapon_unit_id,
)


def component(weapon=GeneratedWeapon.PISTOL, *, shield=False, grip=None):
    ranged = None
    if weapon in (GeneratedWeapon.PISTOL, GeneratedWeapon.REPEATER_PISTOL,
            GeneratedWeapon.REPEATER_HANDBOW, GeneratedWeapon.SHORTBOW):
        blackpowder = weapon in (GeneratedWeapon.PISTOL, GeneratedWeapon.REPEATER_PISTOL)
        ranged = GeneratedRangedFacts(3,4,3,None if weapon is GeneratedWeapon.SHORTBOW else 4,True,
            True if blackpowder else None,True if blackpowder else None,
            awareness=4 if weapon is GeneratedWeapon.SHORTBOW else None)
    return GeneratedNpc(3,3,3,3,4,4,initial_generated_weapons(weapon, grip=grip),
        ArmourLoadout(shield=ShieldKind.SHIELD if shield else None),
        defence=4,ranged=ranged)


def source_for(*components):
    enemies = tuple(npc.participant('npc'+str(index)) for index,npc in enumerate(components,1))
    policies = tuple(pc_npc_ranged_policy_for_generated(npc,enemy.state.actor_id)
        for npc,enemy in zip(components,enemies) if npc.ranged is not None)
    return SimpleNamespace(enemies=enemies,npc_ranged_policies=policies)


def view(source, *, enemies=None):
    state = SimpleNamespace(source=source,history=(),
        enemies=initial_pc_npc_weapon_inventories(source) if enemies is None else enemies)
    state.enemy = lambda actor: next(enemy for enemy in state.enemies if enemy.state.actor_id == actor)
    return state


def fire(state, actor='npc1'):
    before = pc_npc_ranged_weapon(state,actor)
    after = begin_reload_cycle(before,weapon_reload_cycle_id(before.weapon_instance_id,
        len(before.reload_cycle_ids)+1))
    state.enemies = npc_ranged_inventory_update(state,actor,after)
    return after


class PcNpcWeaponInventoryTests(unittest.TestCase):
    def test_initial_admission_copies_snapshots_and_keeps_one_authoritative_k1_state(self):
        source = source_for(component(shield=True),component(GeneratedWeapon.SWORD))
        state = view(source)
        self.assertTrue(all(enemy.state.weapon_inventory is None for enemy in source.enemies))
        for original,actual in zip(source.enemies,state.enemies):
            inventory = actual.state.weapon_inventory
            item, = inventory.items
            self.assertIs(actual.definition,original.definition)
            self.assertEqual(item.source.id,'weapon')
            self.assertEqual(item.id,weapon_unit_id(actual.state.actor_id,'weapon',0))
            self.assertEqual(inventory.active_item_id,item.id)
            self.assertIs(item.location,WeaponItemLocation.HELD)
            self.assertIs(item.grip,WeaponGrip.LEFT)
        inventory = state.enemy('npc1').state.weapon_inventory
        self.assertIs(inventory.shield_hand,WeaponGrip.RIGHT)
        self.assertIs(pc_npc_ranged_weapon(state,'npc1'),inventory.active.reload)
        self.assertIsNone(pc_npc_ranged_weapon(state,'npc2'))
        self.assertFalse(hasattr(state,'npc_ranged_weapons'))

    def test_variable_grip_uses_actual_hands_and_free_bow_has_no_persistent_reload(self):
        for grip,expected in ((RangedWeaponHands.ONE_HANDED,WeaponGrip.LEFT),
                (RangedWeaponHands.TWO_HANDED,WeaponGrip.BOTH)):
            with self.subTest(grip=grip):
                state = view(source_for(component(GeneratedWeapon.FOOT_SPEAR,grip=grip)))
                self.assertIs(state.enemies[0].state.weapon_inventory.active.grip,expected)
        state = view(source_for(component(GeneratedWeapon.SHORTBOW)))
        item = state.enemies[0].state.weapon_inventory.active
        self.assertIs(item.grip,WeaponGrip.BOTH)
        self.assertIsNone(item.reload)
        kernel = pc_npc_ranged_weapon(state,'npc1')
        self.assertIs(type(kernel),FreeReloadWeaponState)
        self.assertEqual(kernel.weapon_instance_id,item.id)
        self.assertEqual(npc_ranged_inventory_update(state,'npc1',kernel),state.enemies)

    def test_canonical_ogre_and_official_sources_keep_their_actual_kind(self):
        for profile,kind in ((PcBookNpcProfile.EMPIRE_OFFICIAL_PISTOL,WeaponKind.PISTOL),
                (PcBookNpcProfile.IMPERIAL_OGRE_PISTOL,WeaponKind.OGRE_PISTOL)):
            with self.subTest(profile=profile):
                original = create_pc_book_npc(profile,'npc')
                source = SimpleNamespace(enemies=(original,),npc_ranged_policies=(
                    PcNpcRangedPolicy('npc',True,True,True,
                        PcNpcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS,initial_weapon=initial_generated_weapons(kind,gm_fit_confirmed=True if kind is WeaponKind.OGRE_PISTOL else None)[0]),))
                actual, = initial_pc_npc_weapon_inventories(source)
                item = actual.state.weapon_inventory.active
                self.assertIs(item.kind,kind)
                self.assertIs(item.source.gm_fit_confirmed,True if kind is WeaponKind.OGRE_PISTOL else None)
                self.assertEqual(item.reload.weapon_instance_id,item.id)
                self.assertIsNone(original.state.weapon_inventory)

    def test_opaque_authored_and_natural_profiles_do_not_infer_items(self):
        for profile in (PcBookNpcProfile.FOOTPAD,PcBookNpcProfile.HORSE):
            with self.subTest(profile=profile):
                original = create_pc_book_npc(profile,'npc')
                source = SimpleNamespace(enemies=(original,),npc_ranged_policies=())
                actual, = initial_pc_npc_weapon_inventories(source)
                self.assertIs(actual,original)
                self.assertIsNone(actual.state.weapon_inventory)
        inventory = initial_weapon_inventory('npc',(
            WeaponItemSource('guessed',WeaponKind.SWORD,WeaponItemLocation.HELD,WeaponGrip.LEFT),))
        source.enemies = (replace(original,state=replace(original.state,weapon_inventory=inventory)),)
        with self.assertRaises(ValueError):
            initial_pc_npc_weapon_inventories(source)

    def test_definition_or_initial_inventory_source_forgery_is_rejected(self):
        source = source_for(component())
        enemy, = initial_pc_npc_weapon_inventories(source)
        inventory = enemy.state.weapon_inventory
        item = inventory.active
        wrong = initial_weapon_inventory('npc1',(
            replace(item.source,kind=WeaponKind.REPEATER_PISTOL),),active_item_id=item.id)
        source.enemies = (replace(enemy,state=replace(enemy.state,weapon_inventory=wrong)),)
        with self.assertRaises(ValueError):
            initial_pc_npc_weapon_inventories(source)
        corrupt = deepcopy(inventory)
        object.__setattr__(corrupt.items[0].source,'kind','pistol')
        with self.assertRaises(TypeError):
            replace(enemy.state,weapon_inventory=corrupt)
        with self.assertRaises(TypeError):
            replace(enemy.state,weapon_inventory=SimpleNamespace(items=()))

    def test_real_k1_zero_partial_complete_reload_is_retained_on_same_unit(self):
        source = source_for(component(),component())
        state = view(source)
        untouched = state.enemy('npc2')
        empty = fire(state)
        for round_number,values,successes in ((1,(10,10),0),(2,(1,10),1),(3,(1,1),3)):
            result = execute_scripted_weapon_reload(pc_npc_ranged_weapon(state,'npc1'),values,
                actor='npc1',round_number=round_number)
            state.enemies = npc_ranged_inventory_update(state,'npc1',result.state)
            self.assertIs(pc_npc_ranged_weapon(state,'npc1'),result.state)
            self.assertEqual(result.state.exacting.accumulated_successes,successes)
            self.assertIs(state.enemy('npc2'),untouched)
        final = pc_npc_ranged_weapon(state,'npc1')
        self.assertTrue(final.loaded)
        self.assertEqual(len(final.exacting.contributions),3)
        self.assertEqual(final.reload_cycle_ids,empty.reload_cycle_ids)
        with self.assertRaises(ValueError):
            npc_ranged_inventory_update(state,'npc1',empty)
        with self.assertRaises(KeyError):
            npc_ranged_inventory_update(state,'npc2',final)
        self.assertTrue(pc_npc_ranged_weapon(view(source),'npc1').loaded)

    def test_update_preserves_current_injury_and_selected_dropped_instance(self):
        state = view(source_for(component()))
        enemy = state.enemy('npc1')
        injury = replace(enemy.state.injury,conditions=ConditionState(frozenset((Condition.STAGGERED,))))
        state.enemies = (replace(enemy,state=replace(enemy.state,injury=injury)),)
        empty = fire(state)
        self.assertIs(state.enemy('npc1').state.injury,injury)
        inventory = state.enemy('npc1').state.weapon_inventory
        item = inventory.active
        dropped = inventory.with_item(replace(item,location=WeaponItemLocation.DROPPED,grip=None))
        enemy = state.enemy('npc1')
        state.enemies = (replace(enemy,state=replace(enemy.state,weapon_inventory=dropped)),)
        self.assertIs(pc_npc_ranged_weapon(state,'npc1'),empty)
        self.assertEqual(dropped.active_item_id,item.id)

    def test_explicit_item_lookup_and_update_touch_one_unit_not_active_label(self):
        state = view(source_for(component()))
        inventory = initial_weapon_inventory('npc1',(
            WeaponItemSource('left',WeaponKind.PISTOL,WeaponItemLocation.HELD,WeaponGrip.LEFT,initially_loaded=True),
            WeaponItemSource('right',WeaponKind.PISTOL,WeaponItemLocation.HELD,WeaponGrip.RIGHT,initially_loaded=True)))
        left,right = inventory.items
        inventory = replace(inventory,active_item_id=left.id)
        enemy = state.enemy('npc1')
        state.enemies = (replace(enemy,state=replace(enemy.state,weapon_inventory=inventory)),)
        before = pc_npc_ranged_weapon(state,'npc1',right.id)
        after = begin_reload_cycle(before,weapon_reload_cycle_id(right.id,1))
        state.enemies = npc_ranged_inventory_update_enemies(state.enemies,'npc1',after)
        inventory = state.enemy('npc1').state.weapon_inventory
        self.assertIs(inventory.item(right.id).reload,after)
        self.assertEqual(inventory.item(left.id),left)
        self.assertEqual(inventory.active_item_id,left.id)

    def test_invalid_legacy_instance_and_cycle_never_enter_actual_inventory(self):
        state = view(source_for(component()))
        old = create_initial_ranged_weapon_reload_state('npc1:weapon',RangedWeaponId.PISTOL)
        with self.assertRaises(KeyError):
            npc_ranged_inventory_update(state,'npc1',old)
        current = pc_npc_ranged_weapon(state,'npc1')
        invalid = begin_reload_cycle(current,'actor-action:ranged:cycle')
        with self.assertRaises(ValueError):
            npc_ranged_inventory_update(state,'npc1',invalid)

    def test_history_validation_accepts_initial_state_and_rejects_unreceipted_progress(self):
        state = view(source_for(component(),component(GeneratedWeapon.SWORD)))
        validate_pc_npc_ranged_weapons(state)
        fire(state)
        with self.assertRaises(ValueError):
            validate_pc_npc_ranged_weapons(state)

    def test_independent_inventory_owner_does_not_waive_equipment_availability_guards(self):
        from towr.domain.pc_minion_defeat_models import validate_pc_minion_defeat_equipment
        state = view(source_for(component(GeneratedWeapon.SWORD)))
        state.npc_shields = ()
        validate_pc_minion_defeat_equipment(state)
        original = state.enemies[0]
        for changes in (dict(wields_weapon=False),dict(available_attack_ids=()),dict(holds_shield=True)):
            with self.subTest(changes=changes):
                state.enemies = (replace(original,state=replace(original.state,**changes)),)
                with self.assertRaises(ValueError):
                    validate_pc_minion_defeat_equipment(state)


if __name__ == '__main__':
    unittest.main()
