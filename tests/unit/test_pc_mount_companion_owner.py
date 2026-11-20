"""Initial mount bodies are separate NPC sources, inactive until real retention."""
from dataclasses import replace
import unittest

from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.armour_models import ArmourLoadout
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from tests.support.generated_weapon_sources import initial_generated_weapons
from towr.domain.condition_models import Condition
from towr.domain.pc_actor_models import pc_active_actor_ids,pc_actor_side
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_companion_models import mount_companion_actor_id
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.pc_mount_models import CombatMount,RiderKind
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
from towr.domain.turn_models import CombatSide


def source(kind=CombatMount.HORSE):
    original=automatic_source(pc_count=1,enemy_count=1)
    rider_kind=RiderKind.HUMAN if kind in (CombatMount.PEGASUS,CombatMount.DEMIGRYPH) else None
    pc=replace(original.party[0],mount=kind,rider_kind=rider_kind)
    npc=GeneratedNpc(3,3,3,3,4,4,initial_generated_weapons(GeneratedWeapon.STAFF),
        ArmourLoadout(),defence=4,mount=kind,rider_kind=rider_kind)
    return replace(original,party=(pc,),enemies=(npc.participant('minion1'),),
        enemy_activation_order=('minion1',),enemy_target_priority=('pc1',),
        battlefield=PcBattlefieldSpec(R.CLOSE,R.LONG),
        facts=replace(original.facts,unmounted=False,can_leave_zone=True))


class MountCompanionOwnerTests(unittest.TestCase):
    def test_both_sides_keep_own_inactive_bodies_without_extra_targets_or_turns(self):
        battle=source()
        state=initial_pc_melee_state(battle)
        self.assertEqual(tuple(row.rider_id for row in state.companions),('pc1','minion1'))
        self.assertEqual(tuple(row.snapshot.state.side for row in state.companions),
            (CombatSide.PLAYERS_AND_ALLIES,CombatSide.OPPOSITION))
        self.assertTrue(all(row.retained_since_round is None for row in state.companions))
        self.assertEqual(pc_active_actor_ids(state),('pc1','minion1'))
        self.assertEqual(tuple(p.entity_id for p in state.round_state.participants),('pc1','minion1'))
        for row in state.companions:
            self.assertEqual(row.snapshot.state.injury.wounds,0)
            self.assertFalse(hasattr(row.snapshot.state,'fate'))
            self.assertNotIn(row.snapshot.state.actor_id,tuple(p.entity_id for p in state.battlefield.spatial.placements))
            self.assertIs(pc_actor_side(state,row.snapshot.state.actor_id),row.snapshot.state.side)

    def test_inactive_source_rows_cannot_be_erased_reordered_or_given_another_side(self):
        state=initial_pc_melee_state(source())
        with self.assertRaises(ValueError):replace(state,companions=())
        with self.assertRaises(ValueError):replace(state,companions=tuple(reversed(state.companions)))
        first=state.companions[0]
        forged=replace(first,snapshot=replace(first.snapshot,state=replace(first.snapshot.state,
            side=CombatSide.OPPOSITION)))
        with self.assertRaises(ValueError):replace(state,companions=(forged,state.companions[1]))

    def test_retention_cannot_be_invented_while_the_rider_is_still_mounted(self):
        state=initial_pc_melee_state(source())
        first=replace(state.companions[0],retained_since_round=1)
        with self.assertRaises(ValueError):replace(state,companions=(first,state.companions[1]))

    def test_mount_body_does_not_copy_the_riders_injury_or_weapon_inventory(self):
        state=initial_pc_melee_state(source(CombatMount.DEMIGRYPH))
        row=state.companions[0]
        self.assertEqual(row.snapshot.state.injury.wound_limit,3)
        self.assertIsNone(row.snapshot.state.weapon_inventory)
        injured=replace(state.party[0],injury=replace(state.party[0].injury,
            conditions=state.party[0].injury.conditions.with_condition(Condition.STAGGERED)))
        prepared=replace(state,party=(injured,))
        self.assertEqual(prepared.companions,state.companions)
        self.assertFalse(prepared.companions[0].snapshot.state.injury.conditions.has(Condition.STAGGERED))


if __name__=='__main__':unittest.main()
