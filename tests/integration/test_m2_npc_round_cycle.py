from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_round_coordinator import Candidates, request, resume
from towr.domain.condition_models import Condition
from towr.domain.npc_attack_selection_models import NpcAttackSelectionResult
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.domain.turn_models import CombatSide, CombatTurnEndResult
from towr.engine import npc_round_coordinator as coordinator
from towr.rules import attack_action_execution as attack_executor


class M2NpcRoundCycleTests(unittest.TestCase):
    def test_full_two_by_two_round_carries_fresh_states_and_executes_four_attacks_once(self):
        # GM 1.1 Allies and Antagonists p97 numeric Brigand profiles; no triggered Abilities.
        source = request()
        before = deepcopy(source)
        provider = Candidates()
        # Close miss, first Staggered hit, two further Close misses (last actor already Staggered).
        dice = [10] * 6 + [1, 10, 10, 10, 10, 10] + [10] * 12
        rng = Mock(wraps=SequenceRandom([*dice, 7]))
        with (
            patch.object(coordinator, "execute_npc_roster_attack", wraps=coordinator.execute_npc_roster_attack) as execute,
            patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
        ):
            result = coordinator.run_npc_round(source, provider, rng)
        self.assertEqual(execute.call_count, 4)
        self.assertEqual(kernel.call_count, 4)
        self.assertEqual(rng.randint.call_count, 24)
        self.assertEqual(rng.randint(1, 10), 7)
        self.assertIs(result.outcome, NpcRoundOutcome.COMPLETE)
        self.assertTrue(result.round_state.round_complete)
        self.assertEqual(result.round_state.round_number, 1)
        self.assertIsNone(result.round_state.active_turn)
        self.assertEqual(result.round_state.completed_turn_entity_ids, source.actor_order)
        self.assertEqual(result.pending_follow_ups, ())
        self.assertEqual(source, before)
        self.assertEqual(tuple(c.actor_id for c in provider.contexts), source.actor_order)
        self.assertEqual(tuple(len(c.state.consumed_execution_ids) for c in provider.contexts), (0, 1, 2, 3))
        self.assertEqual(tuple(len(c.round_state.completed_turn_entity_ids) for c in provider.contexts), (0, 1, 2, 3))
        self.assertTrue(provider.contexts[1].state.roster.participant("brigand:0").state.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(provider.contexts[2].state.roster.participant("brigand:3").state.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(provider.contexts[3].state.roster.participant("brigand:3").state.injury.conditions.has(Condition.STAGGERED))
        attacks = tuple(step for step in result.steps if isinstance(step, NpcRosterAttackExecutionResult))
        self.assertEqual(result.state.consumed_execution_ids, tuple(a.execution.request_id for a in attacks))
        receipts = tuple(step.completed_turn.action_slots[0].execution for step in result.steps
                         if isinstance(step, CombatTurnEndResult))
        self.assertEqual(tuple(r.id for r in receipts), result.state.consumed_execution_ids)
        self.assertEqual(len(set(r.id for r in receipts)), 4)
        selections = tuple(step for step in result.steps if isinstance(step, NpcAttackSelectionResult))
        for attack, selected in zip(attacks, selections):
            self.assertIs(attack.source_request, selected.execution_request)
            self.assertTrue(attack.source_request.preparation.applied_rule_ids)
        self.assertTrue(attacks[-1].source_request.preparation.attack.attacker_is_staggered)
        self.assertEqual(attacks[-1].handled_follow_ups, ())
        self.assertTrue(all(p.state.injury.wounds == 0 for p in result.state.roster.participants))

    def test_explicit_actor_preference_respects_both_persistent_side_orders(self):
        for side_order, expected in (
            ((CombatSide.PLAYERS_AND_ALLIES, CombatSide.OPPOSITION), ("brigand:1", "brigand:0", "brigand:3", "brigand:2")),
            ((CombatSide.OPPOSITION, CombatSide.PLAYERS_AND_ALLIES), ("brigand:3", "brigand:2", "brigand:1", "brigand:0")),
        ):
            with self.subTest(side_order=side_order):
                source = request()
                source = replace(source, actor_order=("brigand:1", "brigand:3", "brigand:0", "brigand:2"),
                                 round_state=replace(source.round_state, side_order=side_order))
                provider = Candidates()
                result = coordinator.run_npc_round(source, provider, SequenceRandom([10] * 24))
                self.assertEqual(tuple(c.actor_id for c in provider.contexts), expected)
                self.assertEqual(result.round_state.completed_turn_entity_ids, expected)
                self.assertEqual(result.round_state.side_order, side_order)
                self.assertIs(result.outcome, NpcRoundOutcome.COMPLETE)

    def test_partial_progress_is_preserved_when_later_actor_has_no_attack_then_resumes(self):
        source = request()
        provider = Candidates()
        original = provider.get_candidates
        provider.get_candidates = lambda context: context if context.actor_id == "brigand:1" else original(context)
        first_rng = SequenceRandom([10] * 6 + [7])
        stopped = coordinator.run_npc_round(source, provider, first_rng)
        self.assertIs(stopped.outcome, NpcRoundOutcome.SELECTION_BLOCKED)
        self.assertEqual(stopped.round_state.completed_turn_entity_ids, ("brigand:0",))
        self.assertEqual(stopped.round_state.active_turn.actor_id, "brigand:1")
        self.assertEqual(len(stopped.state.consumed_execution_ids), 1)
        self.assertEqual(first_rng.randint(1, 10), 7)
        remaining_provider = Candidates()
        remaining_rng = SequenceRandom([10] * 18 + [7])
        final = coordinator.run_npc_round(resume(source, stopped), remaining_provider, remaining_rng)
        self.assertIs(final.outcome, NpcRoundOutcome.COMPLETE)
        self.assertEqual(tuple(c.actor_id for c in remaining_provider.contexts), ("brigand:1", "brigand:2", "brigand:3"))
        self.assertEqual(final.state.consumed_execution_ids[:1], stopped.state.consumed_execution_ids)
        self.assertEqual(len(final.state.consumed_execution_ids), 4)
        self.assertEqual(remaining_rng.randint(1, 10), 7)
