from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.integration.test_m2_npc_roster_preparation import roster
from tests.unit.test_k1_secondary_target_resolution import TargetDecisions
from tests.unit.test_m2_npc_roster_attack_execution import change_participant, request as attack_request
from towr.domain.attack_models import ConditionAfterGiveGroundSpec
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.injury_models import ProfileInjuryState, ProfileStateChangeRequest
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_nearby_stagger_models import NpcNearbyStaggerExecutionRequest, NpcNearbyStaggerExecutionResult
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.ranged_weapon_attack_preparation_models import BLUNDERBUSS_NEARBY_STAGGER_RULE_ID as RULE
from towr.domain.resolution_models import (
    GiveGroundRequest, IdentifiedStaggerTarget, NearbyTargetsStaggerRequest,
    NearbyTargetsStaggerResolutionRequest, StaggerImpactRequest, TargetInjuryPolicy,
)
from towr.rules import npc_nearby_stagger_resolution as nearby
from towr.rules.npc_roster_attack_execution import execute_npc_roster_attack
from towr.rules.stagger_resolution import MissingStaggerDecisionError, InvalidStaggerDecisionError


def request(*, states=(), targets=("brigand:1", "brigand:3")):
    state = NpcRosterAttackState(roster(), ("old:attack",), ("old:attack",), ("old:attack",))
    for index, conditions in states:
        injury = state.roster.participant(f"brigand:{index}").state.injury
        for condition in conditions:
            injury = replace(injury, conditions=injury.conditions.with_condition(condition))
        state = change_participant(state, index, injury=injury)
    return NpcNearbyStaggerExecutionRequest(state, NearbyTargetsStaggerResolutionRequest(
        "batch", NearbyTargetsStaggerRequest("primary", RULE), "brigand:2", tuple(
            IdentifiedStaggerTarget(actor, StaggerImpactRequest("impact:" + actor, actor, TargetInjuryPolicy.MINION,
                state.roster.participant(actor).state.injury, True, False)) for actor in targets)))


