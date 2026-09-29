from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from multiprocessing import active_children
import random
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m7_mixed_candidate_generation_models import request, Group, Stage, Window
from towr.application.mixed_candidate_generation import generate_mixed_candidates
from towr.application import mixed_evaluation_service as bounded_service
from tests.unit.test_m7_npc_mixed_scenario import scenario
from towr.application.mixed_staged_evaluation_service import evaluate_mixed_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.mixed_staged_evaluation_models import MixedStagedEvaluationStatus
from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioOutcome as Outcome
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_rounds_models import NpcRoundsResult
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.engine.npc_mixed_scenario_runner import run_npc_mixed_scenario


BONUS_RULE = "RULE-COMBAT-009:outnumbering"
WOUND = [1, 2, 10, 10, 10, 10]
MISS = [10] * 6


def miss_rng(seed):
    """Importable finite RNG factory for real spawn, independent of trial seed."""
    return SequenceRandom([10] * 100)


def small_request():
    source = request()
    template = source.template_scenario
    # Explicit mixed GM decisions, fixed throughout this whole family.
    first = replace(template.actor_policies[1], outnumbering_bonus_approved=True)
    template = replace(template, initial=replace(template.initial, max_rounds=1),
                       actor_policies=(template.actor_policies[0], first, *template.actor_policies[2:]))
    return replace(source, template_scenario=template, stages=(Stage(2, 2), Stage(4, 1)),
                   max_total_trials=16, window=Window(F(0), F(1, 2), F(1)))


def attacks(result):
    return tuple(action for call in result.runner_report.source_steps if isinstance(call, NpcRoundsResult)
                 for combat in call.rounds for action in combat.steps if isinstance(action, NpcRosterAttackExecutionResult))


def generated_battles(*, approved, rounds=1, melee_reserve=2):
    source = request()
    template = scenario(sizes=(3, melee_reserve + 1), enemy_bow=True, approved=approved,
                        disposition=NpcDefeatDisposition.DISARMED_AND_SURRENDERED)
    template = replace(template, initial=replace(template.initial, max_rounds=rounds))
    enemies = template.objective.target_actor_ids
    groups = (Group("A", enemies[1:][::-1], 1, melee_reserve), Group("B", enemies[:1], 0, 1))
    return generate_mixed_candidates(replace(source, template_scenario=template, groups=groups,
        facts=replace(template.facts), pair_ranges=tuple(replace(p) for p in template.pair_ranges),
        max_candidates=2 * melee_reserve, max_total_trials=20 * melee_reserve + 200))


