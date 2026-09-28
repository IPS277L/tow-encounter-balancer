from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from multiprocessing import active_children
import random
import unittest
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from tests.unit.test_m6_melee_candidate_generation_models import request, Stage, Window
from towr.application.melee_candidate_generation import generate_melee_candidates
from towr.application.melee_staged_evaluation_service import evaluate_melee_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.melee_staged_evaluation_models import MeleeStagedEvaluationStatus
from towr.domain.npc_melee_scenario_result_models import NpcMeleeScenarioOutcome as Outcome
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_rounds_models import NpcRoundsResult
from towr.engine.npc_melee_scenario_runner import run_npc_melee_scenario


BONUS_RULE = "RULE-COMBAT-009:outnumbering"
WOUND = [1, 2, 10, 10, 10, 10]


def small_request():
    source = request()
    template = source.template_scenario
    # Explicit mixed GM decisions, fixed throughout this whole family.
    first = replace(template.actor_policies[0], outnumbering_bonus_approved=True)
    template = replace(template, actor_policies=(first, *template.actor_policies[1:]))
    return replace(source, template_scenario=template, stages=(Stage(2, 2), Stage(4, 1)),
                   max_total_trials=18, window=Window(F(0), F(1, 2), F(1)))


def attacks(result):
    return tuple(action for call in result.runner_report.source_steps if isinstance(call, NpcRoundsResult)
                 for combat in call.rounds for action in combat.steps if isinstance(action, NpcRosterAttackExecutionResult))


def generated_battles(*, approved, rounds=1):
    source = request()
    template = source.template_scenario
    template = replace(template, initial=replace(template.initial, max_rounds=rounds),
                       actor_policies=tuple(replace(p, outnumbering_bonus_approved=approved)
                                            for p in template.actor_policies))
    return generate_melee_candidates(replace(source, template_scenario=template))


class M6MeleeGenerationIntegrationTests(unittest.TestCase):
    def test_generated_family_has_equal_repeated_sequential_and_real_process_reports(self):
        source = small_request()
        before, rng_before = deepcopy(source), random.getstate()
        children_before = {child.pid for child in active_children()}
        generated = generate_melee_candidates(source)
        repeated = generate_melee_candidates(source)
        self.assertEqual(generated, repeated)
        seq = evaluate_melee_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
        proc = evaluate_melee_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 2, 3))
        again = evaluate_melee_candidates_staged(repeated.evaluation_request, Options(Mode.SEQUENTIAL))
        self.assertEqual(seq, proc)
        self.assertEqual(seq, again)
        self.assertEqual(seq.selected_candidate_ids, proc.selected_candidate_ids)
        self.assertIs(generated.source_request, source)
        self.assertIs(seq.source_request, generated.evaluation_request)
        self.assertIs(proc.source_request, generated.evaluation_request)
        self.assertIs(seq.status, MeleeStagedEvaluationStatus.COMPLETED)
        self.assertEqual(tuple(len(stage.candidates) for stage in seq.stage_reports), (5, 2))
        # Full batches are rerun: 5*2 + 2*4, not incremental trial differences.
        self.assertEqual((seq.total_trials, seq.planned_trials, source.max_total_trials), (18, 18, 18))
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), rng_before)
        self.assertEqual({child.pid for child in active_children()}, children_before)

    def test_prefix_rename_preserves_seeds_observations_and_selected_compositions(self):
        source = small_request()
        original = generate_melee_candidates(source)
        renamed = generate_melee_candidates(replace(source, candidate_id_prefix="renamed"))
        seq = evaluate_melee_candidates_staged(original.evaluation_request, Options(Mode.SEQUENTIAL))
        other = evaluate_melee_candidates_staged(renamed.evaluation_request, Options(Mode.SEQUENTIAL))
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
        expected = ((1, 1, 0), (1, 1, 0), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 1, 1, 1))
        for approved in (True, False):
            generated = generated_battles(approved=approved)
            before = deepcopy(generated)
            for candidate, bonuses in zip(generated.evaluation_request.candidates, expected, strict=True):
                with self.subTest(approved=approved, candidate=candidate.candidate_id):
                    deltas = bonuses if approved else (0,) * len(bonuses)
                    draws = 6 * len(deltas) + sum(deltas)
                    rng = Mock(wraps=SequenceRandom([10] * draws))
                    result = run_npc_melee_scenario(candidate.scenario, rng)
                    actual = self.assert_attack_dice(result, deltas)
                    self.assertIs(result.outcome, Outcome.ROUND_LIMIT)
                    self.assertEqual(result.defeat_acknowledgements, ())
                    self.assertEqual(tuple(a.execution.actor_id for a in actual), candidate.scenario.initial.current.actor_order)
                    self.assertEqual(rng.randint.call_count, draws)
            self.assertEqual(generated, before)

    def test_enemy_defeat_enables_bonus_for_next_attack_only_when_gm_approved(self):
        for approved in (True, False):
            with self.subTest(approved=approved):
                generated = generated_battles(approved=approved)
                before = deepcopy(generated)
                candidate = generated.evaluation_request.candidates[3]  # 2 vs 2, counts 2,0.
                self.assertEqual(candidate.candidate_id, "family:counts:2,0")
                rng = Mock(wraps=SequenceRandom(WOUND + WOUND + ([10] if approved else [])))
                result = run_npc_melee_scenario(candidate.scenario, rng)
                actual = self.assert_attack_dice(result, (0, int(approved)))
                self.assertIs(result.outcome, Outcome.OBJECTIVE_ACHIEVED)
                self.assertEqual(tuple(a.execution.target_id for a in actual), ("actor:1:0", "actor:1:1"))
                self.assertEqual(len(result.defeat_acknowledgements), 2)
                self.assertEqual(result.current.pending_follow_ups, ())
                self.assertEqual(rng.randint.call_count, 12 + int(approved))
                for ack in result.defeat_acknowledgements:
                    decision = ack.source_request.decision
                    self.assertIn(decision, candidate.scenario.policy_for(decision.attacker_id).defeat_decisions)
                self.assertEqual(generated, before)

    def test_ally_defeat_removes_bonus_in_next_round_even_with_approval_unchanged(self):
        for approved in (True, False):
            with self.subTest(approved=approved):
                generated = generated_battles(approved=approved, rounds=2)
                before = deepcopy(generated)
                candidate = generated.evaluation_request.candidates[0]  # 2 vs 1, counts 0,1.
                rolls = [10] * (12 + 2 * int(approved)) + WOUND + WOUND
                rng = Mock(wraps=SequenceRandom(rolls))
                result = run_npc_melee_scenario(candidate.scenario, rng)
                actual = self.assert_attack_dice(result, (int(approved), int(approved), 0, 0))
                self.assertIs(result.outcome, Outcome.OBJECTIVE_ACHIEVED)
                self.assertEqual(result.runner_report.visited_round_count, 2)
                self.assertEqual(tuple(a.execution.actor_id for a in actual),
                                 ("actor:0:0", "actor:0:1", "actor:1:2", "actor:0:1"))
                self.assertEqual(tuple(a.execution.target_id for a in actual[-2:]), ("actor:0:0", "actor:1:2"))
                self.assertEqual(len(result.defeat_acknowledgements), 2)
                self.assertEqual(rng.randint.call_count, len(rolls))
                self.assertIs(candidate.scenario.policy_for("actor:0:1").outnumbering_bonus_approved, approved)
                self.assertEqual(generated, before)
