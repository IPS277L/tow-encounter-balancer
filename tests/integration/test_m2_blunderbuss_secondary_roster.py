from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from tests.unit.test_k1_secondary_target_resolution import TargetDecisions
from tests.unit.test_m2_npc_nearby_stagger import request as secondary_context
from tests.unit.test_m2_npc_roster_attack_execution import change_participant, request as attack_context
from tests.unit.test_m2_npc_nearby_give_ground import movement_request, spatial_context
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.injury_models import ProfileStateChangeRequest
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_nearby_defeat_models import NpcNearbyDefeatAcknowledgementRequest
from towr.domain.npc_nearby_stagger_models import NpcNearbyStaggerExecutionRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponId, RangedWeaponRange
from towr.domain.resolution_models import NearbyTargetsStaggerRequest
from towr.rules import attack_action_execution as attack_executor, npc_nearby_stagger_resolution as nearby
from towr.rules import npc_nearby_give_ground_resolution as give_ground
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack
from towr.rules.ranged_weapon_attack_resolution import execute_ranged_weapon_attack
from towr.rules.npc_nearby_defeat_resolution import acknowledge_npc_nearby_defeat, apply_npc_nearby_defeat


class M2BlunderbussSecondaryRosterTests(unittest.TestCase):
    def test_real_k1_profile_hit_reload_and_two_scoped_secondary_results_share_one_roster(self):
        secondary = secondary_context(states=((1, (Condition.STAGGERED,)),
                                              (3, (Condition.STAGGERED, Condition.PRONE))),
                                      targets=("brigand:3", "brigand:1"))
        base = attack_context(selected="warbow", source=secondary.state.roster)
        # K1 numeric Shooting input; the ordinary M2 executor still rejects secondary effects.
        prepared = prepare_ranged_weapon_attack(preparation_request(RangedWeaponId.BLUNDERBUSS,
            attack=base.execution, target_range=RangedWeaponRange.SHORT, lore=True,
            next_cycle="weapon:blunderbuss:hero:1:reload:1"))
        before = deepcopy((prepared, secondary))
        rng = Mock(wraps=SequenceRandom([1, 2, 10, 10, 10, 10, 10, 10, 7]))
        decisions = TargetDecisions(stagger_choices={"impact:brigand:1:stagger": StaggerChoice.GIVE_GROUND})
        with (
            patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
            patch.object(nearby, "resolve_nearby_targets_stagger", wraps=nearby.resolve_nearby_targets_stagger) as resolve,
        ):
            primary = execute_ranged_weapon_attack(prepared.execution, rng)
            primary_before = deepcopy(primary)
            trigger, = (f for f in primary.attack.resolution.follow_ups if isinstance(f, NearbyTargetsStaggerRequest))
            self.assertTrue(primary.attack.resolution.target_state.defeated)
            # Explicit caller transfer of the K1 primary state, pending and receipt is outside this adapter.
            current = change_participant(secondary.state, 2, injury=primary.attack.resolution.target_state)
            current = replace(current, consumed_execution_ids=(*current.consumed_execution_ids, primary.attack.request_id))
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
            self.assertEqual(kernel.call_count, 1)
            self.assertEqual(resolve.call_count, 1)
            self.assertNotEqual(primary.weapon_state, primary.previous_weapon_state)
            self.assertEqual(rng.randint.call_count, 8)
            self.assertEqual(rng.randint(1, 10), 7)
            self.assertEqual(primary, primary_before)
            self.assertEqual((prepared, secondary), before)
            with self.assertRaisesRegex(ValueError, "already consumed"):
                nearby.apply_npc_nearby_stagger(updated, result)
