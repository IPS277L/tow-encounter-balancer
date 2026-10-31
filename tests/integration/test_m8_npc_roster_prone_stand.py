"""Bound self-stand handoffs, not automatic opt-in runner continuation."""
from copy import deepcopy
from dataclasses import fields, replace
import unittest
from unittest.mock import patch

from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_m8_npc_magic_scenario_runner import admitted, Dice
from tests.unit.test_m8_npc_roster_minion_attack import request as attack_request
from tests.unit.test_m8_npc_roster_unnatural_wind import request as wind_request
from tests.integration.test_m8_npc_broken_recover import wounded_broken_wizard
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.movement_models import FreeMovementRequest, MovementSpeed
from towr.domain.npc_magic_step_models import NpcMagicStep
from towr.domain.npc_magic_journal_policy import validate_magic_step_policy
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_roster_prone_models import NpcRosterProneStandRequest as Request
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.npc_roster_casting_resolution import apply_npc_roster_casting_result
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
from towr.rules.npc_roster_miscast_resolution import resolve_npc_roster_unnatural_wind
from towr.rules.npc_roster_prone_resolution import stand_npc_roster_prone as stand, apply_npc_roster_prone_stand as apply


def prone(state, actor_id):
    """Authored standalone Prone, not a simulated automatic Wind continuation."""
    roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=replace(p.state.injury,
        conditions=p.state.injury.conditions.with_condition(Condition.PRONE))))
        if p.state.actor_id == actor_id else p for p in state.roster.participants))
    return replace(state, roster=roster,
        champion_attack=None if state.champion_attack is None else replace(state.champion_attack, roster=roster),
        minion_attack=None if state.minion_attack is None else replace(state.minion_attack, roster=roster))


class ProneStandIntegrationTests(unittest.TestCase):
    def test_stand_then_existing_casting_spends_only_its_original_action(self):
        # Capture a real reserved Casting source, before its actual result.
        captured = run_npc_magic_scenario(admitted(), Dice((9, 9, 9))).steps[-1].result.source
        old = prone(captured.state, captured.state.wizard.actor_id)
        result = stand(Request('self-stand', old, old.wizard.actor_id, False, True))
        current = apply(old, result)
        source = replace(captured, state=current, casting=replace(captured.casting,
            spatial_state=current.casting_spatial_state))
        dice = Dice((1, 10, 10))
        cast = NpcRosterCastingResult(source, execute_cowardly_flight_casting(source.casting, dice))
        final = apply_npc_roster_casting_result(current, cast)
        dice.exhausted()
        self.assertEqual(final.consumed_execution_ids, (source.casting.id,))
        self.assertNotIn(result.source.id, final.consumed_execution_ids)
        self.assertEqual(final.spatial_state.free_move_used_entity_ids, (old.wizard.actor_id,))
        self.assertEqual(final.spatial_state.placements, old.spatial_state.placements)
        self.assertEqual(final.champion_attack.roster, final.roster)
        self.assertEqual(final.minion_attack.roster, final.roster)
        self.assertTrue(final.round_state.active_turn.action_slots[0].executed)

    def test_stand_then_existing_minion_attack_preserves_one_receipt_and_usage(self):
        original = attack_request()
        actor = original.attack.execution.actor_id
        old = prone(original.state, actor)
        current = stand(Request('stand:archer', old, actor, False, True)).state
        source = replace(original, state=current)
        dice = Dice((10,) * 6)
        result = execute_npc_roster_minion_attack(source, dice,
            decisions=FixedKernelDecisions(stagger=StaggerChoice.SUFFER_WOUND))
        dice.exhausted()
        self.assertEqual(result.state.consumed_execution_ids, (source.attack.execution.id,))
        self.assertEqual(result.state.spatial_state.free_move_used_entity_ids, (actor,))
        self.assertEqual(result.state.spatial_state.placements, old.spatial_state.placements)
        self.assertFalse(result.state.roster.participant(actor).state.injury.conditions.has(Condition.PRONE))

    def test_real_wound_timer_magic_daily_history_and_broken_are_preserved(self):
        _, _, wounded = wounded_broken_wizard(1)
        actor = wounded.wizard.actor_id
        old = prone(wounded, actor)
        before = deepcopy(old)
        # This low-level mechanical input asserts no Close enemy. Same-Zone
        # Broken routing belongs to the future runner, not to this reducer.
        with patch('random.Random', side_effect=AssertionError('no RNG')):
            result = stand(Request('stand:wounded', old, actor, False, True))
            final = apply(old, result)
        injury = old.roster.participant(actor).state.injury
        self.assertEqual(final.roster.participant(actor).state.injury,
                         replace(injury, conditions=injury.conditions.without_condition(Condition.PRONE)))
        self.assertTrue(final.roster.participant(actor).state.injury.conditions.has(Condition.BROKEN))
        self.assertTrue(final.roster.participant(actor).state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(final.champion_attack, replace(old.champion_attack, roster=final.roster))
        for field in fields(old):
            if field.name not in ('roster', 'spatial_state', 'champion_attack', 'minion_attack'):
                self.assertEqual(getattr(final, field.name), getattr(old, field.name), field.name)
        self.assertEqual(final.wound_expiries[0].deadline_round_number, final.round_state.round_number)
        self.assertEqual(old, before)

    def test_stand_and_actual_free_movement_share_the_same_resource(self):
        original = attack_request()
        actor = original.attack.execution.actor_id
        old = prone(original.state, actor)
        current = stand(Request('stand:archer', old, actor, False, True)).state
        movement = FreeMovementRequest('move-after-standing', current.round_state, current.spatial_state,
            actor, MovementSpeed.NORMAL, current.roster.participant(actor).state.injury.conditions, ('middle',))
        with self.assertRaisesRegex(ValueError, 'once per turn'):
            resolve_free_movement(movement)
        # A new ID and a fresh standalone Prone application do not reset usage.
        with self.assertRaisesRegex(ValueError, 'unused free movement'):
            Request('stand:again', prone(current, actor), actor, False, True)

    def test_actual_wind_keeps_completed_action_and_cannot_stand_after_it(self):
        source = wind_request()
        wind = resolve_npc_roster_unnatural_wind(source)
        state = wind.state
        self.assertTrue(state.round_state.active_turn.action_slots[0].executed)
        self.assertTrue(state.roster.participant(state.wizard.actor_id).state.injury.conditions.has(Condition.PRONE))
        with self.assertRaisesRegex(ValueError, 'unexecuted standard slot'):
            Request('too-late', state, state.wizard.actor_id, False, True)
        self.assertEqual(state.wizard.magic_state.miscast_dice, 0)

    def test_stand_requires_explicit_journal_opt_in(self):
        original = attack_request()
        actor = original.attack.execution.actor_id
        result = stand(Request('stand:archer', prone(original.state, actor), actor, False, True))
        with self.assertRaises(ValueError):
            validate_magic_step_policy(admitted(), NpcMagicStep(result))


if __name__ == '__main__':
    unittest.main()
