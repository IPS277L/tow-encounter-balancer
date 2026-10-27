"""ADR-0041 pure magic continuation, complete budgets and source/report chains."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction as F
import pickle
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_evaluation import request as bounded_request, Candidate
from tests.unit.test_m8_npc_magic_scenario import scenario, OPPOSITION
from towr.balance.magic_assessment import assess_magic_candidate
from towr.balance.magic_assessment_models import ObjectiveRateWindow as Window
from towr.balance.magic_evaluation_models import (
    MagicBalanceCandidateResult as CandidateResult, MagicBalanceEvaluationRequest as BoundedRequest,
    MagicBalanceEvaluationResult as BoundedResult,
)
from towr.balance.magic_staged_evaluation import magic_continuation_candidate_ids as continuation
from towr.balance.magic_staged_evaluation_models import (
    MagicBalanceStage as Stage, MagicStagedEvaluationRequest as Request,
    MagicStagedEvaluationResult as Result, MagicStagedEvaluationStatus as Status, _stage_request,
)
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.domain.test_models import InlineProfile
from towr.simulation.npc_magic_models import (
    SEED_SCHEME, NpcMagicOutcomeCounts as Counts, NpcMagicSimulationResult, NpcMagicTrialRecord,
)
from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary as Summary


def request():
    source = bounded_request(count=4, trials=10)
    return Request(source.candidates, 42, (Stage(10, 2), Stage(100, 1)), 240,
                   Window(F(9, 20), F(1, 2), F(11, 20)))


def stage_request(source, index=0, candidates=None):
    """Independent expected local request; never execute the simulator."""
    candidates = source.candidates if candidates is None else candidates
    stage = source.stages[index]
    return BoundedRequest(candidates, source.master_seed, stage.trials_per_candidate,
                          len(candidates) * stage.trials_per_candidate, source.window, stage.keep)


def report(source, achieved, unsupported=None):
    unsupported = (0,) * len(achieved) if unsupported is None else unsupported
    rows = []
    for candidate, simulation, goals, unknown in zip(
            source.candidates, source.simulation_requests, achieved, unsupported, strict=True):
        n = simulation.trials
        started = n * simulation.scenario.max_rounds
        completed = started - unknown
        summary = Summary(simulation, Counts(goals, 0, n - goals - unknown, unknown),
                          completed, started, completed)
        rows.append(CandidateResult(candidate.candidate_id,
                                    assess_magic_candidate(simulation, summary, source.window)))
    return BoundedResult(source, tuple(rows))


def reports(source):
    first = report(stage_request(source), (4, 7, 5, 6), (0, 0, 1, 0))
    last = report(stage_request(source, 1, (source.candidates[0], source.candidates[3])), (49, 51))
    return first, last


class MagicStagedModelTests(unittest.TestCase):
    def test_outside_candidates_continue_but_final_selection_uses_last_window_only(self):
        source = request()
        first, last = reports(source)
        self.assertEqual(first.selected_candidate_ids, ())
        self.assertEqual(continuation(first), ('candidate:0', 'candidate:3'))
        result = Result(source, (first, last))
        self.assertIs(result.status, Status.COMPLETED)
        self.assertEqual(result.selected_candidate_ids, ('candidate:0',))
        self.assertEqual((result.total_trials, result.planned_trials, result.seed_scheme), (240, 240, SEED_SCHEME))
        for goals, expected in (((45, 55), ('candidate:0',)), ((40, 60), ())):
            with self.subTest(goals=goals):
                self.assertEqual(Result(source, (first, report(last.source_request, goals))).selected_candidate_ids, expected)

    def test_continuation_restores_original_order_after_ranking_and_stable_cutoff_ties(self):
        source = request()
        closer_last = report(stage_request(source), (4, 7, 5, 5), (0, 0, 1, 0))
        self.assertEqual(closer_last.selected_candidate_ids, ('candidate:3',))
        self.assertEqual(continuation(closer_last), ('candidate:0', 'candidate:3'))
        tied = report(stage_request(source), (4, 6, 4, 6))
        self.assertEqual(continuation(tied), ('candidate:0', 'candidate:1'))
        self.assertEqual(Result(source, (closer_last, reports(source)[1])).selected_candidate_ids, ('candidate:0',))

    def test_continuation_uses_exact_fraction_distances_and_rejects_wrong_type(self):
        n = 2**60 + 1
        source = replace(bounded_request(count=2, trials=n), top_k=1)
        observed = report(source, (n // 2 - 1, n // 2))
        self.assertEqual(float(observed.candidates[0].assessment.objective_achieved_rate),
                         float(observed.candidates[1].assessment.objective_achieved_rate))
        self.assertEqual(continuation(observed), ('candidate:1',))
        for wrong in (None, {}, source, observed.candidates):
            with self.subTest(wrong=type(wrong)), self.assertRaises(TypeError): continuation(wrong)

    def test_actual_budget_shrinks_only_with_fewer_surviving_candidates(self):
        source = request()
        first = report(stage_request(source), (4, 7, 5, 6), (0, 1, 1, 1))
        last = report(stage_request(source, 1, source.candidates[:1]), (49,))
        result = Result(source, (first, last))
        self.assertEqual((result.total_trials, result.planned_trials), (140, 240))
        self.assertIs(result.status, Status.COMPLETED)
        self.assertEqual(result.selected_candidate_ids, ('candidate:0',))

    def test_early_exhaustion_differs_from_all_unsupported_at_final_stage(self):
        source = request()
        exhausted = report(stage_request(source), (4, 7, 5, 6), (1, 1, 1, 1))
        early = Result(source, (exhausted,))
        self.assertIs(early.status, Status.NO_ELIGIBLE_CANDIDATES)
        self.assertEqual((early.total_trials, early.selected_candidate_ids), (40, ()))
        first, last = reports(source)
        final_unknown = report(last.source_request, (0, 0), (100, 100))
        final = Result(source, (first, final_unknown))
        self.assertIs(final.status, Status.COMPLETED)
        self.assertEqual(final.selected_candidate_ids, ())

    def test_early_stop_never_returns_matches_from_an_earlier_stage(self):
        source = replace(request(), stages=(Stage(10, 2), Stage(100, 1), Stage(1000, 1)), max_total_trials=1240)
        first = report(stage_request(source), (5, 5, 5, 5))
        second = report(stage_request(source, 1, source.candidates[:2]), (50, 50), (1, 1))
        self.assertEqual(first.selected_candidate_ids, ('candidate:0', 'candidate:1'))
        actual = Result(source, (first, second))
        self.assertIs(actual.status, Status.NO_ELIGIBLE_CANDIDATES)
        self.assertEqual((actual.total_trials, actual.selected_candidate_ids), (240, ()))

    def test_one_stage_is_completed_even_with_unsupported_and_keep_above_count(self):
        source = replace(request(), stages=(Stage(10, 10),), max_total_trials=40)
        first = report(stage_request(source), (5, 5, 7, 4), (0, 1, 0, 0))
        actual = Result(source, (first,))
        self.assertIs(actual.status, Status.COMPLETED)
        self.assertEqual(actual.selected_candidate_ids, ('candidate:0',))
        self.assertEqual((actual.planned_trials, actual.total_trials), (40, 40))
        unknown = report(stage_request(source), (0, 0, 0, 0), (10, 10, 10, 10))
        self.assertIs(Result(source, (unknown,)).status, Status.COMPLETED)
        self.assertEqual(Result(source, (unknown,)).selected_candidate_ids, ())

    def test_keep_growth_never_restores_eliminated_candidates(self):
        source = replace(request(), stages=(Stage(10, 1), Stage(100, 10), Stage(1000, 20)), max_total_trials=1140)
        first = report(stage_request(source), (5, 7, 3, 6))
        second = report(stage_request(source, 1, source.candidates[:1]), (50,))
        final = report(stage_request(source, 2, source.candidates[:1]), (500,))
        actual = Result(source, (first, second, final))
        self.assertEqual((actual.planned_trials, actual.total_trials), (1140, 1140))
        self.assertEqual(actual.selected_candidate_ids, ('candidate:0',))
        self.assertIs(actual.status, Status.COMPLETED)
        growing = replace(source, stages=(Stage(10, 2), Stage(100, 5), Stage(1000, 1)), max_total_trials=2240)
        self.assertEqual(growing.planned_trials, 2240)

    def test_all_round_limit_continues_and_zero_action_unsupported_does_not(self):
        source = replace(request(), candidates=request().candidates[:1])
        stages = tuple(report(stage_request(source, i), (0,)) for i in range(2))
        for observed in stages:
            self.assertEqual(observed.candidates[0].assessment.round_limit_rate, 1)
            self.assertEqual(continuation(observed), ('candidate:0',))
        actual = Result(source, stages)
        self.assertIs(actual.status, Status.COMPLETED)
        self.assertEqual((actual.total_trials, actual.selected_candidate_ids), (110, ()))
        zero = replace(source, window=Window(F(0), F(0), F(0)))
        self.assertEqual(Result(zero, tuple(report(stage_request(zero, i), (0,)) for i in range(2))).selected_candidate_ids,
                         ('candidate:0',))
        local = stage_request(zero)
        simulation = local.simulation_requests[0]
        summary = Summary(simulation, Counts(0, 0, 0, 10), 0, 10, 0)
        unknown = BoundedResult(local, (CandidateResult('candidate:0', assess_magic_candidate(simulation, summary, zero.window)),))
        self.assertEqual(continuation(unknown), ())
        self.assertIs(Result(zero, (unknown,)).status, Status.NO_ELIGIBLE_CANDIDATES)

    def test_stage_strict_numeric_types_and_all_specs_are_validated(self):
        for wrong in (None, True, False, 1.5, '10', F(10)):
            for name in ('trials_per_candidate', 'keep'):
                with self.subTest(name=name, wrong=wrong), self.assertRaises(TypeError): replace(Stage(10, 2), **{name: wrong})
        for wrong in (0, -1):
            for name in ('trials_per_candidate', 'keep'):
                with self.subTest(name=name, wrong=wrong), self.assertRaises(ValueError): replace(Stage(10, 2), **{name: wrong})
        with self.assertRaises(ValueError): Stage(2**64, 1)
        self.assertEqual(Stage(2**64 - 1, 2**80).keep, 2**80)
        source = request()
        for stages in ((), (Stage(10, 2), Stage(10, 1)), (Stage(10, 2), Stage(9, 1))):
            with self.subTest(stages=stages), self.assertRaises(ValueError): replace(source, stages=stages)
        # A late spec is rejected even if the first stage might exhaust every candidate.
        with self.assertRaises(TypeError): replace(source, stages=(*source.stages, None))
        self.assertEqual(replace(source, stages=(Stage(10, 100), Stage(100, 1)), max_total_trials=440).planned_trials, 440)

    def test_containers_are_strict_and_generators_are_never_consumed(self):
        source = request()
        first, last = reports(source)
        for wrong in (None, {}, set(), 'sequence', 1):
            with self.subTest(wrong=type(wrong)):
                with self.assertRaises(TypeError): replace(source, candidates=wrong)
                with self.assertRaises(TypeError): replace(source, stages=wrong)
                with self.assertRaises(TypeError): Result(source, wrong)
        consumed = []
        def sequence(item):
            consumed.append(item)
            yield item
        for build in (lambda: replace(source, candidates=sequence(source.candidates[0])),
                      lambda: replace(source, stages=sequence(source.stages[0])),
                      lambda: Result(source, sequence(first))):
            with self.assertRaises(TypeError): build()
        self.assertEqual(consumed, [])
        with self.assertRaises(TypeError): Result(source, (first, None))
        with self.assertRaises(TypeError): Result(None, (first, last))

    def test_upper_budget_and_common_candidate_input_are_validated_before_execution(self):
        source = request()
        for wrong in (None, True, False, 1.5, '240'):
            with self.subTest(wrong=wrong), self.assertRaises(TypeError): replace(source, max_total_trials=wrong)
        for wrong in (0, -1, 239, 220):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError): replace(source, max_total_trials=wrong)
        self.assertEqual(replace(source, max_total_trials=240).planned_trials, 240)
        for wrong in (None, True, '42', F(42)):
            with self.subTest(wrong=wrong), self.assertRaises(TypeError): replace(source, master_seed=wrong)
        for wrong in (-1, 2**64):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError): replace(source, master_seed=wrong)
        for candidates in ((), (source.candidates[0], source.candidates[0])):
            with self.subTest(candidates=candidates), self.assertRaises(ValueError): replace(source, candidates=candidates)
        with self.assertRaises(TypeError): replace(source, candidates=(None,))
        with self.assertRaises(TypeError): replace(source, window=None)
        other = source.candidates[1]
        for changed in (replace(other.scenario, max_rounds=4), scenario(perspective=OPPOSITION)):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                replace(source, candidates=(source.candidates[0], replace(other, scenario=changed)))

    def test_budget_is_python_integer_without_uint64_total_cap_or_trial_enumeration(self):
        source = replace(request(), stages=(Stage(2**64 - 2, 2), Stage(2**64 - 1, 1)), max_total_trials=2**68)
        self.assertEqual(source.planned_trials, 4 * (2**64 - 2) + 2 * (2**64 - 1))
        self.assertGreater(source.planned_trials, 2**64)
        self.assertEqual(len(_stage_request(source, 0, source.candidates).simulation_requests), 4)
        with self.assertRaises(ValueError): replace(source, max_total_trials=source.planned_trials - 1)

    def test_private_stage_request_uses_exact_local_cap_sources_window_and_indexed_seeds(self):
        source = request()
        kept = (source.candidates[0], source.candidates[3])
        first = _stage_request(source, 0, source.candidates)
        last = _stage_request(source, 1, kept)
        self.assertEqual(first, stage_request(source))
        self.assertEqual(last, stage_request(source, 1, kept))
        self.assertEqual((first.max_total_trials, first.top_k, last.max_total_trials, last.top_k), (40, 2, 200, 1))
        self.assertIs(last.window, source.window)
        self.assertIs(last.candidates[0], source.candidates[0])
        self.assertIs(last.simulation_requests[0].scenario, source.candidates[0].scenario)
        for index in range(10): self.assertEqual(first.simulation_requests[0].seed_for(index), last.simulation_requests[0].seed_for(index))

    def test_chain_rejects_partial_extra_reordered_wrong_survivors_and_reports_after_exhaustion(self):
        source = request()
        first, last = reports(source)
        restored = report(stage_request(source, 1, source.candidates[:2]), (49, 51))
        reversed_input = report(stage_request(source, 1, last.source_request.candidates[::-1]), (51, 49))
        for chain in ((), (first,), (first, last, last), (last, first), (first, first), (first, restored), (first, reversed_input)):
            with self.subTest(length=len(chain)), self.assertRaises(ValueError): Result(source, chain)
        exhausted = report(stage_request(source), (4, 7, 5, 6), (1, 1, 1, 1))
        with self.assertRaises(ValueError): Result(source, (exhausted, last))

    def test_chain_requires_exact_stage_seed_n_window_local_cap_keep_and_full_scenario(self):
        source = request()
        first, last = reports(source)
        original = last.source_request.candidates[0].scenario
        wizard = replace(original.initial.wizard,
                         caster=replace(original.initial.wizard.caster, wizard_level=3))
        changed = replace(original, initial=replace(original.initial, wizard=wizard))
        foreign_candidates = (replace(last.source_request.candidates[0], scenario=changed), last.source_request.candidates[1])
        variants = ({'master_seed': 43}, {'trials_per_candidate': 99}, {'max_total_trials': 201},
                    {'top_k': 2}, {'window': Window(F(0), F(1, 2), F(1))}, {'candidates': foreign_candidates})
        for changes in variants:
            foreign = replace(last.source_request, **changes)
            with self.subTest(changes=tuple(changes)), self.assertRaises(ValueError):
                Result(source, (first, report(foreign, (49, 51))))

    def test_scenario_source_is_bound_in_every_stage_even_when_observations_match(self):
        source = request()
        alternatives = (scenario(blocker=True), scenario(enemy_zone='middle'))
        source = replace(source, candidates=tuple(replace(c, scenario=alternatives[i % 2])
                                                  for i, c in enumerate(source.candidates)))
        first, last = reports(source)
        actual = Result(source, (first, last))
        for row, expected in zip(last.candidates, alternatives): self.assertIs(row.assessment.source_request.scenario, expected)
        self.assertEqual(actual.selected_candidate_ids, ('candidate:0',))
        original = alternatives[0]
        variants = (replace(original, actors=tuple(replace(actor, willpower_profile=InlineProfile(2, 3))
                                                   if actor.actor_id == 'enemy' else actor for actor in original.actors)),
                    replace(original, scene_frames=tuple(replace(frame, pair_ranges=frame.pair_ranges[::-1])
                                                         for frame in original.scene_frames)))
        for changed in variants:
            self.assertNotEqual(changed, original)
            self.assertEqual(changed.id, original.id)
            for index, current in enumerate((first, last)):
                local = replace(current.source_request, candidates=(replace(current.source_request.candidates[0], scenario=changed),
                                                                     *current.source_request.candidates[1:]))
                foreign = report(local, (4, 7, 5, 6), (0, 0, 1, 0)) if index == 0 else report(local, (49, 51))
                with self.subTest(stage=index, changed=changed), self.assertRaises(ValueError):
                    Result(source, (foreign, last) if index == 0 else (first, foreign))

    def test_equal_source_copies_and_replace_revalidate_budget_and_chain_without_rebinding(self):
        source = request()
        observed = reports(source)
        copied = deepcopy(source)
        result = Result(copied, observed)
        self.assertIs(result.source_request, copied)
        self.assertIs(result.stage_reports[0], observed[0])
        self.assertEqual(result, Result(source, observed))
        updated = replace(source, stages=(Stage(20, 2), Stage(200, 1)), max_total_trials=480)
        self.assertEqual((updated.planned_trials, source.planned_trials), (480, 240))
        with self.assertRaises(ValueError): replace(source, stages=updated.stages)
        with self.assertRaises(ValueError): replace(result, source_request=updated)

    def test_tuple_copies_frozen_derived_fields_pickle_and_shared_window_identity(self):
        source = request()
        candidates, stages = list(source.candidates), list(source.stages)
        actual = replace(source, candidates=candidates, stages=stages)
        candidates.clear(); stages.clear()
        mutable = list(reports(source))
        result = Result(actual, mutable)
        mutable.clear()
        self.assertEqual(actual, source)
        self.assertEqual(len(result.stage_reports), 2)
        for obj, name, value in ((source, 'master_seed', 43), (source.stages[0], 'keep', 3), (result, 'stage_reports', ())):
            self.assertFalse(hasattr(obj, '__dict__'))
            with self.assertRaises(FrozenInstanceError): setattr(obj, name, value)
        for name in ('status', 'selected_candidate_ids', 'total_trials', 'planned_trials', 'seed_scheme'):
            with self.subTest(name=name), self.assertRaises(TypeError): replace(result, **{name: None})
        with self.assertRaises(TypeError): replace(source, planned_trials=0)
        restored = pickle.loads(pickle.dumps(result))
        self.assertEqual(restored, result)
        self.assertIs(type(restored.source_request.stages[0]), Stage)
        self.assertIs(type(restored.source_request.window), Window)
        self.assertIs(restored.status, Status.COMPLETED)

    def test_other_families_cannot_supply_stages_candidates_sources_reports_or_status(self):
        from tests.unit.test_m5_ranged_staged_evaluation import request as ranged_request, reports as ranged_reports
        from tests.unit.test_m6_melee_staged_evaluation import request as melee_request, reports as melee_reports
        from tests.unit.test_m7_mixed_staged_evaluation import request as mixed_request, reports as mixed_reports
        from towr.balance.ranged_staged_evaluation_models import RangedStagedEvaluationStatus
        from towr.balance.melee_staged_evaluation_models import MeleeStagedEvaluationStatus
        from towr.balance.mixed_staged_evaluation_models import MixedStagedEvaluationStatus
        source = request()
        for make, make_reports, status in ((ranged_request, ranged_reports, RangedStagedEvaluationStatus),
                                          (melee_request, melee_reports, MeleeStagedEvaluationStatus),
                                          (mixed_request, mixed_reports, MixedStagedEvaluationStatus)):
            other = make()
            foreign = make_reports(other)
            for build in (lambda: replace(source, stages=other.stages), lambda: replace(source, candidates=other.candidates),
                          lambda: continuation(foreign[0]), lambda: Result(source, foreign), lambda: Result(other, reports(source))):
                with self.subTest(family=type(other)), self.assertRaises(TypeError): build()
            self.assertIsNot(type(Result(source, reports(source)).status), status)

    def test_construction_preflight_selection_and_graph_retention_remain_pure(self):
        with ExitStack() as stack:
            for target in ('random.Random', 'towr.application.magic_evaluation_service.evaluate_magic_candidates',
                           'towr.simulation.npc_magic_simulation.run_npc_magic_simulation',
                           'towr.simulation.npc_magic_parallel.run_npc_magic_simulation_parallel',
                           'towr.engine.npc_magic_scenario_runner.run_npc_magic_scenario',
                           'concurrent.futures.ProcessPoolExecutor', 'json.loads'):
                stack.enter_context(patch(target, side_effect=AssertionError('staged models must remain pure')))
            source = request()
            observed = reports(source)
            before = deepcopy((source, observed))
            result = Result(source, observed)
            self.assertEqual(continuation(observed[0]), ('candidate:0', 'candidate:3'))
            self.assertEqual(result.selected_candidate_ids, ('candidate:0',))
            with self.assertRaises(ValueError): replace(source, max_total_trials=239)
            with self.assertRaises(TypeError): replace(source, stages=(*source.stages, None))
            self.assertEqual((source, observed), before)
        pending, seen = [result], set()
        while pending:
            item = pending.pop()
            if id(item) in seen: continue
            seen.add(id(item))
            self.assertNotIsInstance(item, (NpcMagicSimulationResult, NpcMagicTrialRecord, NpcMagicScenarioResult))
            if is_dataclass(item): pending.extend(getattr(item, f.name) for f in fields(item))
            elif isinstance(item, (tuple, list)): pending.extend(item)
