"""Independent ADR-0038 trials over real M8 transitions and finite dice streams."""
from copy import deepcopy
from dataclasses import fields, replace
from random import Random, getstate
import unittest

from tests.unit.test_m8_npc_magic_scenario import scenario, frame
from tests.unit.test_m8_npc_magic_scenario_runner import Dice, admitted, departures, after_curse
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_scene_models import NpcMagicBrokenPlan, NpcMagicBrokenPlanKind
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import (
    NpcMagicOutcomeCounts, NpcMagicSimulationRequest, NpcMagicSimulationResult,
)
from towr.simulation.npc_magic_simulation import run_npc_magic_trial, run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


def simulation_scenario():
    """Enemy first defeats the allied Minion; supplied archive permits later attacks."""
    source = scenario()
    policy = replace(source.policy_for('enemy'), target_actor_ids=('ally', 'wizard'))
    return departures(replace(source, max_rounds=4,
        actors=tuple(policy if p.actor_id == 'enemy' else p for p in source.actors),
        scene_frames=(*source.scene_frames, frame(source.initial, live=('wizard', 'enemy')))))


WAIT, MISS, HIT = (10,) * 3, (10,) * 6, (1, 2, 3, 10, 10, 10)
SCRIPTS = (
    WAIT + HIT,
    WAIT + MISS + HIT + WAIT + HIT + (1,) + WAIT + HIT + (1, 1) + WAIT + HIT + (10, 10, 5),
    (10,) * 60,
    (9, 9, 9),
)


