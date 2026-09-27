from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from itertools import permutations, product
import unittest
from unittest.mock import Mock, patch

from tests.unit.test_k1_secondary_target_resolution import TargetDecisions
from tests.unit.test_m2_npc_nearby_defeat import acknowledgement
from tests.unit.test_m2_npc_nearby_give_ground import context, movement_request, spatial_context
from towr.domain.condition_models import Condition, ConditionState, StaggerChoice
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_nearby_consequence_models import NpcNearbyConsequenceChain
from towr.domain.npc_nearby_defeat_models import NpcNearbyDefeatAcknowledgementRequest
from towr.domain.npc_nearby_give_ground_models import NpcNearbyGiveGroundExecutionRequest
from towr.domain.resolution_models import GiveGroundResolutionRequest
from towr.rules import npc_nearby_consequence_resolution as consequences
from towr.rules import npc_nearby_give_ground_resolution as movement
from towr.rules.npc_nearby_defeat_resolution import acknowledge_npc_nearby_defeat
from towr.rules.npc_nearby_stagger_resolution import execute_npc_nearby_stagger


def chain_context(*, enemy=False, two_movements=False):
    source = context(two_movements=two_movements).batch.source_request
    template = source.state.roster.participant("brigand:3")
    extra = replace(template, state=replace(template.state, actor_id="brigand:4",
        injury=replace(template.state.injury, conditions=ConditionState((Condition.STAGGERED, Condition.PRONE)))))
    state = replace(source.state, roster=replace(source.state.roster,
        participants=(*source.state.roster.participants, extra)))
    template_target = source.resolution.targets[-1]
    target = replace(template_target, target_id="brigand:4", impact=replace(template_target.impact,
        id="impact:brigand:4", target_id="brigand:4", target_state=extra.state.injury))
    source = replace(source, state=state, resolution=replace(source.resolution, targets=(*source.resolution.targets, target)))
    rng = Mock()
    batch = execute_npc_nearby_stagger(source, rng, decisions=TargetDecisions(stagger_choices={
        "impact:brigand:1:stagger": StaggerChoice.GIVE_GROUND,
        "impact:brigand:3:stagger": StaggerChoice.GIVE_GROUND,
    }))
    rng.randint.assert_not_called()
    return NpcNearbyConsequenceChain(batch, spatial_context(batch, enemy=enemy))


def defeat_request(chain, target="brigand:3", disposition=NpcDefeatDisposition.KNOCKED_OUT):
    return NpcNearbyDefeatAcknowledgementRequest("ack:" + target, chain.state, chain.batch,
        MinionDefeatDecision("brigand:0", target, disposition, True), continuation=chain)


def give_ground_request(chain, target="brigand:1"):
    follow_up, = next(t.impact.follow_ups for t in chain.pending_targets if t.target_id == target)
    request = GiveGroundResolutionRequest(follow_up, chain.spatial_state, target, "zone:c",
        chain.state.roster.participant(target).state.injury.conditions,
        away_from_entity_id=chain.batch.source_request.primary_attack.attack.actor_id)
    return NpcNearbyGiveGroundExecutionRequest("move:" + target, chain.state, chain.spatial_state,
        chain.batch, target, request, continuation=chain)


def append(chain, result):
    return consequences.apply_npc_nearby_consequence(chain.state, chain.spatial_state, chain, result)


