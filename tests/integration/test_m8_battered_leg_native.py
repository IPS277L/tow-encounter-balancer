"""ADR-0061 actual runner journals, bounded tails and native mass APIs."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from functools import partial
import json
from multiprocessing import active_children
import os
from random import getstate
import unittest
from unittest.mock import Mock, patch

from tests.unit.test_m8_npc_magic_scenario import OPPOSITION
from tests.unit.test_m8_npc_magic_scenario_runner import Dice, admitted
from tests.unit.test_m8_stationary_wound_generation import family, Unreadable
from tests.unit.test_m8_magic_json import document as simulation_v1
from tests.unit.test_m8_magic_json_v2 import document as simulation_v2
from tests.unit.test_m8_magic_json_v3 import document as simulation_v3
from tests.unit.test_m8_magic_json_v4 import document as version4
from tests.unit.test_m8_magic_json_v5 import document as simulation_v5
from tests.unit.test_m8_magic_balance_json import document as balance_v1
from tests.unit.test_m8_magic_balance_json_v2 import document as balance_v2
from tests.unit.test_m8_magic_balance_json_v3 import document as balance_v3
from tests.unit.test_m8_magic_balance_json_v5 import document as balance_v5
from towr.adapters import magic_balance_json as balance_json, magic_simulation_json as simulation_json
from towr.adapters._magic_scenario_json import scenario_document
from towr.adapters.magic_json_errors import MagicBalanceInputError, MagicSimulationInputError
from towr.application import magic_candidate_generation as generation, magic_evaluation_service as evaluation
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.magic_assessment import assess_magic_candidate
from towr.balance.magic_assessment_models import MagicAssessmentStatus, ObjectiveRateWindow
from towr.balance.magic_evaluation_models import MagicBalanceCandidate
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage, MagicStagedEvaluationRequest
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_battered_leg_policy import (
    initial_magic_battered_leg_history, advance_magic_battered_leg_history,
)
from towr.domain.npc_magic_scenario_models import (
    NpcMagicBatteredLegPolicy, NpcMagicMiscastContinuationPolicy, NpcMagicPronePolicy,
)
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.domain.npc_magic_step_models import (
    NpcMagicPhase, NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason,
)
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_battered_leg_models import NpcRosterBatteredLegResult
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.npc_roster_miscast_models import NpcRosterMiscastFacts, NpcRosterMiscastPolicy
from towr.domain.npc_roster_prone_models import NpcRosterProneStandResult
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest, NpcMagicOutcomeCounts
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


POLICY = NpcMagicBatteredLegPolicy(InlineProfile(2, 5))
FIRST_FIVE = (1, 2, 3, 10, 10, 10, 5)
SUCCESS = (*FIRST_FIVE, 1, 10, *((10,) * 9))
FAILURE = (*FIRST_FIVE, 10, 10)


def native(*, opted=True, rounds=1, completed_wizard=False, miscast=False):
    source = admitted() if completed_wizard else admitted(wizard_side=OPPOSITION)
    return replace(source, max_rounds=rounds,
        battered_leg_continuation=deepcopy(POLICY) if opted else None,
        miscast_continuation=(NpcMagicMiscastContinuationPolicy(
            NpcRosterMiscastPolicy.DECLINE_CAST_BEFORE_MISCAST,
            NpcRosterMiscastFacts(True, True, True, True, True),
            NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE) if miscast else None))


def scripted(seed, *, seeds, streams, parent_pid=None):
    if parent_pid is not None and os.getpid() == parent_pid:
        raise AssertionError('native trial must run in spawn child')
    return Dice(streams[seeds.index(seed)])


class NativeBatteredLegIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.global_rng = getstate()
        self.children = {child.pid for child in active_children()}

    def tearDown(self):
        self.assertEqual(getstate(), self.global_rng)
        self.assertEqual({child.pid for child in active_children()}, self.children)

    def run_actual(self, source, stream):
        before = deepcopy(source)
        rng = Dice(stream)
        result = run_npc_magic_scenario(source, rng)
        rng.exhausted()
        self.assertEqual(source, before)
        self.assertIs(result.source, source)
        self.assertEqual(NpcMagicScenarioResult(source, result.steps, result.unsupported), result)
        self.assertEqual(result.current.roster, result.current.champion_attack.roster)
        self.assertEqual(result.current.roster, result.current.minion_attack.roster)
        return result

    def completion(self, result):
        steps = tuple(step for step in result.steps if isinstance(step.result, NpcRosterBatteredLegResult))
        self.assertEqual(len(steps), 1)
        return steps[0]

    def test_success_publishes_one_wizard_test_during_enemy_turn_and_continues_normal_casting(self):
        result = self.run_actual(native(), SUCCESS)
        completion = self.completion(result)
        index = result.steps.index(completion)
        self.assertEqual(completion.actor_id, 'wizard')
        self.assertEqual(completion.before.round_state.active_turn.actor_id, 'enemy')
        self.assertEqual(completion.result.source.attack, result.steps[index - 1].result)
        self.assertEqual(completion.result.endurance.request.endurance_test.profile, POLICY.endurance_profile)
        self.assertEqual(completion.before.consumed_execution_ids, completion.after.consumed_execution_ids)
        self.assertEqual(completion.before.round_state, completion.after.round_state)
        self.assertEqual(completion.before.spatial_state, completion.after.spatial_state)
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertEqual((result.executed_actions, result.completed_rounds), (3, 1))
        self.assertTrue(any(isinstance(step.result, NpcRosterCastingResult) for step in result.steps[index + 1:]))
        history = initial_magic_battered_leg_history(result.source)
        for step in result.steps:
            history = advance_magic_battered_leg_history(result.source, history, step)
        self.assertEqual(history.state, result.current)
        self.assertEqual(history.completion, completion.result)
        self.assertEqual(result.current.battered_leg_receipt, completion.after.battered_leg_receipt)
        self.assertEqual(len(result.current.champion_attack.daily_wounds.receipts), 1)
        self.assertEqual(len(result.current.champion_attack.consumed_wound_roll_ids), 1)

    def test_default_none_keeps_exact_pending_stop_without_endurance_or_completion(self):
        result = self.run_actual(native(opted=False), FIRST_FIVE)
        self.assertIs(result.unsupported.phase, NpcMagicPhase.CONTINUATION)
        self.assertIs(result.unsupported.reason, Reason.WOUND_EFFECT)
        self.assertEqual(result.unsupported.actor_id, 'enemy')
        self.assertEqual(result.unsupported.missing_actor_ids, ('wizard',))
        self.assertEqual(result.unsupported.source_id, result.steps[-1].result.attack.execution.request_id)
        self.assertIsNotNone(result.current.champion_attack.pending)
        self.assertIsNone(result.current.battered_leg_receipt)
        self.assertFalse(any(isinstance(step.result, NpcRosterBatteredLegResult) for step in result.steps))

    def test_failure_retains_sourced_prone_and_stops_at_wizard_action_with_or_without_miscast(self):
        for miscast in (False, True):
            with self.subTest(miscast=miscast):
                result = self.run_actual(native(miscast=miscast), FAILURE)
                completion = self.completion(result)
                self.assertFalse(completion.result.endurance.test_result.succeeded)
                self.assertIs(result.unsupported.reason, Reason.ACTOR_INJURY)
                self.assertEqual(result.unsupported.actor_id, 'wizard')
                self.assertIsNone(result.current.champion_attack.pending)
                injury = result.current.roster.participant('wizard').state.injury
                self.assertTrue(injury.conditions.has(Condition.PRONE))
                self.assertEqual(injury, completion.result.endurance.wound_result.state)
                self.assertEqual(result.current.battered_leg_receipt, completion.after.battered_leg_receipt)
                self.assertFalse(any(isinstance(step.result, NpcRosterProneStandResult) for step in result.steps))
                self.assertEqual((result.executed_actions, result.completed_rounds), (1, 0))

    def test_immediate_test_is_not_delayed_when_wizard_turn_already_completed(self):
        for values, succeeded in (((1, 10), True), ((10, 10), False)):
            with self.subTest(succeeded=succeeded):
                source = native(completed_wizard=True)
                result = self.run_actual(source, (*((10,) * 9), *FIRST_FIVE, *values))
                completion = self.completion(result)
                self.assertIn('wizard', completion.before.round_state.completed_turn_entity_ids)
                self.assertEqual(completion.result.endurance.test_result.succeeded, succeeded)
                self.assertEqual(completion.before.round_state, completion.after.round_state)
                self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
                self.assertEqual((result.executed_actions, result.completed_rounds), (3, 1))

    def test_new_staggered_after_success_is_saved_then_stopped_before_normal_end_factory(self):
        result = self.run_actual(native(rounds=2), (*SUCCESS, 1, 10, 10, 10, 10, 10))
        completion = self.completion(result)
        self.assertIs(result.unsupported.phase, NpcMagicPhase.END_TURN)
        self.assertIs(result.unsupported.reason, Reason.END_TURN)
        self.assertEqual(result.unsupported.actor_id, 'enemy')
        self.assertEqual(result.unsupported.missing_actor_ids, ('wizard',))
        self.assertEqual(result.unsupported.source_id, result.steps[-1].id)
        self.assertTrue(result.current.roster.participant('wizard').state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(result.current.battered_leg_receipt, completion.after.battered_leg_receipt)
        self.assertEqual((result.executed_actions, result.completed_rounds), (4, 1))
        self.assertTrue(result.current.round_state.active_turn.action_slots[0].executed)

    def test_new_wounds_keep_pending_priority_or_bounded_scope_and_all_receipts(self):
        for rolls, reason in (((1, 3), Reason.WOUND_EFFECT), ((2, 3), Reason.WOUND_EFFECT),
                              ((1, 1), Reason.END_TURN), ((5, 5), Reason.END_TURN)):
            with self.subTest(rolls=rolls):
                result = self.run_actual(native(rounds=2), (*SUCCESS, 1, 2, 3, 10, 10, 10, *rolls))
                completion = self.completion(result)
                self.assertIs(result.unsupported.reason, reason)
                self.assertEqual(result.current.battered_leg_receipt, completion.after.battered_leg_receipt)
                self.assertEqual(len(result.current.champion_attack.daily_wounds.receipts), 2)
                self.assertEqual(len(result.current.champion_attack.consumed_wound_roll_ids), 2)
                self.assertEqual(tuple(w.table_total for w in result.current.roster.participant('wizard').state.injury.wounds),
                                 (5, sum(rolls)))

    def test_pending_miscast_preserves_actual_completed_test_and_pool_without_retry(self):
        result = self.run_actual(native(), (*FIRST_FIVE, 1, 10, 9, 9, 9))
        completion = self.completion(result)
        self.assertIs(result.unsupported.reason, Reason.MISCAST_PREPARATION)
        self.assertIsNotNone(result.current.pending_miscast)
        self.assertEqual(result.current.battered_leg_receipt, completion.after.battered_leg_receipt)
        self.assertEqual(result.current.wizard.magic_state.miscast_dice, 3)

    def test_reconstructed_journal_rejects_other_authored_profile_even_with_equal_injury(self):
        result = self.run_actual(native(), SUCCESS)
        changed = replace(result.source, battered_leg_continuation=NpcMagicBatteredLegPolicy(InlineProfile(2, 4)))
        with self.assertRaises(ValueError):
            NpcMagicScenarioResult(changed, result.steps, result.unsupported)

    def test_both_perspectives_preserve_full_source_and_permission(self):
        source = native()
        for side in CombatSide:
            with self.subTest(side=side):
                targets = tuple(p.state.actor_id for p in source.initial.roster.participants if p.state.side is not side)
                selected = replace(source, perspective_side=side, objective=NpcDefeatObjective(targets))
                result = self.run_actual(selected, SUCCESS)
                self.assertIs(result.source.perspective_side, side)
                self.assertEqual(result.source.battered_leg_continuation, POLICY)
                self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)

    def test_seq_and_real_spawn_preserve_records_full_source_seed_and_unsupported_denominator(self):
        request = NpcMagicSimulationRequest(native(), 42, 2)
        before = deepcopy(request)
        seeds = tuple(request.seed_for(i) for i in range(2))
        streams = (SUCCESS, FAILURE)
        sequential = run_npc_magic_simulation(request,
            rng_factory=partial(scripted, seeds=seeds, streams=streams))
        spawned = run_npc_magic_simulation_parallel(request, workers=1, batch_size=1,
            rng_factory=partial(scripted, seeds=seeds, streams=streams, parent_pid=os.getpid()))
        self.assertEqual(sequential, spawned)
        self.assertEqual(spawned.outcome_counts, NpcMagicOutcomeCounts(0, 0, 1, 1))
        self.assertEqual(tuple(record.seed for record in spawned.trials), seeds)
        self.assertTrue(all(record.source_scenario is request.scenario for record in spawned.trials))
        summary = summarize_npc_magic_simulation(spawned)
        self.assertEqual(summary, summarize_npc_magic_simulation(sequential))
        self.assertEqual(summary.trials, 2)
        assessment = assess_magic_candidate(request, summary,
            ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1)))
        self.assertEqual(assessment.unsupported_path_rate, Fraction(1, 2))
        self.assertIs(assessment.status, MagicAssessmentStatus.UNSUPPORTED_OBSERVATIONS)
        self.assertEqual(request, before)

    def test_corrupt_permission_or_nested_profile_refused_before_rng_or_worker_pool(self):
        for corrupt_profile in (False, True):
            request = NpcMagicSimulationRequest(native(), 42, 1)
            if corrupt_profile:
                object.__setattr__(request.scenario.battered_leg_continuation.endurance_profile, 'threshold', True)
            else:
                object.__setattr__(request.scenario, 'battered_leg_continuation', 'normal_endurance')
            factory = Mock(side_effect=AssertionError('must not create RNG'))
            with patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor',
                       side_effect=AssertionError('must not create pool')) as pool:
                with self.subTest(corrupt_profile=corrupt_profile), self.assertRaises(TypeError):
                    run_npc_magic_simulation_parallel(request, workers=1, batch_size=1, rng_factory=factory)
                factory.assert_not_called()
                pool.assert_not_called()

    def test_explicit_candidate_stages_keep_profile_common_seeds_and_denominator_in_both_backends(self):
        request = MagicStagedEvaluationRequest((MagicBalanceCandidate('native', native()),), 42,
            (MagicBalanceStage(2, 1), MagicBalanceStage(3, 1)), 5,
            ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1)))
        before, captured = deepcopy(request), []

        def execute(source, process=False, **kwargs):
            seeds = tuple(source.seed_for(i) for i in range(source.trials))
            streams = (SUCCESS,) * source.trials
            factory = partial(scripted, seeds=seeds, streams=streams,
                parent_pid=os.getpid() if process else None)
            result = (run_npc_magic_simulation_parallel(source, rng_factory=factory, **kwargs) if process
                      else run_npc_magic_simulation(source, rng_factory=factory))
            captured.append(result)
            return result

        with patch.object(evaluation, 'run_npc_magic_simulation', side_effect=execute), \
                patch.object(evaluation, 'run_npc_magic_simulation_parallel',
                    side_effect=lambda source, **kwargs: execute(source, True, **kwargs)):
            sequential = evaluate_magic_candidates_staged(request, Options(Mode.SEQUENTIAL))
            spawned = evaluate_magic_candidates_staged(request, Options(Mode.PROCESS, 1, 2))
        self.assertEqual(sequential, spawned)
        self.assertEqual((sequential.total_trials, sequential.planned_trials), (5, 5))
        self.assertEqual(captured[0].trials, captured[1].trials[:2])
        self.assertEqual(captured[2].trials, captured[3].trials[:2])
        for report in sequential.stage_reports:
            for row in report.candidates:
                self.assertIs(row.assessment.source_request.scenario, request.candidates[0].scenario)
                self.assertEqual(row.assessment.summary.source_request.scenario.battered_leg_continuation, POLICY)
        self.assertEqual(request, before)


class BatteredLegNativeTransportRefusalTests(unittest.TestCase):
    def test_generation_requires_matching_family_before_collection_or_projection(self):
        source = family(stationary=None)
        selected = replace(source.template_scenario, battered_leg_continuation=POLICY)
        with self.assertRaisesRegex(ValueError, 'Battered Leg'):
            replace(source, template_scenario=selected,
                groups=Unreadable(source.groups), scene_frames=Unreadable(source.scene_frames),
                stages=Unreadable(source.stages))
        wrong = deepcopy(source)
        object.__setattr__(wrong, 'template_scenario', selected)
        with patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')) as vectors, \
                patch.object(generation, '_project_candidate', side_effect=AssertionError('no projection')) as project:
            with self.assertRaisesRegex(ValueError, 'Battered Leg'):
                generation.generate_magic_candidates(wrong)
            vectors.assert_not_called()
            project.assert_not_called()

    def test_all_five_wire_versions_refuse_permission_before_missing_definition_projection(self):
        source = native()
        before = deepcopy(source)
        for version in ('1', '2', '3', '4', '5'):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'Battered Leg'):
                scenario_document(source, ('missing:definition',), schema_version=version)
        self.assertEqual(source, before)

    def test_closed_decoders_refuse_new_field_even_null_in_all_existing_versions(self):
        simulations = (simulation_v1(), simulation_v2(opted=False),
            simulation_v3(stationary=False, miscast=False), version4(stationary=False, repeated=False),
            simulation_v5(opted=False))
        balances = (balance_v1(), balance_v2(opted=False), balance_v3(stationary=False, miscast=False),
            version4(balance=True, stationary=False, repeated=False), balance_v5())
        for documents, balanced, parser, error in (
            (simulations, False, simulation_json.parse_magic_simulation_request, MagicSimulationInputError),
            (balances, True, balance_json.parse_magic_balance_request, MagicBalanceInputError),
        ):
            for original in documents:
                data = deepcopy(original)
                scenario = data['reserve']['scenario'] if balanced else data['scenario']
                scenario['battered_leg_continuation'] = None
                with self.subTest(version=data['schema_version'], balance=balanced), self.assertRaises(error):
                    parser(json.dumps(data))


if __name__ == '__main__':
    unittest.main()
