from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock

from tests.unit.test_m2_npc_round_advance import completed_context
from tests.unit.test_m2_npc_round_exclusion import defeat
from tests.unit.test_m2_npc_rounds_runner import request
from towr.domain.npc_objective_models import NpcDefeatObjective, NpcDefeatObjectiveAssessment
from towr.domain.npc_rounds_models import NpcRoundsOutcome as Outcome, NpcRoundsRequest
from towr.domain.resolution_models import GiveGroundRequest
from towr.engine.npc_objective_evaluation import assess_npc_defeat_objective
from towr.engine.npc_rounds_reporting import summarize_npc_rounds_chain
from towr.engine.npc_rounds_runner import run_npc_rounds


def observe(source):
    candidates, plans, rng = Mock(), Mock(), Mock()
    candidates.get_candidates.side_effect = lambda c, s: c
    result = run_npc_rounds(source, candidates, plans, rng)
    assert not plans.mock_calls and not rng.mock_calls
    return summarize_npc_rounds_chain((result,))


class M2NpcObjectiveEvaluationTests(unittest.TestCase):
    def test_none_partial_and_all_defeated_on_both_sides_preserve_target_order_and_pending(self):
        for reverse in (False, True):
            source = request(reverse=reverse)
            targets = (1, 0) if reverse else (3, 2)
            objective = NpcDefeatObjective(tuple(f"brigand:{i}" for i in targets))
            for defeated in ((), targets[:1], targets):
                with self.subTest(reverse=reverse, defeated=defeated):
                    current = replace(defeat(source.current, *defeated), pending_follow_ups=(GiveGroundRequest("pending"),))
                    report = observe(replace(source, current=current))
                    before = deepcopy((report, objective))
                    result = assess_npc_defeat_objective(report, objective)
                    self.assertEqual(result.remaining_target_actor_ids,
                                     tuple(f"brigand:{i}" for i in targets if i not in defeated))
                    self.assertEqual(result.achieved, defeated == targets)
                    self.assertIs(result.source_report, report)
                    self.assertIs(result.objective, objective)
                    self.assertIs(report.outcome, Outcome.PENDING_FOLLOW_UPS)
                    self.assertEqual(report.current.pending_follow_ups, current.pending_follow_ups)
                    self.assertEqual(report.defeat_acknowledgements, ())
                    self.assertEqual(assess_npc_defeat_objective(report, objective), result)
                    self.assertEqual((report, objective), before)

    def test_stop_reason_does_not_decide_objective_and_initial_defeat_counts(self):
        objective = NpcDefeatObjective(("brigand:0",))
        source = request()
        blocked = observe(source)
        defeated = observe(replace(source, current=defeat(source.current, 0)))
        complete = completed_context()
        limit = observe(NpcRoundsRequest(complete.current, complete.spatial_state, 1))
        for report, achieved, outcome in ((blocked, False, Outcome.SELECTION_BLOCKED),
                                           (defeated, True, Outcome.DEFEATED_ACTOR),
                                           (limit, False, Outcome.ROUND_LIMIT)):
            result = assess_npc_defeat_objective(report, objective)
            self.assertIs(report.outcome, outcome)
            self.assertEqual(result.achieved, achieved)
            self.assertEqual(report.executed_attack_count, 0)

    def test_unknown_and_unused_roster_targets_are_rejected(self):
        source = request()
        members = source.current.round_state.participants
        current = replace(source.current, round_state=replace(source.current.round_state,
                          participants=(members[0], members[2])), actor_order=("brigand:0", "brigand:2"))
        report = observe(replace(source, current=current))
        self.assertEqual(len(report.current.state.roster.participants), 4)
        for target in ("unknown", "brigand:1", "brigand:3"):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, "participated"):
                assess_npc_defeat_objective(report, NpcDefeatObjective(("brigand:0", target)))
        self.assertEqual(assess_npc_defeat_objective(report, NpcDefeatObjective(("brigand:2", "brigand:0")))
                         .remaining_target_actor_ids, ("brigand:2", "brigand:0"))

    def test_objective_requires_nonempty_unique_ordered_string_ids(self):
        for invalid in ((), ("",), ("  ",), ("brigand:0", "brigand:0")):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                NpcDefeatObjective(invalid)
        for invalid in (None, "brigand:0", {"brigand:0"}, {"brigand:0": True}, (1,), (True,)):
            with self.subTest(invalid=invalid), self.assertRaises(TypeError):
                NpcDefeatObjective(invalid)
        supplied = ["brigand:2", "brigand:0"]
        objective = NpcDefeatObjective(supplied)
        supplied.clear()
        self.assertEqual(objective.target_actor_ids, ("brigand:2", "brigand:0"))
        with self.assertRaises(FrozenInstanceError):
            objective.target_actor_ids = ()

    def test_assessment_requires_typed_sources_and_derived_values_cannot_be_supplied(self):
        source = request()
        report = observe(source)
        objective = NpcDefeatObjective(("brigand:0",))
        for invalid in (None, source, report.source_steps[0], report.final_summary):
            with self.assertRaises(TypeError):
                assess_npc_defeat_objective(invalid, objective)
        for invalid in (None, (), ("brigand:0",)):
            with self.assertRaises(TypeError):
                assess_npc_defeat_objective(report, invalid)
        with self.assertRaises(TypeError):
            NpcDefeatObjectiveAssessment(report, objective, achieved=True)
        result = assess_npc_defeat_objective(report, objective)
        with self.assertRaises(FrozenInstanceError):
            result.source_report = None
        changed = observe(replace(source, current=defeat(source.current, 0)))
        rebound = replace(result, source_report=changed)
        self.assertTrue(rebound.achieved)
        self.assertFalse(result.achieved)
        self.assertFalse(replace(rebound, objective=NpcDefeatObjective(("brigand:1",))).achieved)
        with self.assertRaisesRegex(ValueError, "participated"):
            replace(result, objective=NpcDefeatObjective(("foreign",)))
