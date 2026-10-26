"""Finite evidence for authored M8 profiling inputs; no timing assertions."""
import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from random import getstate
import unittest

from tools.m8_benchmark_fixtures import CASES, benchmark_request
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_scene_models import NpcMagicBrokenPlanKind
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation


class ScriptedDice:
    def __init__(self, values):
        self.values = tuple(values)
        self.calls = 0

    def randint(self, low, high):
        assert (low, high) == (1, 10) and self.calls < len(self.values), 'unexpected RNG draw'
        value = self.values[self.calls]
        self.calls += 1
        assert low <= value <= high
        return value


def request(case='curse-routes', *, round_budget=4, trials=1, master_seed=42):
    return benchmark_request(case, trials=trials, master_seed=master_seed, round_budget=round_budget)


WAIT, MISS, HIT = (10,) * 3, (10,) * 6, (1, 2, 3, 10, 10, 10)


class MagicBenchmarkFixtureTests(unittest.TestCase):
    def test_cases_preserve_input_parameters_and_fresh_immutable_admission(self):
        self.assertEqual(CASES, ('curse-routes', 'champion-pressure', 'missing-departure'))
        state = getstate()
        for case in CASES:
            with self.subTest(case=case):
                first = request(case, trials=7, master_seed=123, round_budget=6)
                second = request(case, trials=7, master_seed=123, round_budget=6)
                self.assertIsInstance(first, NpcMagicSimulationRequest)
                self.assertEqual((first.trials, first.master_seed, first.scenario.max_rounds), (7, 123, 6))
                self.assertEqual(first, second)
                self.assertIsNot(first.scenario, second.scenario)
                self.assertEqual(first.scenario.id, f'benchmark:magic:{case}')
                self.assertEqual(len(first.scenario.actors), 3)
                self.assertEqual(first.scenario.initial.wizard.magic_state.miscast_dice, 0)
                with self.assertRaises(FrozenInstanceError):
                    first.trials = 1
        self.assertEqual(getstate(), state)

    def test_profiles_are_authored_champion_and_shooting_minions_with_explicit_facts(self):
        source = request().scenario
        roster = source.initial.roster
        wizard = roster.participant('wizard')
        self.assertIs(wizard.definition.injury_policy, TargetInjuryPolicy.CHAMPION)
        self.assertEqual(wizard.definition.resilience.total, 4)
        for actor in ('ally', 'enemy'):
            row = roster.participant(actor)
            self.assertIs(row.definition.injury_policy, TargetInjuryPolicy.MINION)
            self.assertEqual(row.definition.resilience.total, 3)
            self.assertEqual(row.state.available_attack_ids, ('shot',))
        for fact in fields(source.facts):
            self.assertIs(getattr(source.facts, fact.name), fact.name != 'requires_reload_action')
        self.assertEqual(source.activation_order, ('wizard', 'ally', 'enemy'))
        self.assertEqual(tuple(p.entity_id for p in source.initial.spatial_state.placements),
                         ('enemy', 'wizard', 'ally'))
        self.assertEqual(request('curse-routes').scenario.policy_for('enemy').target_actor_ids,
                         ('wizard', 'ally'))
        self.assertEqual(request('champion-pressure').scenario.policy_for('enemy').target_actor_ids,
                         ('ally', 'wizard'))

    def test_full_live_and_archived_frames_cover_all_three_enemy_positions(self):
        for case in CASES[:2]:
            source = request(case).scenario
            self.assertEqual(len(source.scene_frames), 6)
            expected = {(zone, live) for zone in ('arena', 'shelter', 'boundary')
                        for live in (('wizard', 'ally', 'enemy'), ('wizard', 'enemy'))}
            actual = set()
            for frame in source.scene_frames:
                placements = {p.entity_id: p.zone_id for p in frame.key.placements}
                zone = placements['enemy']
                actual.add((zone, frame.key.live_actor_ids))
                self.assertEqual(placements['wizard'], 'arena')
                self.assertEqual(placements['ally'], 'arena')
                self.assertEqual(tuple(p.entity_id for p in frame.key.placements), ('enemy', 'wizard', 'ally'))
                self.assertEqual(tuple(f.actor_id for f in frame.attack_departures), frame.key.live_actor_ids)
                expected_departures = {
                    'arena': {'wizard': True, 'ally': True, 'enemy': True},
                    'shelter': {'wizard': False, 'ally': False, 'enemy': True},
                    'boundary': {'wizard': False, 'ally': False, 'enemy': False},
                }[zone]
                self.assertEqual({fact.actor_id: fact.can_leave_zone for fact in frame.attack_departures},
                                 {actor: expected_departures[actor] for actor in frame.key.live_actor_ids})
                distance = {'arena': RangedWeaponRange.SHORT, 'shelter': RangedWeaponRange.MEDIUM,
                            'boundary': RangedWeaponRange.LONG}[zone]
                pairs = {frozenset((pair.first_actor_id, pair.second_actor_id)) for pair in frame.pair_ranges}
                self.assertEqual(pairs, {frozenset((actor, 'enemy')) for actor in ('wizard', 'ally')
                                        if actor in frame.key.live_actor_ids})
                for pair in frame.pair_ranges:
                    self.assertIs(pair.target_range, distance)
                    self.assertFalse(pair.first_range_approved_by_gm)
                    self.assertFalse(pair.second_range_approved_by_gm)
            self.assertEqual(actual, expected)

    def test_routes_and_safe_recover_are_supplied_without_implicit_graph_policies(self):
        source = request().scenario
        for frame in source.scene_frames:
            enemy_zone = next(p.zone_id for p in frame.key.placements if p.entity_id == 'enemy')
            plan, = frame.give_ground_plans
            destination = {'arena': 'shelter', 'shelter': 'boundary', 'boundary': None}[enemy_zone]
            self.assertEqual(plan.actor_id, 'enemy')
            self.assertEqual(plan.destination_zone_id, destination)
            self.assertIs(plan.can_leave_zone, destination is not None)
            self.assertIs(plan.impossible_confirmed, destination is None)
            if destination:
                self.assertEqual(plan.route.path_entity_ids, ())
                self.assertFalse(plan.route.crosses_obstacle)
                self.assertFalse(plan.route.crosses_difficult_terrain)
            else:
                self.assertIsNone(plan.route)
            if enemy_zone == 'arena':
                self.assertEqual(frame.broken_plans, ())
            else:
                broken, = frame.broken_plans
                self.assertIs(broken.kind, NpcMagicBrokenPlanKind.SAFE_RECOVER)
                self.assertTrue(broken.fastest_route_confirmed)
                self.assertEqual(broken.free_move_zone_ids, ())
                self.assertIsNone(broken.run_destination_zone_id)

    def test_scripted_curse_broken_recover_completes_round_without_defeat(self):
        source = request(round_budget=1).scenario
        before, global_rng = deepcopy(source), getstate()
        values = HIT + MISS + (1, 2, 3)
        rng = ScriptedDice(values)
        result = run_npc_magic_scenario(source, rng)
        self.assertEqual(rng.calls, len(values))
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertEqual((result.executed_actions, result.started_rounds, result.completed_rounds), (3, 1, 1))
        enemy = result.current.roster.participant('enemy').state.injury
        self.assertFalse(enemy.defeated)
        self.assertFalse(enemy.conditions.has(Condition.BROKEN))
        self.assertEqual(result.current.spatial_state.placement_for('enemy').zone_id, 'shelter')
        self.assertEqual(source, before)
        self.assertEqual(getstate(), global_rng)

    def test_scripted_archive_continues_curse_and_recover_through_both_destinations(self):
        source = request('champion-pressure', round_budget=3).scenario
        before, global_rng = deepcopy(source), getstate()
        # First defeat ally; then cast twice while only Wizard and enemy are live.
        values = WAIT + MISS + HIT + ((1, 2, 3) + WAIT + (1, 2, 3)) * 2
        rng = ScriptedDice(values)
        result = run_npc_magic_scenario(source, rng)
        self.assertEqual(rng.calls, 33)
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertEqual((result.executed_actions, result.started_rounds, result.completed_rounds), (7, 3, 3))
        self.assertEqual(result.current.round_state.excluded_turn_entity_ids, ('ally',))
        self.assertEqual(result.current.spatial_state.placement_for('enemy').zone_id, 'boundary')
        self.assertEqual(len(result.current.spatial_state.placements), 3)
        self.assertEqual(len(result.current.minion_attack.acknowledged_defeat_execution_ids), 1)
        self.assertFalse(result.current.roster.participant('enemy').state.injury.conditions.has(Condition.BROKEN))
        self.assertIsNone(result.unsupported)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), global_rng)

    def test_scripted_lethal_champion_chain_preserves_daily_and_archive(self):
        request_source = request('champion-pressure')
        source = request_source.scenario
        before, global_rng = deepcopy(source), getstate()
        values = WAIT + MISS + HIT + WAIT + HIT + (1,) + WAIT + HIT + (1, 1) + WAIT + HIT + (10, 10, 5)
        streams = []

        def factory(seed):
            self.assertEqual(seed, request_source.seed_for(0))
            stream = ScriptedDice(values)
            streams.append(stream)
            return stream

        batch = run_npc_magic_simulation(request_source, rng_factory=factory)
        self.assertEqual(streams[0].calls, 48)
        record, = batch.trials
        self.assertIs(record.outcome, Outcome.PERSPECTIVE_DEFEATED)
        self.assertEqual((record.executed_action_count, record.started_round_count,
                          record.completed_round_count), (9, 4, 4))
        self.assertIs(record.source_scenario, source)
        replay = run_npc_magic_scenario(source, ScriptedDice(values))
        self.assertTrue(replay.current.roster.participant('wizard').state.injury.dead)
        self.assertEqual(len(replay.current.champion_attack.daily_wounds.receipts), 3)
        self.assertEqual(len(replay.current.champion_attack.consumed_wound_roll_ids), 3)
        self.assertEqual(replay.current.round_state.excluded_turn_entity_ids, ('ally',))
        self.assertEqual(len(replay.current.roster.participants), 3)
        self.assertIsNone(replay.current.round_state.active_turn)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), global_rng)

    def test_missing_departure_is_zero_draw_zero_action_calibration_control(self):
        source = request('missing-departure', trials=3)
        before, global_rng = deepcopy(source), getstate()
        self.assertEqual(source.scenario.activation_order, ('ally', 'wizard', 'enemy'))
        self.assertEqual(len(source.scenario.scene_frames), 1)
        self.assertEqual(source.scenario.initial_frame.attack_departures, ())
        streams, seeds = [], []

        def factory(seed):
            seeds.append(seed)
            stream = ScriptedDice(())
            streams.append(stream)
            return stream

        result = run_npc_magic_simulation(source, rng_factory=factory)
        self.assertEqual(seeds, [source.seed_for(i) for i in range(3)])
        self.assertEqual(len({id(rng) for rng in streams}), 3)
        self.assertTrue(all(rng.calls == 0 for rng in streams))
        for trial in result.trials:
            self.assertIs(trial.outcome, Outcome.UNSUPPORTED_PATH)
            self.assertEqual((trial.executed_action_count, trial.started_round_count, trial.completed_round_count),
                             (0, 1, 0))
        replay = run_npc_magic_scenario(source.scenario, ScriptedDice(()))
        self.assertIs(replay.unsupported.reason, Reason.MISSING_ROUTE)
        self.assertFalse(replay.current.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), global_rng)

    def test_invalid_case_and_parameters_use_existing_public_admission(self):
        for case in (None, True, 1):
            with self.subTest(case=case), self.assertRaises(TypeError):
                request(case)
        for case in ('', 'melee', 'Curse-routes'):
            with self.subTest(case=case), self.assertRaises(ValueError):
                request(case)
        for parameter in ('trials', 'master_seed', 'round_budget'):
            for value in (True, None, '4', 1.5):
                with self.subTest(parameter=parameter, value=value), self.assertRaises(TypeError):
                    request(**{parameter: value})
        for parameter in ('trials', 'round_budget'):
            for value in (0, -1):
                with self.subTest(parameter=parameter, value=value), self.assertRaises(ValueError):
                    request(**{parameter: value})
        for parameter in ('master_seed', 'trials'):
            with self.subTest(parameter=parameter), self.assertRaises(ValueError):
                request(**{parameter: 1 << 64})

    def test_tools_fixture_has_no_docs_tests_or_private_import_dependencies(self):
        root = Path(__file__).resolve().parents[2]
        tree = ast.parse((root / 'tools/m8_benchmark_fixtures.py').read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name.split('.')[0], ('docs', 'tests'))
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                self.assertNotIn(node.module.split('.')[0], ('docs', 'tests'))
                self.assertTrue(all(not alias.name.startswith('_') for alias in node.names))


if __name__ == '__main__':
    unittest.main()
