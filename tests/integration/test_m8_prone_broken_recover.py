"""Safe Prone Recover -> interruption/expiry handoffs, not automatic policy."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.integration.test_m8_npc_broken_recover import wounded_broken_wizard
from tests.integration.test_m8_npc_roster_prone_stand import prone
from tests.unit.test_m8_npc_broken_recover import request as recovery
from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from tests.unit.test_m8_npc_roster_unnatural_wind import request as wind_request
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionSourceSnapshot
from towr.domain.npc_broken_recover_models import NpcBrokenRecoverRequest
from towr.domain.npc_roster_prone_models import NpcRosterProneStandRequest, NpcRosterProneTurnEndRequest
from towr.domain.test_models import InlineProfile
from towr.engine.npc_broken_recover import execute_npc_broken_recover, apply_npc_broken_recover_result
from towr.rules.npc_roster_miscast_resolution import resolve_npc_roster_unnatural_wind
from towr.rules.npc_roster_prone_resolution import stand_npc_roster_prone, end_npc_roster_prone_turn


def wounded_safe(pool=0):
    _, _, state = wounded_broken_wizard(pool)
    actor = state.wizard.actor_id
    # Authored safe/Prone entry context; real earlier attack owns the wound clock.
    state = prone(state, actor)
    state = replace(state, spatial_state=replace(state.spatial_state,
        placements=tuple(replace(p, zone_id='empty') if p.entity_id == actor else p
                         for p in state.spatial_state.placements), free_move_used_entity_ids=(actor,)))
    return NpcBrokenRecoverRequest('prone:recover', state, actor, InlineProfile(3, 3), None, True, True)


def end_request(state):
    return NpcRosterProneTurnEndRequest('end:recover', state, state.wizard.actor_id,
                                      (WoundConditionSourceSnapshot(Condition.DRAINED, False),))


class ProneBrokenRecoverIntegrationTests(unittest.TestCase):
    def test_real_stomach_blow_recovers_then_expires_only_at_prone_turn_end(self):
        for values, broken in (((1, 10, 10), False), ((10, 10, 10), True)):
            with self.subTest(broken=broken):
                source = wounded_safe()
                dice = Dice(values)
                with patch('towr.engine.npc_broken_recover.resolve_free_movement', side_effect=AssertionError('no move')):
                    result = execute_npc_broken_recover(source, dice)
                current = apply_npc_broken_recover_result(source.state, result)
                dice.exhausted()
                injury = current.roster.participant(source.actor_id).state.injury
                self.assertTrue(injury.conditions.has(Condition.PRONE))
                self.assertTrue(injury.conditions.has(Condition.DRAINED))
                self.assertEqual(injury.conditions.has(Condition.BROKEN), broken)
                self.assertEqual(current.wound_expiries, source.state.wound_expiries)
                self.assertEqual(current.champion_attack.daily_wounds, source.state.champion_attack.daily_wounds)
                self.assertEqual(current.spatial_state, source.state.spatial_state)
                self.assertEqual(current.wizard.magic_state.miscast_dice, 1)
                final = end_npc_roster_prone_turn(end_request(current)).state
                after = final.roster.participant(source.actor_id).state.injury
                self.assertTrue(after.conditions.has(Condition.PRONE))
                self.assertEqual(after.conditions.has(Condition.BROKEN), broken)
                self.assertFalse(after.conditions.has(Condition.DRAINED))
                self.assertEqual(after.wounds, injury.wounds)
                self.assertEqual(final.wound_expiries, ())
                self.assertEqual(final.wizard, current.wizard)
                self.assertEqual(final.consumed_execution_ids, (*source.state.consumed_execution_ids, source.id))

    def test_action_interruption_blocks_end_until_actual_wind_before_expiry(self):
        source = wounded_safe(pool=2)
        dice = Dice((9, 9, 9))
        result = execute_npc_broken_recover(source, dice)
        current = result.state
        dice.exhausted()
        self.assertIs(current.pending_interruption, result.interruption)
        self.assertEqual(current.wizard.magic_state.miscast_dice, 3)  # One skipped action, not three nines.
        with self.assertRaises(ValueError):
            end_request(current)
        effect = resolve_npc_roster_unnatural_wind(wind_request(raw=current))
        self.assertEqual(effect.state.wizard.magic_state.miscast_dice, 0)
        self.assertEqual(effect.state.wound_expiries, source.state.wound_expiries)
        self.assertEqual(effect.state.consumed_execution_ids, current.consumed_execution_ids)
        final = end_npc_roster_prone_turn(end_request(effect.state)).state
        self.assertTrue(final.roster.participant(source.actor_id).state.injury.conditions.has(Condition.PRONE))
        self.assertTrue(final.roster.participant(source.actor_id).state.injury.conditions.has(Condition.BROKEN))
        self.assertEqual(final.wound_expiries, ())

    def test_explicit_safe_self_stand_then_alternative_recover_spends_free_move_once(self):
        original = recovery(safe=True, extra_conditions=(Condition.PRONE, Condition.STAGGERED))
        stood = stand_npc_roster_prone(NpcRosterProneStandRequest(
            'stand:safe', original.state, original.actor_id, False, True)).state
        source = replace(original, state=stood)
        dice = Dice((1, 10, 10))
        final = execute_npc_broken_recover(source, dice).state
        dice.exhausted()
        conditions = final.roster.participant(source.actor_id).state.injury.conditions
        self.assertFalse(conditions.has(Condition.PRONE))
        self.assertFalse(conditions.has(Condition.BROKEN))
        self.assertTrue(conditions.has(Condition.STAGGERED))
        self.assertEqual(final.spatial_state.free_move_used_entity_ids, (source.actor_id,))
        self.assertEqual(final.consumed_execution_ids, (source.id,))
        self.assertEqual(final.wizard.magic_state.miscast_dice, 1)

    def test_safe_prone_minion_does_not_interrupt_another_wizard(self):
        source = recovery(actor='first', safe=True, pool=2, extra_conditions=(Condition.PRONE,))
        dice = Dice((1, 10, 10))
        result = execute_npc_broken_recover(source, dice)
        dice.exhausted()
        self.assertIsNone(result.interruption)
        final = end_npc_roster_prone_turn(NpcRosterProneTurnEndRequest(
            'end:minion', result.state, source.actor_id)).state
        self.assertEqual(final.wizard, source.state.wizard)
        self.assertEqual(final.spatial_state, source.state.spatial_state)
        self.assertTrue(final.roster.participant(source.actor_id).state.injury.conditions.has(Condition.PRONE))


if __name__ == '__main__':
    unittest.main()
