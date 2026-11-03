"""ADR-0062 generated source/profile through actual native61 and mass APIs."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from functools import partial
from multiprocessing import active_children
import os
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_scenario_runner import Dice, admitted
from towr.application import magic_evaluation_service as evaluation
from towr.application.magic_balance_models import MagicBalanceResult, _validate_staged_result_source
from towr.application.magic_candidate_generation import generate_magic_candidates
from towr.application.magic_candidate_generation_models import MagicCandidateGenerationRequest, MagicCompositionGroup
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage as Stage, MagicStagedEvaluationStatus
from towr.balance.ranged_assessment_models import ObjectiveRateWindow as Window
from towr.domain.npc_magic_scenario_models import NpcMagicBatteredLegPolicy as Policy
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_roster_battered_leg_models import NpcRosterBatteredLegResult
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation


POLICY = Policy(InlineProfile(2, 5))
FIRST_FIVE = (1, 2, 3, 10, 10, 10, 5)


def family(*, opted=True, wizard_opposite=False):
    source = admitted(wizard_side=CombatSide.OPPOSITION if not wizard_opposite else CombatSide.PLAYERS_AND_ALLIES,
        perspective=CombatSide.OPPOSITION, blocker=True, fast_blocker=wizard_opposite)
    source = replace(source, max_rounds=1, battered_leg_continuation=POLICY if opted else None)
    group = (MagicCompositionGroup('support', ('ally',), 1, 1) if wizard_opposite else
             MagicCompositionGroup('enemies', ('enemy', 'blocker'), 1, 2))
    return MagicCandidateGenerationRequest(source, (group,), source.facts, source.scene_frames,
        'generated:battered', 2, 42, (Stage(2, 2), Stage(3, 1)), 10,
        Window(F(0), F(1, 2), F(1)), battered_leg_continuation=POLICY if opted else None)


def stream(actor_count, success=True):
    return (*FIRST_FIVE, *((1, 10) if success else (10, 10)),
            *((10,) * (9 + 6 * (actor_count - 3)) if success else ()))


def generated_rng(seed, *, seeds, actor_count, mixed, parent_pid=None):
    if parent_pid is not None and os.getpid() == parent_pid:
        raise AssertionError('process trial must run in a spawn child')
    return Dice(stream(actor_count, success=not mixed or seeds.index(seed) != 1))


class BatteredLegGenerationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.global_rng = getstate()
        self.children = {child.pid for child in active_children()}

    def tearDown(self):
        self.assertEqual(getstate(), self.global_rng)
        self.assertEqual({child.pid for child in active_children()}, self.children)

    def assert_sources(self, report, generated):
        originals = {candidate.candidate_id: candidate.scenario for candidate in generated.evaluation_request.candidates}
        self.assertEqual(report.source_request, generated.evaluation_request)
        for stage in report.stage_reports:
            for row in stage.candidates:
                request = row.assessment.source_request
                self.assertEqual(request.scenario, originals[row.candidate_id])
                self.assertEqual(request.scenario.battered_leg_continuation, POLICY)
                self.assertEqual(row.assessment.summary.source_request, request)
            for request in stage.source_request.simulation_requests:
                self.assertEqual(request.scenario.battered_leg_continuation, POLICY)

    def actual_reports(self, generated, mixed):
        captures = []
        seq_run, spawn_run = run_npc_magic_simulation, run_npc_magic_simulation_parallel
        def sequential(request):
            factory = partial(generated_rng, seeds=tuple(request.seed_for(i) for i in range(request.trials)),
                actor_count=len(request.scenario.initial.roster.participants), mixed=mixed)
            result = seq_run(request, rng_factory=factory)
            captures.append(result)
            return result
        def spawned(request, *, workers, batch_size):
            factory = partial(generated_rng, seeds=tuple(request.seed_for(i) for i in range(request.trials)),
                actor_count=len(request.scenario.initial.roster.participants), mixed=mixed, parent_pid=os.getpid())
            return spawn_run(request, workers=workers, batch_size=batch_size, rng_factory=factory)
        with (patch.object(evaluation, 'run_npc_magic_simulation', side_effect=sequential),
              patch.object(evaluation, 'run_npc_magic_simulation_parallel', side_effect=spawned)):
            sequential_report = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
            spawned_report = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 2, 1))
        self.assertEqual(sequential_report, spawned_report)
        self.assert_sources(sequential_report, generated)
        return sequential_report, captures

    def test_actual_three_four_actor_candidates_run_success_and_failure_with_exact_profile(self):
        source = family()
        original = deepcopy(source)
        generated = generate_magic_candidates(source)
        legacy = generate_magic_candidates(family(opted=False))
        self.assertEqual([len(c.scenario.initial.roster.participants)
            for c in generated.evaluation_request.candidates], [3, 4])
        for candidate, old in zip(generated.evaluation_request.candidates, legacy.evaluation_request.candidates, strict=True):
            self.assertEqual(candidate.scenario, replace(old.scenario, battered_leg_continuation=POLICY))
            count = len(candidate.scenario.initial.roster.participants)
            for success in (True, False):
                dice = Dice(stream(count, success))
                result = run_npc_magic_scenario(candidate.scenario, dice)
                dice.exhausted()
                completion = next(step for step in result.steps if isinstance(step.result, NpcRosterBatteredLegResult))
                self.assertEqual(completion.actor_id, 'wizard')
                self.assertEqual(completion.result.source.endurance_profile, POLICY.endurance_profile)
                self.assertIs(completion.result.endurance.test_result.succeeded, success)
                self.assertEqual(result.current.battered_leg_receipt, completion.after.battered_leg_receipt)
                self.assertEqual(len(result.current.champion_attack.daily_wounds.receipts), 1)
                if success:
                    self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
                    self.assertEqual(result.executed_actions, count)
                else:
                    self.assertIs(result.outcome, Outcome.UNSUPPORTED_PATH)
                    self.assertIs(result.unsupported.reason, Reason.ACTOR_INJURY if count == 3 else Reason.TARGET_INJURY)
            none_dice = Dice(FIRST_FIVE)
            none = run_npc_magic_scenario(old.scenario, none_dice)
            none_dice.exhausted()
            self.assertIs(none.unsupported.reason, Reason.WOUND_EFFECT)
        self.assertEqual(source, original)

    def test_wizard_opposite_perspective_keeps_all_five_actors_and_completed_turn(self):
        source = family(wizard_opposite=True)
        generated = generate_magic_candidates(source)
        self.assertEqual(source.candidate_count, 1)
        scenario = generated.evaluation_request.candidates[0].scenario
        self.assertEqual(len(scenario.initial.roster.participants), 5)
        self.assertIsNot(scenario.initial.roster.participant('wizard').state.side, scenario.perspective_side)
        dice = Dice((*((10,) * 9), *FIRST_FIVE, 1, 10, *((10,) * 12)))
        result = run_npc_magic_scenario(scenario, dice)
        dice.exhausted()
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        completion = next(step for step in result.steps if isinstance(step.result, NpcRosterBatteredLegResult))
        self.assertIn('wizard', completion.before.round_state.completed_turn_entity_ids)
        self.assertEqual(completion.result.source.endurance_profile, POLICY.endurance_profile)

    def test_mixed_generated_stages_preserve_unsupported_denominator_in_real_spawn(self):
        source = family()
        generated = generate_magic_candidates(source)
        report, captures = self.actual_reports(generated, mixed=True)
        self.assertIs(report.status, MagicStagedEvaluationStatus.NO_ELIGIBLE_CANDIDATES)
        self.assertEqual((report.total_trials, report.planned_trials), (4, 10))
        self.assertEqual(len(captures), 2)
        for run in captures:
            self.assertEqual(run.outcome_counts, NpcMagicOutcomeCounts(0, 0, 1, 1))
        for row in report.stage_reports[0].candidates:
            self.assertEqual(row.assessment.summary.trials, 2)
            self.assertEqual(row.assessment.unsupported_path_rate, F(1, 2))

    def test_full_generated_stages_preserve_repeated_seed_prefix_and_budget(self):
        generated = generate_magic_candidates(family())
        report, captures = self.actual_reports(generated, mixed=False)
        self.assertIs(report.status, MagicStagedEvaluationStatus.COMPLETED)
        self.assertEqual((report.total_trials, report.planned_trials), (10, 10))
        self.assertEqual([run.source_request.trials for run in captures], [2, 2, 3, 3])
        for candidate_id in [c.candidate_id for c in generated.evaluation_request.candidates]:
            first, later = [run for run in captures if run.source_request.scenario.id == candidate_id]
            self.assertEqual(tuple(t.seed for t in first.trials), tuple(t.seed for t in later.trials[:2]))
        self.assertEqual(MagicBalanceResult(generated, report).evaluation_result, report)

    def test_foreign_profile_in_late_report_cache_is_rejected_before_rebuilding(self):
        generated = generate_magic_candidates(family())
        with patch.object(evaluation, 'run_npc_magic_simulation', side_effect=lambda request:
            run_npc_magic_simulation(request, rng_factory=partial(generated_rng,
                seeds=tuple(request.seed_for(i) for i in range(request.trials)),
                actor_count=len(request.scenario.initial.roster.participants), mixed=False))):
            report = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
        for raw in (False, True):
            corrupted = deepcopy(report)
            cache = list(corrupted.stage_reports[-1].source_request.simulation_requests)
            request = deepcopy(cache[-1])
            if raw:
                object.__setattr__(request.scenario.battered_leg_continuation.endurance_profile, 'threshold', 5.0)
            else:
                object.__setattr__(request, 'scenario', replace(request.scenario,
                    battered_leg_continuation=Policy(InlineProfile(2, 4))))
            cache[-1] = request
            object.__setattr__(corrupted.stage_reports[-1].source_request, 'simulation_requests', tuple(cache))
            with self.subTest(raw=raw), self.assertRaises((TypeError, ValueError)):
                _validate_staged_result_source(corrupted)


if __name__ == '__main__':
    unittest.main()
