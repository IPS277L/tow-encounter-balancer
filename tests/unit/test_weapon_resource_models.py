"""Common item resources consume one selected weapon and bridge actual K1 work."""
from dataclasses import FrozenInstanceError, replace
import unittest

from tests.support.weapon_reload import execute_scripted_weapon_reload as actual_reload
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.reload_models import (
    begin_reload_cycle, create_initial_ranged_weapon_reload_state,
)
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_equip_models import plan_weapon_equip
from towr.domain.weapon_inventory_models import (
    WeaponGrip as G, WeaponItemLocation as L, WeaponItemSource,
    initial_weapon_inventory, weapon_reload_cycle_id,
)
from towr.domain.weapon_resource_models import (
    WeaponShotResourceTransition, WeaponReloadResourceTransition,
    prepare_weapon_shot_resources, apply_weapon_shot_resources, apply_weapon_reload_result,
)
from towr.domain.weapon_use_models import build_weapon_use


def gun_inventory(kind=W.PISTOL, *, loaded=True, shield_hand=None):
    source = WeaponItemSource('gun', kind, L.HELD, G.LEFT, initially_loaded=loaded)
    return initial_weapon_inventory('pc', (source,), shield_hand=shield_hand)


def first_empty_kernel(item, *, weapon_id=None, instance_id=None):
    """Use the authoritative unit state; overrides construct negative sources."""
    if weapon_id is None and instance_id is None:
        return item.reload
    loaded = create_initial_ranged_weapon_reload_state(instance_id or item.id,
        weapon_id or RangedWeaponId(item.kind.value))
    return begin_reload_cycle(loaded, weapon_reload_cycle_id(loaded.weapon_instance_id,1))


