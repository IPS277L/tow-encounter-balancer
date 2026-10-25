"""Real Curse/Champion Wound sources followed by the deterministic Run chain."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.unit.test_m8_cowardly_flight_casting import CountingDice
from tests.unit.test_m8_cowardly_flight_casting_models import casting_input
from tests.unit.test_m8_npc_roster_casting import bound_request, change_injury
from tests.unit.test_m8_npc_broken_run import request as run_request
from tests.integration.test_m8_npc_broken_recover import first_enemy_recover_turn, wounded_broken_wizard
from towr.domain.condition_models import Condition
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.movement_models import FreeMovementRequest, MovementSpeed
from towr.domain.npc_broken_run_models import NpcBrokenRunRequest
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest
from towr.domain.spatial_models import ZoneGraph, ZoneConnection
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind, ManoeuvreKind
from towr.domain.magic_models import WizardMagicState
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.engine.npc_broken_run import execute_npc_broken_run, apply_npc_broken_run_result
from towr.rules.npc_roster_casting_resolution import apply_npc_roster_casting_result, prepare_npc_roster_casting


def run_slot(combat):
    turn = combat.active_turn
    slot = replace(turn.action_slots[0], declaration=CombatActionDeclaration(
        CombatActionKind.MANOEUVRE, manoeuvre=ManoeuvreKind.RUN))
    return replace(combat, active_turn=replace(turn, action_slots=(slot,)))


def from_owner(owner, actor):
    combat = run_slot(owner.round_state)
    spatial = replace(owner.spatial_state,
        graph=ZoneGraph(('arena', 'middle', 'safe'), (
            ZoneConnection('arena', 'middle'), ZoneConnection('middle', 'safe'))),
        placements=tuple(replace(p, zone_id='middle') if p.entity_id == 'brigand:1'
                         else replace(p, zone_id='arena') for p in owner.spatial_state.placements))
    champion = owner.champion_attack
    if champion is not None:
        champion = replace(champion, round_state=combat)
    owner = replace(owner, round_state=combat, spatial_state=spatial, champion_attack=champion)
    movement = FreeMovementRequest('broken-run:free-move', combat, spatial, actor,
        MovementSpeed.NORMAL, owner.roster.participant(actor).state.injury.conditions, ('middle',))
    return NpcBrokenRunRequest('broken-run', owner, actor, movement, 'safe', (), False, False, True)


class NpcBrokenRunIntegrationTests(unittest.TestCase):
    def test_real_curse_then_broken_minion_free_move_and_run_without_recover(self):
        source = casting_input()
        spatial = replace(source.spatial_state,
            graph=ZoneGraph(('arena', 'elsewhere', 'empty'), (
                ZoneConnection('arena', 'elsewhere'), ZoneConnection('elsewhere', 'empty'))),
            placements=tuple(replace(p, zone_id='elsewhere') if p.entity_id == 'friend' else p
                             for p in source.spatial_state.placements),
            gave_ground_entity_ids=('second', 'first'))
        bound = bound_request(replace(source, spatial_state=spatial))
        rng = CountingDice([1, 2, 3] + [10] * 6)
        cast = execute_cowardly_flight_casting(bound.casting, rng)
        owner = apply_npc_roster_casting_result(bound.state, NpcRosterCastingResult(bound, cast))
        combat = run_slot(first_enemy_recover_turn(owner.round_state))
        owner = replace(owner, round_state=combat)
        movement = FreeMovementRequest('broken-run:free-move', combat, owner.spatial_state, 'first',
            MovementSpeed.NORMAL, owner.roster.participant('first').state.injury.conditions, ('elsewhere',))
        request = NpcBrokenRunRequest('broken-run', owner, 'first', movement, 'empty', (), False, False, True)
        with patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Run Test')):
            result = execute_npc_broken_run(request)
            final = apply_npc_broken_run_result(owner, result)
        self.assertEqual(rng.calls, 9)
        self.assertTrue(final.roster.participant('first').state.injury.conditions.has(Condition.BROKEN))
        self.assertEqual(final.spatial_state.placement_for('first').zone_id, 'empty')
        self.assertEqual(final.spatial_state.gave_ground_entity_ids, ('second', 'first'))
        self.assertEqual(final.spatial_state.free_move_used_entity_ids, ('first',))
        self.assertEqual(final.consumed_execution_ids, ('cast', 'broken-run'))
        self.assertIs(final.wizard, owner.wizard)
        self.assertIsNone(result.interruption)
        self.assertEqual(final.round_state.completed_turn_entity_ids, ('wizard', 'friend'))

    def test_real_wound_wizard_run_preserves_daily_and_both_histories(self):
        source, attack, owner = wounded_broken_wizard(1)
        request = from_owner(owner, owner.wizard.actor_id)
        result = execute_npc_broken_run(request)
        final = apply_npc_broken_run_result(request.state, result)
        self.assertIs(final.roster, request.state.roster)
        injury = final.roster.participant(final.wizard.actor_id).state.injury
        self.assertEqual(injury.wounds, attack.resolution.target_state.wounds)
        self.assertEqual(injury.active_wound_effects, attack.resolution.target_state.active_wound_effects)
        self.assertTrue(injury.conditions.has(Condition.BROKEN))
        self.assertTrue(injury.conditions.has(Condition.DRAINED))
        self.assertEqual(final.wizard.magic_state, WizardMagicState(2, 1, 'lore:battle-magic', 1))
        self.assertIsNone(final.pending_interruption)
        self.assertEqual(final.champion_attack.daily_wounds, owner.champion_attack.daily_wounds)
        self.assertEqual(final.champion_attack.consumed_wound_roll_ids, owner.champion_attack.consumed_wound_roll_ids)
        self.assertEqual(final.champion_attack.consumed_execution_ids, (source.attack.execution.id,))
        self.assertEqual(final.consumed_execution_ids, (source.attack.execution.id, 'broken-run'))
        self.assertIs(final.champion_attack.roster, final.roster)
        self.assertIs(final.champion_attack.round_state, final.round_state)
        self.assertIs(final.round_state.active_turn.action_slots[0].execution, result.interruption.action)

    def test_run_triggered_miscast_keeps_successes_and_blocks_bound_actions(self):
        source, _, owner = wounded_broken_wizard(2)
        request = from_owner(owner, owner.wizard.actor_id)
        result = execute_npc_broken_run(request)
        final = result.state
        self.assertIs(final.pending_interruption, result.interruption)
        self.assertEqual(final.wizard.magic_state, WizardMagicState(3, 1, 'lore:battle-magic', 1))
        self.assertEqual(final.pending_interruption.miscast_pool.roll_request.pool_dice_count, 3)
        self.assertEqual(final.pending_interruption.miscast_pool.roll_request.bonus_dice, 0)
        self.assertTrue(final.roster.participant(final.wizard.actor_id).state.injury.conditions.has(Condition.BROKEN))
        self.assertEqual(final.champion_attack.daily_wounds, owner.champion_attack.daily_wounds)
        with self.assertRaisesRegex(ValueError, 'pending interruption'):
            NpcRosterChampionAttackRequest(final, source.attack)
        with self.assertRaisesRegex(ValueError, 'pending interruption'):
            prepare_npc_roster_casting(request_id='cast', state=final, selected_zone_id='safe', targets=(),
                facts=casting_input().facts, policy=casting_input().policy)

    def test_archived_enemy_does_not_block_safety_and_all_usage_histories_survive(self):
        source = run_request()
        state = change_injury(source.state, 'first', ProfileInjuryState(1, 1, defeated=True))
        spatial = replace(state.spatial_state,
            placements=tuple(replace(p, zone_id='empty') if p.entity_id == 'first' else p
                             for p in state.spatial_state.placements),
            gave_ground_entity_ids=('first',), free_move_used_entity_ids=('first',),
            difficult_terrain_tested_entity_ids=('first',))
        source = replace(source, state=replace(state, spatial_state=spatial),
                         movement=replace(source.movement, state=spatial))
        result = execute_npc_broken_run(source)
        final = result.state
        self.assertIs(final.roster, source.state.roster)
        self.assertIs(final.spatial_state.placement_for('first'), spatial.placement_for('first'))
        self.assertEqual(final.spatial_state.gave_ground_entity_ids, ('first',))
        self.assertEqual(final.spatial_state.free_move_used_entity_ids, ('first', 'wizard'))
        self.assertEqual(final.spatial_state.difficult_terrain_tested_entity_ids, ('first',))


if __name__ == '__main__':
    unittest.main()
