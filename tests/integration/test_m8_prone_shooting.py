"""Actual scoped Shooting -> injury/end-turn handoffs with full owner evidence."""
from dataclasses import replace
import unittest

from tests.integration.test_m8_champion_casting_handoff import incoming_attack
from tests.integration.test_m8_npc_roster_prone_stand import prone
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from tests.unit.test_m8_npc_roster_minion_attack import request as minion_request
from tests.unit.test_m8_npc_roster_prone_stand import with_injury
from towr.domain.condition_models import Condition
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_prone_models import NpcRosterProneTurnEndRequest
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
from towr.rules.npc_roster_prone_resolution import end_npc_roster_prone_turn
from towr.rules.npc_roster_shooting_preparation import prepare_npc_roster_shooting


def prepared(original, state):
    attack = original.attack
    source = attack.preparation.npc_attack.source_request
    protection = attack.preparation.protection.source_request
    return prepare_npc_roster_shooting(request_id=attack.execution.id, state=state,
        actor_id=attack.execution.actor_id, target_id=attack.execution.target_id,
        selected_attack_id=source.selected_attack_id, target_range=source.target_range,
        has_enemy_in_close_range=source.has_enemy_in_close_range,
        range_approved_by_gm=source.range_approved_by_gm,
        defender_is_aware=protection.defender_is_aware, selected_protection_skill=protection.selected_skill,
        can_target_leave_zone=True)


class ProneShootingIntegrationTests(unittest.TestCase):
    def test_prone_shooter_miss_preserves_full_owner_and_ends_without_standing(self):
        original = minion_request()
        old = prone(original.state, original.attack.execution.actor_id)
        source = prepared(original, old)
        dice = Dice((10,) * 6)
        result = execute_npc_roster_minion_attack(source, dice)
        dice.exhausted()
        final = result.state
        self.assertEqual(final.spatial_state, old.spatial_state)
        self.assertEqual(final.wizard, old.wizard)
        self.assertEqual(final.consumed_execution_ids, (source.attack.execution.id,))
        self.assertEqual(final.champion_attack.roster, final.roster)
        self.assertEqual(final.minion_attack.roster, final.roster)
        actor_id = source.attack.execution.actor_id
        self.assertTrue(final.roster.participant(actor_id).state.injury.conditions.has(Condition.PRONE))
        ended = end_npc_roster_prone_turn(NpcRosterProneTurnEndRequest('end:shooting', final, actor_id)).state
        self.assertEqual(ended.roster, final.roster)
        self.assertEqual(ended.spatial_state, old.spatial_state)

    def test_prone_minion_target_costs_exactly_one_attacker_die_not_protection(self):
        original = minion_request()
        target_id = original.attack.execution.target_id
        old = prone(original.state, target_id)
        source = prepared(original, old)
        dice = Dice((10,) * 5)
        result = execute_npc_roster_minion_attack(source, dice)
        dice.exhausted()
        self.assertEqual(source.attack.preparation.protection.source_request.options,
                         original.attack.preparation.protection.source_request.options)
        self.assertFalse(source.attack.execution.kernel_request.can_target_leave_zone)
        self.assertEqual(result.state.roster.participant(target_id), old.roster.participant(target_id))
        self.assertEqual(result.state.spatial_state, old.spatial_state)

    def test_prone_staggered_minion_suffers_wound_without_departure(self):
        original = minion_request()
        target_id = original.attack.execution.target_id
        old = with_injury(prone(original.state, target_id), target_id, lambda i: replace(
            i, conditions=i.conditions.with_condition(Condition.STAGGERED)))
        source = prepared(original, old)
        dice = Dice((1, 10, 10, 10, 10))
        result = execute_npc_roster_minion_attack(source, dice, decisions=FixedKernelDecisions())
        dice.exhausted()
        self.assertTrue(result.state.roster.participant(target_id).state.injury.defeated)
        self.assertEqual(result.state.spatial_state, old.spatial_state)
        self.assertIsNotNone(result.state.pending_minion_attack)  # Existing defeat continuation, not movement.
        self.assertFalse(source.attack.execution.kernel_request.can_target_leave_zone)

    def test_prone_staggered_champion_retains_wound_daily_magic_and_full_source(self):
        original = incoming_attack()
        target_id = original.attack.execution.target_id
        old = with_injury(prone(original.state, target_id), target_id, lambda i: replace(
            i, conditions=i.conditions.with_condition(Condition.STAGGERED)))
        source = prepared(original, old)
        dice = Dice((1, 10, 10, 10, 10, 2))
        result = NpcRosterChampionAttackResult(source, execute_npc_champion_attack(
            source.attack, dice, decisions=FixedKernelDecisions()))
        dice.exhausted()
        final = result.state
        injury = final.roster.participant(target_id).state.injury
        self.assertEqual(len(injury.wounds), 1)
        self.assertTrue(injury.conditions.has(Condition.PRONE))
        self.assertFalse(injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(len(final.champion_attack.daily_wounds.receipts), 1)
        self.assertEqual(final.wizard, old.wizard)
        self.assertEqual(final.spatial_state, old.spatial_state)
        self.assertEqual(final.consumed_execution_ids, (source.attack.execution.id,))
        self.assertIsNone(final.champion_attack.pending)


if __name__ == '__main__':
    unittest.main()