class M7MixedGenerationIntegrationTests(unittest.TestCase):
    def test_scripted_generated_family_pays_full_repeated_budget_in_both_backends(self):
        source = small_request()
        before, rng_before = deepcopy(source), random.getstate()
        children_before = {child.pid for child in active_children()}
        generated = generate_mixed_candidates(source)
        sequential_runner = bounded_service.run_npc_mixed_simulation
        process_runner = bounded_service.run_npc_mixed_simulation_parallel
        # Only the existing RNG boundary is injected; generation, staged and
        # bounded evaluation and both simulation runners execute production code.
        with patch.object(bounded_service, "run_npc_mixed_simulation",
                          side_effect=lambda s: sequential_runner(s, rng_factory=miss_rng)) as seq_calls, \
                patch.object(bounded_service, "run_npc_mixed_simulation_parallel",
                             side_effect=lambda s, **kw: process_runner(s, rng_factory=miss_rng, **kw)) as proc_calls:
            seq = evaluate_mixed_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
            proc = evaluate_mixed_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 2, 3))
            self.assertEqual([c.args[0].trials for c in seq_calls.call_args_list], [2, 2, 2, 2, 4, 4])
            self.assertEqual([c.args[0] for c in seq_calls.call_args_list], [c.args[0] for c in proc_calls.call_args_list])
            self.assertTrue(all(c.kwargs == {"workers": 2, "batch_size": 3} for c in proc_calls.call_args_list))
        self.assertEqual(seq, proc)
        self.assertIs(seq.status, MixedStagedEvaluationStatus.COMPLETED)
        self.assertEqual(tuple(len(s.candidates) for s in seq.stage_reports), (4, 2))
        # Full batches: 4*2 + 2*4, not 4*2 + 2*(4-2).
        self.assertEqual((seq.total_trials, seq.planned_trials, source.max_total_trials), (16, 16, 16))
        for stage in seq.stage_reports:
            for row in stage.candidates:
                self.assertEqual(row.assessment.round_limit_rate, F(1))
                self.assertEqual(row.assessment.unsupported_path_rate, F(0))
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), rng_before)
        self.assertEqual({child.pid for child in active_children()}, children_before)

    def test_generated_family_has_equal_repeated_sequential_and_real_process_reports(self):
        source = small_request()
        before, rng_before = deepcopy(source), random.getstate()
        children_before = {child.pid for child in active_children()}
        generated = generate_mixed_candidates(source)
        repeated = generate_mixed_candidates(source)
        self.assertEqual(generated, repeated)
        seq = evaluate_mixed_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
        proc = evaluate_mixed_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 2, 3))
        again = evaluate_mixed_candidates_staged(repeated.evaluation_request, Options(Mode.SEQUENTIAL))
        self.assertEqual(seq, proc)
        self.assertEqual(seq, again)
        self.assertEqual(seq.selected_candidate_ids, proc.selected_candidate_ids)
        self.assertIs(generated.source_request, source)
        self.assertIs(seq.source_request, generated.evaluation_request)
        self.assertIs(proc.source_request, generated.evaluation_request)
        # Natural draws may exclude a candidate through unsupported_path.
        # Check complete reports/budget without fixing Monte Carlo observations.
        self.assertEqual((seq.planned_trials, source.max_total_trials), (16, 16))
        self.assertLessEqual(seq.total_trials, seq.planned_trials)
        self.assertEqual(seq.total_trials, sum(stage.total_trials for stage in seq.stage_reports))
        self.assertEqual(len(seq.stage_reports[0].candidates), 4)
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), rng_before)
        self.assertEqual({child.pid for child in active_children()}, children_before)

    def test_prefix_rename_preserves_seeds_observations_and_selected_compositions(self):
        source = small_request()
        original = generate_mixed_candidates(source)
        renamed = generate_mixed_candidates(replace(source, candidate_id_prefix="renamed"))
        seq = evaluate_mixed_candidates_staged(original.evaluation_request, Options(Mode.SEQUENTIAL))
        other = evaluate_mixed_candidates_staged(renamed.evaluation_request, Options(Mode.SEQUENTIAL))
        self.assertEqual((seq.status, seq.total_trials, seq.planned_trials),
                         (other.status, other.total_trials, other.planned_trials))
        for left, right in zip(seq.stage_reports, other.stage_reports, strict=True):
            for a, b in zip(left.candidates, right.candidates, strict=True):
                self.assertEqual(a.candidate_id.removeprefix("family"), b.candidate_id.removeprefix("renamed"))
                # Change only source IDs back, then compare the full assessment
                # including all counts, totals, rates, status and window result.
                old, new = a.assessment.source_request, b.assessment.source_request
                reset_initial = replace(new.scenario.initial, current=replace(
                    new.scenario.initial.current, id=old.scenario.initial.current.id))
                self.assertEqual(replace(new, scenario=replace(new.scenario, initial=reset_initial)), old)
                self.assertEqual(tuple(old.seed_for(i) for i in range(old.trials)),
                                 tuple(new.seed_for(i) for i in range(new.trials)))
                normalized = replace(b.assessment, source_request=old,
                                     summary=replace(b.assessment.summary, source_request=old))
                self.assertEqual(a.assessment, normalized)
        self.assertEqual(tuple(i.removeprefix("family") for i in seq.selected_candidate_ids),
                         tuple(i.removeprefix("renamed") for i in other.selected_candidate_ids))
        for a, b in zip(original.evaluation_request.candidates, renamed.evaluation_request.candidates, strict=True):
            self.assertNotEqual(a.scenario.initial.current.id, b.scenario.initial.current.id)

    def assert_attack_dice(self, result, deltas):
        actual = attacks(result)
        self.assertEqual(len(actual), len(deltas))
        for attack, delta in zip(actual, deltas, strict=True):
            trace = attack.execution.resolution.attack.attacker_test.trace
            self.assertEqual((trace.base_dice, trace.regular_dice_delta, trace.rolled_dice), (3, delta, 3 + delta))
            self.assertEqual(trace.applied_rule_ids.count(BONUS_RULE), delta)
            defender = attack.execution.resolution.attack.defender_test.trace
            self.assertEqual((defender.regular_dice_delta, defender.rolled_dice), (0, 3))
        return actual

    def test_initial_outnumbering_uses_each_generated_composition_and_gm_flag(self):
        # PG1.4 Rules / Attack Modifiers pp118-119: count this battle's actors,
        # never the omitted reserve. Footpad's ordinary attack has three dice.
        expected = ((0, 1, 1, 0), (0, 1, 1, 0, 0), (0, 0, 0, 0, 0),
                    (0, 0, 0, 0, 0, 0), (0, 0, 0, 1, 1, 1), (0, 0, 0, 0, 1, 1, 1))
        for approved in (True, False):
            generated = generated_battles(approved=approved, melee_reserve=3)
            before = deepcopy(generated)
            for candidate, bonuses in zip(generated.evaluation_request.candidates, expected, strict=True):
                with self.subTest(approved=approved, candidate=candidate.candidate_id):
                    deltas = bonuses if approved else (0,) * len(bonuses)
                    draws = 6 * len(deltas) + sum(deltas)
                    rng = Mock(wraps=SequenceRandom([10] * draws))
                    result = run_npc_mixed_scenario(candidate.scenario, rng)
                    actual = self.assert_attack_dice(result, deltas)
                    self.assertIs(result.outcome, Outcome.ROUND_LIMIT)
                    self.assertEqual(result.defeat_acknowledgements, ())
                    self.assertEqual(tuple(a.execution.actor_id for a in actual), candidate.scenario.initial.current.actor_order)
                    for attack in actual:
                        attack_source = attack.source_request.preparation.npc_attack.source_request
                        self.assertIs(attack_source.target_range, candidate.scenario.range_for(
                            attack.execution.actor_id, attack.execution.target_id))
                    self.assertEqual(rng.randint.call_count, draws)
            self.assertEqual(generated, before)

    def test_enemy_defeat_enables_bonus_for_next_attack_only_when_gm_approved(self):
        for approved in (True, False):
            with self.subTest(approved=approved):
                generated = generated_battles(approved=approved)
                before = deepcopy(generated)
                candidate = generated.evaluation_request.candidates[2]  # local 2 vs 2; remote friendly bow is not counted.
                self.assertEqual(candidate.candidate_id, "family:counts:2,0")
                rng = Mock(wraps=SequenceRandom(WOUND + WOUND + ([10] if approved else [])))
                result = run_npc_mixed_scenario(candidate.scenario, rng)
                actual = self.assert_attack_dice(result, (0, int(approved)))
                self.assertEqual(tuple(a.source_request.preparation.npc_attack.source_request.target_range for a in actual),
                                 (Range.MEDIUM, Range.CLOSE))
                self.assertIs(result.outcome, Outcome.OBJECTIVE_ACHIEVED)
                self.assertEqual(tuple(a.execution.target_id for a in actual), ("1:1", "1:2"))
                self.assertEqual(len(result.defeat_acknowledgements), 2)
                self.assertEqual(result.current.pending_follow_ups, ())
                self.assertEqual(rng.randint.call_count, 12 + int(approved))
                for ack in result.defeat_acknowledgements:
                    decision = ack.source_request.decision
                    self.assertIn(decision, candidate.scenario.policy_for(decision.attacker_id).defeat_decisions)
                    self.assertIs(decision.disposition, NpcDefeatDisposition.DISARMED_AND_SURRENDERED)
                self.assertEqual(generated, before)

    def test_ally_defeat_removes_bonus_in_next_round_even_with_approval_unchanged(self):
        for approved in (True, False):
            with self.subTest(approved=approved):
                generated = generated_battles(approved=approved, rounds=2)
                before = deepcopy(generated)
                candidate = generated.evaluation_request.candidates[0]  # local 2 vs 1, counts 1,0; the friendly bow remains remote.
                rolls = MISS + [10] * (12 + 2 * int(approved)) + WOUND + MISS + WOUND
                rng = Mock(wraps=SequenceRandom(rolls))
                result = run_npc_mixed_scenario(candidate.scenario, rng)
                actual = self.assert_attack_dice(result, (0, int(approved), int(approved), 0, 0, 0))
                self.assertIs(result.outcome, Outcome.OBJECTIVE_ACHIEVED)
                self.assertEqual(result.runner_report.visited_round_count, 2)
                self.assertEqual(tuple(a.execution.actor_id for a in actual),
                                 ("0:0", "0:1", "0:2", "1:2", "0:0", "0:2"))
                self.assertEqual(tuple(actual[i].execution.target_id for i in (3, 5)), ("0:1", "1:2"))
                self.assertEqual(len(result.defeat_acknowledgements), 2)
                self.assertEqual(rng.randint.call_count, len(rolls))
                self.assertIs(candidate.scenario.policy_for("0:2").outnumbering_bonus_approved, approved)
                for ack in result.defeat_acknowledgements:
                    decision = ack.source_request.decision
                    self.assertIn(decision, candidate.scenario.policy_for(decision.attacker_id).defeat_decisions)
                    self.assertIs(decision.disposition, NpcDefeatDisposition.DISARMED_AND_SURRENDERED)
                self.assertEqual(result.current.pending_follow_ups, ())
                self.assertEqual(generated, before)