class WeaponResourceModelsTests(unittest.TestCase):
    def test_two_loaded_pistols_consume_only_the_actual_primary_not_the_active_label(self):
        before = initial_weapon_inventory('pc', (
            WeaponItemSource('left', W.PISTOL, L.HELD, G.LEFT, initially_loaded=True),
            WeaponItemSource('right', W.PISTOL, L.HELD, G.RIGHT, initially_loaded=True)))
        left, right = before.items
        before = replace(before, active_item_id=left.id)
        use = build_weapon_use('pc', before, right.id)
        transition = prepare_weapon_shot_resources(use)
        after = apply_weapon_shot_resources(before, transition)
        self.assertEqual(after.item(left.id), left)
        self.assertEqual(after.item(right.id).reload,
            begin_reload_cycle(right.reload,weapon_reload_cycle_id(right.id,1)))
        self.assertEqual(after.active_item_id, left.id)
        self.assertTrue(before.item(right.id).reload.loaded)
        with self.assertRaises(ValueError):
            apply_weapon_shot_resources(after, transition)
        with self.assertRaises(ValueError):
            prepare_weapon_shot_resources(build_weapon_use('pc', after, right.id))

    def test_repeater_bonus_opens_only_its_actual_target_cycle(self):
        for kind, target in ((W.REPEATER_HANDBOW, 3), (W.REPEATER_PISTOL, 3),
                (W.REPEATER_HANDGUN, 5), (W.REPEATER_CROSSBOW, 3)):
            with self.subTest(kind=kind):
                grip = G.BOTH if kind in (W.REPEATER_HANDGUN, W.REPEATER_CROSSBOW) else G.LEFT
                before = initial_weapon_inventory('pc', (
                    WeaponItemSource('repeater', kind, L.HELD, grip, initially_loaded=True),))
                use = build_weapon_use('pc', before, before.items[0].id)
                normal = prepare_weapon_shot_resources(use)
                self.assertEqual(normal.after_inventory, before)
                self.assertTrue(normal.after_inventory.items[0].reload.loaded)
                burst = prepare_weapon_shot_resources(use, uses_repeater_bonus=True)
                loaded=before.items[0].reload
                self.assertIs(normal.after_inventory.items[0].reload,loaded)
                self.assertEqual(burst.after_inventory.items[0].reload,
                    begin_reload_cycle(loaded,weapon_reload_cycle_id(before.items[0].id,1)))
                self.assertEqual(burst.after_inventory.items[0].reload.required_successes,target)
                self.assertEqual(loaded.reload_cycle_ids,())

    def test_regular_exacting_shot_preserves_prior_cycle_count_and_opens_exactly_one_more(self):
        before = gun_inventory(loaded=False)
        item, = before.items
        completed=actual_reload(item.reload,(1,1,1))
        before = before.with_item(replace(item, reload=completed.state))
        transition = prepare_weapon_shot_resources(build_weapon_use('pc', before, item.id))
        self.assertEqual(transition.after_inventory.items[0].reload,
            begin_reload_cycle(completed.state,weapon_reload_cycle_id(item.id,2)))
        self.assertEqual(transition.after_inventory.items[0].reload.reload_cycle_ids,
            (weapon_reload_cycle_id(item.id,1),weapon_reload_cycle_id(item.id,2)))
        self.assertEqual(completed.state.exacting.contributions,(completed.exacting.contribution,))
        with self.assertRaises(ValueError):
            prepare_weapon_shot_resources(build_weapon_use('pc', before, item.id), uses_repeater_bonus=True)

    def test_free_bows_have_no_invented_persistent_reload_state(self):
        for kind in (W.SHORTBOW, W.WARBOW, W.LONGBOW, W.SLING):
            with self.subTest(kind=kind):
                grip = G.LEFT if kind is W.SLING else G.BOTH
                before = initial_weapon_inventory('pc', (WeaponItemSource('bow', kind, L.HELD, grip),))
                transition = prepare_weapon_shot_resources(build_weapon_use('pc', before, before.items[0].id))
                self.assertEqual(apply_weapon_shot_resources(before, transition), before)
                self.assertIsNone(transition.after_inventory.items[0].reload)

    def test_dragon_miss_spends_once_when_applied_but_pre_test_cancellation_changes_nothing(self):
        before = initial_weapon_inventory('pc', (
            WeaponItemSource('dragon', W.DRAGON_BOW, L.HELD, G.BOTH),))
        use = build_weapon_use('pc', before, before.items[0].id)
        prepared = prepare_weapon_shot_resources(use, dragon_fire=True)
        # Preparing and then cancelling before the actual Test never applies it.
        self.assertFalse(before.items[0].dragon_arrow_used)
        self.assertEqual(prepare_weapon_shot_resources(use).after_inventory, before)
        # The actual Attack owner applies the same consequence after a miss.
        after_miss = apply_weapon_shot_resources(before, prepared)
        self.assertTrue(after_miss.items[0].dragon_arrow_used)
        used = build_weapon_use('pc', after_miss, before.items[0].id)
        self.assertEqual(prepare_weapon_shot_resources(used).after_inventory, after_miss)
        with self.assertRaises(ValueError):
            prepare_weapon_shot_resources(used, dragon_fire=True)
        with self.assertRaises(ValueError):
            apply_weapon_shot_resources(after_miss, prepared)

    def test_shot_application_requires_the_entire_before_inventory(self):
        before = initial_weapon_inventory('pc', (
            WeaponItemSource('gun', W.PISTOL, L.HELD, G.LEFT, initially_loaded=True),
            WeaponItemSource('knife', W.SCARAB_KNIFE, L.CARRIED, None, initial_charges=3)))
        gun, knife = before.items
        shot = prepare_weapon_shot_resources(build_weapon_use('pc', before, gun.id))
        stale = before.with_item(replace(knife, charges=2))
        with self.assertRaises(ValueError):
            apply_weapon_shot_resources(stale, shot)
        with self.assertRaises(ValueError):
            replace(shot, after_inventory=before)
        with self.assertRaises(FrozenInstanceError):
            shot.dragon_fire = True

    def test_actual_k1_partial_and_completed_reload_progress_are_bridged_without_another_test(self):
        before = gun_inventory(loaded=False)
        item, = before.items
        kernel = first_empty_kernel(item)
        first = actual_reload(kernel, (1, 10))
        use = build_weapon_use('pc', before, item.id)
        partial = apply_weapon_reload_result(use, first)
        self.assertIs(partial.result, first)
        self.assertIs(partial.use, use)
        self.assertTrue(first.slot.executed)
        self.assertIs(partial.after_inventory.items[0].reload,first.state)
        self.assertEqual(first.state.exacting.accumulated_successes,1)
        second = actual_reload(first.state, (1, 1), round_number=2)
        completed = apply_weapon_reload_result(build_weapon_use('pc', partial.after_inventory, item.id), second)
        self.assertIs(completed.after_inventory.items[0].reload,second.state)
        self.assertEqual(second.state.exacting.accumulated_successes,3)
        self.assertEqual(len(second.state.exacting.contributions), 2)
        self.assertEqual(second.state.exacting.contributions[0], first.exacting.contribution)
        self.assertEqual(len(first.state.exacting.contributions), 1)
        with self.assertRaises(ValueError):
            apply_weapon_reload_result(build_weapon_use('pc', partial.after_inventory, item.id), first)

    def test_actual_exacting_overshoot_is_retained_in_the_same_authoritative_state(self):
        before = gun_inventory(loaded=False)
        item, = before.items
        result = actual_reload(first_empty_kernel(item), (1,)*6)
        transition = apply_weapon_reload_result(build_weapon_use('pc', before, item.id), result)
        self.assertEqual(result.state.exacting.accumulated_successes, 6)
        self.assertIs(transition.after_inventory.items[0].reload,result.state)
        self.assertEqual(transition.after_inventory.items[0].reload.exacting.accumulated_successes,6)
        self.assertTrue(transition.after_inventory.items[0].reload.loaded)
        self.assertIs(transition.result.state.exacting, result.state.exacting)

    def test_zero_success_retains_actual_work_and_rejects_replay_of_the_same_reload(self):
        before = gun_inventory(loaded=False)
        item, = before.items
        result = actual_reload(first_empty_kernel(item), (10, 10))
        transition = apply_weapon_reload_result(build_weapon_use('pc', before, item.id), result)
        self.assertNotEqual(transition.after_inventory,before)
        self.assertIs(transition.after_inventory.items[0].reload,result.state)
        self.assertTrue(transition.result.slot.executed)
        self.assertEqual(len(transition.result.state.exacting.contributions), 1)
        self.assertEqual(transition.result.exacting.contribution.successes, 0)
        with self.assertRaises(ValueError):
            apply_weapon_reload_result(build_weapon_use('pc',transition.after_inventory,item.id),result)
        # A different zero-success history with the same success count and
        # cycle cannot substitute for the actual previous K1 state either.
        alternate=actual_reload(item.reload,(10,10),round_number=2)
        different=before.with_item(replace(item,reload=alternate.state))
        followup=actual_reload(result.state,(1,10),round_number=3)
        with self.assertRaises(ValueError):
            apply_weapon_reload_result(build_weapon_use('pc',different,item.id),followup)

    def test_reload_bridge_rejects_wrong_actor_item_profile_previous_progress_and_cycle(self):
        before = gun_inventory(loaded=False)
        item, = before.items
        use = build_weapon_use('pc', before, item.id)
        initial = first_empty_kernel(item)
        wrong = (actual_reload(initial, actor='other'),
            actual_reload(first_empty_kernel(item, instance_id='other:item')),
            actual_reload(first_empty_kernel(item, weapon_id=RangedWeaponId.CROSSBOW)))
        for result in wrong:
            with self.subTest(actor=result.source_request.actor_id,
                    item=result.previous_state.weapon_instance_id, profile=result.previous_state.weapon_id), self.assertRaises(ValueError):
                apply_weapon_reload_result(use, result)
        first = actual_reload(initial, (1, 10))
        later_progress = actual_reload(first.state, (1, 10), round_number=2)
        with self.assertRaises(ValueError):
            apply_weapon_reload_result(use, later_progress)
        completed = actual_reload(initial, (1, 1, 1))
        cycle_two = begin_reload_cycle(completed.state, weapon_reload_cycle_id(item.id,2))
        other_cycle = actual_reload(cycle_two, round_number=2)
        with self.assertRaises(ValueError):
            apply_weapon_reload_result(use, other_cycle)

    def test_reload_requires_two_usable_hands_no_held_shield_and_no_other_held_weapon(self):
        bare = gun_inventory(loaded=False)
        item, = bare.items
        result = actual_reload(first_empty_kernel(item))
        with self.assertRaises(ValueError):
            apply_weapon_reload_result(build_weapon_use('pc', bare, item.id, usable_hands=(G.LEFT,)), result)
        shield = replace(bare, shield_hand=G.RIGHT)
        with self.assertRaises(ValueError):
            apply_weapon_reload_result(build_weapon_use('pc', shield, item.id), result)
        second = initial_weapon_inventory('pc', (
            WeaponItemSource('gun', W.PISTOL, L.HELD, G.LEFT, initially_loaded=False),
            WeaponItemSource('offhand', W.DAGGER, L.HELD, G.RIGHT)))
        with self.assertRaises(ValueError):
            apply_weapon_reload_result(build_weapon_use('pc', second, item.id), result)
        freed = plan_weapon_equip('pc', 1, second, held_items=((item.id, G.LEFT),),
            active_item_id=item.id, usable_hands=(G.LEFT, G.RIGHT)).after
        self.assertEqual(apply_weapon_reload_result(build_weapon_use('pc', freed, item.id), result)
            .after_inventory.items[1], freed.items[1])

    def test_two_handed_reload_accepts_its_actual_both_grip_and_preserves_clock_receipt(self):
        before = initial_weapon_inventory('pc', (
            WeaponItemSource('crossbow', W.CROSSBOW, L.HELD, G.BOTH, initially_loaded=False),))
        item, = before.items
        result = actual_reload(first_empty_kernel(item), (1, 1))
        transition = apply_weapon_reload_result(build_weapon_use('pc', before, item.id), result)
        self.assertIs(transition.after_inventory.items[0].reload,result.state)
        self.assertTrue(result.state.loaded)
        self.assertEqual(result.state.required_successes,2)
        self.assertIs(transition.result.round_state, result.round_state)
        self.assertIs(transition.after_inventory.items[0].grip, G.BOTH)

    def test_carry_drop_and_redraw_never_refill_a_shot_or_completed_exacting_history(self):
        before = gun_inventory()
        item, = before.items
        empty = apply_weapon_shot_resources(before, prepare_weapon_shot_resources(build_weapon_use('pc', before, item.id)))
        carried = plan_weapon_equip('pc', 1, empty, held_items=(), active_item_id=None,
            usable_hands=(G.LEFT, G.RIGHT)).after
        redrawn = plan_weapon_equip('pc', 2, carried, held_items=((item.id, G.LEFT),),
            active_item_id=item.id, usable_hands=(G.LEFT, G.RIGHT)).after
        dropped = redrawn.with_item(replace(redrawn.items[0], location=L.DROPPED, grip=None))
        # Paid ground pickup remains another owner; this just checks the item's
        # complete K1 state survives a legitimate location-only state update.
        recovered = dropped.with_item(replace(dropped.items[0], location=L.HELD, grip=G.LEFT))
        self.assertIs(recovered.items[0].reload,empty.items[0].reload)
        with self.assertRaises(ValueError):
            prepare_weapon_shot_resources(build_weapon_use('pc', recovered, item.id))

    def test_bridge_and_shot_reject_non_shooting_flags_aliases_and_forged_receipts(self):
        melee = initial_weapon_inventory('pc', (WeaponItemSource('sword', W.SWORD, L.HELD, G.LEFT),))
        with self.assertRaises(ValueError):
            prepare_weapon_shot_resources(build_weapon_use('pc', melee, melee.items[0].id))
        with self.assertRaises(ValueError):
            prepare_weapon_shot_resources(build_weapon_use('pc', initial_weapon_inventory('pc', ()), None))
        before = gun_inventory()
        use = build_weapon_use('pc', before, before.items[0].id)
        for choices in (dict(uses_repeater_bonus=1), dict(dragon_fire=1), dict(dragon_fire=True)):
            with self.subTest(choices=choices), self.assertRaises((TypeError, ValueError)):
                prepare_weapon_shot_resources(use, **choices)
        empty = gun_inventory(loaded=False)
        item, = empty.items
        result = actual_reload(first_empty_kernel(item))
        empty_use = build_weapon_use('pc', empty, item.id)
        with self.assertRaises(ValueError):
            replace(result, round_state=result.previous_round_state)
        with self.assertRaises(ValueError):
            WeaponReloadResourceTransition(empty_use, result, empty)
        with self.assertRaises(TypeError):
            apply_weapon_reload_result(empty_use, {})
        with self.assertRaises(TypeError):
            apply_weapon_shot_resources(before, {})
        with self.assertRaises(TypeError):
            prepare_weapon_shot_resources({})


if __name__ == '__main__':
    unittest.main()
