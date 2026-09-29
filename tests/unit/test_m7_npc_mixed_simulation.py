from dataclasses import FrozenInstanceError, fields, replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m7_npc_mixed_scenario import scenario
from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioOutcome as Outcome
from towr.domain.npc_attack_selection_models import (
    NpcAttackSelectionResult, NpcAttackSelectionBlock, RejectedNpcAttackCandidate, NpcAttackCandidateRejection,
)
from towr.engine import npc_round_coordinator as coordinator
from towr.simulation.npc_ranged_models import npc_ranged_trial_seed
from towr.simulation.npc_melee_models import npc_melee_trial_seed
from towr.simulation.npc_mixed_models import (
    NpcMixedOutcomeCounts, NpcMixedSimulationRequest, NpcMixedSimulationResult,
    NpcMixedTrialSummary, npc_mixed_trial_seed,
)
from towr.simulation import npc_mixed_simulation as simulation


def request(trials=4):
    source = scenario(sizes=(2, 1))
    return NpcMixedSimulationRequest(replace(source, initial=replace(source.initial, max_rounds=1)), 42, trials)


def observations(source):
    return tuple(NpcMixedTrialSummary(index, source.seed_for(index), outcome, attacks, 1)
                 for index, (outcome, attacks) in enumerate((
                     (Outcome.OBJECTIVE_ACHIEVED, 1), (Outcome.SIDE_DEFEATED, 2),
                     (Outcome.ROUND_LIMIT, 2), (Outcome.UNSUPPORTED_PATH, 0))))