class M2NpcNearbyConsequenceTests(unittest.TestCase):
    def test_all_orders_of_two_defeats_and_movement_preserve_decisions_and_pending(self):
        for enemy, first_choice, second_choice in product((False, True), NpcDefeatDisposition, NpcDefeatDisposition):
            initial = chain_context(enemy=enemy)
            before = deepcopy(initial)
            for order in permutations(("brigand:1", "brigand:3", "brigand:4")):
                with self.subTest(enemy=enemy, choices=(first_choice, second_choice), order=order):
                    chain = initial
                    with patch.object(movement, "resolve_give_ground", wraps=movement.resolve_give_ground) as move:
                        for target in order:
                            if target == "brigand:1":
                                result = movement.execute_npc_nearby_give_ground(give_ground_request(chain))
                            else:
                                choice = first_choice if target == "brigand:3" else second_choice
                                result = acknowledge_npc_nearby_defeat(defeat_request(chain, target, choice))
                            old = chain
                            chain = append(chain, result)
                            self.assertIs(result.source_request.continuation, old)
                            self.assertIs(chain.steps[-1], result)
                            self.assertEqual(chain.pending_targets, result.pending_targets)
                            remaining = tuple(t for t in old.pending_targets if t.target_id != target)
                            self.assertEqual(chain.pending_targets, remaining)
                            self.assertTrue(all(a is b for a, b in zip(chain.pending_targets, remaining)))
                    self.assertEqual(move.call_count, 1)
                    self.assertEqual(chain.pending_targets, ())
                    self.assertEqual(chain.spatial_state.gave_ground_entity_ids, ("brigand:1",))
                    self.assertEqual(chain.state.roster.participant("brigand:1").state.injury.conditions.has(Condition.BROKEN), enemy)
                    choices = {a.source_request.decision.target_id: a.source_request.decision.disposition for a in chain.acknowledgements}
                    self.assertEqual(choices, {"brigand:3": first_choice, "brigand:4": second_choice})
                    self.assertEqual(chain.state.consumed_execution_ids, initial.state.consumed_execution_ids)
                    self.assertIs(chain.state.roster.participant("brigand:2"), initial.state.roster.participant("brigand:2"))
                    self.assertEqual(initial, before)

    def test_two_movements_can_surround_acknowledgement_with_continuous_spatial_usage(self):
        initial = chain_context(two_movements=True)
        for order in permutations(("brigand:1", "brigand:3", "brigand:4")):
            with self.subTest(order=order):
                chain = initial
                movers = []
                for target in order:
                    if target == "brigand:4":
                        result = acknowledge_npc_nearby_defeat(defeat_request(chain, target))
                    else:
                        result = movement.execute_npc_nearby_give_ground(give_ground_request(chain, target))
                        movers.append(target)
                    chain = append(chain, result)
                self.assertEqual(chain.spatial_state.gave_ground_entity_ids, tuple(movers))
                self.assertEqual(chain.pending_targets, ())
                self.assertTrue(chain.state.roster.participant(movers[1]).state.injury.conditions.has(Condition.BROKEN))
                self.assertEqual(chain.spatial_state.free_move_used_entity_ids, initial.spatial_state.free_move_used_entity_ids)
                self.assertEqual(chain.spatial_state.difficult_terrain_tested_entity_ids, initial.spatial_state.difficult_terrain_tested_entity_ids)

    def test_chain_rejects_missing_reordered_duplicate_and_foreign_steps_without_reexecution(self):
        initial = chain_context()
        first = acknowledge_npc_nearby_defeat(defeat_request(initial))
        one = append(initial, first)
        second = movement.execute_npc_nearby_give_ground(give_ground_request(one))
        two = append(one, second)
        third = acknowledge_npc_nearby_defeat(defeat_request(two, "brigand:4"))
        final = append(two, third)
        foreign_batch = replace(initial.batch, source_request=replace(initial.batch.source_request, resolution=replace(
            initial.batch.source_request.resolution, id="foreign")), resolution=replace(initial.batch.resolution,
            request_id="foreign", source_request=replace(initial.batch.resolution.source_request, id="foreign")))
        foreign = acknowledge_npc_nearby_defeat(replace(first.source_request, batch=foreign_batch, continuation=None))
        with patch.object(movement, "resolve_give_ground") as move:
            for steps in ((second, third), (first, third), (second, first, third),
                          (first, second, second), (first, second, third, first), (foreign,)):
                with self.subTest(steps=steps), self.assertRaises(ValueError):
                    replace(initial, steps=steps)
            self.assertEqual(replace(initial, steps=final.steps), final)
            move.assert_not_called()

    def test_equal_snapshots_do_not_allow_substitution_of_full_decision_prefix(self):
        initial = chain_context()
        first = acknowledge_npc_nearby_defeat(defeat_request(initial))
        alternative = acknowledge_npc_nearby_defeat(defeat_request(initial, disposition=NpcDefeatDisposition.KILLED))
        one, other = append(initial, first), append(initial, alternative)
        self.assertEqual(one.state, other.state)
        result = movement.execute_npc_nearby_give_ground(give_ground_request(one))
        with self.assertRaisesRegex(ValueError, "exact chain prefix"):
            append(other, result)

    def test_current_snapshots_and_old_chain_are_checked_before_applying_completed_result(self):
        initial = chain_context()
        result = movement.execute_npc_nearby_give_ground(give_ground_request(initial))
        moved = append(initial, result)
        ack = acknowledge_npc_nearby_defeat(defeat_request(moved))
        with (
            patch.object(consequences, "apply_npc_nearby_defeat") as apply_defeat,
            patch.object(consequences, "apply_npc_nearby_give_ground") as apply_move,
        ):
            for current, spatial, chain, step in (
                (moved.state, moved.spatial_state, initial, result),
                (moved.state, initial.spatial_state, moved, ack),
                (initial.state, moved.spatial_state, moved, ack),
                (moved.state, moved.spatial_state, moved, result),
            ):
                with self.subTest(step=step), self.assertRaises(ValueError):
                    consequences.apply_npc_nearby_consequence(current, spatial, chain, step)
            apply_defeat.assert_not_called()
            apply_move.assert_not_called()

    def test_stale_foreign_and_conflicting_continuations_fail_before_movement(self):
        initial = chain_context(two_movements=True)
        first = movement.execute_npc_nearby_give_ground(give_ground_request(initial))
        moved = append(initial, first)
        ack = acknowledge_npc_nearby_defeat(defeat_request(moved, "brigand:4"))
        acknowledged = append(moved, ack)
        source = give_ground_request(acknowledged, "brigand:3")
        for change in ({"continuation": initial}, {"continuation": moved}, {"previous": first},
                       {"spatial_state": initial.spatial_state}, {"current": initial.state},
                       {"continuation": None, "previous": first}):
            with self.subTest(change=change), patch.object(movement, "resolve_give_ground") as move:
                with self.assertRaises(ValueError):
                    movement.execute_npc_nearby_give_ground(replace(source, **change))
                move.assert_not_called()
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(first.source_request, id="new", current=acknowledged.state, continuation=acknowledged)
        with self.assertRaisesRegex(ValueError, "already acknowledged"):
            replace(ack.source_request, id="new", current=acknowledged.state, continuation=acknowledged)
        with self.assertRaisesRegex(ValueError, "exact post-batch"):
            replace(ack.source_request, continuation=None)

    def test_chain_preserves_gm_and_scoped_target_guards_after_movement(self):
        initial = chain_context()
        moved = append(initial, movement.execute_npc_nearby_give_ground(give_ground_request(initial)))
        source = defeat_request(moved)
        for decision in (replace(source.decision, gm_approved=False),
                         replace(source.decision, attacker_id="foreign"),
                         replace(source.decision, target_id="brigand:1")):
            with self.subTest(decision=decision), self.assertRaises(ValueError):
                replace(source, decision=decision)
        bad = replace(give_ground_request(initial), movement=replace(give_ground_request(initial).movement, crosses_obstacle=True))
        before = deepcopy(initial)
        with patch.object(movement, "consume_npc_nearby_give_ground") as consume:
            with self.assertRaises(ValueError):
                movement.execute_npc_nearby_give_ground(bad)
            consume.assert_not_called()
        self.assertEqual(initial, before)

    def test_existing_standalone_results_can_be_registered_but_not_omitted(self):
        source = context(two_movements=True)
        initial = NpcNearbyConsequenceChain(source.batch, source.spatial_state)
        first = movement.execute_npc_nearby_give_ground(source)
        second = movement.execute_npc_nearby_give_ground(movement_request(source.batch, first.state,
            first.spatial_state, "brigand:3", first))
        final = append(append(initial, first), second)
        self.assertEqual(final.pending_targets, ())
        with self.assertRaises(ValueError):
            replace(initial, steps=(second,))
        source = context()
        initial = NpcNearbyConsequenceChain(source.batch, source.spatial_state)
        first = acknowledge_npc_nearby_defeat(acknowledgement(source.batch, target="brigand:3"))
        second = movement.execute_npc_nearby_give_ground(movement_request(source.batch, first.state, source.spatial_state))
        final = append(append(initial, first), second)
        self.assertEqual(final.pending_targets, ())
        self.assertEqual(final.acknowledgements, (first,))

    def test_empty_chain_typed_frozen_source_round_and_side_contracts(self):
        initial = chain_context()
        self.assertEqual(initial.state, initial.batch.state)
        self.assertIs(initial.spatial_state, initial.initial_spatial_state)
        self.assertEqual(initial.pending_targets, initial.batch.pending_targets)
        self.assertEqual(initial.acknowledgements, ())
        self.assertEqual(replace(initial, steps=[]).steps, ())
        with self.assertRaises(FrozenInstanceError):
            initial.steps = ()
        for change in ({"batch": object()}, {"initial_spatial_state": object()}, {"steps": (object(),)}):
            with self.subTest(change=change), self.assertRaises(TypeError):
                replace(initial, **change)
        with self.assertRaises(TypeError):
            replace(defeat_request(initial), continuation=object())
        with self.assertRaises(TypeError):
            replace(give_ground_request(initial), continuation=object())
        with self.assertRaises(ValueError):
            replace(initial, batch=replace(initial.batch, source_request=replace(initial.batch.source_request, primary_attack=None)))
        for spatial in (replace(initial.spatial_state, round_number=99), replace(initial.spatial_state,
            placements=tuple(replace(p, side_id="foreign") for p in initial.spatial_state.placements))):
            with self.subTest(spatial=spatial), self.assertRaises(ValueError):
                replace(initial, initial_spatial_state=spatial)
