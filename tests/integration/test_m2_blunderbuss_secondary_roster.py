from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_secondary_target_resolution import TargetDecisions
from tests.unit.test_m2_npc_nearby_stagger import request as secondary_context
from tests.unit.test_m2_npc_blunderbuss import request as primary_context
from tests.unit.test_m2_npc_nearby_give_ground import movement_request, spatial_context
from tests.unit.test_m2_npc_nearby_consequences import defeat_request, give_ground_request
from tests.unit.test_m2_npc_nearby_completion import completion_request
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.injury_models import ProfileStateChangeRequest
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_blunderbuss_defeat_models import NpcBlunderbussDefeatAcknowledgementRequest
from towr.domain.npc_round_exclusion_models import NpcRoundExclusionRequest
from towr.domain.npc_nearby_defeat_models import NpcNearbyDefeatAcknowledgementRequest
from towr.domain.npc_nearby_consequence_models import NpcNearbyConsequenceChain
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.domain.npc_nearby_stagger_models import NpcNearbyStaggerExecutionRequest
from towr.domain.resolution_models import NearbyTargetsStaggerRequest
from towr.rules import attack_action_execution as attack_executor, npc_nearby_stagger_resolution as nearby
from towr.rules import npc_nearby_give_ground_resolution as give_ground
from towr.rules import npc_nearby_consequence_resolution as consequences
from towr.rules.npc_nearby_completion_resolution import complete_npc_nearby_consequences, apply_npc_nearby_completion
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules.npc_blunderbuss_resolution import execute_npc_blunderbuss_attack, apply_npc_blunderbuss_attack
from towr.rules.npc_nearby_defeat_resolution import acknowledge_npc_nearby_defeat, apply_npc_nearby_defeat
from towr.rules.npc_blunderbuss_defeat_resolution import acknowledge_npc_blunderbuss_defeat, apply_npc_blunderbuss_defeat
from towr.rules.npc_round_exclusion import exclude_defeated_npc, apply_npc_round_exclusion


def primary_request(secondary):
    source = primary_context(roster=secondary.state.roster)
    return replace(source, current=replace(source.current,
        state=replace(secondary.state, roster=source.current.state.roster)))


