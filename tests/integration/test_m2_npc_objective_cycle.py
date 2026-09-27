from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.integration.test_m2_mixed_round_cycle import MixedCandidates
from tests.unit.test_k1_spatial_resolution import graph
from tests.unit.test_m2_minion_defeat import acknowledgement
from tests.unit.test_m2_npc_round_coordinator import request
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_round_advance_models import NpcRoundAdvanceRequest
from towr.domain.npc_round_exclusion_models import NpcRoundExclusionRequest
from towr.domain.npc_rounds_models import NpcRoundsOutcome as Outcome, NpcRoundsRequest
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement
from towr.domain.turn_models import CombatSide, CombatTurnEndResult
from towr.engine.npc_objective_evaluation import assess_npc_defeat_objective
from towr.engine.npc_rounds_reporting import summarize_npc_rounds_chain
from towr.engine import npc_rounds_runner as runner
from towr.rules import attack_action_execution as attack_executor
from towr.rules import minion_defeat_resolution as defeat, npc_round_exclusion as exclusion
from towr.rules.npc_roster_attack_execution import apply_npc_roster_attack_result


class M2NpcObjectiveCycleTests(unittest.TestCase):
    def test_two_real_defeats_complete_the_explicit_objective_and_round_without_advance(self):
        for reverse, first_disposition, second_disposition in product(
            (False, True), NpcDefeatDisposition, NpcDefeatDisposition,
        ):
            with self.subTest(reverse=reverse, dispositions=(first_disposition, second_disposition)):
                actors, targets = (("brigand:2", "brigand:3"), ("brigand:0", "brigand:1")) if reverse else (
                    ("brigand:0", "brigand:1"), ("brigand:2", "brigand:3"))
                source = request()
                source = replace(source, actor_order=(actors[0], targets[0], actors[1], targets[1]),
                    round_state=replace(source.round_state, side_order=tuple(CombatSide)[::(-1 if reverse else 1)]))
                spatial = SpatialBattleState(graph(), tuple(
                    SpatialEntityPlacement(p.entity_id, p.side.value, "zone:a") for p in source.round_state.participants
                ), free_move_used_entity_ids=(actors[0],), difficult_terrain_tested_entity_ids=(actors[1],))
                original = deepcopy((source, spatial))
                self.assertEqual((source.state.consumed_execution_ids, source.state.acknowledged_defeat_execution_ids,
                                  source.state.consumed_give_ground_execution_ids), ((), (), ()))
                objective = NpcDefeatObjective(targets[::-1])
                candidate_provider, plans = Mock(), Mock()
                candidate_provider.get_candidates.side_effect = lambda c, s: MixedCandidates(s, dict(zip(actors, targets))).get_candidates(c)
                rng = Mock(wraps=SequenceRandom([1, 2, 10, 10, 10, 10] * 2 + [7]))
                chain, attacks, acknowledgements, exclusions, snapshots = [], [], [], [], []
                current = source
                with (
                    patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
                    patch.object(defeat, "acknowledge_minion_defeat", wraps=defeat.acknowledge_minion_defeat) as acknowledge,
                    patch.object(exclusion, "exclude_defeated_npc", wraps=exclusion.exclude_defeated_npc) as exclude,
                    patch.object(runner, "advance_npc_round", side_effect=AssertionError("unexpected advance")) as advance,
                ):
                    for index, disposition in enumerate((first_disposition, second_disposition)):
                        stopped = runner.run_npc_rounds(NpcRoundsRequest(current, spatial, 1), candidate_provider, plans, rng)
                        chain.append(stopped)
                        snapshots.append((stopped, deepcopy(stopped)))
                        self.assertIs(stopped.outcome, Outcome.PENDING_FOLLOW_UPS)
                        self.assertEqual(stopped.advances, ())
                        self.assertIs(stopped.spatial_state, spatial)
                        self.assertEqual(len(stopped.current.pending_follow_ups), 1)
                        self.assertEqual(stopped.current.round_state.completed_turn_entity_ids, actors[:index])
                        self.assertEqual(stopped.current.round_state.excluded_turn_entity_ids, targets[:index])
                        executed = tuple(s for s in stopped.rounds[0].steps if isinstance(s, NpcRosterAttackExecutionResult))
                        self.assertEqual(len(executed), 1)
                        attack = executed[0]
                        attacks.append(attack)
                        self.assertEqual((attack.execution.actor_id, attack.execution.target_id), (actors[index], targets[index]))
                        self.assertEqual(attack.source_request.state.acknowledged_defeat_execution_ids,
                                         tuple(a.execution.request_id for a in attacks[:index]))
                        report = summarize_npc_rounds_chain(tuple(chain))
                        assessment = assess_npc_defeat_objective(report, objective)
                        self.assertEqual(assessment.achieved, index == 1)
                        self.assertEqual(assessment.remaining_target_actor_ids, (targets[1],) if index == 0 else ())
                        self.assertEqual(report.defeat_acknowledgements, tuple(acknowledgements))
                        self.assertEqual(report.executed_attack_count, index + 1)
                        self.assertEqual(report.newly_completed_round_count, 0)
                        self.assertEqual(report.current.pending_follow_ups, stopped.current.pending_follow_ups)

                        # Pending observations and an achieved objective cannot consume consequences or attack again.
                        unused_candidates, unused_plans, unused_rng = Mock(), Mock(), Mock()
                        observed = runner.run_npc_rounds(NpcRoundsRequest(stopped.current, spatial, 2),
                            unused_candidates, unused_plans, unused_rng)
                        self.assertEqual(observed.current, stopped.current)
                        self.assertEqual(observed.rounds[0].steps, ())
                        self.assertEqual(unused_candidates.mock_calls + unused_plans.mock_calls + unused_rng.mock_calls, [])
                        with self.assertRaisesRegex(ValueError, "pending"):
                            NpcRoundExclusionRequest("early", stopped.current, targets[index])

                        confirmation = defeat.acknowledge_minion_defeat(acknowledgement(stopped.current, attack, disposition))
                        confirmed = defeat.apply_minion_defeat_acknowledgement(stopped.current, confirmation)
                        self.assertEqual(confirmed.pending_follow_ups, ())
                        removed = exclusion.exclude_defeated_npc(NpcRoundExclusionRequest("exclude:" + targets[index], confirmed, targets[index]))
                        current = exclusion.apply_npc_round_exclusion(confirmed, removed)
                        self.assertIs(current.round_state.active_turn, stopped.current.round_state.active_turn)
                        self.assertFalse(current.round_state.round_complete)
                        chain.extend((confirmation, removed))
                        acknowledgements.append(confirmation)
                        exclusions.append(removed)

                    # Close the already executed second turn; every target turn has been explicitly excluded.
                    final = runner.run_npc_rounds(NpcRoundsRequest(current, spatial, 1), candidate_provider, plans, rng)
                    chain.append(final)
                    chain_before = deepcopy(chain)
                    report = summarize_npc_rounds_chain(tuple(chain))
                    assessment = assess_npc_defeat_objective(report, objective)
                    self.assertTrue(assessment.achieved)
                    self.assertEqual(assessment.remaining_target_actor_ids, ())
                    self.assertIs(report.outcome, Outcome.ROUND_LIMIT)
                    self.assertIsNone(report.blocked_reason)
                    self.assertEqual(report.pending_follow_up_count, 0)
                    self.assertEqual((report.executed_attack_count, report.newly_completed_round_count, report.visited_round_count), (2, 1, 1))
                    self.assertEqual(tuple(s.executed_attack_count for s in report.call_summaries), (1, 1, 0))
                    self.assertEqual(tuple(s.newly_completed_round_count for s in report.call_summaries), (0, 0, 1))
                    self.assertTrue(final.current.round_state.round_complete)
                    self.assertIsNone(final.current.round_state.active_turn)
                    self.assertEqual(final.current.round_state.completed_turn_entity_ids, actors)
                    self.assertEqual(final.current.round_state.excluded_turn_entity_ids, targets)
                    self.assertEqual(final.current.round_state.side_order, source.round_state.side_order)
                    self.assertIs(final.spatial_state, spatial)
                    ids = tuple(a.execution.request_id for a in attacks)
                    self.assertEqual(len(set(ids)), 2)
                    self.assertEqual(final.current.state.consumed_execution_ids, ids)
                    self.assertEqual(final.current.state.acknowledged_defeat_execution_ids, ids)
                    self.assertEqual(final.current.state.consumed_give_ground_execution_ids, ())
                    self.assertEqual(report.defeat_acknowledgements, tuple(acknowledgements))
                    self.assertEqual(tuple(a.source_request.decision.disposition for a in report.defeat_acknowledgements),
                                     (first_disposition, second_disposition))
                    for index, confirmation in enumerate(report.defeat_acknowledgements):
                        self.assertIs(confirmation.source_request.attack, attacks[index])
                        self.assertEqual(confirmation.source_request.decision.target_id, targets[index])
                    for record in report.participants:
                        self.assertEqual((record.wounds, record.defeated), (1, True) if record.actor_id in targets else (0, False))
                        self.assertEqual(record.conditions, source.state.roster.participant(record.actor_id).state.injury.conditions)
                    ended = tuple(step.completed_turn for call in report.call_summaries for r in call.source_result.rounds
                                  for step in r.steps if isinstance(step, CombatTurnEndResult))
                    self.assertEqual(tuple(t.action_slots[0].execution.id for t in ended), ids)
                    self.assertEqual(ended, tuple(result.current.round_state.active_turn for result, _ in snapshots))

                    # The supplied limit ends this scenario. No next-round plan for one living side is executed.
                    living = tuple(final.current.state.roster.participant(actor).turn_participant for actor in actors)
                    with self.assertRaisesRegex(ValueError, "both sides"):
                        NpcRoundAdvanceRequest("one-side", final.current, spatial, living, actors)
                    for attack, confirmation, removed in zip(attacks, acknowledgements, exclusions):
                        with self.assertRaisesRegex(ValueError, "already consumed"):
                            apply_npc_roster_attack_result(final.current.state, attack)
                        with self.assertRaisesRegex(ValueError, "already consumed"):
                            replace(attack.source_request, state=final.current.state)
                        with self.assertRaisesRegex(ValueError, "already acknowledged"):
                            replace(confirmation.source_request, id="new:" + confirmation.source_request.id,
                                    current=replace(final.current, pending_follow_ups=attack.pending_follow_ups))
                        with self.assertRaisesRegex(ValueError, "source differs"):
                            defeat.apply_minion_defeat_acknowledgement(final.current, confirmation)
                        with self.assertRaisesRegex(ValueError, "source differs"):
                            exclusion.apply_npc_round_exclusion(final.current, removed)
                    with self.assertRaisesRegex(ValueError, "source differs"):
                        summarize_npc_rounds_chain((*chain, acknowledgements[-1], final))
                    repeated = runner.run_npc_rounds(NpcRoundsRequest(final.current, spatial, 1), candidate_provider, plans, rng)
                    repeated_report = summarize_npc_rounds_chain((*chain, repeated))
                    self.assertEqual(repeated.current, final.current)
                    self.assertTrue(assess_npc_defeat_objective(repeated_report, objective).achieved)
                    self.assertEqual((repeated_report.executed_attack_count, repeated_report.newly_completed_round_count), (2, 1))
                    self.assertEqual(tuple(call.args[0].actor_id for call in candidate_provider.get_candidates.call_args_list), actors)
                    self.assertTrue(all(call.args[1] is spatial for call in candidate_provider.get_candidates.call_args_list))
                    self.assertEqual(kernel.call_count, 2)
                    self.assertEqual(acknowledge.call_count, 2)
                    self.assertEqual(exclude.call_count, 2)
                    plans.get_next_round.assert_not_called()
                    advance.assert_not_called()
                    self.assertEqual(rng.randint.call_count, 12)
                    self.assertEqual(rng.randint(1, 10), 7)
                    self.assertEqual(chain, chain_before)
                    self.assertEqual((source, spatial), original)
                    for result, before in snapshots:
                        self.assertEqual(result, before)
