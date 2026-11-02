"""Actual native57 journals, recorded witnesses and seq/spawn/staged sources."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from functools import partial
import importlib.util
from multiprocessing import active_children
import os
from pathlib import Path
from random import Random, getstate
import sys
import unittest
from unittest.mock import Mock, patch

from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from towr.application import magic_evaluation_service as evaluation
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.magic_assessment import assess_magic_candidate
from towr.balance.magic_assessment_models import MagicAssessmentStatus, ObjectiveRateWindow
from towr.balance.magic_evaluation_models import MagicBalanceCandidate
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage, MagicStagedEvaluationRequest
from towr.domain.npc_crushed_rib_models import NpcCrushedRibContext as Context, NpcCrushedRibConsumptionWitness as Witness
from towr.domain.npc_magic_crushed_rib_policy import initial_magic_crushed_rib_history, advance_magic_crushed_rib_history
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.domain.npc_magic_step_models import NpcMagicStep, NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionResult
from towr.domain.npc_roster_miscast_models import NpcRosterUnnaturalWindResult
from towr.domain.condition_models import Condition
from towr.domain.turn_models import CombatSide
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest, NpcMagicOutcomeCounts
from towr.simulation.npc_magic_simulation import run_npc_magic_trial, run_npc_magic_simulation
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel, _normalize_batch
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation as summarize


def public_fixture():
    examples = Path(__file__).resolve().parents[2] / 'docs/examples/m8'
    spec = importlib.util.spec_from_file_location('adr0057_actual_public_fixture', examples / 'crushed_rib_native.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with patch.object(sys, 'path', [str(examples), *sys.path]):
        spec.loader.exec_module(module)
    return module


def scripted(seed, *, seeds, streams, parent_pid=None):
    if parent_pid is not None and os.getpid() == parent_pid:
        raise AssertionError('native trial must run in spawn child')
    return Dice(streams[seeds.index(seed)])


def child_random(seed, *, parent_pid):
    if os.getpid() == parent_pid:
        raise AssertionError('seeded native trial must run in spawn child')
    return Random(seed)


class NativeCrushedRibIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = public_fixture()

    def setUp(self):
        self.rng = getstate()
        self.children = {p.pid for p in active_children()}

    def tearDown(self):
        self.assertEqual(getstate(), self.rng)
        self.assertEqual({p.pid for p in active_children()}, self.children)

    def test_actual_casting_and_protection_first_are_reconstructed_from_their_own_prefix(self):
        for scenario, stream, actions, rounds in (
            (self.public.casting_scenario(), self.public.CASTING_STREAM, 6, 2),
            (self.public.protection_scenario(), self.public.PROTECTION_STREAM, 5, 1),
        ):
            before = deepcopy(scenario)
            result = self.public.direct(scenario, stream)
            self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
            self.assertEqual((result.executed_actions, result.completed_rounds), (actions, rounds))
            history = initial_magic_crushed_rib_history(scenario)
            for step in result.steps:
                history = advance_magic_crushed_rib_history(scenario, history, step)
            self.assertEqual(history.state, result.current)
            self.assertIsNotNone(history.consumption)
            self.assertEqual(result.current.roster.participant('wizard').state.injury, history.consumption.consumption.state)
            self.assertEqual(scenario, before)

    def test_both_perspectives_keep_explicit_full_source_and_native_permission(self):
        source = self.public.protection_scenario()
        for side in CombatSide:
            targets = tuple(p.state.actor_id for p in source.initial.roster.participants if p.state.side is not side)
            scenario = replace(source, perspective_side=side, objective=NpcDefeatObjective(targets))
            result = self.public.direct(scenario, self.public.PROTECTION_STREAM)
            self.assertIs(result.source.perspective_side, side)
            self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
            self.assertEqual(result.source.crushed_rib_continuation, scenario.crushed_rib_continuation)

    def test_equal_current_different_actual_trace_cannot_replace_recorded_first_witness(self):
        source = self.public.protection_scenario()
        first = self.public.direct(source, self.public.PROTECTION_STREAM)
        alternate_stream = (*self.public.FIRST_TEN, *((10,) * 21))
        alternate = self.public.direct(self.public.protection_scenario(), alternate_stream)
        self.assertEqual(first.current, alternate.current)
        consuming = next(s.result for s in first.steps if isinstance(s.result, NpcRosterChampionAttackResult)
                         and s.result.attack.crushed_rib is not None)
        foreign = next(s.result for s in alternate.steps if isinstance(s.result, NpcRosterChampionAttackResult)
                       and s.result.attack.crushed_rib is not None)
        self.assertEqual(consuming.source, foreign.source)
        self.assertNotEqual(consuming.attack.crushed_rib.test, foreign.attack.crushed_rib.test)
        later_index = next(i for i, step in enumerate(first.steps) if isinstance(step.result, NpcRosterChampionAttackResult)
                           and step.result.attack.execution.actor_id == 'E3')
        later = first.steps[later_index].result
        context = Context(later.source.state, 'wizard', True, Witness(foreign, foreign.attack.crushed_rib))
        lower_source = replace(later.source.attack, crushed_rib_consumption=foreign.attack.crushed_rib)
        upper_source = replace(later.source, attack=lower_source, crushed_rib_context=context)
        lower = replace(later.attack, source=lower_source)
        outer = replace(later, source=upper_source, attack=lower)
        steps = (*first.steps[:later_index], NpcMagicStep(outer), *first.steps[later_index + 1:])
        with self.assertRaises(ValueError):
            NpcMagicScenarioResult(source, steps, first.unsupported)

    def test_post_test_new_wounds_preserve_receipts_then_stop_by_actual_priority(self):
        for rolls, reason in (((1, 3), Reason.WOUND_EFFECT), ((5, 5), Reason.TARGET_INJURY),
                              ((1, 1), Reason.TARGET_INJURY)):
            stream = (*self.public.FIRST_TEN, 1, 2, 3, 1, 6, 10, 9, *rolls)
            result = self.public.direct(self.public.protection_scenario(), stream)
            with self.subTest(rolls=rolls):
                self.assertIs(result.unsupported.reason, reason)
                self.assertEqual(len(result.current.champion_attack.daily_wounds.receipts), 2)
                self.assertEqual(len(result.current.champion_attack.consumed_wound_roll_ids), 2)
                self.assertEqual(result.current.roster.participant('wizard').state.injury.wounds[-1].table_total, sum(rolls))

    def test_pending_miscast_and_wind_keep_consumption_before_scope_stop(self):
        pending = self.public.direct(self.public.miscast_scenario(), self.public.MISCAST_STREAM)
        self.assertIs(pending.unsupported.reason, Reason.MISCAST_PREPARATION)
        self.assertIsNotNone(pending.current.pending_miscast.crushed_rib)
        source = self.public.casting_scenario(miscast=True)
        source = replace(source, initial=replace(source.initial, wizard=replace(source.initial.wizard,
            caster=replace(source.initial.wizard.caster, wizard_level=2))))
        wind = self.public.direct(source, (*self.public.MISCAST_STREAM, 7, 7, 7))
        self.assertTrue(any(isinstance(step.result, NpcRosterUnnaturalWindResult) for step in wind.steps))
        injury = wind.current.roster.participant('wizard').state.injury
        self.assertTrue(injury.conditions.has(Condition.PRONE))
        self.assertTrue(injury.conditions.has(Condition.DRAINED))
        self.assertIs(wind.unsupported.reason, Reason.END_TURN)

    def test_later_death_keeps_first_consumption_and_immediate_exclusion(self):
        source = self.public.death_scenario()
        result = self.public.direct(source, self.public.DEATH_STREAM)
        history = initial_magic_crushed_rib_history(source)
        first = None
        for step in result.steps:
            history = advance_magic_crushed_rib_history(source, history, step)
            if history.consumption is not None:
                first = history.consumption if first is None else first
                self.assertEqual(history.consumption, first)
        self.assertIsNotNone(first)
        self.assertTrue(history.state.roster.participant('wizard').state.injury.dead)
        self.assertIs(result.unsupported.reason, Reason.MISSING_SCENE)

    def test_pending_movement_completes_normal_target_tests_without_recasting_or_losing_receipt(self):
        result = self.public.direct(self.public.casting_scenario(rounds=1), self.public.MOVEMENT_STREAM)
        origins = tuple(s.result for s in result.steps if isinstance(s.result, NpcRosterCastingResult))
        completion = next(s.result for s in result.steps if isinstance(s.result, NpcRosterCastingCompletionResult))
        self.assertEqual(len(origins), 1)
        receipt = origins[0].casting.crushed_rib
        self.assertIsNotNone(receipt)
        self.assertEqual(completion.completion.casting.crushed_rib, receipt)
        self.assertEqual(result.current.roster.participant('wizard').state.injury, receipt.state)
        self.assertIsNone(result.current.pending_movement)
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)

    def test_scripted_seq_spawn_records_summary_source_seeds_and_unsupported_denominator(self):
        request = NpcMagicSimulationRequest(self.public.protection_scenario(), 42, 2)
        before = deepcopy(request)
        seeds = tuple(request.seed_for(i) for i in range(2))
        streams = (self.public.PROTECTION_STREAM, self.public.NEW_FOUR_STREAM)
        sequential = run_npc_magic_simulation(request, rng_factory=partial(scripted, seeds=seeds, streams=streams))
        spawned = run_npc_magic_simulation_parallel(request, workers=1, batch_size=1,
            rng_factory=partial(scripted, seeds=seeds, streams=streams, parent_pid=os.getpid()))
        self.assertEqual(sequential, spawned)
        self.assertEqual(summarize(sequential), summarize(spawned))
        self.assertEqual(spawned.outcome_counts, NpcMagicOutcomeCounts(0, 0, 1, 1))
        self.assertEqual(tuple(r.seed for r in spawned.trials), seeds)
        self.assertTrue(all(r.source_scenario is request.scenario for r in spawned.trials))
        assessment = assess_magic_candidate(request, summarize(spawned), ObjectiveRateWindow(F(0), F(1, 2), F(1)))
        self.assertEqual(assessment.unsupported_path_rate, F(1, 2))
        self.assertIs(assessment.status, MagicAssessmentStatus.UNSUPPORTED_OBSERVATIONS)
        self.assertEqual(request, before)

    def test_same_runtime_default_seeded_seq_spawn_parity(self):
        request = NpcMagicSimulationRequest(self.public.protection_scenario(), 613, 2)
        sequential = run_npc_magic_simulation(request)
        spawned = run_npc_magic_simulation_parallel(request, workers=1, batch_size=2,
            rng_factory=partial(child_random, parent_pid=os.getpid()))
        self.assertEqual(sequential, spawned)
        self.assertEqual(summarize(sequential), summarize(spawned))

    def test_parent_refuses_raw_permission_or_fact_before_rng_and_pool_and_worker_normalization(self):
        for kind in ('permission', 'fact'):
            request = NpcMagicSimulationRequest(self.public.protection_scenario(), 42, 1)
            if kind == 'permission':
                object.__setattr__(request.scenario, 'crushed_rib_continuation', request.scenario.crushed_rib_continuation.value)
            else:
                object.__setattr__(request.scenario.facts, 'no_external_condition_sources', 1)
            factory = Mock(side_effect=AssertionError('invalid source created RNG'))
            with patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor', side_effect=AssertionError('invalid source opened pool')) as pool:
                for operation in (lambda: run_npc_magic_trial(request, 0, rng_factory=factory),
                                  lambda: run_npc_magic_simulation(request, rng_factory=factory),
                                  lambda: run_npc_magic_simulation_parallel(request, workers=1, rng_factory=factory)):
                    with self.subTest(kind=kind), self.assertRaises(TypeError):
                        operation()
                factory.assert_not_called()
                pool.assert_not_called()
        request = NpcMagicSimulationRequest(self.public.protection_scenario(), 42, 1)
        record = run_npc_magic_trial(request, 0, rng_factory=lambda seed: Dice(self.public.PROTECTION_STREAM))
        bad = deepcopy(record)
        object.__setattr__(bad.source_scenario, 'crushed_rib_continuation', request.scenario.crushed_rib_continuation.value)
        self.assertEqual(bad.source_scenario, request.scenario)
        with self.assertRaises(TypeError):
            _normalize_batch(request, range(1), (bad,))

    def test_explicit_list_staged_seq_spawn_preserve_permission_and_common_seed_prefix(self):
        candidates = (MagicBalanceCandidate('native', self.public.protection_scenario()),
                      MagicBalanceCandidate('legacy', self.public.protection_scenario(opted=False)))
        request = MagicStagedEvaluationRequest(candidates, 42, (MagicBalanceStage(2, 1), MagicBalanceStage(3, 1)),
            7, ObjectiveRateWindow(F(0), F(1, 2), F(1)))
        before, captured = deepcopy(request), []

        def execute(source, process=False, **kwargs):
            seeds = tuple(source.seed_for(i) for i in range(source.trials))
            stream = (self.public.PROTECTION_STREAM if source.scenario.crushed_rib_continuation is not None
                      else self.public.FIRST_TEN)
            factory = partial(scripted, seeds=seeds, streams=(stream,) * source.trials,
                parent_pid=os.getpid() if process else None)
            result = (run_npc_magic_simulation_parallel(source, rng_factory=factory, **kwargs) if process
                      else run_npc_magic_simulation(source, rng_factory=factory))
            captured.append(result)
            return result

        with patch.object(evaluation, 'run_npc_magic_simulation', side_effect=execute), \
                patch.object(evaluation, 'run_npc_magic_simulation_parallel', side_effect=lambda source, **kw: execute(source, True, **kw)):
            sequential = evaluate_magic_candidates_staged(request, Options(Mode.SEQUENTIAL))
            spawned = evaluate_magic_candidates_staged(request, Options(Mode.PROCESS, 1, 2))
        self.assertEqual(sequential, spawned)
        self.assertEqual((sequential.total_trials, sequential.planned_trials), (7, 7))
        self.assertEqual(len(sequential.stage_reports), 2)
        for report in sequential.stage_reports:
            for row in report.candidates:
                source = next(c.scenario for c in candidates if c.candidate_id == row.candidate_id)
                self.assertIs(row.assessment.source_request.scenario, source)
                self.assertIs(row.assessment.summary.source_request.scenario, source)
        self.assertEqual(captured[0].trials, captured[2].trials[:2])
        self.assertEqual(request, before)


if __name__ == '__main__':
    unittest.main()
