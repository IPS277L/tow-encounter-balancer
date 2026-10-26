"""Actual action/end-turn chains across source-bound scheduling phases."""
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_m8_npc_magic_scenario import scenario
from tests.unit.test_m8_npc_roster_minion_attack import parts
from tests.integration.test_m8_npc_roster_minion_defeat import shoot, close
from towr.domain.cowardly_flight_casting_models import CowardlyFlightCastingFacts, CowardlyFlightCastingPolicy
from towr.domain.cowardly_flight_casting_completion_models import CowardlyFlightCastingCompletionRequest
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionSourceSnapshot
from towr.domain.npc_champion_attack_models import NpcChampionAttackRequest
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest, NpcRosterChampionAttackResult
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingTargetContext
from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionRequest, NpcRosterCastingCompletionResult
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest, NpcRosterRoundAdvanceRequest
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.resolution_models import GiveGroundResolutionRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.test_models import InlineProfile
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting, complete_cowardly_flight_casting
from towr.rules.cowardly_flight_resolution import complete_cowardly_flight_movement
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_champion_attack_resolution import apply_npc_roster_champion_attack_result
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting, apply_npc_roster_casting_result
from towr.rules.npc_roster_casting_completion_resolution import apply_npc_roster_casting_completion
from towr.rules.npc_wound_turn_end import end_npc_wound_turn, apply_npc_wound_turn_end_result
from towr.rules.spatial_resolution import resolve_give_ground
from towr.rules.npc_roster_turn_resolution import (
    start_npc_roster_turn, advance_npc_roster_round, apply_npc_roster_turn_start_result, apply_npc_roster_round_advance_result,
)
from tests.unit.test_m8_npc_roster_turn import ATTACK, CAST


def activate(state, actor, declaration=ATTACK):
    request = NpcRosterTurnStartRequest(f'phase:{state.round_state.round_number}:{actor}', state, actor, declaration)
    return apply_npc_roster_turn_start_result(state, start_npc_roster_turn(request))


def end(state, actor, drained=False):
    sources = (WoundConditionSourceSnapshot(Condition.DRAINED, False),) if drained else ()
    request = NpcWoundTurnEndRequest(f'end:{state.round_state.round_number}:{actor}', state, actor, sources)
    return apply_npc_wound_turn_end_result(state, end_npc_wound_turn(request))


def advance(state):
    result = advance_npc_roster_round(NpcRosterRoundAdvanceRequest(f'advance:{state.round_state.round_number}', state))
    return apply_npc_roster_round_advance_result(state, result)


def cast(state, dice):
    source = prepare_npc_roster_casting(request_id=f'cast:{state.round_state.round_number}', state=state,
        selected_zone_id=state.spatial_state.placement_for('enemy').zone_id,
        targets=(NpcRosterCastingTargetContext('enemy', InlineProfile(3, 3), True),),
        facts=CowardlyFlightCastingFacts(True, True, True, True, True, True, True, True, True, True, True, True),
        policy=CowardlyFlightCastingPolicy.CAST_WHEN_READY)
    result = NpcRosterCastingResult(source, execute_cowardly_flight_casting(source.casting, SequenceRandom(dice)))
    return apply_npc_roster_casting_result(state, result)


