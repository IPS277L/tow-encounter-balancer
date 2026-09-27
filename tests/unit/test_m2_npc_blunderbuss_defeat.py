from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_blunderbuss import request as primary_request
from tests.unit.test_m2_npc_nearby_stagger import request as secondary_request
from tests.unit.test_m2_npc_nearby_consequences import append, defeat_request, give_ground_request
from tests.unit.test_m2_npc_nearby_give_ground import spatial_context
from tests.unit.test_k1_secondary_target_resolution import TargetDecisions
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_blunderbuss_defeat_models import (
    NpcBlunderbussDefeatAcknowledgementRequest, NpcBlunderbussDefeatAcknowledgementResult,
)
from towr.domain.npc_nearby_completion_models import NpcNearbyCompletionRequest
from towr.domain.npc_nearby_consequence_models import NpcNearbyConsequenceChain
from towr.domain.npc_nearby_stagger_models import NpcNearbyStaggerExecutionRequest
from towr.domain.resolution_models import GiveGroundRequest, NearbyTargetsStaggerRequest
from towr.rules import npc_blunderbuss_defeat_resolution as resolution
from towr.rules.npc_blunderbuss_resolution import execute_npc_blunderbuss_attack, apply_npc_blunderbuss_attack
from towr.rules.npc_nearby_stagger_resolution import execute_npc_nearby_stagger
from towr.rules.npc_nearby_defeat_resolution import acknowledge_npc_nearby_defeat
from towr.rules.npc_nearby_give_ground_resolution import execute_npc_nearby_give_ground
from towr.rules.npc_nearby_completion_resolution import complete_npc_nearby_consequences, apply_npc_nearby_completion
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack


def context(*, enemy=False, empty=False, secondary_disposition=NpcDefeatDisposition.KNOCKED_OUT,
            extra_pending=(), foreign_primary=False, foreign_history=False, primary_wound=True, missing_wound_proof=False):
    secondary = secondary_request(states=((1, (Condition.STAGGERED,)), (3, (Condition.STAGGERED, Condition.PRONE))),
                                  targets=() if empty else ("brigand:1", "brigand:3"))
    source = primary_request(roster=secondary.state.roster)
    source = replace(source, current=replace(source.current, state=replace(secondary.state, roster=source.current.state.roster)))
    if foreign_primary:
        preparation = source.preparation.source_request
        source = replace(source, preparation=prepare_ranged_weapon_attack(replace(preparation,
            attack=replace(preparation.attack, id="foreign:primary"))))
    dice = [1, 2, 10, 10, 10, 10, 10, 10] if primary_wound else [1, 10, 10, 10, 10, 1, 10, 10]
    attack = execute_npc_blunderbuss_attack(source, SequenceRandom(dice))
    if missing_wound_proof:
        ranged = attack.primary_attack
        ranged = replace(ranged, attack=replace(ranged.attack, resolution=replace(ranged.attack.resolution, profile_wound=None)))
        attack = replace(attack, execution=replace(attack.execution, execution=ranged))
    current, _ = apply_npc_blunderbuss_attack(source.current, source.weapon_state, attack)
    trigger, = (p for p in current.pending_follow_ups if isinstance(p, NearbyTargetsStaggerRequest))
    if foreign_history:
        current = replace(current, state=replace(current.state, consumed_execution_ids=(*current.state.consumed_execution_ids, "foreign:history")))
    batch = execute_npc_nearby_stagger(NpcNearbyStaggerExecutionRequest(current.state,
        replace(secondary.resolution, source=trigger), attack.primary_attack), Mock(),
        decisions=TargetDecisions(stagger_choices={"impact:brigand:1:stagger": StaggerChoice.GIVE_GROUND}))
    chain = NpcNearbyConsequenceChain(batch, spatial_context(batch, enemy=enemy))
    if not empty:
        chain = append(chain, execute_npc_nearby_give_ground(give_ground_request(chain)))
        chain = append(chain, acknowledge_npc_nearby_defeat(defeat_request(chain, disposition=secondary_disposition)))
    pending = (*extra_pending, *current.pending_follow_ups)
    completion = complete_npc_nearby_consequences(NpcNearbyCompletionRequest("complete",
        replace(current, state=chain.state, pending_follow_ups=pending), chain.spatial_state, chain))
    current, spatial = apply_npc_nearby_completion(completion.source_request.current, completion.spatial_state, completion)
    return attack, completion, current, spatial


