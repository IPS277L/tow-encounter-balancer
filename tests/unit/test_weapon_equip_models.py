"""Complete incidental equips preserve physical units and all item resources."""
from dataclasses import FrozenInstanceError, replace
import unittest

from tests.support.weapon_reload import execute_scripted_weapon_reload as actual_reload
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_inventory_models import (
    WeaponGrip as G, WeaponItemLocation as L, WeaponItemSource, WeaponInventoryState,
    initial_weapon_inventory,
)
from towr.domain.weapon_equip_models import (
    WeaponEquipTransition, WeaponEquipTurnState, plan_weapon_equip, apply_incidental_equip,
)


def three_weapons():
    return initial_weapon_inventory('pc', (
        WeaponItemSource('sword', W.SWORD, L.HELD, G.LEFT),
        WeaponItemSource('dagger', W.DAGGER, L.HELD, G.RIGHT),
        WeaponItemSource('glaive', W.GLAIVE, L.CARRIED, None)))


class WeaponEquipModelsTests(unittest.TestCase):
    def test_stow_two_held_weapons_and_draw_one_two_handed_item_in_one_equip(self):
        before = three_weapons()
        glaive = before.items[2]
        transition = plan_weapon_equip('pc', 1, before,
            held_items=((glaive.id, G.BOTH),), active_item_id=glaive.id, usable_hands=(G.LEFT, G.RIGHT))
        self.assertEqual(tuple(item.location for item in transition.after.items), (L.CARRIED, L.CARRIED, L.HELD))
        self.assertEqual(tuple(item.grip for item in transition.after.items), (None, None, G.BOTH))
        self.assertEqual(transition.after.active_item_id, glaive.id)
        self.assertIs(transition.before, before)
        self.assertEqual(tuple(item.location for item in before.items), (L.HELD, L.HELD, L.CARRIED))
        self.assertEqual(apply_incidental_equip(WeaponEquipTurnState(1, 'pc'), transition),
            WeaponEquipTurnState(1, 'pc', True))
        with self.assertRaises(FrozenInstanceError):
            transition.actor_id = 'npc'

    def test_reverse_draws_two_real_items_and_allows_no_preselected_attack(self):
        initial = three_weapons()
        sword, dagger, glaive = initial.items
        first = plan_weapon_equip('pc', 1, initial, held_items=((glaive.id, G.BOTH),),
            active_item_id=glaive.id, usable_hands=(G.LEFT, G.RIGHT))
        second = plan_weapon_equip('pc', 2, first.after,
            held_items=((sword.id, G.RIGHT), (dagger.id, G.LEFT)), active_item_id=None,
            usable_hands=(G.LEFT, G.RIGHT))
        self.assertEqual(tuple(item.grip for item in second.after.items), (G.RIGHT, G.LEFT, None))
        self.assertIsNone(second.after.active)
        self.assertTrue(second.changes_equipment)
        self.assertEqual(tuple(item.id for item in second.after.items), tuple(item.id for item in initial.items))

    def test_change_variable_grip_without_replacing_or_redrawing_the_item(self):
        before = initial_weapon_inventory('pc', (
            WeaponItemSource('spear', W.FOOT_SPEAR, L.HELD, G.LEFT),))
        item, = before.items
        changed = plan_weapon_equip('pc', 1, before, held_items=((item.id, G.BOTH),),
            active_item_id=item.id, usable_hands=(G.LEFT, G.RIGHT))
        self.assertIs(changed.after.active.grip, G.BOTH)
        self.assertIs(changed.after.active.source, item.source)
        with self.assertRaises(ValueError):
            plan_weapon_equip('pc', 1, before, held_items=((item.id, G.BOTH),),
                active_item_id=item.id, usable_hands=(G.LEFT,))

    def test_no_usable_hands_can_stow_but_cannot_leave_any_weapon_held(self):
        before = three_weapons()
        transition = plan_weapon_equip('pc', 1, before, held_items=(), active_item_id=None, usable_hands=())
        self.assertTrue(all(item.location is L.CARRIED for item in transition.after.items))
        with self.assertRaises(ValueError):
            plan_weapon_equip('pc', 1, before, held_items=((before.items[0].id, G.LEFT),),
                active_item_id=None, usable_hands=())

    def test_reload_charges_and_dragon_activation_are_preserved_across_the_entire_inventory(self):
        before = initial_weapon_inventory('pc', (
            WeaponItemSource('pistol', W.PISTOL, L.HELD, G.LEFT, initially_loaded=False),
            WeaponItemSource('scarab', W.SCARAB_KNIFE, L.HELD, G.RIGHT, initial_charges=3),
            WeaponItemSource('dragon', W.DRAGON_BOW, L.CARRIED, None)))
        pistol, scarab, dragon = before.items
        partial = actual_reload(pistol.reload, (1, 1))
        before = before.with_item(replace(pistol, reload=partial.state))
        before = before.with_item(replace(scarab, charges=1))
        before = before.with_item(replace(dragon, dragon_arrow_used=True))
        changed = plan_weapon_equip('pc', 4, before, held_items=((dragon.id, G.BOTH),),
            active_item_id=None, usable_hands=(G.LEFT, G.RIGHT))
        self.assertIs(changed.after.item(pistol.id).reload, before.item(pistol.id).reload)
        self.assertIs(changed.after.item(pistol.id).reload, partial.state)
        self.assertEqual(changed.after.item(pistol.id).reload.exacting.accumulated_successes, 2)
        self.assertEqual(changed.after.item(pistol.id).reload.exacting.contributions,
            (partial.exacting.contribution,))
        self.assertEqual(changed.after.item(scarab.id).charges, 1)
        self.assertTrue(changed.after.item(dragon.id).dragon_arrow_used)
        for old, new in zip(before.items, changed.after.items, strict=True):
            self.assertIs(new.source, old.source)

    def test_direct_transition_cannot_reload_refill_spend_or_reset_an_item(self):
        before = initial_weapon_inventory('pc', (
            WeaponItemSource('pistol', W.PISTOL, L.CARRIED, None, initially_loaded=False),
            WeaponItemSource('scarab', W.SCARAB_KNIFE, L.CARRIED, None, initial_charges=3),
            WeaponItemSource('dragon', W.DRAGON_BOW, L.CARRIED, None)))
        pistol, scarab, dragon = before.items
        partial = actual_reload(pistol.reload, (1, 1))
        completed = actual_reload(partial.state, (1,), round_number=2)
        before = before.with_item(replace(pistol, reload=partial.state))
        before = before.with_item(replace(scarab, charges=1))
        before = before.with_item(replace(dragon, dragon_arrow_used=True))
        forged_units = (replace(before.items[0], reload=pistol.reload),
            replace(before.items[0], reload=completed.state),
            replace(before.items[1], charges=3), replace(before.items[1], charges=0),
            replace(before.items[2], dragon_arrow_used=False))
        for unit in forged_units:
            with self.subTest(unit=unit.id, reload=unit.reload, charges=unit.charges), self.assertRaises(ValueError):
                after = replace(before, items=tuple(unit if old.id == unit.id else old for old in before.items))
                WeaponEquipTransition('pc', 1, before, after)

    def test_ground_deployed_stuck_and_spent_units_never_enter_the_free_draw_path(self):
        for location in (L.DROPPED, L.DEPLOYED, L.STUCK, L.SPENT):
            with self.subTest(location=location):
                before = initial_weapon_inventory('pc', (
                    WeaponItemSource('rock', W.ROCK, L.CARRIED, None),
                    WeaponItemSource('sword', W.SWORD, L.CARRIED, None)))
                rock, sword = before.items
                before = before.with_item(replace(rock, location=location))
                transition = plan_weapon_equip('pc', 1, before, held_items=((sword.id, G.LEFT),),
                    active_item_id=sword.id, usable_hands=(G.LEFT,))
                self.assertEqual(transition.after.items[0], before.items[0])
                with self.assertRaises(ValueError):
                    plan_weapon_equip('pc', 1, before, held_items=((rock.id, G.LEFT),),
                        active_item_id=rock.id, usable_hands=(G.LEFT,))
                forged = replace(before, items=(replace(before.items[0], location=L.CARRIED), sword))
                with self.assertRaises(ValueError):
                    WeaponEquipTransition('pc', 1, before, forged)

    def test_free_equip_preserves_selected_ground_item_without_claiming_a_pickup(self):
        before = initial_weapon_inventory('pc', (
            WeaponItemSource('selected', W.SWORD, L.HELD, G.LEFT),
            WeaponItemSource('other', W.DAGGER, L.CARRIED, None)))
        selected, other = before.items
        before = replace(before, active_item_id=selected.id)
        dropped = before.with_item(replace(selected, location=L.DROPPED, grip=None))
        self.assertEqual(dropped.active_item_id, selected.id)
        transition = plan_weapon_equip('pc', 1, dropped, held_items=((other.id, G.RIGHT),),
            active_item_id=selected.id, usable_hands=(G.RIGHT,))
        self.assertEqual(transition.after.active_item_id, selected.id)
        self.assertIs(transition.after.active.location, L.DROPPED)
        self.assertEqual(transition.after.item(selected.id), dropped.item(selected.id))
        self.assertIs(transition.after.item(other.id).location, L.HELD)

    def test_finite_throwing_spare_is_drawn_without_refilling_the_spent_first_unit(self):
        before = initial_weapon_inventory('pc', (
            WeaponItemSource('oil', W.OIL_FLASK, L.HELD, G.LEFT, quantity=2),))
        first, spare = before.items
        before = before.with_item(replace(first, location=L.SPENT, grip=None))
        transition = plan_weapon_equip('pc', 1, before, held_items=((spare.id, G.LEFT),),
            active_item_id=spare.id, usable_hands=(G.LEFT,))
        self.assertEqual(len(transition.after.items), 2)
        self.assertEqual(transition.after.items[0], before.items[0])
        self.assertIs(transition.after.items[0].location, L.SPENT)
        self.assertEqual(transition.after.active.id, spare.id)

    def test_shield_hand_is_unchanged_and_still_blocks_conflicting_weapons(self):
        before = initial_weapon_inventory('pc', (
            WeaponItemSource('sword', W.SWORD, L.HELD, G.LEFT),
            WeaponItemSource('glaive', W.GLAIVE, L.CARRIED, None)), shield_hand=G.RIGHT)
        sword, glaive = before.items
        for held in (((sword.id, G.RIGHT),), ((glaive.id, G.BOTH),)):
            with self.subTest(held=held), self.assertRaises(ValueError):
                plan_weapon_equip('pc', 1, before, held_items=held,
                    active_item_id=None, usable_hands=(G.LEFT, G.RIGHT))
        with self.assertRaises(ValueError):
            WeaponEquipTransition('pc', 1, before, replace(before, shield_hand=None))

    def test_transition_cannot_replace_reorder_add_remove_or_drop_source_units(self):
        before = three_weapons()
        sword, dagger, glaive = before.items
        replacements = (replace(before, items=(dagger, sword, glaive)),
            replace(before, items=(sword, dagger)),
            replace(before, items=(*before.items, initial_weapon_inventory('other', (
                WeaponItemSource('axe', W.AXE, L.CARRIED, None),)).items[0])),
            replace(before, items=(replace(sword, location=L.DROPPED, grip=None), dagger, glaive)),
            replace(before, items=(replace(sword, source=WeaponItemSource('sword', W.AXE, L.HELD, G.LEFT)), dagger, glaive)))
        for after in replacements:
            with self.subTest(items=len(after.items)), self.assertRaises(ValueError):
                WeaponEquipTransition('pc', 1, before, after)

    def test_active_selection_and_identity_transition_do_not_spend_equip_allowance(self):
        before = three_weapons()
        sword, dagger, _ = before.items
        selected = plan_weapon_equip('pc', 1, before,
            held_items=((sword.id, G.LEFT), (dagger.id, G.RIGHT)), active_item_id=dagger.id,
            usable_hands=(G.LEFT, G.RIGHT))
        self.assertFalse(selected.changes_equipment)
        for used in (False, True):
            state = WeaponEquipTurnState(1, 'pc', used)
            self.assertIs(apply_incidental_equip(state, selected), state)
            self.assertIs(apply_incidental_equip(state, WeaponEquipTransition('pc', 1, before, before)), state)
        with self.assertRaises(ValueError):
            plan_weapon_equip('pc', 1, before,
                held_items=((sword.id, G.LEFT), (dagger.id, G.RIGHT)), active_item_id=None,
                usable_hands=(G.LEFT, G.RIGHT))

    def test_turn_budget_checks_actor_round_and_once_without_claiming_global_inventory_membership(self):
        before = three_weapons()
        changed = plan_weapon_equip('pc', 3, before, held_items=(), active_item_id=None,
            usable_hands=())
        state = WeaponEquipTurnState(3, 'pc')
        used = apply_incidental_equip(state, changed)
        with self.assertRaises(ValueError):
            apply_incidental_equip(used, changed)
        for other in (WeaponEquipTurnState(2, 'pc'), WeaponEquipTurnState(3, 'npc')):
            with self.subTest(other=other), self.assertRaises(ValueError):
                apply_incidental_equip(other, changed)
        self.assertFalse(state.incidental_used)
        self.assertEqual(used, WeaponEquipTurnState(3, 'pc', True))

    def test_foreign_origin_is_preserved_without_confusing_provenance_with_current_actor(self):
        before = initial_weapon_inventory('original:npc', (
            WeaponItemSource('sword', W.SWORD, L.CARRIED, None),))
        item, = before.items
        changed = plan_weapon_equip('recipient:pc', 1, before, held_items=((item.id, G.RIGHT),),
            active_item_id=item.id, usable_hands=(G.RIGHT,))
        self.assertEqual(changed.after.active.initial_actor_id, 'original:npc')
        self.assertEqual(changed.after.active.id, item.id)
        self.assertIs(changed.after.active.source, item.source)

    def test_exact_types_invalid_hands_and_invented_choices_are_rejected(self):
        before = three_weapons()
        sword = before.items[0]
        options = (dict(actor_id=True), dict(round_number=True), dict(held_items=[]),
            dict(held_items=([sword.id, G.LEFT],)), dict(held_items=((sword.id, 'left'),)),
            dict(held_items=((sword.id, G.LEFT), (sword.id, G.RIGHT))),
            dict(held_items=(('invented', G.LEFT),)), dict(usable_hands=[G.LEFT]),
            dict(usable_hands=(G.BOTH,)), dict(usable_hands=(G.LEFT, G.LEFT)),
            dict(active_item_id='invented'))
        for changed in options:
            kwargs = dict(actor_id='pc', round_number=1, inventory=before,
                held_items=((sword.id, G.LEFT),), active_item_id=sword.id, usable_hands=(G.LEFT, G.RIGHT))
            kwargs.update(changed)
            with self.subTest(changed=changed), self.assertRaises((TypeError, ValueError)):
                plan_weapon_equip(**kwargs)
        with self.assertRaises(TypeError):
            WeaponEquipTurnState(1, 'pc', 1)
        with self.assertRaises(TypeError):
            apply_incidental_equip({}, WeaponEquipTransition('pc', 1, before, before))
        with self.assertRaises(ValueError):
            WeaponEquipTransition('pc', 0, before, before)


if __name__ == '__main__':
    unittest.main()
