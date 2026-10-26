"""Real multi-turn magic encounters, finite scenes and exact RNG budgets."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_scenario import scenario, frame, OPPOSITION, ROUTE
from tests.unit.test_m8_npc_magic_scenario_runner import Dice, admitted, departures, after_curse
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.npc_magic_scene_models import NpcMagicBrokenPlan, NpcMagicBrokenPlanKind
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartResult, NpcRosterRoundAdvanceResult
from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionResult
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario as run


class MagicRunnerIntegrationTests(unittest.TestCase):
    def test_objective_closes_defeat_and_end_before_stopping_without_new_wizard_turn(self):
        source = replace(admitted(), activation_order=('ally', 'wizard', 'enemy'))
        rng = Dice((1, 2, 3, 10, 10, 10)); result = run(source, rng); rng.exhausted()
        self.assertIs(result.outcome, Outcome.OBJECTIVE_ACHIEVED)
        self.assertEqual((result.started_rounds, result.completed_rounds, result.executed_actions), (1, 0, 1))
        self.assertEqual(result.current.round_state.completed_turn_entity_ids, ('ally',))
        self.assertEqual(result.current.round_state.excluded_turn_entity_ids, ('enemy',))
        self.assertEqual(len(result.current.roster.participants), 3)
        self.assertEqual(len(result.steps), 4)
        self.assertEqual(result.current.minion_attack.acknowledged_defeat_execution_ids,
                         result.current.minion_attack.consumed_execution_ids)
        self.assertIsNone(result.current.pending_minion_attack)

    def test_independent_perspective_uses_same_defeat_chain(self):
        source = replace(admitted(), perspective_side=OPPOSITION, objective=NpcDefeatObjective(('wizard', 'ally')))
        rng = Dice((10, 10, 10, 1, 2, 3, 10, 10, 10))
        result = run(source, rng); rng.exhausted()
        self.assertIs(result.outcome, Outcome.PERSPECTIVE_DEFEATED)
        self.assertEqual(result.executed_actions, 2)
        self.assertEqual(result.completed_rounds, 1)

    def test_archived_defeat_survives_live_cast_projection_and_next_round(self):
        source = scenario(blocker=True)
        future = frame(source.initial, live=('wizard', 'ally', 'blocker'))
        source = departures(replace(source, activation_order=('ally', 'wizard', 'enemy', 'blocker'),
            scene_frames=(*source.scene_frames, future)))
        rng = Dice((1, 2, 3, 10, 10, 10) + (10,) * 9 + (1, 2, 3, 10, 10, 10))
        result = run(source, rng); rng.exhausted()
        self.assertIs(result.outcome, Outcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.current.round_state.excluded_turn_entity_ids, ('enemy', 'blocker'))
        self.assertEqual(len(result.current.roster.participants), 4)
        self.assertEqual(len(result.current.spatial_state.placements), 4)
        self.assertEqual(len(result.current.minion_attack.acknowledged_defeat_execution_ids), 2)
        self.assertEqual(result.current.roster, result.current.minion_attack.roster)
        self.assertEqual(result.current.roster, result.current.champion_attack.roster)
        cast = next(s.result for s in result.steps if hasattr(s.result, 'casting'))
        self.assertEqual(tuple(t.actor_id for t in cast.source.casting.targets), ('blocker',))

    def test_two_completed_rounds_use_one_advance_and_no_extra_slot_after_limit(self):
        source = replace(admitted(), max_rounds=2); rng = Dice((10,) * 30)
        result = run(source, rng); rng.exhausted()
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertEqual((result.started_rounds, result.completed_rounds, result.executed_actions), (2, 2, 6))
        self.assertEqual(sum(isinstance(s.result, NpcRosterRoundAdvanceResult) for s in result.steps), 1)
        self.assertEqual([s.actor_id for s in result.steps if isinstance(s.result, NpcRosterTurnStartResult)],
                         ['wizard', 'ally', 'enemy'] * 2)
        self.assertEqual(result.current.round_state.round_number, result.current.spatial_state.round_number)
        self.assertEqual(len(result.current.minion_attack.consumed_execution_ids), 2)
        self.assertEqual(len(result.current.champion_attack.consumed_execution_ids), 2)

    def test_miscast_keeps_pool_source_and_unfinished_turn_even_at_one_round_budget(self):
        rng = Dice((9, 9, 9)); result = run(replace(admitted(), max_rounds=1), rng); rng.exhausted()
        self.assertIs(result.outcome, Outcome.UNSUPPORTED_PATH)
        self.assertIs(result.unsupported.reason, Reason.MISCAST_PREPARATION)
        self.assertEqual(result.current.wizard.magic_state.miscast_dice, 3)
        self.assertEqual((result.completed_rounds, result.executed_actions), (0, 1))
        self.assertIsNotNone(result.current.round_state.active_turn)

    def test_champion_wound_follow_up_blocks_end_turn_with_full_daily_history(self):
        rng = Dice((1, 2, 3, 10, 10, 10, 4))
        result = run(admitted(wizard_side=OPPOSITION), rng); rng.exhausted()
        self.assertIs(result.unsupported.reason, Reason.WOUND_EFFECT)
        self.assertEqual(result.unsupported.actor_id, 'enemy')
        self.assertEqual(result.unsupported.missing_actor_ids, ('wizard',))
        self.assertIsNotNone(result.current.champion_attack.pending)
        self.assertEqual(len(result.current.champion_attack.daily_wounds.receipts), 1)
        self.assertEqual(len(result.current.champion_attack.consumed_wound_roll_ids), 1)
        self.assertEqual(result.current.wound_turn_end_receipts, ())

    def test_wound_after_wizard_turn_advances_then_expires_at_next_wizard_end(self):
        rng = Dice((10,) * 9 + (1, 2, 3, 10, 10, 10, 6) + (10,) * 3 + (1, 2, 3, 10, 10, 10))
        result = run(admitted(), rng); rng.exhausted()
        self.assertIs(result.outcome, Outcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.current.wound_expiries, ())
        self.assertFalse(result.current.roster.participant('wizard').state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(len(result.current.champion_attack.daily_wounds.receipts), 1)
        self.assertEqual(len(result.current.champion_attack.consumed_wound_roll_ids), 1)
        self.assertEqual((result.started_rounds, result.executed_actions), (2, 5))
        self.assertTrue(any(r.expired_attack_ids for r in result.current.wound_turn_end_receipts))

    def test_injured_first_champion_target_is_not_skipped_for_an_available_minion(self):
        rng = Dice((1, 2, 3, 10, 10, 10, 6))
        result = run(admitted(wizard_side=OPPOSITION, blocker=True), rng); rng.exhausted()
        self.assertIs(result.unsupported.reason, Reason.TARGET_INJURY)
        self.assertEqual(result.unsupported.actor_id, 'blocker')
        self.assertEqual(result.unsupported.missing_actor_ids, ('wizard',))
        self.assertEqual(result.executed_actions, 1)
        self.assertTrue(result.current.wound_expiries)

    def test_curse_give_ground_and_safe_broken_recover_complete_actual_round(self):
        plan = NpcMagicBrokenPlan('enemy', NpcMagicBrokenPlanKind.SAFE_RECOVER, (), None, None, None, True)
        rng = Dice((1, 2, 3, 10, 10, 10) + (10,) * 6 + (1, 2, 3))
        result = run(after_curse(plan=plan), rng); rng.exhausted()
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertEqual(result.current.spatial_state.placement_for('enemy').zone_id, 'middle')
        self.assertEqual(result.current.spatial_state.gave_ground_entity_ids, ('enemy',))
        self.assertFalse(result.current.roster.participant('enemy').state.injury.conditions.has(Condition.BROKEN))
        self.assertEqual(result.executed_actions, 3)

    def test_curse_to_unsafe_zone_uses_supplied_free_move_before_recover(self):
        plan = NpcMagicBrokenPlan('enemy', NpcMagicBrokenPlanKind.FREE_MOVE_RECOVER, ('shelter',), ROUTE, None, None, True)
        rng = Dice((1, 2, 3, 10, 10, 10) + (10,) * 6 + (1, 2, 3))
        result = run(after_curse(plan=plan, ally_zone='middle'), rng); rng.exhausted()
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertEqual(result.current.spatial_state.placement_for('enemy').zone_id, 'shelter')
        self.assertEqual(result.current.spatial_state.free_move_used_entity_ids, ('enemy',))

    def test_missing_future_frame_is_preserved_after_real_curse_completion_and_end(self):
        rng = Dice((1, 2, 3, 10, 10, 10)); result = run(admitted(), rng); rng.exhausted()
        self.assertIs(result.unsupported.reason, Reason.MISSING_SCENE)
        self.assertEqual(result.unsupported.actor_id, 'ally')
        self.assertIsNone(result.current.pending_movement)
        self.assertEqual(result.current.spatial_state.placement_for('enemy').zone_id, 'middle')
        self.assertEqual(len(result.current.wound_turn_end_receipts), 1)
        self.assertEqual(result.executed_actions, 1)

    def test_partial_curse_keeps_full_unmoved_pending_and_does_not_roll_willpower(self):
        source = scenario(blocker=True)
        initial = replace(source.initial, spatial_state=replace(source.initial.spatial_state, placements=tuple(
            replace(p, zone_id='arena') if p.entity_id == 'blocker' else p for p in source.initial.spatial_state.placements)))
        source = departures(replace(source, initial=initial, scene_frames=(frame(initial),)))
        rng = Dice((1, 2, 3)); result = run(source, rng); rng.exhausted()
        self.assertIs(result.unsupported.reason, Reason.MISSING_SCENE)
        self.assertEqual(result.unsupported.missing_actor_ids, ('blocker',))
        self.assertEqual(len(result.unsupported.staged_movements), 1)
        self.assertEqual(len(result.current.pending_movement.zone.movement_follow_ups), 2)
        self.assertEqual(result.current.spatial_state.placement_for('enemy').zone_id, 'arena')
        self.assertEqual(result.unsupported.staged_movements[0].resolution.state.placement_for('enemy').zone_id, 'middle')
        self.assertEqual(len(result.steps), 2)

    def test_complete_two_target_movement_uses_intermediate_frame_and_one_completion(self):
        from towr.rules.spatial_resolution import resolve_give_ground
        source = scenario(blocker=True)
        initial = replace(source.initial, spatial_state=replace(source.initial.spatial_state, placements=tuple(
            replace(p, zone_id='arena') if p.entity_id == 'blocker' else p for p in source.initial.spatial_state.placements)))
        intermediate = frame(initial, placements=tuple(replace(p, zone_id='middle') if p.entity_id == 'enemy'
            else p for p in initial.spatial_state.placements))
        source = departures(replace(source, initial=initial, scene_frames=(frame(initial), intermediate)))
        rng = Dice((1, 2, 3) + (10,) * 6)
        with patch('towr.engine.npc_magic_scenario_runner.resolve_give_ground', wraps=resolve_give_ground) as move:
            result = run(source, rng)
        rng.exhausted(); self.assertEqual(move.call_count, 2)
        self.assertEqual(sum(isinstance(s.result, NpcRosterCastingCompletionResult) for s in result.steps), 1)
        self.assertIsNone(result.current.pending_movement)
        self.assertEqual(result.current.spatial_state.gave_ground_entity_ids, ('enemy', 'blocker'))
        self.assertEqual(result.unsupported.actor_id, 'ally')

    def test_missing_second_curse_route_stops_before_willpower(self):
        source = scenario(blocker=True)
        initial = replace(source.initial, spatial_state=replace(source.initial.spatial_state, placements=tuple(
            replace(p, zone_id='arena') if p.entity_id == 'blocker' else p for p in source.initial.spatial_state.placements)))
        intermediate = frame(initial, placements=tuple(replace(p, zone_id='middle') if p.entity_id == 'enemy'
            else p for p in initial.spatial_state.placements))
        plan = replace(intermediate.give_ground_plans[1], can_leave_zone=False, destination_zone_id=None, route=None, impossible_confirmed=True)
        intermediate = replace(intermediate, give_ground_plans=(intermediate.give_ground_plans[0], plan))
        source = departures(replace(source, initial=initial, scene_frames=(frame(initial), intermediate)))
        rng = Dice((1, 2, 3)); result = run(source, rng); rng.exhausted()
        self.assertIs(result.unsupported.reason, Reason.MISSING_ROUTE)
        self.assertEqual(len(result.unsupported.staged_movements), 1)
        self.assertEqual(result.executed_actions, 1)

    def test_broken_without_route_does_not_attack_or_invent_wait(self):
        rng = Dice((1, 2, 3, 10, 10, 10) + (10,) * 6)
        result = run(after_curse(), rng); rng.exhausted()
        self.assertIs(result.unsupported.reason, Reason.BROKEN_ROUTE)
        self.assertEqual(result.unsupported.actor_id, 'enemy')
        self.assertEqual(result.executed_actions, 2)
        self.assertFalse(result.current.round_state.active_turn.action_slots[0].executed)

    def test_out_of_range_after_curse_is_no_legal_target_without_extra_rng(self):
        rng = Dice((1, 2, 3, 1, 2, 3)); result = run(after_curse(enemy_zone='shelter'), rng); rng.exhausted()
        self.assertIs(result.unsupported.reason, Reason.NO_LEGAL_TARGET)
        self.assertEqual(result.unsupported.actor_id, 'ally')
        self.assertEqual(result.current.spatial_state.placement_for('enemy').zone_id, 'far')

    def test_directed_range_approval_reaches_existing_outside_optimum_preparation(self):
        rng = Dice((10,) * 13)
        result = run(replace(admitted(enemy_zone='middle', short_optimum=True, approval=True), max_rounds=1), rng)
        rng.exhausted()
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        requests = [s.result.source.attack.preparation.npc_attack.source_request for s in result.steps
                    if hasattr(s.result.source, 'attack')]
        self.assertTrue(all(r.range_approved_by_gm for r in requests))

    def test_repeated_stagger_uses_explicit_suffer_wound_policy_then_closes_defeat(self):
        from towr.domain.attack_models import DamageProfile
        from towr.domain.npc_roster_models import NpcRoster
        source = replace(admitted(), activation_order=('ally', 'wizard', 'enemy'))
        roster = NpcRoster(tuple(replace(p, definition=replace(p.definition,
            attacks=tuple(replace(a, damage=DamageProfile(2)) for a in p.definition.attacks)))
            if p.state.actor_id != 'wizard' else p for p in source.initial.roster.participants))
        source = replace(source, initial=replace(source.initial, roster=roster,
            champion_attack=replace(source.initial.champion_attack, roster=roster)))
        rng = Dice((1, 10, 10, 10, 10, 10) + (10,) * 9 + (1, 10, 10, 10, 10, 10))
        result = run(source, rng); rng.exhausted()
        self.assertIs(result.outcome, Outcome.OBJECTIVE_ACHIEVED)
        attacks = [s.result.attack for s in result.steps if hasattr(s.result, 'attack')]
        self.assertIs(attacks[-1].execution.resolution.stagger.selected_choice, StaggerChoice.SUFFER_WOUND)
        self.assertEqual(result.current.minion_attack.acknowledged_defeat_execution_ids,
                         (attacks[-1].execution.request_id,))

    def test_necessary_broken_run_takes_full_free_move_then_one_run_without_recover(self):
        from towr.domain.npc_magic_scene_models import NpcMagicPairRange, NpcMagicZoneRange
        from towr.domain.spatial_models import ZoneGraph, ZoneConnection
        from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
        source = scenario()
        graph = ZoneGraph(('arena', 'middle', 'shelter', 'far'),
            (ZoneConnection('arena', 'middle'), ZoneConnection('arena', 'shelter'), ZoneConnection('shelter', 'far')))
        placements = tuple(replace(p, zone_id='middle') if p.entity_id == 'ally' else p for p in source.initial.spatial_state.placements)
        initial = replace(source.initial, spatial_state=replace(source.initial.spatial_state, graph=graph, placements=placements))
        zones = tuple(NpcMagicZoneRange(z, r) for z, r in zip(graph.zone_ids, (Range.SHORT, Range.MEDIUM, Range.MEDIUM, Range.LONG)))
        first = replace(source.initial_frame, key=replace(source.initial_frame.key, placements=placements), zone_ranges=zones,
            pair_ranges=(NpcMagicPairRange('wizard', 'enemy', Range.SHORT, False, False),
                         NpcMagicPairRange('ally', 'enemy', Range.MEDIUM, False, False)))
        plan = NpcMagicBrokenPlan('enemy', NpcMagicBrokenPlanKind.FREE_MOVE_RUN, ('arena',), ROUTE, 'shelter', ROUTE, True)
        future = replace(first, key=replace(first.key, placements=tuple(replace(p, zone_id='middle')
            if p.entity_id == 'enemy' else p for p in placements)),
            pair_ranges=(NpcMagicPairRange('wizard', 'enemy', Range.MEDIUM, False, False),
                         NpcMagicPairRange('ally', 'enemy', Range.SHORT, False, False)), broken_plans=(plan,),
            give_ground_plans=(replace(first.give_ground_plans[0], destination_zone_id=None, route=None,
                can_leave_zone=False, impossible_confirmed=True),))
        source = departures(replace(source, initial=initial, max_rounds=1, scene_frames=(first, future)))
        rng = Dice((1, 2, 3, 10, 10, 10) + (10,) * 6)
        with patch('towr.engine.npc_magic_scenario_runner.execute_npc_broken_recover', side_effect=AssertionError('no Recover')):
            result = run(source, rng)
        rng.exhausted()
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertEqual(result.current.spatial_state.placement_for('enemy').zone_id, 'shelter')
        self.assertTrue(result.current.roster.participant('enemy').state.injury.conditions.has(Condition.BROKEN))
        self.assertEqual(result.current.spatial_state.free_move_used_entity_ids, ('enemy',))

    def test_failure_on_second_curse_movement_propagates_without_retry_or_willpower(self):
        from copy import deepcopy
        from towr.rules.spatial_resolution import resolve_give_ground
        source = scenario(blocker=True)
        initial = replace(source.initial, spatial_state=replace(source.initial.spatial_state, placements=tuple(
            replace(p, zone_id='arena') if p.entity_id == 'blocker' else p for p in source.initial.spatial_state.placements)))
        intermediate = frame(initial, placements=tuple(replace(p, zone_id='middle') if p.entity_id == 'enemy'
            else p for p in initial.spatial_state.placements))
        source = departures(replace(source, initial=initial, scene_frames=(frame(initial), intermediate)))
        before = deepcopy(source); failure = ValueError('second movement failed'); calls = []
        def movement(request):
            calls.append(request)
            if len(calls) == 2: raise failure
            return resolve_give_ground(request)
        rng = Dice((1, 2, 3))
        with (patch('towr.engine.npc_magic_scenario_runner.resolve_give_ground', side_effect=movement),
              patch('towr.engine.npc_magic_scenario_runner.complete_cowardly_flight_casting', side_effect=AssertionError('no Willpower'))):
            with self.assertRaises(ValueError) as caught: run(source, rng)
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(calls), 2)
        self.assertEqual(source, before); rng.exhausted()

    def test_public_runner_probe_from_external_cwd_matches_saved_output(self):
        import os
        from pathlib import Path
        import subprocess
        import sys
        import tempfile
        root = Path(__file__).resolve().parents[2]
        example = root / 'docs/examples/m8/scenario_runner_probe.py'
        with tempfile.TemporaryDirectory() as cwd:
            result = subprocess.run([sys.executable, str(example)], cwd=cwd,
                env=dict(os.environ, PYTHONPATH=str(root / 'src')), capture_output=True, check=True)
        self.assertEqual(result.stderr, b'')
        self.assertEqual(result.stdout, example.with_suffix('.output.txt').read_bytes())


if __name__ == '__main__':
    unittest.main()
