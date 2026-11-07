"""Pistol/shield hand availability and explicit Reload versus pickup priorities."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.support.pc_shield_scenarios import shield_loadout
from tests.unit.test_m54_pistol_core import block_hand, pistol_source, reserve
from tests.unit.test_k1_reload_resolution import weapon_state
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import PcWeaponHand as Hand
from towr.domain.pc_melee_result_models import (
    _pc_recover_needed, build_pc_melee_recover, initial_pc_melee_state,
    pc_melee_action_declaration, pc_melee_selected_action,
)
from towr.domain.pc_pistol_models import build_pc_pistol_reload, pc_pistol_unsupported
from towr.domain.pc_shield_models import (
    PcShieldLocation as Location, PcShieldState, expected_pc_shield_release,
    pc_shield_recover_hand, pc_shield_recover_needed,
)
from towr.domain.turn_models import CombatActionKind as Action, CombatTurnStartRequest
from towr.rules.reload_resolution import execute_reload_action
from towr.rules.turn_resolution import start_combat_turn


def shield_state(*, empty=False, dropped=False):
    source = pistol_source()
    source = replace(source, party=(replace(source.party[0], shield=shield_loadout(Hand.RIGHT)),))
    state = initial_pc_melee_state(source)
    combat = start_combat_turn(CombatTurnStartRequest('turn:pc',state.round_state,'pc')).state
    member = state.party[0]
    if empty:
        member = replace(member,pistol=weapon_state(weapon_instance_id='pc:weapon',
            reload_cycle_id='pc:first:cycle'))
    if dropped:
        member = replace(member,shield=PcShieldState(Location.DROPPED,None))
    return replace(state,party=(member,),round_state=combat)


class M55PistolShieldCoreTests(unittest.TestCase):
    def test_loaded_shot_keeps_held_shield_and_needs_no_release(self):
        state = shield_state()
        self.assertIs(pc_melee_selected_action(state),Action.ATTACK)
        self.assertIsNone(expected_pc_shield_release(state))

    def test_empty_held_shield_requires_release_before_reload(self):
        state = shield_state(empty=True)
        release = expected_pc_shield_release(state)
        self.assertEqual((release.actor_id,release.hand),('pc',Hand.RIGHT))
        reserved = reserve(state,pc_melee_action_declaration(state))
        with self.assertRaises(ValueError):
            build_pc_pistol_reload(reserved)

    def test_dropped_shield_preserved_in_owner_while_reload_is_allowed(self):
        state = shield_state(empty=True,dropped=True)
        self.assertIsNone(expected_pc_shield_release(state))
        self.assertFalse(pc_shield_recover_needed(state.party[0]))
        self.assertIsNone(pc_shield_recover_hand(state.party[0]))
        self.assertIs(pc_melee_selected_action(state),Action.IMPROVISE)
        state = reserve(state,pc_melee_action_declaration(state))
        result = execute_reload_action(build_pc_pistol_reload(state),SequenceRandom([1,1,1]))
        self.assertTrue(result.state.loaded)
        self.assertEqual(state.party[0].shield,PcShieldState(Location.DROPPED,None))

    def test_partial_reload_does_not_restore_shield_but_completed_reload_does(self):
        for rolls,loaded in (([1,10,10],False),([1,1,1],True)):
            with self.subTest(rolls=rolls):
                state = shield_state(empty=True,dropped=True)
                reserved = reserve(state,pc_melee_action_declaration(state))
                result = execute_reload_action(build_pc_pistol_reload(reserved),SequenceRandom(rolls))
                member = replace(state.party[0],pistol=result.state)
                state = replace(state,party=(member,))
                self.assertIs(pc_shield_recover_needed(member),loaded)
                self.assertIs(pc_melee_selected_action(state),Action.RECOVER if loaded else Action.IMPROVISE)

    def test_prone_recover_precedes_release_and_cannot_pick_up_empty_pistol_shield(self):
        for dropped in (False,True):
            state = shield_state(empty=True,dropped=dropped)
            member = state.party[0]
            member = replace(member,injury=replace(member.injury,
                conditions=member.injury.conditions.with_condition(Condition.PRONE)))
            state = replace(state,party=(member,))
            self.assertTrue(_pc_recover_needed(member))
            self.assertIsNone(expected_pc_shield_release(state))
            self.assertIs(pc_melee_selected_action(state),Action.RECOVER)
            self.assertIsNone(build_pc_melee_recover(state).choice.object_interaction)

    def test_weapon_pickup_precedes_reload_and_does_not_reset_cycle(self):
        state = shield_state(empty=True,dropped=True)
        member = replace(state.party[0],weapon_hand=None)
        state = replace(state,party=(member,))
        self.assertIs(pc_melee_selected_action(state),Action.RECOVER)
        self.assertIsNone(expected_pc_shield_release(state))
        self.assertEqual(build_pc_melee_recover(state).choice.object_interaction.object_id,'pc:weapon')
        self.assertEqual(member.pistol.reload_cycle_id,'pc:first:cycle')

    def test_unavailable_reload_does_not_release_or_pick_up_shield(self):
        for total in (16,18,20):
            state = block_hand(shield_state(empty=True),Hand.RIGHT,total=total)
            shield = (PcShieldState(Location.DROPPED,None) if total==18
                else PcShieldState(Location.UNAVAILABLE,Hand.RIGHT))
            state = replace(state,party=(replace(state.party[0],shield=shield),))
            self.assertIsNone(expected_pc_shield_release(state))
            self.assertIsNone(pc_shield_recover_hand(state.party[0]))
            self.assertEqual(pc_pistol_unsupported(state).reason,'pistol_reload_hands_unavailable')
            self.assertEqual(state.party[0].shield,shield)

    def test_loaded_dropped_shield_still_uses_original_restore_before_attack(self):
        state = shield_state(dropped=True)
        self.assertIs(pc_shield_recover_hand(state.party[0]),Hand.RIGHT)
        self.assertIs(pc_melee_selected_action(state),Action.RECOVER)
        self.assertEqual(build_pc_melee_recover(state).choice.object_interaction.object_id,'pc:shield')


if __name__ == '__main__':
    unittest.main()