class RosterTurnIntegrationTests(unittest.TestCase):
    def test_real_curse_give_ground_round_and_next_start_keep_usage_until_advance(self):
        current = cast(activate(scenario().initial_runtime_state, 'wizard', CAST), (1, 2, 3))
        pending = current.pending_movement
        follow_up, = pending.pending_movements
        movement = resolve_give_ground(GiveGroundResolutionRequest(follow_up.request, pending.spatial_state,
            'enemy', 'middle', pending.source.targets[0].injury.conditions, away_from_entity_id='wizard'))
        source = NpcRosterCastingCompletionRequest(current, CowardlyFlightCastingCompletionRequest(pending,
            (complete_cowardly_flight_movement(follow_up, movement),), movement.state))
        result = NpcRosterCastingCompletionResult(source,
            complete_cowardly_flight_casting(source.completion, SequenceRandom((1, 2, 3))))
        current = apply_npc_roster_casting_completion(current, result)
        current = shoot(activate(end(current, 'wizard'), 'ally'), 'ally', 'enemy', 'shot:ally', (10,) * 6, Range.MEDIUM)
        current = shoot(activate(end(current, 'ally'), 'enemy'), 'enemy', 'ally', 'shot:enemy', (10,) * 6, Range.MEDIUM)
        current = end(current, 'enemy')
        self.assertTrue(current.round_state.round_complete)
        self.assertEqual(current.spatial_state.gave_ground_entity_ids, ('enemy',))
        final = advance(current)
        self.assertEqual(final.spatial_state.gave_ground_entity_ids, ())
        self.assertEqual(final.spatial_state.placement_for('enemy').zone_id, 'middle')
        self.assertEqual(final.consumed_execution_ids, current.consumed_execution_ids)
        self.assertEqual(final.wound_turn_end_receipts, current.wound_turn_end_receipts)
        started = activate(final, 'ally')  # Caller may change intra-side preference next round.
        self.assertEqual(started.round_state.active_turn.actor_id, 'ally')
        self.assertEqual(started.round_state.round_number, 2)
        self.assertFalse(started.round_state.active_turn.action_slots[0].executed)

    def test_wound_received_after_wizard_turn_carries_to_next_target_turn_end(self):
        current = cast(activate(scenario().initial_runtime_state, 'wizard', CAST), (10, 10, 10))
        current = shoot(activate(end(current, 'wizard'), 'ally'), 'ally', 'enemy', 'shot:ally', (10,) * 6)
        current = activate(end(current, 'ally'), 'enemy')
        prepared, execution = parts(current, 'enemy', 'wizard', 'incoming')
        source = NpcRosterChampionAttackRequest(current, NpcChampionAttackRequest(current.champion_attack, prepared, execution))
        result = NpcRosterChampionAttackResult(source, execute_npc_champion_attack(source.attack,
            SequenceRandom((1, 2, 3, 10, 10, 10, 6))))
        current = end(apply_npc_roster_champion_attack_result(current, result), 'enemy')
        self.assertEqual(current.wound_expiries[0].deadline_round_number, 2)
        following = advance(current)
        self.assertIs(following.wizard, current.wizard)
        self.assertEqual(following.wound_expiries, current.wound_expiries)
        self.assertEqual(following.champion_attack.daily_wounds, current.champion_attack.daily_wounds)
        self.assertTrue(following.roster.participant('wizard').state.injury.conditions.has(Condition.DRAINED))
        following = cast(activate(following, 'wizard', CAST), (10, 10, 10))
        final = end(following, 'wizard', drained=True)
        self.assertEqual(final.wound_expiries, ())
        self.assertFalse(final.roster.participant('wizard').state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(final.champion_attack.daily_wounds, current.champion_attack.daily_wounds)
        self.assertEqual(final.champion_attack.consumed_wound_roll_ids, current.champion_attack.consumed_wound_roll_ids)
        self.assertEqual(final.minion_attack.consumed_execution_ids, ('shot:ally',))
        self.assertEqual(final.consumed_execution_ids, ('cast:1', 'shot:ally', 'incoming', 'cast:2'))

    def test_acknowledged_defeat_archive_is_excluded_again_in_new_round_without_reack(self):
        current = shoot(activate(scenario(blocker=True).initial_runtime_state, 'ally'), 'ally', 'enemy', 'defeat',
                        (1, 2, 3, 10, 10, 10))
        current, _ = close(current)
        # A legal WAIT targets the surviving Minion's Zone, not the dead enemy.
        current = activate(end(current, 'ally'), 'wizard', CAST)
        from tests.integration.test_m8_npc_roster_minion_defeat import wait_cast
        current = wait_cast(current, 'blocker')
        current = shoot(activate(end(current, 'wizard'), 'blocker'), 'blocker', 'ally', 'shot:blocker', (10,) * 6, Range.MEDIUM)
        current = end(current, 'blocker')
        final = advance(current)
        self.assertEqual(final.round_state.excluded_turn_entity_ids, ('enemy',))
        self.assertEqual(final.round_state.completed_turn_entity_ids, ())
        self.assertEqual(len(final.roster.participants), 4)
        self.assertEqual(len(final.spatial_state.placements), 4)
        self.assertEqual(final.minion_attack.acknowledged_defeat_execution_ids, ('defeat',))
        self.assertEqual(final.minion_attack.consumed_execution_ids, ('defeat', 'shot:blocker'))
        self.assertEqual(final.minion_attack.roster, final.roster)
        self.assertIsNone(final.pending_minion_attack)


if __name__ == '__main__':
    unittest.main()