class M2BlunderbussSecondaryRosterTests(unittest.TestCase):
    def test_primary_executor_empty_secondary_batch_and_completion_keep_one_weapon_transition(self):
        secondary = secondary_context(targets=())
        source = primary_request(secondary)
        rng = Mock(wraps=SequenceRandom([1, 10, 10, 10, 10, 1, 10, 10, 7]))
        with patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel:
            executed = execute_npc_blunderbuss_attack(source, rng)
            current, weapon = apply_npc_blunderbuss_attack(source.current, source.weapon_state, executed)
            trigger, = current.pending_follow_ups
            batch = nearby.execute_npc_nearby_stagger(NpcNearbyStaggerExecutionRequest(
                current.state, replace(secondary.resolution, source=trigger), executed.primary_attack), rng)
            state = nearby.apply_npc_nearby_stagger(current.state, batch)
            chain = NpcNearbyConsequenceChain(batch, spatial_context(batch))
            completion = replace(completion_request(chain), current=replace(current, state=state))
            result = complete_npc_nearby_consequences(completion)
            final, spatial = apply_npc_nearby_completion(completion.current, completion.spatial_state, result)
            self.assertEqual(final.pending_follow_ups, ())
            self.assertEqual(final.state.completed_nearby_stagger_sources, (trigger,))
            self.assertEqual(chain.steps, ())
            self.assertIs(spatial, completion.spatial_state)
            self.assertIs(weapon, executed.primary_attack.weapon_state)
            self.assertFalse(weapon.loaded)
            self.assertEqual(kernel.call_count, 1)
            self.assertEqual(rng.randint.call_count, 8)
            self.assertEqual(rng.randint(1, 10), 7)

    def test_completion_of_fresh_secondary_stagger_resumes_round_without_replaying_primary_attack(self):
        secondary = secondary_context()
        primary_source = primary_request(secondary)
        # A tied successful Attack gives no extra Damage: RES 4 receives Staggered, no primary Wound pending.
        rng = Mock(wraps=SequenceRandom([1, 10, 10, 10, 10, 1, 10, 10, 7]))
        with (
            patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
            patch.object(nearby, "resolve_nearby_targets_stagger", wraps=nearby.resolve_nearby_targets_stagger) as resolve,
            patch.object(give_ground, "resolve_give_ground") as move,
        ):
            executed = execute_npc_blunderbuss_attack(primary_source, rng)
            primary = executed.primary_attack
            current_round, weapon = apply_npc_blunderbuss_attack(primary_source.current, primary_source.weapon_state, executed)
            trigger, = primary.attack.resolution.follow_ups
            self.assertIsInstance(trigger, NearbyTargetsStaggerRequest)
            current = current_round.state
            batch = nearby.execute_npc_nearby_stagger(NpcNearbyStaggerExecutionRequest(
                current, replace(secondary.resolution, source=trigger), primary), rng)
            chain = NpcNearbyConsequenceChain(batch, spatial_context(batch))
            self.assertEqual(chain.pending_targets, ())
            self.assertEqual(chain.steps, ())
            source = completion_request(chain)
            source = replace(source, current=replace(current_round, state=chain.state))
            completed = complete_npc_nearby_consequences(source)
            resumed, spatial = apply_npc_nearby_completion(source.current, source.spatial_state, completed)
            self.assertEqual(resumed.pending_follow_ups, ())
            candidates = Mock()
            candidates.get_candidates.side_effect = lambda context: context
            stopped = run_npc_round(resumed, candidates, rng)
            self.assertIs(stopped.outcome, NpcRoundOutcome.SELECTION_BLOCKED)
            self.assertEqual(stopped.round_state.completed_turn_entity_ids, ("brigand:0",))
            candidates.get_candidates.assert_called_once()
            self.assertEqual(stopped.state.completed_nearby_stagger_sources, (trigger,))
            self.assertEqual(stopped.state.consumed_execution_ids, current.consumed_execution_ids)
            self.assertIs(weapon, primary.weapon_state)
            self.assertFalse(weapon.loaded)
            self.assertIs(spatial, source.spatial_state)
            self.assertEqual(kernel.call_count, 1)
            self.assertEqual(resolve.call_count, 1)
            move.assert_not_called()
            self.assertEqual(rng.randint.call_count, 8)
            self.assertEqual(rng.randint(1, 10), 7)
            with self.assertRaisesRegex(ValueError, "already completed"):
                apply_npc_nearby_completion(replace(resumed, state=stopped.state, round_state=stopped.round_state,
                    pending_follow_ups=source.current.pending_follow_ups), spatial, completed)

    def test_real_k1_profile_hit_reload_and_two_scoped_secondary_results_share_one_roster(self):
        secondary = secondary_context(states=((1, (Condition.STAGGERED,)),
                                              (3, (Condition.STAGGERED, Condition.PRONE))),
                                      targets=("brigand:3", "brigand:1"))
        primary_source = primary_request(secondary)
        before = deepcopy((primary_source, secondary))
        rng = Mock(wraps=SequenceRandom([1, 2, 10, 10, 10, 10, 10, 10, 7]))
        decisions = TargetDecisions(stagger_choices={"impact:brigand:1:stagger": StaggerChoice.GIVE_GROUND})
        with (
            patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
            patch.object(nearby, "resolve_nearby_targets_stagger", wraps=nearby.resolve_nearby_targets_stagger) as resolve,
        ):
            executed = execute_npc_blunderbuss_attack(primary_source, rng)
            primary = executed.primary_attack
            current_round, weapon = apply_npc_blunderbuss_attack(primary_source.current, primary_source.weapon_state, executed)
            primary_before = deepcopy(primary)
            trigger, = (f for f in primary.attack.resolution.follow_ups if isinstance(f, NearbyTargetsStaggerRequest))
            self.assertTrue(primary.attack.resolution.target_state.defeated)
            current = current_round.state
            batch = replace(secondary.resolution, source=trigger, primary_target_id=primary.attack.target_id)
            source = NpcNearbyStaggerExecutionRequest(current, batch, primary)
            result = nearby.execute_npc_nearby_stagger(source, rng, decisions=decisions)
            updated = nearby.apply_npc_nearby_stagger(current, result)
            self.assertEqual(kernel.call_count, 1)
            resolve.assert_called_once_with(batch, rng, decisions=decisions)
            self.assertIs(result.resolution.source_request, batch)
            self.assertEqual(updated.consumed_nearby_stagger_sources, (trigger,))
            self.assertEqual(updated.consumed_execution_ids, current.consumed_execution_ids)
            self.assertIs(updated.roster.participant("brigand:2"), current.roster.participant("brigand:2"))
            self.assertIs(updated.roster.participant("brigand:0"), current.roster.participant("brigand:0"))
            self.assertTrue(updated.roster.participant("brigand:3").state.injury.defeated)
            self.assertEqual(updated.roster.participant("brigand:1"), current.roster.participant("brigand:1"))
            self.assertEqual(tuple(t.target_id for t in result.pending_targets), ("brigand:3", "brigand:1"))
            self.assertIsInstance(result.pending_targets[0].impact.follow_ups[0], ProfileStateChangeRequest)
            self.assertTrue(any(isinstance(f, ProfileStateChangeRequest) for f in primary.attack.resolution.follow_ups))
            for disposition in NpcDefeatDisposition:
                confirmation = acknowledge_npc_nearby_defeat(NpcNearbyDefeatAcknowledgementRequest(
                    "secondary:ack", updated, result, MinionDefeatDecision("brigand:0", "brigand:3", disposition, True)))
                confirmed = apply_npc_nearby_defeat(updated, confirmation)
                self.assertIs(confirmed.roster, updated.roster)
                self.assertEqual(confirmation.pending_targets, (result.pending_targets[1],))
                self.assertIs(confirmation.pending_targets[0], result.pending_targets[1])
                self.assertIs(confirmation.source_request.batch.source_request.primary_attack, primary)
                self.assertIs(confirmation.source_request.decision.disposition, disposition)
                for enemy in (False, True):
                    with self.subTest(disposition=disposition, enemy=enemy):
                        spatial = spatial_context(result, enemy=enemy)
                        movement_source = movement_request(result, confirmed, spatial)
                        before_movement = deepcopy((confirmed, spatial, primary, result))
                        with (
                            patch.object(give_ground, "resolve_give_ground", wraps=give_ground.resolve_give_ground) as move,
                            patch.object(give_ground, "consume_npc_nearby_give_ground", wraps=give_ground.consume_npc_nearby_give_ground) as consume,
                        ):
                            moved = give_ground.execute_npc_nearby_give_ground(movement_source)
                            final, final_spatial = give_ground.apply_npc_nearby_give_ground(confirmed, spatial, moved)
                        move.assert_called_once_with(movement_source.movement)
                        consume.assert_called_once_with(moved.source_request)
                        self.assertEqual(moved.pending_targets, ())
                        self.assertEqual(final.acknowledged_nearby_defeats, confirmed.acknowledged_nearby_defeats)
                        self.assertEqual(final.consumed_nearby_give_ground, (movement_source.key,))
                        self.assertEqual(final_spatial.gave_ground_entity_ids, ("brigand:1",))
                        self.assertEqual(final.roster.participant("brigand:1").state.injury.conditions.has(Condition.BROKEN), enemy)
                        self.assertIs(final.roster.participant("brigand:2"), confirmed.roster.participant("brigand:2"))
                        self.assertIs(final.roster.participant("brigand:3"), confirmed.roster.participant("brigand:3"))
                        self.assertEqual((confirmed, spatial, primary, result), before_movement)
                        with self.assertRaisesRegex(ValueError, "source differs"):
                            give_ground.apply_npc_nearby_give_ground(final, final_spatial, moved)
                        with self.assertRaisesRegex(ValueError, "already consumed"):
                            replace(movement_source, id="another", current=final)
                with self.assertRaisesRegex(ValueError, "scoped"):
                    NpcNearbyDefeatAcknowledgementRequest("not-defeated", updated, result,
                        MinionDefeatDecision("brigand:0", "brigand:1", disposition, True))
            for disposition, enemy, movement_first in product(NpcDefeatDisposition, (False, True), (False, True)):
                with self.subTest(disposition=disposition, enemy=enemy, movement_first=movement_first):
                    chain = NpcNearbyConsequenceChain(result, spatial_context(result, enemy=enemy))
                    original = deepcopy(chain)
                    with (
                        patch.object(give_ground, "resolve_give_ground", wraps=give_ground.resolve_give_ground) as move,
                        patch.object(consequences, "apply_npc_nearby_give_ground", wraps=consequences.apply_npc_nearby_give_ground) as apply_move,
                        patch.object(consequences, "apply_npc_nearby_defeat", wraps=consequences.apply_npc_nearby_defeat) as apply_defeat,
                    ):
                        order = ("move", "defeat") if movement_first else ("defeat", "move")
                        for kind in order:
                            if kind == "move":
                                step = give_ground.execute_npc_nearby_give_ground(give_ground_request(chain))
                            else:
                                step = acknowledge_npc_nearby_defeat(defeat_request(chain, disposition=disposition))
                            previous = chain
                            chain = consequences.apply_npc_nearby_consequence(chain.state, chain.spatial_state, chain, step)
                            self.assertIs(step.source_request.continuation, previous)
                            self.assertEqual(chain.pending_targets, step.pending_targets)
                        self.assertEqual(move.call_count, 1)
                        self.assertEqual(apply_move.call_count, 1)
                        self.assertEqual(apply_defeat.call_count, 1)
                        for step in chain.steps:
                            with self.assertRaises(ValueError):
                                consequences.apply_npc_nearby_consequence(chain.state, chain.spatial_state, chain, step)
                        self.assertEqual(apply_move.call_count, 1)
                        self.assertEqual(apply_defeat.call_count, 1)
                    self.assertEqual(chain.pending_targets, ())
                    self.assertEqual(len(chain.steps), 2)
                    self.assertEqual(chain.acknowledgements[0].source_request.decision.disposition, disposition)
                    self.assertEqual(chain.spatial_state.gave_ground_entity_ids, ("brigand:1",))
                    self.assertEqual(chain.state.roster.participant("brigand:1").state.injury.conditions.has(Condition.BROKEN), enemy)
                    self.assertIs(chain.state.roster.participant("brigand:2"), updated.roster.participant("brigand:2"))
                    self.assertIs(chain.batch.source_request.primary_attack, primary)
                    self.assertEqual(original.steps, ())
                    self.assertEqual(original.state, updated)
                    completion = completion_request(chain)
                    completion = replace(completion, current=replace(current_round, state=chain.state))
                    completed = complete_npc_nearby_consequences(completion)
                    resumed, final_spatial = apply_npc_nearby_completion(completion.current, completion.spatial_state, completed)
                    self.assertEqual(resumed.pending_follow_ups, tuple(f for f in primary.attack.resolution.follow_ups if f != trigger))
                    self.assertTrue(any(isinstance(f, ProfileStateChangeRequest) for f in resumed.pending_follow_ups))
                    self.assertEqual(resumed.state.completed_nearby_stagger_sources, (trigger,))
                    self.assertIs(resumed.state.roster, completion.current.state.roster)
                    self.assertIs(resumed.round_state, primary.attack.state)
                    self.assertIs(final_spatial, completion.spatial_state)
                    self.assertIs(completed.source_request.chain, chain)
                    self.assertEqual(completed.source_request.chain.acknowledgements, chain.acknowledgements)
                    candidates = Mock()
                    stopped = run_npc_round(resumed, candidates, rng)
                    self.assertIs(stopped.outcome, NpcRoundOutcome.PENDING_FOLLOW_UPS)
                    self.assertEqual(stopped.steps, ())
                    candidates.get_candidates.assert_not_called()
                    for primary_disposition in NpcDefeatDisposition:
                        with self.subTest(primary_disposition=primary_disposition):
                            confirmation = acknowledge_npc_blunderbuss_defeat(NpcBlunderbussDefeatAcknowledgementRequest(
                                "primary:ack", resumed, final_spatial, executed, completed,
                                MinionDefeatDecision("brigand:0", "brigand:2", primary_disposition, True)))
                            confirmed, confirmed_spatial = apply_npc_blunderbuss_defeat(resumed, final_spatial, confirmation)
                            self.assertEqual(confirmed.pending_follow_ups, ())
                            self.assertIs(confirmed.state.roster, resumed.state.roster)
                            self.assertIs(confirmed_spatial, final_spatial)
                            self.assertIs(confirmation.weapon_state, weapon)
                            self.assertEqual(confirmed.state.acknowledged_defeat_execution_ids,
                                             (*resumed.state.acknowledged_defeat_execution_ids, primary.attack.request_id))
                            self.assertEqual(confirmed.state.completed_nearby_stagger_sources, (trigger,))
                            self.assertEqual(confirmation.source_request.completion.source_request.chain.acknowledgements,
                                             chain.acknowledgements)
                            for target_id in ("brigand:2", "brigand:3"):
                                exclusion = exclude_defeated_npc(NpcRoundExclusionRequest(
                                    f"exclude:{target_id}", confirmed, target_id))
                                confirmed = apply_npc_round_exclusion(confirmed, exclusion)
                            provider = Mock()
                            provider.get_candidates.side_effect = lambda context: context
                            continued = run_npc_round(confirmed, provider, rng)
                            self.assertIs(continued.outcome, NpcRoundOutcome.SELECTION_BLOCKED)
                            self.assertEqual(continued.round_state.completed_turn_entity_ids, ("brigand:0",))
                            self.assertEqual(continued.round_state.excluded_turn_entity_ids, ("brigand:2", "brigand:3"))
                            self.assertEqual(continued.state, confirmed.state)
                            requeued = replace(confirmed, state=continued.state, round_state=continued.round_state,
                                               pending_follow_ups=resumed.pending_follow_ups)
                            with self.assertRaisesRegex(ValueError, "already acknowledged"):
                                apply_npc_blunderbuss_defeat(requeued, confirmed_spatial, confirmation)
                            with self.assertRaisesRegex(ValueError, "already acknowledged"):
                                replace(confirmation.source_request, id="new:ack", current=requeued)
                    with self.assertRaisesRegex(ValueError, "already completed"):
                        apply_npc_nearby_completion(resumed, final_spatial, completed)
                    with self.assertRaisesRegex(ValueError, "already completed"):
                        replace(completion, id="requeued", current=replace(resumed, pending_follow_ups=completion.current.pending_follow_ups))
            self.assertEqual(kernel.call_count, 1)
            self.assertEqual(resolve.call_count, 1)
            self.assertNotEqual(primary.weapon_state, primary.previous_weapon_state)
            self.assertEqual(rng.randint.call_count, 8)
            self.assertEqual(rng.randint(1, 10), 7)
            self.assertEqual(primary, primary_before)
            self.assertEqual((primary_source, secondary), before)
            self.assertIs(weapon, primary.weapon_state)
            self.assertFalse(weapon.loaded)
            with self.assertRaisesRegex(ValueError, "already consumed"):
                apply_npc_blunderbuss_attack(current_round, weapon, executed)
            with self.assertRaisesRegex(ValueError, "already consumed"):
                nearby.apply_npc_nearby_stagger(updated, result)
