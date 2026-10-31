"""Scoped end-turn handoffs and the explicit journal opt-in boundary."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.integration.test_m8_npc_roster_prone_stand import prone
from tests.unit.test_m8_npc_magic_scenario_runner import Dice, admitted
from tests.unit.test_m8_npc_roster_minion_attack import request as attack_request
from tests.unit.test_m8_npc_roster_turn import ATTACK
from tests.unit.test_m8_npc_roster_unnatural_wind import request as wind_request
from tests.unit.test_m8_npc_wound_turn_end import request as wound_request
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_step_models import NpcMagicStep
from towr.domain.npc_magic_journal_policy import validate_magic_step_policy
from towr.domain.npc_roster_prone_models import NpcRosterProneStandRequest, NpcRosterProneTurnEndRequest
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
from towr.rules.npc_roster_miscast_resolution import resolve_npc_roster_unnatural_wind
from towr.rules.npc_roster_prone_resolution import (
    end_npc_roster_prone_turn as end, apply_npc_roster_prone_turn_end as apply,
    stand_npc_roster_prone,
)
from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn
from towr.rules.npc_wound_turn_end import end_npc_wound_turn


class ProneTurnEndIntegrationTests(unittest.TestCase):
    def test_real_wind_end_next_turn_and_stand_preserve_effect_and_action_history(self):
        wind = resolve_npc_roster_unnatural_wind(wind_request())
        old = wind.state
        with patch('random.Random', side_effect=AssertionError('no RNG')):
            result = end(NpcRosterProneTurnEndRequest('end:wind', old, old.wizard.actor_id))
            current = apply(old, result)
            begun = start_npc_roster_turn(NpcRosterTurnStartRequest('next:ally', current, 'ally', ATTACK))
            # Explicit no-Close fact; same Zone alone neither proves nor denies it.
            stood = stand_npc_roster_prone(NpcRosterProneStandRequest(
                'stand:ally', begun.state, 'ally', False, True)).state
        self.assertEqual(stood.round_state.active_turn.actor_id, 'ally')
        self.assertFalse(stood.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(stood.round_state.completed_turn_entity_ids, ('wizard',))
        self.assertEqual(stood.consumed_execution_ids, old.consumed_execution_ids)
        self.assertEqual(stood.wizard, old.wizard)
        self.assertEqual(stood.wizard.magic_state.miscast_dice, 0)
        self.assertEqual(stood.spatial_state.placements, old.spatial_state.placements)
        self.assertEqual(stood.spatial_state.free_move_used_entity_ids, ('ally',))
        for actor in ('wizard', 'enemy'):
            self.assertEqual(stood.roster.participant(actor), old.roster.participant(actor))
        self.assertFalse(stood.roster.participant('ally').state.injury.conditions.has(Condition.PRONE))
        self.assertEqual(stood.wound_turn_end_receipts, current.wound_turn_end_receipts)
        self.assertEqual(stood.champion_attack.roster, stood.roster)
        self.assertEqual(stood.minion_attack.roster, stood.roster)

    def test_executed_minion_attack_then_authored_prone_end_keeps_one_execution(self):
        source = attack_request()
        dice = Dice((10,) * 6)
        attack = execute_npc_roster_minion_attack(source, dice)
        dice.exhausted()
        actor = source.attack.execution.actor_id
        # Authored Condition after completed Attack, not a claimed Wind trigger.
        old = prone(attack.state, actor)
        final = apply(old, end(NpcRosterProneTurnEndRequest('end:archer', old, actor)))
        self.assertEqual(final.consumed_execution_ids, (source.attack.execution.id,))
        self.assertEqual(final.roster, old.roster)
        self.assertEqual(final.minion_attack, old.minion_attack)
        self.assertEqual(final.spatial_state, old.spatial_state)
        self.assertEqual(len(final.wound_turn_end_receipts), len(old.wound_turn_end_receipts) + 1)
        self.assertIsNone(final.round_state.active_turn)

    def test_real_expiry_shared_projection_matches_old_control_except_retained_prone(self):
        for other_source in (False, True):
            with self.subTest(other_source=other_source):
                control = wound_request(other=other_source)
                old = prone(control.state, control.actor_id)
                source = NpcRosterProneTurnEndRequest(control.id, old, control.actor_id, control.condition_sources)
                final = apply(old, end(source))
                expected = prone(end_npc_wound_turn(control).state, control.actor_id)
                self.assertEqual(final, expected)
                self.assertEqual(final.wound_expiries, ())
                self.assertEqual(final.spatial_state, old.spatial_state)
                self.assertEqual(final.champion_attack.daily_wounds, old.champion_attack.daily_wounds)
                self.assertEqual(final.consumed_execution_ids, old.consumed_execution_ids)
                self.assertEqual(final.roster.participant(control.actor_id).state.injury.conditions.has(
                    Condition.DRAINED), other_source)
                self.assertTrue(final.roster.participant(control.actor_id).state.injury.conditions.has(Condition.PRONE))

    def test_bound_end_requires_explicit_journal_opt_in(self):
        old = resolve_npc_roster_unnatural_wind(wind_request()).state
        result = end(NpcRosterProneTurnEndRequest('end:wind', old, old.wizard.actor_id))
        with self.assertRaises(ValueError):
            validate_magic_step_policy(admitted(), NpcMagicStep(result))
        with self.assertRaises(ValueError):
            apply(replace(old, consumed_execution_ids=(*old.consumed_execution_ids, 'foreign')), result)


if __name__ == '__main__':
    unittest.main()
