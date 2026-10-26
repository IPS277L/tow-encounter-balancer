"""Defeat closure through actual M8 attacks/turns, including final targets."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_m8_npc_magic_scenario import scenario, OPPOSITION
from tests.unit.test_m8_npc_roster_minion_attack import request as attack_request, begin, parts
from tests.unit.test_m8_npc_roster_minion_defeat import request as defeat_request
from tests.integration.test_m8_npc_roster_minion_attack import end
from towr.domain.cowardly_flight_casting_models import CowardlyFlightCastingFacts, CowardlyFlightCastingPolicy
from towr.domain.condition_models import Condition
from towr.domain.npc_champion_attack_models import NpcChampionAttackRequest
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest, NpcRosterChampionAttackResult
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingTargetContext
from towr.domain.npc_roster_minion_attack_models import NpcRosterMinionAttackRequest
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import CombatActionKind
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
from towr.rules.npc_roster_minion_defeat_resolution import acknowledge_npc_roster_minion_defeat, apply_npc_roster_minion_defeat_result
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_champion_attack_resolution import apply_npc_roster_champion_attack_result
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting, apply_npc_roster_casting_result
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting


def close(state):
    result = acknowledge_npc_roster_minion_defeat(defeat_request(state))
    return apply_npc_roster_minion_defeat_result(state, result), result


def shoot(state, actor, target, identifier, dice, target_range=Range.SHORT):
    prepared, execution = parts(state, actor, target, identifier, target_range=target_range)
    source = NpcRosterMinionAttackRequest(state, NpcRosterAttackExecutionRequest(state.minion_attack, prepared, execution))
    return execute_npc_roster_minion_attack(source, SequenceRandom(dice)).state


def wait_cast(state, target):
    source = prepare_npc_roster_casting(request_id='wizard:cast', state=state,
        selected_zone_id=state.spatial_state.placement_for(target).zone_id,
        targets=(NpcRosterCastingTargetContext(target, InlineProfile(3, 3), True),),
        facts=CowardlyFlightCastingFacts(True, True, True, True, True, True, True, True, True, True, True, True),
        policy=CowardlyFlightCastingPolicy.CAST_WHEN_READY)
    result = NpcRosterCastingResult(source, execute_cowardly_flight_casting(source.casting, SequenceRandom((10, 10, 10))))
    return apply_npc_roster_casting_result(state, result)


def incoming(state, wound=False):
    state = begin(state, 'enemy')
    prepared, execution = parts(state, 'enemy', 'wizard', 'incoming')
    source = NpcRosterChampionAttackRequest(state, NpcChampionAttackRequest(state.champion_attack, prepared, execution))
    dice = (1, 2, 3, 10, 10, 10, 6) if wound else (10,) * 6
    result = NpcRosterChampionAttackResult(source, execute_npc_champion_attack(source.attack, SequenceRandom(dice)))
    return apply_npc_roster_champion_attack_result(state, result)


class MinionDefeatIntegrationTests(unittest.TestCase):
    def test_last_enemy_closes_pending_and_allows_end_turn_without_live_cast_projection(self):
        source = attack_request()
        pending = execute_npc_roster_minion_attack(source, SequenceRandom((1, 2, 3, 10, 10, 10))).state
        with self.assertRaisesRegex(ValueError, 'pending Minion attack'): end(pending, 'ally')
        final, result = close(pending)
        self.assertTrue(result.excludes_target)
        self.assertEqual(final.round_state.excluded_turn_entity_ids, ('enemy',))
        self.assertEqual(len(final.round_state.participants), 3)
        self.assertEqual(len(final.spatial_state.placements), 3)
        ended = end(final, 'ally')
        self.assertEqual(ended.round_state.completed_turn_entity_ids, ('ally',))
        self.assertFalse(ended.round_state.round_complete)  # Wizard turn remains; no invented victory/advance.
        self.assertEqual(ended.minion_attack.acknowledged_defeat_execution_ids, ('minion:attack',))

    def test_target_which_already_acted_is_not_excluded_or_completed_again(self):
        current = incoming(scenario(wizard_side=OPPOSITION).initial_runtime_state)
        current = begin(end(current, 'enemy'), 'ally')
        pending = execute_npc_roster_minion_attack(attack_request(current), SequenceRandom((1, 2, 3, 10, 10, 10))).state
        final, result = close(pending)
        self.assertFalse(result.excludes_target)
        self.assertIs(final.round_state, pending.round_state)
        self.assertEqual(final.round_state.completed_turn_entity_ids, ('enemy',))
        self.assertEqual(final.round_state.excluded_turn_entity_ids, ())
        self.assertEqual(result.applied_rule_ids, ('RULE-NPC-002',))
        self.assertEqual(final.champion_attack.consumed_execution_ids, ('incoming',))

    def test_wound_daily_magic_and_expiry_survive_defeat_closure(self):
        wounded = incoming(scenario(wizard_side=OPPOSITION, blocker=True).initial_runtime_state, wound=True)
        current = begin(end(wounded, 'enemy'), 'blocker')
        current = shoot(current, 'blocker', 'ally', 'blocker:shot', (10,) * 6, Range.MEDIUM)
        current = begin(end(current, 'blocker'), 'ally')
        pending = execute_npc_roster_minion_attack(attack_request(current), SequenceRandom((1, 2, 3, 10, 10, 10))).state
        closed, _ = close(pending)
        self.assertEqual(closed.wound_expiries, wounded.wound_expiries)
        self.assertIs(closed.wizard, pending.wizard)
        self.assertIs(closed.spatial_state, pending.spatial_state)
        self.assertEqual(closed.champion_attack.daily_wounds, wounded.champion_attack.daily_wounds)
        current = begin(end(closed, 'ally'), 'wizard', CombatActionKind.IMPROVISE)
        current = wait_cast(current, 'blocker')
        final = end(current, 'wizard', drained=True)
        self.assertFalse(final.roster.participant('wizard').state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(final.champion_attack.daily_wounds, wounded.champion_attack.daily_wounds)
        self.assertEqual(final.champion_attack.consumed_wound_roll_ids, wounded.champion_attack.consumed_wound_roll_ids)
        self.assertEqual(final.minion_attack.acknowledged_defeat_execution_ids, ('minion:attack',))
        self.assertEqual(final.minion_attack.consumed_execution_ids, ('blocker:shot', 'minion:attack'))
        self.assertEqual(final.minion_attack.roster, final.roster)
        self.assertEqual(final.consumed_execution_ids, ('incoming', 'blocker:shot', 'minion:attack', 'wizard:cast'))

    def test_two_defeats_preserve_histories_and_only_complete_current_round(self):
        current = execute_npc_roster_minion_attack(attack_request(scenario(blocker=True).initial_runtime_state),
            SequenceRandom((1, 2, 3, 10, 10, 10))).state
        current, _ = close(current)
        current = begin(end(current, 'ally'), 'wizard', CombatActionKind.IMPROVISE)
        current = wait_cast(current, 'blocker')
        current = begin(end(current, 'wizard'), 'blocker')
        current = shoot(current, 'blocker', 'ally', 'second:attack', (1, 2, 3, 10, 10, 10), Range.MEDIUM)
        current, result = close(current)
        self.assertFalse(result.excludes_target)
        self.assertEqual(current.round_state.excluded_turn_entity_ids, ('enemy',))
        final = end(current, 'blocker')
        self.assertTrue(final.round_state.round_complete)
        self.assertEqual(final.round_state.round_number, 1)
        self.assertEqual(final.minion_attack.acknowledged_defeat_execution_ids, ('minion:attack', 'second:attack'))
        self.assertEqual(final.consumed_execution_ids, ('minion:attack', 'wizard:cast', 'second:attack'))
        self.assertEqual(len(final.roster.participants), 4)


if __name__ == '__main__':
    unittest.main()