def acknowledgement(values, disposition=NpcDefeatDisposition.KNOCKED_OUT):
    attack, completion, current, spatial = values
    return NpcBlunderbussDefeatAcknowledgementRequest("primary:ack", current, spatial, attack, completion,
        MinionDefeatDecision("brigand:0", "brigand:2", disposition, True))


class M2NpcBlunderbussDefeatTests(unittest.TestCase):
    def test_independent_primary_secondary_dispositions_keep_equal_follow_ups_scoped(self):
        for enemy, primary_choice, secondary_choice in product((False, True), NpcDefeatDisposition, NpcDefeatDisposition):
            with self.subTest(enemy=enemy, choices=(primary_choice, secondary_choice)):
                source = acknowledgement(context(enemy=enemy, secondary_disposition=secondary_choice,
                    extra_pending=(GiveGroundRequest("other"),)), primary_choice)
                before = deepcopy(source)
                chain = source.completion.source_request.chain
                secondary = next(t for t in chain.batch.pending_targets if t.target_id == "brigand:3")
                self.assertEqual(source.follow_up, secondary.impact.follow_ups[0])
                with patch("towr.rules.npc_blunderbuss_resolution.execute_prepared_ranged_weapon_attack") as execute:
                    result = resolution.acknowledge_npc_blunderbuss_defeat(source)
                    current, spatial = resolution.apply_npc_blunderbuss_defeat(source.current, source.spatial_state, result)
                    execute.assert_not_called()
                self.assertEqual(current.pending_follow_ups, (GiveGroundRequest("other"),))
                self.assertIs(current.state.roster, source.current.state.roster)
                self.assertIs(current.round_state, source.current.round_state)
                self.assertIs(spatial, source.spatial_state)
                self.assertIs(result.weapon_state, source.attack.weapon_state)
                self.assertEqual(current.state.acknowledged_defeat_execution_ids,
                    (*source.current.state.acknowledged_defeat_execution_ids, source.attack.primary_attack.attack.request_id))
                self.assertEqual(replace(current.state, acknowledged_defeat_execution_ids=source.current.state.acknowledged_defeat_execution_ids), source.current.state)
                self.assertIs(result.source_request.completion, source.completion)
                self.assertEqual(chain.acknowledgements[0].source_request.decision.disposition, secondary_choice)
                self.assertEqual(result.source_request.decision.disposition, primary_choice)
                self.assertEqual(result.applied_rule_ids, ("RULE-NPC-002",))
                self.assertEqual(source, before)

    def test_empty_secondary_batch_allows_primary_defeat_without_artificial_secondary_steps(self):
        source = acknowledgement(context(empty=True))
        self.assertEqual(source.completion.source_request.chain.steps, ())
        result = resolution.acknowledge_npc_blunderbuss_defeat(source)
        current, _ = resolution.apply_npc_blunderbuss_defeat(source.current, source.spatial_state, result)
        self.assertEqual(current.pending_follow_ups, ())
        self.assertEqual(current.state.completed_nearby_stagger_sources, source.current.state.completed_nearby_stagger_sources)

    def test_gm_actor_and_primary_target_are_required(self):
        source = acknowledgement(context())
        for change in ({"gm_approved": False}, {"attacker_id": "brigand:1"}, {"target_id": "brigand:3"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(source, decision=replace(source.decision, **change))

    def test_foreign_attack_and_post_primary_history_cannot_use_equal_defeat_notification(self):
        source = acknowledgement(context())
        foreign, _, _, _ = context(foreign_primary=True)
        self.assertEqual(foreign.primary_attack.attack.resolution.follow_ups, source.attack.primary_attack.attack.resolution.follow_ups)
        with self.assertRaisesRegex(ValueError, "another primary"):
            replace(source, attack=foreign)
        with self.assertRaisesRegex(ValueError, "post-primary roster/history"):
            acknowledgement(context(foreign_history=True))
        for current in (replace(source.completion.source_request.current, id="other"),
                        replace(source.completion.source_request.current, actor_order=tuple(reversed(source.current.actor_order)))):
            completion = replace(source.completion, source_request=replace(source.completion.source_request, current=current))
            with self.assertRaisesRegex(ValueError, "request/order"):
                replace(source, completion=completion, current=completion.continuation)

    def test_stale_round_roster_queue_histories_and_spatial_are_rejected(self):
        source = acknowledgement(context(enemy=True))
        result = resolution.acknowledge_npc_blunderbuss_defeat(source)
        currents = (
            source.completion.source_request.current,
            replace(source.current, pending_follow_ups=()),
            replace(source.current, round_state=replace(source.current.round_state, active_turn=None)),
            replace(source.current, state=replace(source.current.state, acknowledged_nearby_defeats=())),
            replace(source.current, state=replace(source.current.state, consumed_nearby_give_ground=())),
        )
        for current in currents:
            with self.subTest(current=current):
                with self.assertRaisesRegex(ValueError, "exact post-completion"):
                    replace(source, current=current)
                with self.assertRaisesRegex(ValueError, "source differs"):
                    resolution.apply_npc_blunderbuss_defeat(current, source.spatial_state, result)
        for spatial in (source.completion.source_request.chain.initial_spatial_state, replace(source.spatial_state, round_number=99)):
            with self.assertRaisesRegex(ValueError, "exact post-completion"):
                replace(source, spatial_state=spatial)
            with self.assertRaisesRegex(ValueError, "source differs"):
                resolution.apply_npc_blunderbuss_defeat(source.current, spatial, result)

    def test_replay_new_ack_id_disposition_and_requeued_primary_defeat_are_rejected(self):
        source = acknowledgement(context())
        result = resolution.acknowledge_npc_blunderbuss_defeat(source)
        current, spatial = resolution.apply_npc_blunderbuss_defeat(source.current, source.spatial_state, result)
        for pending in ((), source.current.pending_follow_ups):
            requeued = replace(current, pending_follow_ups=pending)
            with self.assertRaisesRegex(ValueError, "already acknowledged"):
                resolution.apply_npc_blunderbuss_defeat(requeued, spatial, result)
            with self.assertRaisesRegex(ValueError, "already acknowledged"):
                replace(source, id="new:ack", current=requeued,
                    decision=replace(source.decision, disposition=NpcDefeatDisposition.KILLED))

    def test_actual_wound_proof_and_single_primary_follow_up_are_required(self):
        for values in (context(primary_wound=False), context(missing_wound_proof=True)):
            with self.assertRaisesRegex(ValueError, "new Minion Wound"):
                acknowledgement(values)
        source = acknowledgement(context())
        with self.assertRaisesRegex(ValueError, "exactly one matching"):
            acknowledgement(context(extra_pending=(source.follow_up,)))

    def test_typed_frozen_contracts_do_not_accept_bare_incomplete_sources(self):
        source = acknowledgement(context())
        with self.assertRaises(FrozenInstanceError):
            source.id = "changed"
        for change in ({"current": object()}, {"spatial_state": object()}, {"attack": source.attack.primary_attack},
                       {"completion": source.completion.source_request.chain}, {"decision": object()}):
            with self.subTest(change=change), self.assertRaises(TypeError):
                replace(source, **change)
        with self.assertRaises(ValueError):
            replace(source, id="")
        with self.assertRaises(TypeError):
            NpcBlunderbussDefeatAcknowledgementResult(object())
        with self.assertRaises(TypeError):
            resolution.acknowledge_npc_blunderbuss_defeat(object())
        with self.assertRaises(TypeError):
            resolution.apply_npc_blunderbuss_defeat(source.current, source.spatial_state, object())
