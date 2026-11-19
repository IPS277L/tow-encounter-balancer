"""Prepared source-bound geometry for action ordering, not a native prefix.

The dropped Shield is an explicitly prepared interaction boundary. These
snapshots do not claim a preceding drop or completed combat-turn history.
"""
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.domain.armour_models import ArmourLoadout, ShieldKind
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedRangedFacts
from towr.domain.pc_battlefield_models import PcBattlefieldSpec, battlefield_range
from towr.domain.pc_battlefield_movement_models import (
    expected_pc_action_positioning, expected_pc_battlefield_move,
)
from towr.domain.pc_melee_models import PcMeleePolicy
from towr.domain.pc_melee_result_models import initial_pc_melee_state, pc_melee_selected_action
from towr.domain.pc_mount_attack_models import pc_uses_mount_attack
from towr.domain.pc_mount_models import CombatMount
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.pc_npc_shield_models import (
    NpcShieldGroundPosition, NpcShieldLocation, _add_marker, _with_shield,
    build_npc_shield_pickup, npc_shield_item_close,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
from towr.domain.turn_models import CombatActionKind, CombatSide, CombatTurnState
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import WeaponGrip, WeaponItemLocation, WeaponItemSource


class PreparedShieldSnapshot:
    """A local preparation view retains its full immutable participant source."""

    def __init__(self, initial, *, dropped):
        self.initial = initial
        self.round_state = replace(initial.round_state,
            completed_turn_entity_ids=('pc',), active_turn=CombatTurnState('minion1', CombatSide.OPPOSITION))
        self.enemies = initial.enemies
        self.npc_shields = initial.npc_shields
        self.battlefield = initial.battlefield
        if dropped:
            previous = initial.npc_shields[0]
            ground = NpcShieldGroundPosition(
                initial.battlefield.spatial.placement_for('minion1').zone_id, ('minion1',))
            item = replace(previous, location=NpcShieldLocation.DROPPED, ground=ground)
            self.npc_shields = (item,)
            self.enemies = (_with_shield(initial.enemy('minion1'), False),)
            self.battlefield = _add_marker(initial.battlefield, item)

    def __getattr__(self, name):
        return getattr(self.initial, name)

    def enemy(self, actor_id):
        return next(enemy for enemy in self.enemies if enemy.state.actor_id == actor_id)

    @property
    def live_enemies(self):
        return self.enemies


def prepared(*, dropped=True, mounted=False):
    base = make_pc_melee_scenario(max_rounds=1)
    pc = replace(base.party[0], policy=PcMeleePolicy.AUTOMATIC_COMBAT)
    npc = GeneratedNpc(1, 3, 4, 3, 2, 4,
        (WeaponItemSource('gun', WeaponKind.PISTOL, WeaponItemLocation.HELD,
            WeaponGrip.LEFT, initially_loaded=True),),
        ArmourLoadout(shield=ShieldKind.SHIELD), defence=2,
        ranged=GeneratedRangedFacts(1, 2, 3, 4, True, True, True),
        mount=CombatMount.HORSE if mounted else None)
    distance = R.CLOSE if mounted else R.MEDIUM
    source = replace(base, party=(pc,), enemies=(npc.participant('minion1'),),
        battlefield=PcBattlefieldSpec(distance, R.LONG),
        npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc, 'minion1'),),
        facts=replace(base.facts, can_leave_zone=True, all_opponents_close=distance is R.CLOSE,
            unmounted=not mounted))
    return PreparedShieldSnapshot(initial_pc_melee_state(source), dropped=dropped)


class PcActionPositioningTests(unittest.TestCase):
    def test_selected_shield_recover_keeps_its_actual_nearby_item_before_attack_positioning(self):
        state = prepared()
        pickup = build_npc_shield_pickup(state)
        self.assertIsNotNone(pickup)
        self.assertTrue(npc_shield_item_close(state, 'minion1'))
        self.assertEqual(pickup.choice.object_interaction.object_id, state.npc_shields[0].item_id)
        self.assertEqual(pickup.actor_id, 'minion1')
        self.assertIs(pc_melee_selected_action(state), CombatActionKind.RECOVER)
        physical = expected_pc_battlefield_move(state)
        self.assertIsNotNone(physical)
        self.assertEqual(physical.actor_id, 'minion1')
        self.assertNotEqual(physical.previous.spatial.placement_for('minion1'),
            physical.state.spatial.placement_for('minion1'))
        self.assertIsNone(expected_pc_action_positioning(state))
        self.assertEqual(state.enemy('minion1').state.weapon_inventory.active.reload.loaded, True)
        self.assertIs(state.npc_shields[0].location, NpcShieldLocation.DROPPED)

    def test_actual_mount_attack_can_outrank_a_possible_shield_recover(self):
        state = prepared(mounted=True)
        self.assertIsNotNone(build_npc_shield_pickup(state))
        self.assertTrue(pc_uses_mount_attack(state, 'minion1'))
        self.assertIs(pc_melee_selected_action(state), CombatActionKind.ATTACK)
        self.assertIs(battlefield_range(state.battlefield, 'minion1', 'pc'), R.CLOSE)
        # A real mount Attack requires Close. Its 1H rider weapon permits
        # Close too, so this actual geometry needs no physical movement.
        self.assertIsNone(expected_pc_battlefield_move(state))
        self.assertIsNone(expected_pc_action_positioning(state))

    def test_without_recovery_the_same_real_physical_move_is_retained(self):
        state = prepared(dropped=False)
        self.assertIsNone(build_npc_shield_pickup(state))
        self.assertIs(pc_melee_selected_action(state), CombatActionKind.ATTACK)
        physical = expected_pc_battlefield_move(state)
        self.assertIsNotNone(physical)
        self.assertEqual(expected_pc_action_positioning(state), physical)
        self.assertEqual(physical.source_round, state.round_state)
        self.assertEqual(physical.previous, state.battlefield)


if __name__ == '__main__':
    unittest.main()
