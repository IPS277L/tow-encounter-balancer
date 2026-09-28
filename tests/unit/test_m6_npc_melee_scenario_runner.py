from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m6_npc_melee_scenario import scenario
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.npc_melee_scenario_result_models import NpcMeleeScenarioOutcome as Outcome, NpcMeleeScenarioResult
from towr.domain.npc_rounds_chain_summary_models import NpcRoundsChainSummary
from towr.domain.npc_rounds_models import NpcRoundsRequest
from towr.domain.test_models import DiceModifier
from towr.engine import npc_melee_scenario_runner as runner


WOUND = [1, 2, 10, 10, 10, 10]


def terminal():
    return runner.run_npc_melee_scenario(scenario(), SequenceRandom(WOUND + [1, 2, 10, 10, 10, 10, 10]))


class M6NpcMeleeScenarioRunnerTests(unittest.TestCase):
    def test_result_preserves_final_sources_without_reexecuting_rules_or_rng(self):
        result = terminal()
        with patch.object(runner, "run_npc_rounds", side_effect=AssertionError("unexpected execution")):
            projected = replace(result)
        self.assertEqual(projected, result)
        self.assertIs(projected.source_scenario, result.source_scenario)
        self.assertIs(projected.runner_report, result.runner_report)
        self.assertEqual(len(projected.runner_report.current.pending_follow_ups), 1)
        self.assertEqual(projected.current.pending_follow_ups, ())
        with self.assertRaises(FrozenInstanceError):
            result.runner_report = None

    def test_rejects_foreign_initial_source_and_wrong_types_before_execution(self):
        result = terminal()
        initial = result.source_scenario.initial
        foreign = replace(result.source_scenario, initial=replace(initial, current=replace(initial.current, id="foreign")))
        with self.assertRaisesRegex(ValueError, "initial source"):
            replace(result, source_scenario=foreign)
        for changes in ({"source_scenario": None}, {"runner_report": None}, {"terminal_acknowledgement": "wrong"}):
            with self.subTest(changes=changes), self.assertRaises(TypeError):
                replace(result, **changes)
        rng = Mock()
        with self.assertRaises(TypeError):
            runner.run_npc_melee_scenario(initial, rng)
        rng.randint.assert_not_called()

    def test_rejects_missing_or_foreign_terminal_consequences(self):
        result = terminal()
        with self.assertRaisesRegex(ValueError, "omits a supported defeat"):
            replace(result, terminal_acknowledgement=None, terminal_exclusion=None)
        with self.assertRaisesRegex(ValueError, "requires its acknowledgement"):
            replace(result, terminal_acknowledgement=None)
        with self.assertRaisesRegex(ValueError, "unfinished defeated turn"):
            replace(result, terminal_exclusion=None)
        with self.assertRaisesRegex(ValueError, "report snapshot"):
            replace(result, terminal_acknowledgement=result.defeat_acknowledgements[0])

    def test_rejects_terminal_decision_substitution_even_with_identical_snapshots(self):
        result = terminal()
        ack = result.terminal_acknowledgement
        altered = replace(ack, source_request=replace(ack.source_request,
            decision=replace(ack.source_request.decision, disposition=NpcDefeatDisposition.KILLED)))
        self.assertEqual(altered.continuation, ack.continuation)
        with self.assertRaisesRegex(ValueError, "supplied GM decision"):
            replace(result, terminal_acknowledgement=altered)

    def test_rejects_different_priority_and_nonterminal_decision_policy(self):
        result = terminal()
        source = result.source_scenario
        first = source.actor_policies[0]
        reversed_policy = replace(first, target_actor_ids=first.target_actor_ids[::-1],
                                  defeat_decisions=first.defeat_decisions[::-1])
        with self.assertRaisesRegex(ValueError, "target priority"):
            replace(result, source_scenario=replace(source, actor_policies=(reversed_policy, *source.actor_policies[1:])))
        changed = replace(first, defeat_decisions=(replace(first.defeat_decisions[0],
            disposition=NpcDefeatDisposition.KILLED), *first.defeat_decisions[1:]))
        with self.assertRaisesRegex(ValueError, "supplied GM decision"):
            replace(result, source_scenario=replace(source, actor_policies=(changed, *source.actor_policies[1:])))

    def test_budget_cannot_be_lowered_or_extended_to_relabel_a_finished_report(self):
        source = scenario()
        result = runner.run_npc_melee_scenario(source, SequenceRandom([10] * 72))
        for budget, message in ((2, "exceeds the global"), (4, "stopped before")):
            with self.subTest(budget=budget), self.assertRaisesRegex(ValueError, message):
                replace(result, source_scenario=replace(source, initial=replace(source.initial, max_rounds=budget)))

    def test_empty_candidate_substitution_is_not_an_unsupported_scenario_result(self):
        source = scenario()
        provider, rng = Mock(), Mock()
        provider.get_candidates.side_effect = lambda context, spatial: context
        blocked = runner.run_npc_rounds(replace(source.initial, max_rounds=1), provider, Mock(), rng)
        with patch.object(runner, "run_npc_rounds", return_value=blocked):
            with self.assertRaisesRegex(ValueError, "scenario policy"):
                runner.run_npc_melee_scenario(source, rng)
        rng.randint.assert_not_called()

    def test_source_consistent_technical_block_preserves_diagnostic_without_rng(self):
        from towr.domain.npc_attack_selection_models import (
            NpcAttackSelectionResult, NpcAttackSelectionBlock, RejectedNpcAttackCandidate, NpcAttackCandidateRejection,
        )
        from towr.engine import npc_round_coordinator as coordinator
        def reject(context):
            return NpcAttackSelectionResult(context, None, None, tuple(
                RejectedNpcAttackCandidate(c.id, NpcAttackCandidateRejection.ATTACK_CONTEXT, "technical stop")
                for c in context.candidates), NpcAttackSelectionBlock.NO_CANDIDATE)
        rng = Mock()
        # Exercise the technical stop protocol with correct candidates/snapshots.
        # No such stop is expected from the currently admitted healthy scenario.
        with patch.object(coordinator, "select_npc_attack", side_effect=reject):
            result = runner.run_npc_melee_scenario(scenario(), rng)
        self.assertIs(result.outcome, Outcome.UNSUPPORTED_PATH)
        self.assertIs(result.runner_report.blocked_reason, NpcAttackSelectionBlock.NO_CANDIDATE)
        self.assertEqual(result.runner_report.executed_attack_count, 0)
        self.assertEqual(result.defeat_acknowledgements, ())
        rng.randint.assert_not_called()

    def test_unexpected_executor_errors_are_not_converted_into_scenario_outcomes(self):
        rng = Mock()
        rng.randint.side_effect = RuntimeError("broken RNG")
        with self.assertRaisesRegex(RuntimeError, "broken RNG"):
            runner.run_npc_melee_scenario(scenario(), rng)

    def test_report_with_extra_attack_modifiers_does_not_prove_the_supplied_scenario(self):
        source = scenario()
        source = replace(source, initial=replace(source.initial, max_rounds=1))
        provider = Mock()
        def modified(context, spatial):
            candidates = runner.melee_scenario_candidates(source, context, spatial)
            return replace(context, candidates=tuple(replace(item,
                dice_modifiers=(DiceModifier("test:extra", 1),)) for item in candidates))
        provider.get_candidates.side_effect = modified
        played = runner.run_npc_rounds(source.initial, provider, Mock(), Mock(randint=Mock(return_value=10)))
        with self.assertRaisesRegex(ValueError, "scenario policy"):
            NpcMeleeScenarioResult(source, NpcRoundsChainSummary((played,)))

    def test_runner_observations_after_terminal_defeat_are_rejected(self):
        source = scenario(sizes=(3, 1))
        result = runner.run_npc_melee_scenario(source, SequenceRandom([1, 2, 10, 10, 10, 10, 10]))
        provider, rng = Mock(), Mock()
        provider.get_candidates.side_effect = lambda context, spatial: context
        observed = runner.run_npc_rounds(NpcRoundsRequest(result.current, source.initial.spatial_state, 1),
                                         provider, Mock(), rng)
        report = NpcRoundsChainSummary((*result.runner_report.source_steps, result.terminal_acknowledgement,
                                       result.terminal_exclusion, observed))
        with self.assertRaisesRegex(ValueError, "runner after terminal"):
            NpcMeleeScenarioResult(source, report)
        rng.randint.assert_not_called()

    def test_result_rejects_changed_gm_bonus_and_escape_facts(self):
        result = terminal()
        source = result.source_scenario
        second = source.actor_policies[1]
        with self.assertRaisesRegex(ValueError, "scenario policy"):
            replace(result, source_scenario=replace(source, actor_policies=(source.actor_policies[0],
                replace(second, outnumbering_bonus_approved=False), *source.actor_policies[2:])))
        with self.assertRaisesRegex(ValueError, "scenario policy"):
            replace(result, source_scenario=replace(source, facts=replace(source.facts, can_leave_zone=False)))

    def test_advance_order_and_duplicate_transitions_are_rejected(self):
        source = scenario()
        played = runner.run_npc_melee_scenario(source, SequenceRandom([10] * 72))
        first = played.runner_report.source_steps[0]
        with self.assertRaises(ValueError):
            NpcRoundsChainSummary((first, first))
        with self.assertRaisesRegex(ValueError, "stopped before"):
            NpcMeleeScenarioResult(source, NpcRoundsChainSummary((first,)))

    def test_rejects_actual_report_with_different_stagger_choice(self):
        from tests.unit.test_k1_kernel import FixedKernelDecisions
        from towr.domain.condition_models import StaggerChoice
        source = scenario(sizes=(1, 1))
        source = replace(source, initial=replace(source.initial, max_rounds=1))
        provider = Mock()
        provider.get_candidates.side_effect = lambda context, spatial: replace(context,
            candidates=runner.melee_scenario_candidates(source, context, spatial))
        # Close miss, then a weak hit: a different legal low-level decision.
        played = runner.run_npc_rounds(source.initial, provider, Mock(),
            SequenceRandom([10, 10, 10, 1, 10, 10, 1, 10, 10, 1, 10, 10]),
            decisions=FixedKernelDecisions(stagger=StaggerChoice.FALL_PRONE))
        with self.assertRaisesRegex(ValueError, "Staggered policy"):
            NpcMeleeScenarioResult(source, NpcRoundsChainSummary((played,)))

    def test_rejects_source_consistent_advance_with_changed_actor_order(self):
        from towr.domain.npc_round_advance_models import NpcRoundAdvanceRequest
        source = scenario()
        source = replace(source, initial=replace(source.initial, max_rounds=2))
        provider = Mock()
        provider.get_candidates.side_effect = lambda context, spatial: replace(context,
            candidates=runner.melee_scenario_candidates(source, context, spatial))
        first = runner.run_npc_rounds(replace(source.initial, max_rounds=1), provider, Mock(), SequenceRandom([10] * 24))
        advance = runner.advance_npc_round(NpcRoundAdvanceRequest("changed:advance", first.current, first.spatial_state,
            first.current.round_state.participants, first.current.actor_order[::-1]))
        second = runner.run_npc_rounds(NpcRoundsRequest(advance.continuation, advance.spatial_state, 1),
            provider, Mock(), SequenceRandom([10] * 24))
        with self.assertRaisesRegex(ValueError, "surviving composition/order"):
            NpcMeleeScenarioResult(source, NpcRoundsChainSummary((first, advance, second)))
