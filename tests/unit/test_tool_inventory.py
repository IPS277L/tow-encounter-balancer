"""Physical Musician's Gear, actual hands, ground positions and source proofs."""
from dataclasses import FrozenInstanceError, replace
import unittest

from towr.domain.tool_inventory_models import (
    ToolInventoryState, ToolInventoryTransition, ToolInventoryTransitionKind as T,
    ToolItemSource, ToolItemState, ToolKind, ToolUse, build_tool_use,
    drop_tool, equip_tool, initial_tool_inventory, pickup_tool, stow_tool, tool_item_id,
)
from towr.domain.weapon_inventory_models import WeaponGrip as G, WeaponItemLocation as L


def source(identifier='drum', *, hands=1, location=L.CARRIED, grip=None, name=None):
    return ToolItemSource(identifier, ToolKind.MUSICIANS_GEAR, hands, location, grip, name)


class ToolInventoryTests(unittest.TestCase):
    def test_empty_inventory_creates_no_instrument_from_a_prerequisite(self):
        inventory = initial_tool_inventory('pc', ())
        self.assertEqual(inventory, ToolInventoryState())
        self.assertEqual(inventory.occupied_hands, ())
        with self.assertRaises(ValueError):
            build_tool_use('pc', inventory, 'musicians_gear')
        with self.assertRaises(KeyError):
            inventory.item('missing')

    def test_initial_snapshot_retains_one_actual_item_per_ordered_source(self):
        drum = source(location=L.HELD, grip=G.RIGHT, name='My marching drum')
        flute = source('flute', hands=2)
        inventory = initial_tool_inventory('pc', (drum, flute))
        self.assertEqual(inventory.items, (
            ToolItemState(drum, 'tool-item:2:pc:4:drum', 'pc', 'drum', L.HELD, G.RIGHT),
            ToolItemState(flute, 'tool-item:2:pc:5:flute', 'pc', 'flute', L.CARRIED, None),
        ))
        self.assertIs(inventory.items[0].source, drum)
        self.assertEqual(inventory.items[0].source.instrument_name, 'My marching drum')
        self.assertIs(inventory.items[0].kind, ToolKind.MUSICIANS_GEAR)
        self.assertEqual(inventory.items[1].hands_required, 2)
        self.assertEqual(inventory.occupied_hands, (G.RIGHT,))

    def test_canonical_ids_separate_actors_sources_and_colon_names(self):
        self.assertEqual(tool_item_id('pc', 'drum'), 'tool-item:2:pc:4:drum')
        self.assertNotEqual(tool_item_id('a:b', 'c'), tool_item_id('a', 'b:c'))
        self.assertNotEqual(tool_item_id('pc', 'drum'), tool_item_id('npc', 'drum'))
        self.assertNotEqual(tool_item_id('pc', 'drum'), tool_item_id('pc', 'flute'))
        with self.assertRaises(ValueError):
            initial_tool_inventory('pc', (source('same'), source('same', hands=2)))
        for actor, item_id in ((True, 'drum'), ('pc', False), ('', 'drum'), ('pc', ' ')):
            with self.subTest(actor=actor, item_id=item_id), self.assertRaises(TypeError):
                tool_item_id(actor, item_id)

    def test_sources_are_immutable_and_new_battles_have_independent_states(self):
        original = source(location=L.HELD, grip=G.LEFT)
        first = initial_tool_inventory('pc', (original,))
        second = initial_tool_inventory('pc', (original,))
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first.items[0], second.items[0])
        dropped = drop_tool('pc', first, first.items[0].id, actor_zone_id='yard').after
        self.assertIs(dropped.items[0].location, L.DROPPED)
        self.assertIs(first.items[0].location, L.HELD)
        self.assertEqual(first, second)
        with self.assertRaises(FrozenInstanceError):
            original.hands_required = 2
        with self.assertRaises(FrozenInstanceError):
            first.items[0].location = L.CARRIED

    def test_sources_require_exact_typed_facts_and_actual_one_or_two_hands(self):
        valid = source()
        for fields in (dict(id=True), dict(id=' '), dict(kind='musicians_gear'),
                dict(hands_required=True), dict(hands_required=False), dict(hands_required=1.0),
                dict(initial_location='carried'), dict(initial_grip='left'),
                dict(instrument_name=True), dict(instrument_name=' ')):
            with self.subTest(fields=fields), self.assertRaises(TypeError):
                replace(valid, **fields)
        for hands in (0, 3, -1):
            with self.subTest(hands=hands), self.assertRaises(ValueError):
                source(hands=hands)
        for location in (L.DROPPED, L.DEPLOYED, L.STUCK, L.SPENT):
            with self.subTest(location=location), self.assertRaises(ValueError):
                source(location=location)

    def test_held_grips_match_the_specific_instrument_hand_requirement(self):
        for grip in (G.LEFT, G.RIGHT):
            self.assertIs(source(location=L.HELD, grip=grip).initial_grip, grip)
        self.assertIs(source(hands=2, location=L.HELD, grip=G.BOTH).initial_grip, G.BOTH)
        for hands, grip in ((1, None), (1, G.BOTH), (2, None), (2, G.LEFT), (2, G.RIGHT)):
            with self.subTest(hands=hands, grip=grip), self.assertRaises(ValueError):
                source(hands=hands, location=L.HELD, grip=grip)
        with self.assertRaises(ValueError):
            source(location=L.CARRIED, grip=G.LEFT)

    def test_runtime_location_retains_only_the_actual_dropped_zone(self):
        item = initial_tool_inventory('pc', (source(),)).items[0]
        dropped = replace(item, location=L.DROPPED, dropped_zone_id='hall')
        self.assertEqual(dropped.dropped_zone_id, 'hall')
        self.assertEqual(dropped.occupied_hands, ())
        self.assertIs(dropped.source, item.source)
        for zone in (None, '', ' ', True):
            with self.subTest(zone=zone), self.assertRaises(TypeError):
                replace(item, location=L.DROPPED, dropped_zone_id=zone)
        with self.assertRaises(ValueError):
            replace(item, dropped_zone_id='hall')
        with self.assertRaises(ValueError):
            replace(dropped, grip=G.LEFT)
        for location in (L.DEPLOYED, L.STUCK, L.SPENT):
            with self.subTest(location=location), self.assertRaises(ValueError):
                replace(item, location=location)

    def test_inventory_rejects_malformed_containers_duplicate_units_and_cached_ids(self):
        inventory = initial_tool_inventory('pc', (source(),))
        item, = inventory.items
        for items in ([item], (True,), (item.source,)):
            with self.subTest(items=items), self.assertRaises(TypeError):
                ToolInventoryState(items)
        with self.assertRaises(ValueError):
            ToolInventoryState((item, item))
        with self.assertRaises(TypeError):
            initial_tool_inventory('pc', [source()])
        with self.assertRaises(TypeError):
            initial_tool_inventory('pc', (True,))
        for fields in (dict(id='invented'), dict(source_item_id='other'),
                dict(initial_actor_id='other')):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                replace(item, **fields)
        with self.assertRaises(TypeError):
            replace(item, source=True)
        with self.assertRaises(TypeError):
            replace(item, source_item_id=True)

    def test_two_held_tools_occupy_distinct_hands_without_automatic_stowing(self):
        inventory = initial_tool_inventory('pc', (
            source('left', location=L.HELD, grip=G.LEFT),
            source('right', location=L.HELD, grip=G.RIGHT)))
        self.assertEqual(inventory.occupied_hands, (G.LEFT, G.RIGHT))
        self.assertEqual(inventory.items[0].occupied_hands, (G.LEFT,))
        for second in (source('other', location=L.HELD, grip=G.LEFT),
                source('other', hands=2, location=L.HELD, grip=G.BOTH)):
            with self.subTest(second=second), self.assertRaises(ValueError):
                initial_tool_inventory('pc', (inventory.items[0].source, second))
        two_handed = initial_tool_inventory('pc', (
            source(hands=2, location=L.HELD, grip=G.BOTH),))
        self.assertEqual(two_handed.occupied_hands, (G.LEFT, G.RIGHT))

    def test_inventory_update_preserves_whole_source_origin_and_order(self):
        inventory = initial_tool_inventory('pc', (source(), source('spare')))
        item, spare = inventory.items
        held = replace(item, location=L.HELD, grip=G.RIGHT)
        updated = inventory.with_item(held)
        self.assertEqual(updated.items, (held, spare))
        self.assertIs(updated.items[1], spare)
        for changed_source in (replace(item.source, hands_required=2),
                replace(item.source, instrument_name='forged label'),
                replace(item.source, initial_location=L.HELD, initial_grip=G.LEFT)):
            with self.subTest(source=changed_source), self.assertRaises(ValueError):
                inventory.with_item(replace(item, source=changed_source))
        foreign = initial_tool_inventory('other', (source(),)).items[0]
        with self.assertRaises(KeyError):
            inventory.with_item(foreign)
        with self.assertRaises(TypeError):
            inventory.with_item(True)

    def test_foreign_tool_retains_origin_without_treating_origin_as_permission(self):
        original = initial_tool_inventory('npc', (source(),)).items[0]
        held = replace(original, location=L.HELD, grip=G.RIGHT)
        recipient = ToolInventoryState((held,))
        use = build_tool_use('ally', recipient, held.id, usable_hands=(G.RIGHT,))
        self.assertEqual(use.actor_id, 'ally')
        self.assertEqual(use.item.initial_actor_id, 'npc')
        self.assertEqual(use.item.source_item_id, 'drum')
        self.assertIs(use.item.source, original.source)

    def test_use_requires_the_current_held_item_and_all_its_usable_hands(self):
        inventory = initial_tool_inventory('pc', (source(location=L.HELD, grip=G.RIGHT),))
        item, = inventory.items
        use = build_tool_use('pc', inventory, item.id, usable_hands=(G.RIGHT,))
        self.assertIs(type(use), ToolUse)
        self.assertIs(use.inventory, inventory)
        self.assertIs(use.item, item)
        self.assertIs(use.kind, ToolKind.MUSICIANS_GEAR)
        self.assertEqual(use.used_hands, (G.RIGHT,))
        for usable in ((), (G.LEFT,)):
            with self.subTest(usable=usable), self.assertRaises(ValueError):
                build_tool_use('pc', inventory, item.id, usable_hands=usable)
        with self.assertRaises(ValueError):
            build_tool_use('pc', inventory, 'absent')
        for current in (stow_tool('pc', inventory, item.id).after,
                drop_tool('pc', inventory, item.id, actor_zone_id='yard').after):
            with self.subTest(location=current.items[0].location), self.assertRaises(ValueError):
                build_tool_use('pc', current, item.id)
        both = initial_tool_inventory('npc', (source(hands=2, location=L.HELD, grip=G.BOTH),))
        self.assertEqual(build_tool_use('npc', both, both.items[0].id,
            usable_hands=(G.RIGHT, G.LEFT)).used_hands, (G.LEFT, G.RIGHT))
        with self.assertRaises(ValueError):
            build_tool_use('npc', both, both.items[0].id, usable_hands=(G.RIGHT,))

    def test_use_rejects_bool_string_and_duplicate_hand_facts(self):
        inventory = initial_tool_inventory('pc', (source(location=L.HELD, grip=G.LEFT),))
        item_id = inventory.items[0].id
        for hands in ([G.LEFT], ('left',), (True,)):
            with self.subTest(hands=hands), self.assertRaises(TypeError):
                build_tool_use('pc', inventory, item_id, usable_hands=hands)
        for hands in ((G.BOTH,), (G.LEFT, G.LEFT)):
            with self.subTest(hands=hands), self.assertRaises(ValueError):
                build_tool_use('pc', inventory, item_id, usable_hands=hands)
        for fields in (dict(actor_id=True), dict(item_id=True), dict(inventory=True)):
            with self.subTest(fields=fields), self.assertRaises(TypeError):
                replace(build_tool_use('pc', inventory, item_id), **fields)

    def test_nested_sources_and_cached_facts_are_readmitted_before_use(self):
        for attribute, value in (('hands_required', True), ('kind', 'musicians_gear'),
                ('initial_location', 'carried'), ('instrument_name', False)):
            inventory = initial_tool_inventory('pc', (source(location=L.HELD, grip=G.LEFT),))
            object.__setattr__(inventory.items[0].source, attribute, value)
            with self.subTest(attribute=attribute), self.assertRaises(TypeError):
                build_tool_use('pc', inventory, inventory.items[0].id)
        inventory = initial_tool_inventory('pc', (source(location=L.HELD, grip=G.LEFT),))
        object.__setattr__(inventory.items[0], 'source_item_id', 'another')
        with self.assertRaises(ValueError):
            build_tool_use('pc', inventory, inventory.items[0].id)
        broken = source()
        object.__setattr__(broken, 'id', [])
        with self.assertRaises(TypeError):
            initial_tool_inventory('pc', (broken,))

    def test_equip_and_stow_change_one_item_without_rebuilding_spares(self):
        inventory = initial_tool_inventory('pc', (source(), source('spare')))
        first, spare = inventory.items
        equipped = equip_tool('pc', inventory, first.id, G.LEFT, usable_hands=(G.LEFT,))
        self.assertIs(type(equipped), ToolInventoryTransition)
        self.assertIs(equipped.kind, T.EQUIP)
        self.assertIs(equipped.before, inventory)
        self.assertEqual(equipped.after.items[0].occupied_hands, (G.LEFT,))
        self.assertIs(equipped.after.items[1], spare)
        self.assertIs(equipped.after.items[0].source, first.source)
        self.assertEqual(equipped.usable_hands, (G.LEFT,))
        stowed = stow_tool('pc', equipped.after, first.id)
        self.assertIs(stowed.kind, T.STOW)
        self.assertEqual(stowed.after, inventory)
        self.assertEqual(equipped.after.occupied_hands, (G.LEFT,))
        self.assertIsNone(stowed.zone_id)
        with self.assertRaises(ValueError):
            stow_tool('pc', stowed.after, first.id)
        with self.assertRaises(ValueError):
            equip_tool('pc', equipped.after, first.id, G.LEFT)

    def test_equip_cannot_free_a_hand_or_use_a_missing_hand_implicitly(self):
        inventory = initial_tool_inventory('pc', (
            source('held', location=L.HELD, grip=G.LEFT), source('carried')))
        item_id = inventory.items[1].id
        with self.assertRaises(ValueError):
            equip_tool('pc', inventory, item_id, G.LEFT)
        with self.assertRaises(ValueError):
            equip_tool('pc', inventory, item_id, G.RIGHT, usable_hands=(G.LEFT,))
        equipped = equip_tool('pc', inventory, item_id, G.RIGHT)
        self.assertEqual(equipped.after.occupied_hands, (G.LEFT, G.RIGHT))
        both = initial_tool_inventory('pc', (source(hands=2),))
        for grip, hands in ((G.LEFT, (G.LEFT, G.RIGHT)), (G.BOTH, (G.RIGHT,))):
            with self.subTest(grip=grip, hands=hands), self.assertRaises(ValueError):
                equip_tool('pc', both, both.items[0].id, grip, usable_hands=hands)

    def test_drop_after_hand_loss_records_actual_zone_and_pickup_requires_that_zone(self):
        inventory = initial_tool_inventory('pc', (
            source(location=L.HELD, grip=G.LEFT), source('spare')))
        item, spare = inventory.items
        dropped = drop_tool('pc', inventory, item.id, actor_zone_id='gate', usable_hands=())
        self.assertIs(dropped.kind, T.DROP)
        self.assertEqual(dropped.after.items[0].dropped_zone_id, 'gate')
        self.assertEqual(dropped.after.occupied_hands, ())
        self.assertIs(dropped.after.items[1], spare)
        with self.assertRaises(ValueError):
            pickup_tool('pc', dropped.after, item.id, G.RIGHT, actor_zone_id='yard')
        with self.assertRaises(ValueError):
            pickup_tool('pc', dropped.after, item.id, G.LEFT,
                actor_zone_id='gate', usable_hands=(G.RIGHT,))
        picked = pickup_tool('pc', dropped.after, item.id, G.RIGHT,
            actor_zone_id='gate', usable_hands=(G.RIGHT,))
        self.assertIs(picked.kind, T.PICKUP)
        self.assertEqual(picked.zone_id, 'gate')
        self.assertIsNone(picked.after.items[0].dropped_zone_id)
        self.assertIs(picked.after.items[0].source, item.source)
        self.assertEqual(build_tool_use('pc', picked.after, item.id,
            usable_hands=(G.RIGHT,)).used_hands, (G.RIGHT,))

    def test_pickup_keeps_both_required_hands_and_cannot_bypass_another_tool(self):
        inventory = initial_tool_inventory('npc', (source(hands=2, location=L.HELD, grip=G.BOTH),))
        item_id = inventory.items[0].id
        dropped = drop_tool('npc', inventory, item_id, actor_zone_id='hall').after
        for grip, hands in ((G.RIGHT, (G.LEFT, G.RIGHT)), (G.BOTH, (G.LEFT,))):
            with self.subTest(grip=grip, hands=hands), self.assertRaises(ValueError):
                pickup_tool('npc', dropped, item_id, grip, actor_zone_id='hall', usable_hands=hands)
        occupied = ToolInventoryState(dropped.items + initial_tool_inventory('ally', (
            source('other', location=L.HELD, grip=G.RIGHT),)).items)
        with self.assertRaises(ValueError):
            pickup_tool('npc', occupied, item_id, G.BOTH, actor_zone_id='hall')
        picked = pickup_tool('npc', dropped, item_id, G.BOTH, actor_zone_id='hall')
        self.assertEqual(picked.after.items[0].occupied_hands, (G.LEFT, G.RIGHT))

    def test_transitions_reject_wrong_origin_location_and_repeated_changes(self):
        inventory = initial_tool_inventory('pc', (source(location=L.HELD, grip=G.LEFT),))
        item_id = inventory.items[0].id
        dropped = drop_tool('pc', inventory, item_id, actor_zone_id='yard')
        for operation in (
            lambda: drop_tool('pc', dropped.after, item_id, actor_zone_id='hall'),
            lambda: stow_tool('pc', dropped.after, item_id),
            lambda: equip_tool('pc', dropped.after, item_id, G.RIGHT),
            lambda: pickup_tool('pc', inventory, item_id, G.LEFT, actor_zone_id='yard'),
            lambda: drop_tool('pc', stow_tool('pc', inventory, item_id).after,
                item_id, actor_zone_id='yard'),
        ):
            with self.assertRaises(ValueError):
                operation()
        picked = pickup_tool('pc', dropped.after, item_id, G.RIGHT, actor_zone_id='yard')
        with self.assertRaises(ValueError):
            pickup_tool('pc', picked.after, item_id, G.RIGHT, actor_zone_id='yard')
        with self.assertRaises(ValueError):
            replace(dropped, after=inventory)
        with self.assertRaises(ValueError):
            replace(dropped, zone_id='hall')
        with self.assertRaises(TypeError):
            replace(dropped, kind='drop')
        with self.assertRaises(TypeError):
            replace(dropped, zone_id=True)
        with self.assertRaises(TypeError):
            replace(dropped, actor_id=True)

    def test_receipt_rejects_second_item_changes_reordering_or_source_replacement(self):
        inventory = initial_tool_inventory('pc', (source(), source('spare')))
        first, spare = inventory.items
        proof = equip_tool('pc', inventory, first.id, G.LEFT)
        changed_spare = replace(spare, location=L.HELD, grip=G.RIGHT)
        two_changes = ToolInventoryState((proof.after.items[0], changed_spare))
        with self.assertRaises(ValueError):
            replace(proof, after=two_changes)
        with self.assertRaises(ValueError):
            replace(proof, after=ToolInventoryState(tuple(reversed(proof.after.items))))
        forged_item = replace(proof.after.items[0], source=replace(first.source,
            instrument_name='different source'))
        with self.assertRaises(ValueError):
            replace(proof, after=ToolInventoryState((forged_item, spare)))
        with self.assertRaises(ValueError):
            replace(proof, zone_id='hall')
        with self.assertRaises(ValueError):
            replace(proof, item_id=spare.id)
        with self.assertRaises(TypeError):
            replace(proof, usable_hands=(True,))


if __name__ == '__main__':
    unittest.main()