class M2NpcNearbyStaggerTests(unittest.TestCase):
    def test_equal_defeat_follow_ups_keep_both_target_identities(self):
        source = request(states=((1, (Condition.STAGGERED, Condition.PRONE)),
                                 (3, (Condition.STAGGERED, Condition.PRONE))))
        result = nearby.execute_npc_nearby_stagger(source, Mock())
        first, second = result.pending_targets
        self.assertEqual((first.target_id, second.target_id), ("brigand:1", "brigand:3"))
        self.assertEqual(first.impact.follow_ups, second.impact.follow_ups)
        self.assertNotEqual(first.impact.request_id, second.impact.request_id)
        self.assertTrue(all(result.state.roster.participant(t.target_id).state.injury.defeated
                            for t in result.pending_targets))

    def test_unsupported_policies_defeated_extra_effects_and_unknown_targets_fail_preflight(self):
        source = request(targets=("brigand:1",))
        participant = source.state.roster.participant("brigand:1")
        brute = replace(participant.definition, id="brute", injury_policy=TargetInjuryPolicy.BRUTE, wound_limit=2)
        changed = replace(participant, definition=brute, state=replace(participant.state,
            definition_id="brute", injury=ProfileInjuryState(0, 2)))
        roster_state = replace(source.state, roster=NpcRoster(tuple(
            changed if p is participant else p for p in source.state.roster.participants)))
        target = source.resolution.targets[0]
        with self.assertRaisesRegex(ValueError, "Minion"):
            replace(source, state=roster_state, resolution=replace(source.resolution, targets=(replace(target,
                impact=replace(target.impact, target_policy=TargetInjuryPolicy.BRUTE, target_state=changed.state.injury)),)))
        dead = replace(participant.state.injury, wounds=1, defeated=True)
        with self.assertRaisesRegex(ValueError, "defeated"):
            replace(source, state=change_participant(source.state, 1, injury=dead),
                    resolution=replace(source.resolution, targets=(replace(target, impact=replace(target.impact, target_state=dead)),)))
        with self.assertRaisesRegex(ValueError, "additional"):
            replace(source, resolution=replace(source.resolution, targets=(replace(target, impact=replace(target.impact,
                after_give_ground_effects=(ConditionAfterGiveGroundSpec(Condition.BROKEN, "extra"),))),)))
        with self.assertRaises(ValueError):
            replace(source, resolution=replace(source.resolution, targets=(replace(target, target_id="unknown",
                impact=replace(target.impact, target_id="unknown")),)))

    def test_ordered_friendly_and_hostile_targets_keep_scoped_pending_and_unselected_state(self):
        source = request(states=((1, (Condition.STAGGERED,)), (3, (Condition.STAGGERED,))),
                         targets=("brigand:3", "brigand:0", "brigand:1"))
        before = deepcopy(source)
        decisions = Mock(wraps=TargetDecisions(stagger_choices={
            "impact:brigand:3:stagger": StaggerChoice.SUFFER_WOUND,
            "impact:brigand:1:stagger": StaggerChoice.GIVE_GROUND,
        }))
        rng = Mock()
        with patch.object(nearby, "resolve_nearby_targets_stagger", wraps=nearby.resolve_nearby_targets_stagger) as resolve:
            result = nearby.execute_npc_nearby_stagger(source, rng, decisions=decisions)
            updated = nearby.apply_npc_nearby_stagger(source.state, result)
            self.assertEqual(result.state, updated)
        resolve.assert_called_once_with(source.resolution, rng, decisions=decisions)
        self.assertIs(result.resolution.source_request, source.resolution)
        self.assertEqual(tuple(c.kwargs["request"].id for c in decisions.choose_repeated_stagger.call_args_list),
                         ("impact:brigand:3:stagger", "impact:brigand:1:stagger"))
        self.assertEqual(tuple(t.target_id for t in result.resolution.targets), ("brigand:3", "brigand:0", "brigand:1"))
        self.assertEqual(tuple(t.target_id for t in result.pending_targets), ("brigand:3", "brigand:1"))
        self.assertIsInstance(result.pending_targets[0].impact.follow_ups[0], ProfileStateChangeRequest)
        self.assertIsInstance(result.pending_targets[1].impact.follow_ups[0], GiveGroundRequest)
        self.assertTrue(updated.roster.participant("brigand:3").state.injury.defeated)
        self.assertFalse(updated.roster.participant("brigand:3").state.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(updated.roster.participant("brigand:0").state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(updated.roster.participant("brigand:1"), source.state.roster.participant("brigand:1"))
        self.assertIs(updated.roster.participant("brigand:2"), source.state.roster.participant("brigand:2"))
        self.assertEqual(updated.consumed_nearby_stagger_sources, (source.resolution.source,))
        self.assertEqual((updated.consumed_execution_ids, updated.acknowledged_defeat_execution_ids,
                          updated.consumed_give_ground_execution_ids), (("old:attack",),) * 3)
        self.assertEqual(result.applied_rule_ids, (RULE,))
        self.assertEqual(rng.mock_calls, [])
        self.assertEqual(source, before)

    def test_prone_and_forced_wound_use_existing_stagger_rules(self):
        for conditions, can_leave, used, choice, expected in (
            ((Condition.STAGGERED,), True, False, StaggerChoice.FALL_PRONE, Condition.PRONE),
            ((Condition.STAGGERED, Condition.PRONE), True, False, None, None),
            ((Condition.STAGGERED,), False, False, StaggerChoice.GIVE_GROUND, "invalid"),
            ((Condition.STAGGERED,), True, True, StaggerChoice.GIVE_GROUND, "invalid"),
        ):
            with self.subTest(conditions=conditions, used=used, choice=choice):
                source = request(states=((1, conditions),), targets=("brigand:1",))
                target = source.resolution.targets[0]
                source = replace(source, resolution=replace(source.resolution, targets=(replace(target,
                    impact=replace(target.impact, can_target_leave_zone=can_leave, target_has_given_ground_this_round=used)),)))
                decisions = TargetDecisions(stagger_choices={"impact:brigand:1:stagger": choice}) if choice else Mock()
                if expected == "invalid":
                    with self.assertRaises(InvalidStaggerDecisionError):
                        nearby.execute_npc_nearby_stagger(source, Mock(), decisions=decisions)
                    continue
                result = nearby.execute_npc_nearby_stagger(source, Mock(), decisions=decisions)
                injury = result.state.roster.participant("brigand:1").state.injury
                if expected is Condition.PRONE:
                    self.assertTrue(injury.conditions.has(Condition.PRONE))
                    self.assertTrue(injury.conditions.has(Condition.STAGGERED))
                    self.assertEqual(result.pending_targets, ())
                else:
                    self.assertEqual((injury.wounds, injury.defeated), (1, True))
                    self.assertEqual(decisions.mock_calls, [])

    def test_replay_is_keyed_by_effect_source_even_with_new_batch_ids_or_unchanged_injury(self):
        source = request(states=((1, (Condition.STAGGERED,)),), targets=("brigand:1",))
        decisions = TargetDecisions(stagger_choices={"impact:brigand:1:stagger": StaggerChoice.GIVE_GROUND})
        result = nearby.execute_npc_nearby_stagger(source, Mock(), decisions=decisions)
        updated = nearby.apply_npc_nearby_stagger(source.state, result)
        self.assertEqual(updated.roster, source.state.roster)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            nearby.apply_npc_nearby_stagger(updated, result)
        target = source.resolution.targets[0]
        changed_ids = replace(source.resolution, id="new-batch", targets=(replace(target, impact=replace(target.impact, id="new-impact")),))
        for batch in (source.resolution, changed_ids, replace(changed_ids, targets=())):
            with self.assertRaisesRegex(ValueError, "already consumed"):
                replace(source, state=updated, resolution=batch)

    def test_stale_history_and_any_roster_change_are_rejected_before_transfer(self):
        source = request()
        result = nearby.execute_npc_nearby_stagger(source, Mock())
        for current in (replace(source.state, consumed_execution_ids=("old:attack", "other")),
                        change_participant(source.state, 0, holds_shield=not source.state.roster.participant("brigand:0").state.holds_shield)):
            with self.assertRaisesRegex(ValueError, "source differs"):
                nearby.apply_npc_nearby_stagger(current, result)
        changed = change_participant(source.state, 1, injury=replace(source.state.roster.participant("brigand:1").state.injury,
            conditions=source.state.roster.participant("brigand:1").state.injury.conditions.with_condition(Condition.STAGGERED)))
        with self.assertRaisesRegex(ValueError, "stale"):
            replace(source, state=changed)

    def test_source_guards_reject_same_ids_different_context_and_malformed_results(self):
        source = request()
        result = nearby.execute_npc_nearby_stagger(source, Mock())
        targets = source.resolution.targets
        foreign = replace(source, resolution=replace(source.resolution, targets=(replace(targets[0],
            impact=replace(targets[0].impact, can_target_leave_zone=False)), targets[1])))
        other_result = nearby.execute_npc_nearby_stagger(foreign, Mock())
        with self.assertRaisesRegex(ValueError, "full executed source"):
            replace(result, resolution=other_result.resolution)
        for changes in ({"request_id": "other"}, {"source_resolution_id": "other"},
                        {"targets": result.resolution.targets[::-1]}, {"targets": result.resolution.targets[:1]},
                        {"applied_rule_ids": ()}):
            with self.assertRaises(ValueError):
                replace(result.resolution, **changes)
        with self.assertRaises(TypeError):
            replace(result.resolution, source_request=None)
        with self.assertRaises(TypeError):
            replace(result.resolution, targets=(None,))
        with self.assertRaises(FrozenInstanceError):
            result.source_request = None

    def test_empty_batch_still_consumes_source_and_history_survives_next_ordinary_attack(self):
        source = request(targets=())
        result = nearby.execute_npc_nearby_stagger(source, Mock())
        self.assertEqual(result.state.roster, source.state.roster)
        self.assertEqual(result.pending_targets, ())
        with self.assertRaisesRegex(ValueError, "already consumed"):
            nearby.apply_npc_nearby_stagger(result.state, result)
        attack = attack_request(source=result.state.roster)
        attack = replace(attack, state=result.state)
        executed = execute_npc_roster_attack(attack, SequenceRandom([10] * 6))
        self.assertEqual(executed.state.consumed_nearby_stagger_sources, (source.resolution.source,))

    def test_preflight_rejects_unsupported_inputs_and_missing_decision_leaves_source_intact(self):
        source = request(states=((3, (Condition.STAGGERED,)),))
        before = deepcopy(source)
        with self.assertRaises(MissingStaggerDecisionError):
            nearby.execute_npc_nearby_stagger(source, Mock())
        self.assertEqual(source, before)  # first target had resolved before the second required a decision
        with self.assertRaises(TypeError):
            nearby.execute_npc_nearby_stagger(None, Mock())
        with self.assertRaises(TypeError):
            NpcNearbyStaggerExecutionResult(source, None)
        with self.assertRaises(TypeError):
            nearby.apply_npc_nearby_stagger(None, None)
        with self.assertRaises(ValueError):
            replace(source, resolution=replace(source.resolution, source=NearbyTargetsStaggerRequest("primary", "other-rule")))
        with self.assertRaises(ValueError):
            replace(source, resolution=replace(source.resolution, primary_target_id="unknown"))
        with self.assertRaises(TypeError):
            replace(source.state, consumed_nearby_stagger_sources=("primary",))
        with self.assertRaises(ValueError):
            replace(source.state, consumed_nearby_stagger_sources=(source.resolution.source,) * 2)