class MagicSimulationIntegrationTests(unittest.TestCase):
    def test_one_input_real_four_outcomes_fresh_rngs_and_aggregate_only_summary(self):
        source = simulation_scenario()
        before, global_rng = deepcopy(source), getstate()
        request = NpcMagicSimulationRequest(source, 42, 4)
        seeds = [request.seed_for(i) for i in range(4)]
        streams, calls = [], []

        def factory(seed):
            calls.append(seed)
            stream = Dice(SCRIPTS[seeds.index(seed)])
            streams.append(stream)
            return stream

        result = run_npc_magic_simulation(request, rng_factory=factory)
        self.assertEqual(calls, seeds)
        self.assertEqual(len({id(rng) for rng in streams}), 4)
        for rng in streams:
            rng.exhausted()
        expected = (
            (Outcome.OBJECTIVE_ACHIEVED, 2, 1, 1),
            (Outcome.PERSPECTIVE_DEFEATED, 9, 4, 4),
            (Outcome.ROUND_LIMIT_REACHED, 12, 4, 4),
            (Outcome.UNSUPPORTED_PATH, 1, 1, 0),
        )
        self.assertEqual(tuple((r.outcome, r.executed_action_count, r.started_round_count,
                                r.completed_round_count) for r in result.trials), expected)
        self.assertTrue(all(record.source_scenario is source for record in result.trials))
        self.assertEqual(result.outcome_counts, NpcMagicOutcomeCounts(1, 1, 1, 1))
        self.assertEqual((result.total_action_count, result.total_started_round_count,
                          result.total_completed_round_count), (24, 10, 9))
        self.assertEqual(NpcMagicSimulationResult(request, list(reversed(result.trials))), result)
        summary = summarize_npc_magic_simulation(result)
        self.assertIs(summary.source_request, request)
        self.assertEqual(summary.trials, 4)
        self.assertEqual(summary.outcome_counts, result.outcome_counts)
        self.assertEqual((summary.total_action_count, summary.total_started_round_count,
                          summary.total_completed_round_count), (24, 10, 9))
        self.assertEqual({f.name for f in fields(summary)}, {'source_request', 'outcome_counts',
            'total_action_count', 'total_started_round_count', 'total_completed_round_count'})
        self.assertEqual(source, before)
        self.assertEqual(getstate(), global_rng)

    def test_real_wounds_death_and_minion_archive_replay_into_one_compact_record(self):
        source = simulation_scenario()
        request = NpcMagicSimulationRequest(source, 42, 2)
        record = run_npc_magic_trial(request, 1, rng_factory=lambda seed: Dice(SCRIPTS[1]))
        replay_rng = Dice(SCRIPTS[1])
        replay = run_npc_magic_scenario(source, replay_rng)
        replay_rng.exhausted()
        self.assertIs(record.outcome, Outcome.PERSPECTIVE_DEFEATED)
        self.assertEqual((record.executed_action_count, record.started_round_count,
                          record.completed_round_count), (replay.executed_actions,
                          replay.started_rounds, replay.completed_rounds))
        wizard = replay.current.roster.participant('wizard').state.injury
        self.assertTrue(wizard.dead)
        self.assertEqual(len(wizard.wounds), 3)
        self.assertEqual(len(replay.current.champion_attack.daily_wounds.receipts), 3)
        self.assertEqual(len(replay.current.champion_attack.consumed_wound_roll_ids), 3)
        self.assertEqual(replay.current.round_state.excluded_turn_entity_ids, ('ally',))
        self.assertEqual(len(replay.current.roster.participants), 3)
        self.assertEqual(len(replay.current.spatial_state.placements), 3)
        self.assertTrue(replay.current.roster.participant('ally').state.injury.defeated)
        self.assertEqual(len(replay.current.minion_attack.acknowledged_defeat_execution_ids), 1)
        self.assertIsNone(replay.current.pending_minion_attack)
        self.assertIsNone(replay.current.champion_attack.pending)
        self.assertIsNone(replay.current.round_state.active_turn)
        self.assertGreater(len(replay.steps), record.executed_action_count)
        self.assertNotIn('steps', {f.name for f in fields(record)})
        self.assertIs(record.source_scenario, source)
        self.assertFalse(source.initial.roster.participant('wizard').state.injury.dead)

    def test_zero_action_stop_uses_its_own_full_source_even_with_same_id_and_seed(self):
        source = simulation_scenario()
        zero_source = replace(source, activation_order=('ally', 'wizard', 'enemy'),
            scene_frames=(replace(source.initial_frame, attack_departures=()),))
        request = NpcMagicSimulationRequest(zero_source, 42, 1)
        stream = Dice(())
        result = run_npc_magic_simulation(request, rng_factory=lambda seed: stream)
        stream.exhausted()
        record = result.trials[0]
        self.assertIs(record.outcome, Outcome.UNSUPPORTED_PATH)
        self.assertEqual((record.executed_action_count, record.started_round_count,
                          record.completed_round_count), (0, 1, 0))
        replay = run_npc_magic_scenario(zero_source, Dice(()))
        self.assertIs(replay.unsupported.reason, Reason.MISSING_ROUTE)
        self.assertFalse(replay.current.round_state.active_turn.action_slots[0].executed)
        other = NpcMagicSimulationRequest(source, 42, 1)
        self.assertEqual(other.seed_for(0), record.seed)
        self.assertEqual(source.id, zero_source.id)
        self.assertNotEqual(source, zero_source)
        with self.assertRaises(ValueError):
            NpcMagicSimulationResult(other, (record,))
        summary = summarize_npc_magic_simulation(result)
        self.assertEqual(summary.outcome_counts, NpcMagicOutcomeCounts(0, 0, 0, 1))
        self.assertEqual(summary.total_action_count, 0)

    def test_miscast_record_retains_separate_unsupported_outcome_and_replays_pending(self):
        source = simulation_scenario()
        request = NpcMagicSimulationRequest(source, 42, 1)
        record = run_npc_magic_trial(request, 0, rng_factory=lambda seed: Dice((9, 9, 9)))
        replay = run_npc_magic_scenario(source, Dice((9, 9, 9)))
        self.assertIs(record.outcome, Outcome.UNSUPPORTED_PATH)
        self.assertIs(replay.unsupported.reason, Reason.MISCAST_PREPARATION)
        self.assertIsNotNone(replay.current.pending_miscast)
        self.assertEqual(replay.current.wizard.magic_state.miscast_dice, 3)
        self.assertEqual((record.executed_action_count, record.started_round_count,
                          record.completed_round_count), (1, 1, 0))
        self.assertIsNotNone(replay.current.round_state.active_turn)

    def test_real_wound_expiry_counts_actions_instead_of_journal_steps(self):
        source = admitted()
        values = (10,) * 9 + HIT + (6,) + (10,) * 3 + HIT
        request = NpcMagicSimulationRequest(source, 42, 1)
        result = run_npc_magic_simulation(request, rng_factory=lambda seed: Dice(values))
        replay = run_npc_magic_scenario(source, Dice(values))
        record = result.trials[0]
        self.assertIs(record.outcome, Outcome.OBJECTIVE_ACHIEVED)
        self.assertEqual((record.executed_action_count, record.started_round_count,
                          record.completed_round_count), (5, 2, 2))
        self.assertGreater(len(replay.steps), record.executed_action_count)
        self.assertEqual(replay.current.wound_expiries, ())
        self.assertFalse(replay.current.roster.participant('wizard').state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(len(replay.current.champion_attack.daily_wounds.receipts), 1)
        self.assertTrue(any(receipt.expired_attack_ids for receipt in replay.current.wound_turn_end_receipts))
        self.assertEqual(summarize_npc_magic_simulation(result).total_action_count, 5)

    def test_curse_broken_recover_is_not_counted_as_defeat(self):
        plan = NpcMagicBrokenPlan('enemy', NpcMagicBrokenPlanKind.SAFE_RECOVER, (), None, None, None, True)
        source = after_curse(plan=plan)
        values = HIT + (10,) * 6 + (1, 2, 3)
        request = NpcMagicSimulationRequest(source, 42, 1)
        record = run_npc_magic_trial(request, 0, rng_factory=lambda seed: Dice(values))
        replay = run_npc_magic_scenario(source, Dice(values))
        self.assertIs(record.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertEqual((record.executed_action_count, record.started_round_count,
                          record.completed_round_count), (3, 1, 1))
        target = replay.current.roster.participant('enemy').state.injury
        self.assertFalse(target.defeated)
        self.assertFalse(target.conditions.has(Condition.BROKEN))
        self.assertEqual(replay.current.spatial_state.placement_for('enemy').zone_id, 'middle')

    def test_repeat_reverse_prefix_and_renamed_id_preserve_real_observations(self):
        source = simulation_scenario()
        before, global_rng = deepcopy(source), getstate()
        request = NpcMagicSimulationRequest(source, 42, 4)
        baseline = run_npc_magic_simulation(request)
        self.assertEqual(run_npc_magic_simulation(request), baseline)
        reverse = tuple(run_npc_magic_trial(request, i) for i in reversed(range(request.trials)))
        self.assertEqual(NpcMagicSimulationResult(request, reverse), baseline)
        expanded = run_npc_magic_simulation(replace(request, trials=6))
        self.assertEqual(expanded.trials[:4], baseline.trials)
        renamed = run_npc_magic_simulation(replace(request, scenario=replace(source, id='renamed:magic')))
        for original, changed in zip(baseline.trials, renamed.trials):
            self.assertEqual((original.trial_index, original.seed, original.outcome,
                original.executed_action_count, original.started_round_count, original.completed_round_count),
                (changed.trial_index, changed.seed, changed.outcome,
                changed.executed_action_count, changed.started_round_count, changed.completed_round_count))
            self.assertNotEqual(original.source_scenario, changed.source_scenario)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), global_rng)

    def test_extra_random_draws_affect_only_their_own_trial(self):
        request = NpcMagicSimulationRequest(simulation_scenario(), 42, 4)
        baseline = run_npc_magic_simulation(request)
        calls = []

        def shifted_factory(seed):
            calls.append(seed)
            rng = Random(seed)
            if seed == request.seed_for(0):
                for _ in range(17):
                    rng.randint(1, 10)
            return rng

        shifted = run_npc_magic_simulation(request, rng_factory=shifted_factory)
        self.assertEqual(calls, [request.seed_for(i) for i in range(4)])
        self.assertEqual(shifted.trials[1:], baseline.trials[1:])


if __name__ == '__main__':
    unittest.main()