class M7NpcMixedSimulationTests(unittest.TestCase):
    def test_seed_v1_golden_vectors_and_prefix_independence(self):
        # Public compatibility vectors for the versioned byte encoding, not Monte Carlo expectations.
        for seed, index, expected in (
            (0, 0, "31b5bc60517dc8c6ec3ebca91c0319881480062cc5353cee054661e8b5acae5c"),
            (42, 7, "ecbb86faf8c674f5ecc8b5aea0a13fe836004fecafbbd4ec7cf59e50a9165ed7"),
            (2**64-1, 2**64-1, "b55deeeb08ed8633fb362bb47dc3deff6d27b5fafc3e08d538c1c99486637f89"),
        ):
            with self.subTest(seed=seed, index=index):
                self.assertEqual(npc_mixed_trial_seed(seed, index), int(expected, 16))
                self.assertNotEqual(npc_mixed_trial_seed(seed, index), npc_ranged_trial_seed(seed, index))
                self.assertNotEqual(npc_mixed_trial_seed(seed, index), npc_melee_trial_seed(seed, index))
        source = request()
        self.assertEqual(source.seed_for(3), replace(source, trials=9).seed_for(3))
        self.assertNotEqual(source.seed_for(0), source.seed_for(1))
        self.assertNotEqual(source.seed_for(0), replace(source, master_seed=43).seed_for(0))
        self.assertEqual(replace(source, master_seed=0, trials=2**64-1).seed_for(2**64-2),
                         npc_mixed_trial_seed(0, 2**64-2))

    def test_request_and_index_validation_happen_before_rng_creation(self):
        source = request()
        for name in ("master_seed", "trials"):
            for value in (-1, 2**64, True, False, 1.2, "1", None):
                with self.subTest(name=name, value=value), self.assertRaises((TypeError, ValueError)):
                    replace(source, **{name: value})
        with self.assertRaises(ValueError):
            replace(source, trials=0)
        with self.assertRaises(TypeError):
            replace(source, scenario=None)
        factory = Mock()
        for index in (-1, source.trials, 2**64, True, 1.2, None):
            with self.subTest(index=index), self.assertRaises((ValueError, TypeError)):
                simulation.run_npc_mixed_trial(source, index, rng_factory=factory)
        with self.assertRaises(TypeError):
            simulation.run_npc_mixed_simulation(None, rng_factory=factory)
        with self.assertRaises(TypeError):
            simulation.run_npc_mixed_trial(None, 0, rng_factory=factory)
        factory.assert_not_called()
        for seed, index in ((True, 0), (0, False), (-1, 0), (0, 2**64), ("1", 0), (0, 1.5)):
            with self.subTest(seed=seed, index=index), self.assertRaises((TypeError, ValueError)):
                npc_mixed_trial_seed(seed, index)

    def test_aggregates_four_outcomes_separately_and_normalizes_record_order(self):
        source = request()
        records = list(observations(source)[::-1])
        result = NpcMixedSimulationResult(source, records)
        records.clear()
        self.assertEqual(result.trials, observations(source))
        self.assertEqual(result.outcome_counts, NpcMixedOutcomeCounts(1, 1, 1, 1))
        self.assertEqual(result.total_attack_count, 5)
        self.assertEqual(result.total_visited_round_count, 4)
        self.assertEqual(result.mean_attack_count, 1.25)
        self.assertEqual(result.mean_visited_round_count, 1.0)
        with self.assertRaises(FrozenInstanceError):
            result.trials = ()
        with self.assertRaises(FrozenInstanceError):
            result.trials[0].seed = 0

    def test_rejects_missing_duplicate_foreign_records_and_inconsistent_budget(self):
        source = request()
        records = observations(source)
        for invalid in (records[:-1], (*records, records[0]), (records[0], *records[:-1]),
                        (replace(records[0], seed=0), *records[1:]),
                        (replace(records[0], trial_index=8), *records[1:]),
                        (replace(records[0], executed_attack_count=4), *records[1:]),
                        (replace(records[0], visited_round_count=2), *records[1:])):
            with self.subTest(records=invalid), self.assertRaises(ValueError):
                NpcMixedSimulationResult(source, invalid)
        longer = replace(source, scenario=replace(source.scenario, initial=replace(source.scenario.initial, max_rounds=2)))
        with self.assertRaisesRegex(ValueError, "ROUND_LIMIT"):
            NpcMixedSimulationResult(longer, records)
        with self.assertRaises(TypeError):
            NpcMixedSimulationResult(None, records)
        with self.assertRaises(TypeError):
            NpcMixedSimulationResult(source, (None,) * 4)

    def test_trial_and_counter_contracts_reject_invalid_types_and_impossible_terminal(self):
        record = observations(request())[0]
        for name, value in (("outcome", "round_limit"), ("seed", True), ("seed", -1), ("seed", 2**256),
                            ("executed_attack_count", True), ("executed_attack_count", -1),
                            ("executed_attack_count", 0), ("visited_round_count", 0), ("visited_round_count", 1.5)):
            with self.subTest(name=name, value=value), self.assertRaises((TypeError, ValueError)):
                replace(record, **{name: value})
        with self.assertRaises(ValueError):
            NpcMixedOutcomeCounts(0, -1, 0, 0)

    def test_source_consistent_controller_stop_is_counted_separately(self):
        source = request(1)
        def reject(context):
            return NpcAttackSelectionResult(context, None, None, tuple(
                RejectedNpcAttackCandidate(c.id, NpcAttackCandidateRejection.ATTACK_CONTEXT, "technical stop")
                for c in context.candidates), NpcAttackSelectionBlock.NO_CANDIDATE)
        rng = Mock()
        # This exercises the stop protocol, not an expected admitted game path.
        with patch.object(coordinator, "select_npc_attack", side_effect=reject):
            result = simulation.run_npc_mixed_simulation(source, rng_factory=lambda seed: rng)
        self.assertEqual(result.outcome_counts, NpcMixedOutcomeCounts(0, 0, 0, 1))
        self.assertEqual(result.total_attack_count, 0)
        self.assertEqual(result.total_visited_round_count, 1)
        rng.randint.assert_not_called()

    def test_execution_error_stops_batch_without_returning_partial_success(self):
        source = request(3)
        first_rng = SequenceRandom([1, 2, 10, 10, 10, 10])
        factory = Mock(side_effect=[first_rng, RuntimeError("RNG unavailable"), Mock()])
        with self.assertRaisesRegex(RuntimeError, "RNG unavailable"):
            simulation.run_npc_mixed_simulation(source, rng_factory=factory)
        self.assertEqual(factory.call_count, 2)
        rng = Mock()
        rng.randint.side_effect = RuntimeError("broken dice")
        with self.assertRaisesRegex(RuntimeError, "broken dice"):
            simulation.run_npc_mixed_trial(source, 0, rng_factory=lambda seed: rng)

    def test_wrong_runner_source_or_result_type_is_not_aggregated(self):
        source = request(1)
        # Same scenario ID, different complete source (unused escape decision).
        other = replace(source.scenario, actor_policies=tuple(
            replace(p, can_leave_zone=True) for p in source.scenario.actor_policies))
        foreign = simulation.run_npc_mixed_scenario(other, SequenceRandom([1, 2, 10, 10, 10, 10]))
        self.assertEqual(foreign.source_scenario.initial.current.id, source.scenario.initial.current.id)
        for value, exception in ((foreign, ValueError), (None, TypeError)):
            with patch.object(simulation, "run_npc_mixed_scenario", return_value=value):
                with self.assertRaises(exception):
                    simulation.run_npc_mixed_simulation(source)

    def test_ranged_contracts_cannot_be_mislabelled_as_mixed(self):
        from tests.unit.test_m3_npc_ranged_simulation import request as ranged_request
        from towr.domain.npc_ranged_scenario_result_models import NpcRangedScenarioOutcome
        from towr.simulation.npc_ranged_models import NpcRangedOutcomeCounts
        from towr.simulation.npc_mixed_summary_models import NpcMixedSimulationSummary
        source = request()
        factory = Mock()
        with self.assertRaises(TypeError):
            replace(source, scenario=ranged_request().scenario)
        with self.assertRaises(TypeError):
            simulation.run_npc_mixed_simulation(ranged_request(), rng_factory=factory)
        with self.assertRaises(TypeError):
            replace(observations(source)[0], outcome=NpcRangedScenarioOutcome.OBJECTIVE_ACHIEVED)
        with self.assertRaises(TypeError):
            NpcMixedSimulationSummary(source, NpcRangedOutcomeCounts(1, 1, 1, 1), 5, 4)
        factory.assert_not_called()

    def test_melee_types_and_equal_enum_strings_cannot_enter_mixed_contract(self):
        from tests.unit.test_m6_npc_melee_simulation import request as melee_request, observations as melee_observations
        from towr.domain.npc_melee_scenario_result_models import NpcMeleeScenarioOutcome
        from towr.simulation.npc_melee_models import NpcMeleeSimulationResult
        from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation
        from towr.simulation.npc_mixed_summary_models import NpcMixedSimulationSummary
        source, foreign = request(), melee_request()
        foreign_result = NpcMeleeSimulationResult(foreign, melee_observations(foreign))
        self.assertEqual(Outcome.OBJECTIVE_ACHIEVED, NpcMeleeScenarioOutcome.OBJECTIVE_ACHIEVED)
        factory = Mock()
        with self.assertRaises(TypeError):
            replace(source, scenario=foreign.scenario)
        with self.assertRaises(TypeError):
            simulation.run_npc_mixed_trial(foreign, 0, rng_factory=factory)
        with self.assertRaises(TypeError):
            simulation.run_npc_mixed_simulation(foreign, rng_factory=factory)
        with self.assertRaises(TypeError):
            replace(observations(source)[0], outcome=NpcMeleeScenarioOutcome.OBJECTIVE_ACHIEVED)
        for src, records in ((foreign, observations(source)), (source, foreign_result.trials)):
            with self.assertRaises(TypeError):
                NpcMixedSimulationResult(src, records)
        with self.assertRaises(TypeError):
            summarize_npc_mixed_simulation(foreign_result)
        with self.assertRaises(TypeError):
            NpcMixedSimulationSummary(source, foreign_result.outcome_counts, 5, 4)
        factory.assert_not_called()

    def test_second_executor_failure_or_bad_source_stops_before_third_trial(self):
        source = request(3)
        runner = simulation.run_npc_mixed_scenario
        good = runner(source.scenario, SequenceRandom([1, 2, 10, 10, 10, 10]))
        foreign_scenario = replace(source.scenario, actor_policies=tuple(
            replace(p, outnumbering_bonus_approved=False) for p in source.scenario.actor_policies))
        foreign = runner(foreign_scenario, SequenceRandom([1, 2, 10, 10, 10, 10]))
        for failure, error in ((RuntimeError('executor'), RuntimeError), (None, TypeError),
                               (foreign, ValueError), (KeyboardInterrupt(), KeyboardInterrupt)):
            with self.subTest(error=error):
                factory = Mock(side_effect=lambda seed: Mock())
                with patch.object(simulation, 'run_npc_mixed_scenario', side_effect=[good, failure, good]) as execute:
                    with self.assertRaises(error):
                        simulation.run_npc_mixed_simulation(source, rng_factory=factory)
                self.assertEqual((factory.call_count, execute.call_count), (2, 2))

    def test_all_models_are_frozen_slotted_and_count_fields_reject_coercion(self):
        source = request()
        result = NpcMixedSimulationResult(source, observations(source))
        for item in (source, result, result.trials[0], result.outcome_counts):
            self.assertFalse(hasattr(item, '__dict__'))
            name = fields(item)[0].name
            with self.assertRaises(FrozenInstanceError):
                setattr(item, name, getattr(item, name))
        for field in fields(result.outcome_counts):
            for value in (True, False, -1, 1.0, '1', None):
                with self.subTest(field=field.name, value=value), self.assertRaises(ValueError):
                    replace(result.outcome_counts, **{field.name: value})
