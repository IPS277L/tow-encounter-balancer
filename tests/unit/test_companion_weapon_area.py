"""Prepared area geometry and bank updates, not native detach/replay tests."""
from copy import deepcopy
from dataclasses import replace
from itertools import combinations
import unittest

from tests.unit.test_pc_companion_actor_queries import prepared
from towr.domain.condition_models import Condition
from towr.domain.pc_actor_models import pc_actor_injury
from towr.domain.pc_battlefield_models import PcBattlefieldSpec, build_pc_battlefield, with_actor_placement
from towr.domain.pc_weapon_area_models import _with_injury, weapon_area_target_ids
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.weapon_catalog import WeaponKind


def prepared_geometry():
    state = prepared()
    battlefield = build_pc_battlefield(PcBattlefieldSpec(RangedWeaponRange.MEDIUM,
        RangedWeaponRange.LONG), state.source.pc_activation_order,
        state.source.enemy_activation_order, state.source.facts.zone_id)
    extra = tuple(SpatialEntityPlacement(row.snapshot.state.actor_id, row.snapshot.state.side.value,
        battlefield.spatial.placement_for(row.rider_id).zone_id) for row in state.companions)
    battlefield = replace(battlefield, spatial=replace(battlefield.spatial,
        placements=(*battlefield.spatial.placements, *extra)),
        close_pairs=tuple(combinations(('pc1', 'pc1:mount', 'pc2'), 2))
            + tuple(combinations(('minion1', 'minion1:mount', 'minion2'), 2)))
    state.battlefield = battlefield
    return state


class CompanionWeaponAreaTests(unittest.TestCase):
    def test_all_creatures_include_both_companion_sides_after_their_riders(self):
        state = prepared()
        before = deepcopy(state)
        expected = ('pc1', 'pc1:mount', 'pc2', 'minion1', 'minion1:mount', 'minion2')
        for weapon in (WeaponKind.OIL_FLASK, WeaponKind.BLASTING_CHARGE):
            with self.subTest(weapon=weapon):
                self.assertEqual(weapon_area_target_ids(state, weapon, 'minion1'), expected)
        self.assertEqual(state, before)

    def test_oil_close_and_blast_zone_geometry_keep_actual_companion_positions(self):
        state = prepared_geometry()
        self.assertEqual(weapon_area_target_ids(state, WeaponKind.OIL_FLASK, 'pc1'),
            ('pc1', 'pc1:mount', 'pc2'))
        self.assertEqual(weapon_area_target_ids(state, WeaponKind.BLASTING_CHARGE, 'minion1'),
            ('minion1', 'minion1:mount', 'minion2'))
        destination = state.battlefield.spatial.placement_for('pc1').zone_id
        state.battlefield = with_actor_placement(state.battlefield, 'minion1:mount', destination)
        # The explicit placement is Short, without an invented Close relation.
        self.assertEqual(weapon_area_target_ids(state, WeaponKind.OIL_FLASK, 'pc1'),
            ('pc1', 'pc1:mount', 'pc2'))
        self.assertEqual(weapon_area_target_ids(state, WeaponKind.BLASTING_CHARGE, 'pc1'),
            ('pc1', 'pc1:mount', 'pc2', 'minion1:mount'))
        self.assertEqual(weapon_area_target_ids(state, WeaponKind.OIL_FLASK, 'pc1', hit=False), ())

    def test_inactive_and_defeated_companions_are_excluded_but_defenceless_remains_a_victim(self):
        originals = ('pc1', 'pc2', 'minion1', 'minion2')
        for state in (prepared(mounted=True), prepared(retained=None)):
            self.assertEqual(weapon_area_target_ids(state, WeaponKind.BLASTING_CHARGE, 'minion1'), originals)
        state = prepared()
        ally, enemy = state.companions
        state.companions = (replace(ally, snapshot=replace(ally.snapshot,
            state=replace(ally.snapshot.state, injury=replace(ally.snapshot.state.injury,
                wounds=1, defeated=True)))), replace(enemy, snapshot=replace(enemy.snapshot,
            state=replace(enemy.snapshot.state, injury=replace(enemy.snapshot.state.injury,
                conditions=enemy.snapshot.state.injury.conditions.with_condition(Condition.DEFENCELESS))))))
        self.assertEqual(weapon_area_target_ids(state, WeaponKind.BLASTING_CHARGE, 'minion1'),
            ('pc1', 'pc2', 'minion1', 'minion1:mount', 'minion2'))

    def test_companion_condition_update_changes_only_its_own_bank_without_fate(self):
        state = prepared()
        before = deepcopy(state)
        for actor in ('pc1:mount', 'minion1:mount'):
            with self.subTest(actor=actor):
                injury = pc_actor_injury(state, actor)
                burning = replace(injury, conditions=injury.conditions.with_condition(Condition.ABLAZE))
                updates = _with_injury(state, actor, burning)
                self.assertEqual(tuple(updates), ('companions',))
                updated = next(row for row in updates['companions'] if row.snapshot.state.actor_id == actor)
                original = next(row for row in state.companions if row.snapshot.state.actor_id == actor)
                self.assertIs(updated.snapshot.state.side, original.snapshot.state.side)
                self.assertEqual(updated.snapshot.state.injury, burning)
                self.assertEqual(updated.retained_since_round, original.retained_since_round)
                self.assertFalse(hasattr(updated.snapshot.state, 'fate'))
                with self.assertRaises(ValueError):
                    _with_injury(state, actor, burning, fate=state.participant('pc1').fate)
        self.assertEqual(state, before)

    def test_original_npc_stays_in_the_original_bank(self):
        state = prepared()
        injury = pc_actor_injury(state, 'minion1')
        updates = _with_injury(state, 'minion1',
            replace(injury, conditions=injury.conditions.with_condition(Condition.ABLAZE)))
        self.assertEqual(tuple(updates), ('enemies',))
        self.assertTrue(updates['enemies'][0].state.injury.conditions.has(Condition.ABLAZE))
        self.assertEqual(state.companions, prepared().companions)


if __name__ == '__main__':
    unittest.main()
