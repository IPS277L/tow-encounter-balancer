"""Literal spatial facts, without exercising or duplicating movement rules."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import pickle
import unittest

from towr.domain.pc_battlefield_models import (
    PcBattlefieldSpec,
    PcBattlefieldState,
    battlefield_nearby,
    battlefield_range,
    build_pc_battlefield,
    with_actor_placement,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneGraph


def arena(initial=Range.SHORT, maximum=Range.LONG):
    return build_pc_battlefield(PcBattlefieldSpec(initial, maximum),
        ('pc:a', 'pc:b'), ('npc:a', 'npc:b'), 'scene')


class PcBattlefieldModelTests(unittest.TestCase):
    def test_all_initial_ranges_have_literal_cross_side_distance_and_clustered_sides(self):
        expected_zones = {
            Range.CLOSE: 'scene:zone:0', Range.SHORT: 'scene:zone:0',
            Range.MEDIUM: 'scene:zone:1', Range.LONG: 'scene:zone:2',
            Range.EXTREME: 'scene:zone:3',
        }
        for initial, enemy_zone in expected_zones.items():
            with self.subTest(initial=initial):
                state = arena(initial)
                self.assertEqual(state.spatial.placement_for('pc:a').zone_id, 'scene:zone:0')
                self.assertEqual(state.spatial.placement_for('npc:a').zone_id, enemy_zone)
                self.assertIs(battlefield_range(state, 'pc:a', 'npc:a'), initial)
                self.assertIs(battlefield_range(state, 'npc:a', 'pc:a'), initial)
                self.assertIs(battlefield_range(state, 'pc:a', 'pc:b'), Range.CLOSE)
                self.assertIs(battlefield_range(state, 'npc:a', 'npc:b'), Range.CLOSE)
                self.assertEqual(tuple(p.entity_id for p in state.spatial.placements),
                    ('pc:a', 'pc:b', 'npc:a', 'npc:b'))
                self.assertEqual(state.spatial.placement_for('pc:a').side_id, 'players_and_allies')
                self.assertEqual(state.spatial.placement_for('npc:a').side_id, 'opposition')

    def test_line_graph_has_source_bound_ids_and_three_zone_margins(self):
        state = arena(Range.MEDIUM)
        self.assertEqual(state.spatial.graph.zone_ids, tuple(
            f'scene:zone:{index}' for index in (-3, -2, -1, 0, 1, 2, 3, 4)))
        self.assertEqual(tuple((edge.first_zone_id, edge.second_zone_id)
            for edge in state.spatial.graph.connections), (
                ('scene:zone:-3', 'scene:zone:-2'), ('scene:zone:-2', 'scene:zone:-1'),
                ('scene:zone:-1', 'scene:zone:0'), ('scene:zone:0', 'scene:zone:1'),
                ('scene:zone:1', 'scene:zone:2'), ('scene:zone:2', 'scene:zone:3'),
                ('scene:zone:3', 'scene:zone:4')))
        other = build_pc_battlefield(PcBattlefieldSpec(Range.MEDIUM, Range.LONG),
            ('pc:a', 'pc:b'), ('npc:a', 'npc:b'), 'other')
        self.assertTrue(set(state.spatial.graph.zone_ids).isdisjoint(other.spatial.graph.zone_ids))

    def test_equal_zone_does_not_imply_close_and_close_is_not_transitive(self):
        source = arena()
        state = PcBattlefieldState(source.spatial, (('pc:a', 'npc:a'), ('npc:a', 'npc:b')))
        self.assertIs(battlefield_range(state, 'pc:a', 'npc:a'), Range.CLOSE)
        self.assertIs(battlefield_range(state, 'npc:a', 'npc:b'), Range.CLOSE)
        self.assertIs(battlefield_range(state, 'pc:a', 'npc:b'), Range.SHORT)
        self.assertIs(battlefield_range(state, 'pc:a', 'pc:b'), Range.SHORT)
        self.assertEqual(battlefield_nearby(state, 'pc:a', ('npc:b', 'pc:b', 'npc:a')),
            ('npc:a',))

    def test_adjacent_zone_close_requires_explicit_link_and_canonicalises_direction(self):
        source = arena(Range.MEDIUM)
        self.assertIs(battlefield_range(source, 'pc:a', 'npc:a'), Range.MEDIUM)
        linked = PcBattlefieldState(source.spatial, (('pc:a', 'npc:a'),))
        reversed_link = PcBattlefieldState(source.spatial, (('npc:a', 'pc:a'),))
        self.assertEqual(linked, reversed_link)
        self.assertEqual(linked.close_pairs, (('npc:a', 'pc:a'),))
        self.assertIs(battlefield_range(linked, 'pc:a', 'npc:a'), Range.CLOSE)
        self.assertIs(battlefield_range(linked, 'pc:a', 'npc:b'), Range.MEDIUM)
        with self.assertRaises(ValueError):
            PcBattlefieldState(arena(Range.LONG).spatial, (('pc:a', 'npc:a'),))

    def test_nearby_preserves_caller_order_excludes_self_and_accepts_dead_anchor(self):
        source = arena(Range.CLOSE)
        self.assertEqual(battlefield_nearby(source, 'pc:a',
            ('npc:b', 'pc:a', 'pc:b', 'npc:a')), ('npc:b', 'pc:b', 'npc:a'))
        self.assertEqual(battlefield_nearby(source, 'pc:a', ('npc:a', 'pc:b')),
            ('npc:a', 'pc:b'))
        self.assertEqual(battlefield_nearby(source, 'pc:a', ()), ())
        self.assertIs(battlefield_range(source, 'pc:a', 'pc:a'), Range.CLOSE)

    def test_placement_projection_changes_only_actor_links_and_preserves_round_usage(self):
        source = arena()
        source = replace(source, spatial=replace(source.spatial, round_number=3,
            gave_ground_entity_ids=('pc:b',), free_move_used_entity_ids=('npc:b',),
            difficult_terrain_tested_entity_ids=('pc:a',)))
        original = deepcopy(source)
        result = with_actor_placement(source, 'pc:a', 'scene:zone:1',
            close_to_ids=('npc:a',))
        self.assertEqual(source, original)
        self.assertEqual(result.spatial.placement_for('pc:a'),
            SpatialEntityPlacement('pc:a', 'players_and_allies', 'scene:zone:1'))
        self.assertEqual(result.close_pairs, (('npc:a', 'npc:b'), ('npc:a', 'pc:a')))
        self.assertEqual(result.spatial.round_number, 3)
        self.assertEqual(result.spatial.gave_ground_entity_ids, ('pc:b',))
        self.assertEqual(result.spatial.free_move_used_entity_ids, ('npc:b',))
        self.assertEqual(result.spatial.difficult_terrain_tested_entity_ids, ('pc:a',))
        self.assertIs(result.spatial.graph, source.spatial.graph)
        for actor in ('pc:b', 'npc:a', 'npc:b'):
            self.assertIs(result.spatial.placement_for(actor), source.spatial.placement_for(actor))
        self.assertIs(battlefield_range(result, 'pc:a', 'pc:b'), Range.MEDIUM)
        self.assertIs(battlefield_range(result, 'pc:a', 'npc:a'), Range.CLOSE)

    def test_placement_can_clear_or_replace_close_without_inferring_new_links(self):
        source = arena(Range.CLOSE)
        moved = with_actor_placement(source, 'pc:a', 'scene:zone:0')
        self.assertEqual(moved.close_pairs,
            (('npc:a', 'npc:b'), ('npc:a', 'pc:b'), ('npc:b', 'pc:b')))
        self.assertIs(battlefield_range(moved, 'pc:a', 'pc:b'), Range.SHORT)
        linked = with_actor_placement(moved, 'pc:a', 'scene:zone:0', close_to_ids=('pc:b',))
        self.assertIs(battlefield_range(linked, 'pc:a', 'pc:b'), Range.CLOSE)
        self.assertIs(battlefield_range(linked, 'pc:a', 'npc:a'), Range.SHORT)

    def test_far_placement_is_only_a_fact_projection_and_does_not_spend_movement(self):
        source = arena(Range.LONG)
        projected = with_actor_placement(source, 'pc:a', 'scene:zone:-3')
        self.assertIs(battlefield_range(projected, 'pc:a', 'npc:a'), Range.EXTREME)
        self.assertEqual(projected.spatial.free_move_used_entity_ids, ())
        self.assertEqual(projected.spatial.gave_ground_entity_ids, ())
        self.assertEqual(projected.spatial.round_number, 1)

    def test_spec_requires_typed_ranges_but_allows_initial_distance_beyond_shooting_cap(self):
        spec = PcBattlefieldSpec(Range.EXTREME, Range.SHORT)
        self.assertEqual(spec.initial_range, Range.EXTREME)
        for field, value in (('initial_range', 'short'), ('initial_range', True),
                ('two_handed_max_range', 'long')):
            with self.subTest(field=field, value=value), self.assertRaises(TypeError):
                replace(spec, **{field: value})
        with self.assertRaises(ValueError):
            replace(spec, two_handed_max_range=Range.CLOSE)

    def test_builder_rejects_empty_nonexact_duplicate_and_overlapping_actor_ids(self):
        spec = PcBattlefieldSpec(Range.SHORT, Range.LONG)
        for party, enemies, arena_id in (((), ('n',), 'x'), (('p',), (), 'x'),
                (('p', 'p'), ('n',), 'x'), (('p',), ('p',), 'x'),
                (('p',), ('n', 'n'), 'x'), ((' ',), ('n',), 'x'),
                (('p',), ('n',), ' ')):
            with self.subTest(party=party, enemies=enemies, arena=arena_id), self.assertRaises(ValueError):
                build_pc_battlefield(spec, party, enemies, arena_id)
        for party, enemies, arena_id in ((['p'], ('n',), 'x'), ((1,), ('n',), 'x'),
                (('p',), ('n',), 3)):
            with self.subTest(party=party, enemies=enemies, arena=arena_id), self.assertRaises(TypeError):
                build_pc_battlefield(spec, party, enemies, arena_id)

    def test_close_pairs_reject_duplicates_unknown_ids_self_and_malformed_shapes(self):
        source = arena()
        for pairs in ((('pc:a', 'pc:b'), ('pc:b', 'pc:a')),
                (('pc:a', 'unknown'),), (('pc:a', 'pc:a'),), (('pc:a', ' '),)):
            with self.subTest(pairs=pairs), self.assertRaises(ValueError):
                PcBattlefieldState(source.spatial, pairs)
        for pairs in ([('pc:a', 'pc:b')], ('pc:a',), (('pc:a',),), (('pc:a', 1),)):
            with self.subTest(pairs=pairs), self.assertRaises(TypeError):
                PcBattlefieldState(source.spatial, pairs)

    def test_queries_and_projection_reject_unknown_or_duplicate_ids_without_mutation(self):
        source = arena()
        original = deepcopy(source)
        operations = (
            lambda: battlefield_range(source, 'unknown', 'pc:a'),
            lambda: battlefield_range(source, 'pc:a', 'unknown'),
            lambda: battlefield_nearby(source, 'unknown', ()),
            lambda: battlefield_nearby(source, 'pc:a', ('unknown',)),
            lambda: battlefield_nearby(source, 'pc:a', ('npc:a', 'npc:a')),
            lambda: with_actor_placement(source, 'unknown', 'scene:zone:0'),
            lambda: with_actor_placement(source, 'pc:a', 'unknown'),
            lambda: with_actor_placement(source, 'pc:a', 'scene:zone:0', close_to_ids=('unknown',)),
            lambda: with_actor_placement(source, 'pc:a', 'scene:zone:0', close_to_ids=('pc:a',)),
            lambda: with_actor_placement(source, 'pc:a', 'scene:zone:0', close_to_ids=('pc:b', 'pc:b')),
            lambda: with_actor_placement(source, 'pc:a', 'scene:zone:3', close_to_ids=('npc:a',)),
        )
        for operation in operations:
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                operation()
            self.assertEqual(source, original)

    def test_disconnected_participants_have_no_invented_range(self):
        source = PcBattlefieldState(SpatialBattleState(ZoneGraph(('first', 'second')), (
            SpatialEntityPlacement('p', 'party', 'first'),
            SpatialEntityPlacement('n', 'enemy', 'second'))), ())
        with self.assertRaises(ValueError):
            battlefield_range(source, 'p', 'n')

    def test_snapshots_are_immutable_and_roundtrip_pickle(self):
        spec = PcBattlefieldSpec(Range.SHORT, Range.LONG)
        source = arena()
        self.assertEqual(pickle.loads(pickle.dumps(spec)), spec)
        self.assertEqual(pickle.loads(pickle.dumps(source)), source)
        with self.assertRaises(FrozenInstanceError):
            source.close_pairs = ()
        with self.assertRaises(FrozenInstanceError):
            spec.initial_range = Range.CLOSE


if __name__ == '__main__':
    unittest.main()
