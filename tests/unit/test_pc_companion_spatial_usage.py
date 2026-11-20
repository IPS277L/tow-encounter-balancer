"""Pure same-round budget snapshots, not native remount/retention admission."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pickle import dumps, loads
import unittest

from tests.unit.test_pc_companion_actor_queries import companion
from towr.domain.pc_battlefield_models import PcBattlefieldState
from towr.domain.pc_companion_usage_models import (
    PcMountCompanionSpatialUsage, capture_companion_usage, restore_companion_usage,
)
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.turn_models import CombatSide


ACTOR = 'rider:mount'


def battlefield(*, round_number=3, actor_present=True):
    graph = ZoneGraph(('ground0', 'ground1', 'sky0', 'sky1'),
        (ZoneConnection('ground0', 'ground1'), ZoneConnection('sky0', 'sky1'),
            ZoneConnection('ground0', 'sky0'), ZoneConnection('ground1', 'sky1')))
    placements = (SpatialEntityPlacement('rider', 'players_and_allies', 'ground0'),
        SpatialEntityPlacement('foe', 'opposition', 'ground1'),
        SpatialEntityPlacement('item:marker', 'objects', 'ground1'))
    if actor_present:
        placements = (*placements, SpatialEntityPlacement(ACTOR, 'players_and_allies', 'ground0'))
    spatial = SpatialBattleState(graph, placements, round_number,
        gave_ground_entity_ids=('foe',), free_move_used_entity_ids=('rider',))
    return PcBattlefieldState(spatial, (('foe', ACTOR), ('rider', ACTOR)) if actor_present else (),
        air_to_ground=(('sky0', 'ground0'), ('sky1', 'ground1')))


def spent(battlefield):
    return replace(battlefield, spatial=replace(battlefield.spatial,
        gave_ground_entity_ids=(ACTOR, 'foe'), free_move_used_entity_ids=('rider', ACTOR),
        difficult_terrain_tested_entity_ids=(ACTOR,)))


class PcCompanionSpatialUsageTests(unittest.TestCase):
    def test_snapshot_is_exact_immutable_picklable_and_capture_does_not_mutate_geometry(self):
        current = spent(battlefield())
        before = deepcopy(current)
        usage = capture_companion_usage(current, ACTOR)
        self.assertEqual(usage, PcMountCompanionSpatialUsage(ACTOR, 3, True, True, True))
        self.assertEqual(loads(dumps(usage)), usage)
        self.assertEqual(current, before)
        with self.assertRaises(FrozenInstanceError):
            usage.gave_ground = False
        fresh = capture_companion_usage(battlefield(), ACTOR)
        self.assertEqual(fresh, PcMountCompanionSpatialUsage(ACTOR, 3, False, False, False))

    def test_same_round_restore_reinstates_exactly_three_budgets_once_preserving_other_ids(self):
        initial = spent(battlefield())
        usage = capture_companion_usage(initial, ACTOR)
        # A remount owner removes placement/IDs; a later retention owner has
        # restored only the physical placement before this pure budget step.
        restored_placement = battlefield()
        before = deepcopy(restored_placement)
        restored = restore_companion_usage(restored_placement, ACTOR, usage)
        self.assertEqual(restored.spatial.gave_ground_entity_ids, ('foe', ACTOR))
        self.assertEqual(restored.spatial.free_move_used_entity_ids, ('rider', ACTOR))
        self.assertEqual(restored.spatial.difficult_terrain_tested_entity_ids, (ACTOR,))
        self.assertIs(restored.spatial.graph, restored_placement.spatial.graph)
        self.assertEqual(restored.spatial.placements, restored_placement.spatial.placements)
        self.assertEqual(restored.close_pairs, restored_placement.close_pairs)
        self.assertEqual(restored.air_to_ground, restored_placement.air_to_ground)
        self.assertEqual(restored.spatial.round_number, restored_placement.spatial.round_number)
        self.assertEqual(restored_placement, before)
        self.assertIs(restore_companion_usage(restored, ACTOR, usage), restored)
        for ids in (restored.spatial.gave_ground_entity_ids, restored.spatial.free_move_used_entity_ids,
                restored.spatial.difficult_terrain_tested_entity_ids):
            self.assertEqual(ids.count(ACTOR), 1)

    def test_partial_flags_restore_only_their_budget_and_never_erase_current_usage(self):
        current = battlefield()
        for flags, expected in (((True, False, False), (('foe', ACTOR), ('rider',), ())),
                ((False, True, False), (('foe',), ('rider', ACTOR), ())),
                ((False, False, True), (('foe',), ('rider',), (ACTOR,)))):
            with self.subTest(flags=flags):
                restored = restore_companion_usage(current, ACTOR, PcMountCompanionSpatialUsage(ACTOR, 3, *flags))
                self.assertEqual((restored.spatial.gave_ground_entity_ids,
                    restored.spatial.free_move_used_entity_ids,
                    restored.spatial.difficult_terrain_tested_entity_ids), expected)
        already_used = spent(current)
        unused = PcMountCompanionSpatialUsage(ACTOR, 3, False, False, False)
        self.assertIs(restore_companion_usage(already_used, ACTOR, unused), already_used)

    def test_old_round_does_not_transfer_spends_and_future_round_cannot_be_restored(self):
        current = battlefield(round_number=4)
        previous = PcMountCompanionSpatialUsage(ACTOR, 3, True, True, True)
        self.assertIs(restore_companion_usage(current, ACTOR, previous), current)
        self.assertIs(restore_companion_usage(spent(current), ACTOR, previous).spatial.graph, current.spatial.graph)
        self.assertEqual(restore_companion_usage(spent(current), ACTOR, previous), spent(current))
        future = replace(previous, round_number=5)
        with self.assertRaises(ValueError):
            restore_companion_usage(current, ACTOR, future)

    def test_actor_must_have_a_real_existing_placement_and_match_the_saved_source(self):
        current = battlefield()
        usage = capture_companion_usage(current, ACTOR)
        for actor in ('rider', 'foe'):
            with self.subTest(actor=actor), self.assertRaises(ValueError):
                restore_companion_usage(current, actor, usage)
        for missing in (ACTOR, 'foreign'):
            no_mount = battlefield(actor_present=False)
            with self.subTest(capture=missing), self.assertRaises(ValueError):
                capture_companion_usage(no_mount, missing)
            with self.subTest(restore=missing), self.assertRaises(ValueError):
                restore_companion_usage(no_mount, missing, usage)
        for invalid in (None, True, '', 1):
            with self.subTest(actor=invalid), self.assertRaises(TypeError):
                capture_companion_usage(current, invalid)

    def test_flags_round_actor_and_cached_storage_reject_aliases(self):
        valid = PcMountCompanionSpatialUsage(ACTOR, 3, True, False, True)
        for changes in (dict(actor_id=True), dict(actor_id=''), dict(round_number=True),
                dict(round_number=0), dict(round_number=-1), dict(gave_ground=1),
                dict(free_move_used='false'), dict(difficult_terrain_tested=None)):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(valid, **changes)
        for field, value in (('actor_id', True), ('round_number', False), ('gave_ground', 1)):
            cached = deepcopy(valid)
            object.__setattr__(cached, field, value)
            with self.subTest(cached=field), self.assertRaises((TypeError, ValueError)):
                restore_companion_usage(battlefield(), ACTOR, cached)
        for invalid in (None, True, {}, (ACTOR, 3, True, False, True)):
            with self.subTest(usage=invalid), self.assertRaises(TypeError):
                restore_companion_usage(battlefield(), ACTOR, invalid)

    def test_companion_field_is_optional_kw_only_and_bound_to_its_full_npc_source(self):
        row = companion('rider', CombatSide.PLAYERS_AND_ALLIES)
        self.assertIsNone(row.stored_spatial_usage)
        usage = capture_companion_usage(spent(battlefield()), ACTOR)
        saved = replace(row, stored_spatial_usage=usage)
        self.assertEqual(saved.snapshot, row.snapshot)
        self.assertEqual(saved.retained_since_round, row.retained_since_round)
        self.assertEqual(loads(dumps(saved)), saved)
        with self.assertRaises(TypeError):
            type(row)(row.rider_id, row.snapshot, row.retained_since_round, usage)
        for invalid in (True, {}, replace(usage, actor_id='other:mount')):
            with self.subTest(stored=invalid), self.assertRaises((TypeError, ValueError)):
                replace(row, stored_spatial_usage=invalid)
        cached = deepcopy(saved)
        object.__setattr__(cached.stored_spatial_usage, 'free_move_used', 1)
        with self.assertRaises(TypeError):
            replace(cached)

    def test_cached_spatial_membership_duplicates_and_wrong_container_types_reject(self):
        current = battlefield()
        for field, value in (('gave_ground_entity_ids', [ACTOR]),
                ('free_move_used_entity_ids', (ACTOR, ACTOR)),
                ('difficult_terrain_tested_entity_ids', ('foreign',)),
                ('round_number', True)):
            cached = deepcopy(current)
            object.__setattr__(cached.spatial, field, value)
            with self.subTest(field=field), self.assertRaises((TypeError, ValueError)):
                capture_companion_usage(cached, ACTOR)
        cached = deepcopy(current)
        object.__setattr__(cached, 'spatial', True)
        with self.assertRaises(TypeError):
            capture_companion_usage(cached, ACTOR)
        with self.assertRaises(TypeError):
            capture_companion_usage(True, ACTOR)


if __name__ == '__main__':
    unittest.main()
