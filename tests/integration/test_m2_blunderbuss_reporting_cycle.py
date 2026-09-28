from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m2_blunderbuss_chain_summary import journal, observe
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.npc_rounds_models import NpcRoundsOutcome
from towr.engine.npc_rounds_reporting import summarize_npc_rounds_chain
from towr.rules import attack_action_execution as attack_executor
from towr.rules import npc_nearby_stagger_resolution as nearby
from towr.rules import npc_nearby_give_ground_resolution as secondary_move
from towr.rules import npc_blunderbuss_give_ground_resolution as primary_move


class M2BlunderbussReportingCycleTests(unittest.TestCase):
    def test_mixed_runner_external_journal_and_final_observations_have_no_reexecution_or_double_count(self):
        for primary, empty, enemy, movement_first, disposition in product(
            ("wound", "move", "stagger"), (False, True), (False, True), (False, True), NpcDefeatDisposition,
        ):
            with self.subTest(primary=primary, empty=empty, enemy=enemy, order=movement_first, disposition=disposition):
                shot = [1, 2, 10, 10, 10, 10, 10, 10] if primary == "wound" else [1, 10, 10, 10, 10, 1, 10, 10]
                rng = Mock(wraps=SequenceRandom([10] * 6 + shot + [7]))
                with (
                    patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
                    patch.object(nearby, "resolve_nearby_targets_stagger", wraps=nearby.resolve_nearby_targets_stagger) as stagger,
                    patch.object(secondary_move, "resolve_give_ground", wraps=secondary_move.resolve_give_ground) as secondary,
                    patch.object(primary_move, "resolve_give_ground", wraps=primary_move.resolve_give_ground) as movement,
                ):
                    steps = journal(primary=primary, empty=empty, enemy=enemy, movement_first=movement_first,
                        disposition=disposition, primary_disposition=NpcDefeatDisposition.DISARMED_AND_SURRENDERED,
                        mixed=True, rng=rng)
                    repeated = observe(steps[-1].current, steps[-1].spatial_state)
                    report = summarize_npc_rounds_chain((*steps, repeated, repeated))
                    self.assertEqual(report.executed_attack_count, 2)
                    self.assertEqual(tuple(s.executed_attack_count for s in report.call_summaries), (2, 0, 0, 0))
                    self.assertEqual(report.visited_round_count, 1)
                    self.assertEqual(report.newly_completed_round_count, int(primary == "wound" and not empty))
                    self.assertEqual(report.pending_follow_up_count, 0)
                    self.assertEqual(report.current, repeated.current)
                    self.assertEqual(report.spatial_state, repeated.spatial_state)
                    self.assertEqual(report.participants, report.final_summary.participants)
                    self.assertEqual(len(report.defeat_acknowledgements), int(not empty) + int(primary == "wound"))
                    if not empty:
                        self.assertEqual(report.defeat_acknowledgements[0].source_request.decision.disposition, disposition)
                    if primary == "wound":
                        self.assertEqual(report.defeat_acknowledgements[-1].source_request.decision.disposition,
                                         NpcDefeatDisposition.DISARMED_AND_SURRENDERED)
                    self.assertIs(report.outcome, NpcRoundsOutcome.ROUND_LIMIT if primary == "wound" and not empty
                                  else NpcRoundsOutcome.SELECTION_BLOCKED)
                    self.assertFalse(report.current.weapons[0].weapon_state.loaded)
                    self.assertEqual(len(report.current.weapons[0].weapon_state.reload_cycle_ids), 1)
                    self.assertEqual(kernel.call_count, 2)
                    self.assertEqual(stagger.call_count, 1)
                    self.assertEqual(secondary.call_count, int(not empty))
                    self.assertEqual(movement.call_count, int(primary == "move"))
                    self.assertEqual(rng.randint.call_count, 14)
                    self.assertEqual(rng.randint(1, 10), 7)
