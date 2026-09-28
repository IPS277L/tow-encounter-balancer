from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_k1_secondary_target_resolution import TargetDecisions
from tests.unit.test_m2_npc_blunderbuss_round import request, Candidates
from tests.unit.test_m2_npc_nearby_stagger import request as secondary_request
from tests.unit.test_m2_npc_nearby_consequences import append, defeat_request, give_ground_request
from tests.unit.test_m2_npc_nearby_give_ground import spatial_context
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_blunderbuss_models import NpcBlunderbussAttackExecutionResult
from towr.domain.npc_blunderbuss_defeat_models import NpcBlunderbussDefeatAcknowledgementRequest
from towr.domain.npc_blunderbuss_give_ground_models import NpcBlunderbussGiveGroundExecutionRequest
from towr.domain.npc_nearby_completion_models import NpcNearbyCompletionRequest
from towr.domain.npc_nearby_consequence_models import NpcNearbyConsequenceChain
from towr.domain.npc_nearby_stagger_models import NpcNearbyStaggerExecutionRequest
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.domain.npc_round_exclusion_models import NpcRoundExclusionRequest
from towr.domain.resolution_models import GiveGroundRequest, GiveGroundResolutionRequest, NearbyTargetsStaggerRequest
from towr.domain.spatial_models import SpatialEntityPlacement, ZoneConnection
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules import attack_action_execution as attack_executor
from towr.rules import npc_nearby_stagger_resolution as nearby
from towr.rules import npc_blunderbuss_give_ground_resolution as primary_movement
from towr.rules.npc_blunderbuss_defeat_resolution import acknowledge_npc_blunderbuss_defeat, apply_npc_blunderbuss_defeat
from towr.rules.npc_nearby_defeat_resolution import acknowledge_npc_nearby_defeat
from towr.rules.npc_nearby_give_ground_resolution import execute_npc_nearby_give_ground
from towr.rules.npc_nearby_completion_resolution import complete_npc_nearby_consequences, apply_npc_nearby_completion
from towr.rules.npc_round_exclusion import exclude_defeated_npc, apply_npc_round_exclusion


class M2BlunderbussRoundCycleTests(unittest.TestCase):
    def test_coordinator_primary_secondary_consumers_and_resume_keep_one_weapon_history(self):
        for wound, enemy, disposition, movement_first in product((False, True), (False, True), NpcDefeatDisposition, (False, True)):
            with self.subTest(wound=wound, enemy=enemy, disposition=disposition, movement_first=movement_first):
                secondary = secondary_request(states=((1, (Condition.STAGGERED,)),
                    (2, () if wound else (Condition.STAGGERED,)), (3, (Condition.STAGGERED, Condition.PRONE))))
                initial = request(roster=secondary.state.roster)
                initial = replace(initial, state=replace(secondary.state, roster=initial.state.roster))
                dice = [1, 2, 10, 10, 10, 10, 10, 10] if wound else [1, 10, 10, 10, 10, 1, 10, 10]
                rng = Mock(wraps=SequenceRandom([*dice, 7]))
                with (
                    patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
                    patch.object(nearby, "resolve_nearby_targets_stagger", wraps=nearby.resolve_nearby_targets_stagger) as resolve,
                    patch.object(primary_movement, "resolve_give_ground", wraps=primary_movement.resolve_give_ground) as move,
                ):
                    stopped = run_npc_round(initial, Candidates(), rng, decisions=FixedKernelDecisions(stagger=StaggerChoice.GIVE_GROUND))
                    self.assertIs(stopped.outcome, NpcRoundOutcome.PENDING_FOLLOW_UPS)
                    self.assertEqual(stopped.executed_attack_count, 1)
                    attack, = (step for step in stopped.steps if isinstance(step, NpcBlunderbussAttackExecutionResult))
                    current = stopped.continuation
                    provider = Mock()
                    observation = run_npc_round(current, provider, rng)
                    self.assertEqual(observation.steps, ())
                    provider.get_candidates.assert_not_called()
                    trigger, = (f for f in current.pending_follow_ups if isinstance(f, NearbyTargetsStaggerRequest))
                    batch = nearby.execute_npc_nearby_stagger(NpcNearbyStaggerExecutionRequest(current.state,
                        replace(secondary.resolution, source=trigger), attack.primary_attack), rng,
                        decisions=TargetDecisions(stagger_choices={"impact:brigand:1:stagger": StaggerChoice.GIVE_GROUND}))
                    spatial = spatial_context(batch)
                    spatial = replace(spatial, graph=replace(spatial.graph, zone_ids=(*spatial.graph.zone_ids, "zone:d"),
                        connections=(*spatial.graph.connections, ZoneConnection("zone:b", "zone:d"))),
                        placements=tuple(replace(p, zone_id="zone:b") if p.entity_id == "brigand:2" else p for p in spatial.placements))
                    if enemy:
                        spatial = replace(spatial, placements=(*spatial.placements,
                            SpatialEntityPlacement("extra:enemy", spatial.placement_for("brigand:0").side_id, "zone:d")))
                    chain = NpcNearbyConsequenceChain(batch, spatial)
                    for kind in (("move", "defeat") if movement_first else ("defeat", "move")):
                        step = (execute_npc_nearby_give_ground(give_ground_request(chain)) if kind == "move"
                                else acknowledge_npc_nearby_defeat(defeat_request(chain, disposition=disposition)))
                        chain = append(chain, step)
                    completion = complete_npc_nearby_consequences(NpcNearbyCompletionRequest("complete",
                        replace(current, state=chain.state), chain.spatial_state, chain))
                    current, spatial = apply_npc_nearby_completion(completion.source_request.current, completion.spatial_state, completion)
                    if wound:
                        confirmation = acknowledge_npc_blunderbuss_defeat(NpcBlunderbussDefeatAcknowledgementRequest(
                            "primary:ack", current, spatial, attack, completion,
                            MinionDefeatDecision("brigand:0", "brigand:2", disposition, True)))
                        current, spatial = apply_npc_blunderbuss_defeat(current, spatial, confirmation)
                        defeated = ("brigand:2", "brigand:3")
                    else:
                        follow_up, = (f for f in current.pending_follow_ups if isinstance(f, GiveGroundRequest))
                        movement = GiveGroundResolutionRequest(follow_up, spatial, "brigand:2", "zone:d",
                            current.state.roster.participant("brigand:2").state.injury.conditions, "brigand:0")
                        moved = primary_movement.execute_npc_blunderbuss_give_ground(NpcBlunderbussGiveGroundExecutionRequest(
                            "primary:move", current, spatial, attack, completion, movement))
                        current, spatial = primary_movement.apply_npc_blunderbuss_give_ground(current, spatial, moved)
                        self.assertEqual(current.state.roster.participant("brigand:2").state.injury.conditions.has(Condition.BROKEN), enemy)
                        defeated = ("brigand:3",)
                    self.assertEqual(current.pending_follow_ups, ())
                    self.assertEqual(chain.acknowledgements[0].source_request.decision.disposition, disposition)
                    self.assertEqual(current.weapons, stopped.weapons)
                    self.assertIs(current.weapons[0].weapon_state, attack.weapon_state)
                    for actor in defeated:
                        current = apply_npc_round_exclusion(current, exclude_defeated_npc(NpcRoundExclusionRequest("exclude:" + actor, current, actor)))
                    provider.get_candidates.side_effect = lambda source: source
                    resumed = run_npc_round(current, provider, rng)
                    self.assertEqual(resumed.executed_attack_count, 0)
                    self.assertIs(resumed.outcome, NpcRoundOutcome.SELECTION_BLOCKED)
                    self.assertEqual(resumed.round_state.completed_turn_entity_ids, ("brigand:0",))
                    self.assertEqual(resumed.round_state.excluded_turn_entity_ids, defeated)
                    self.assertEqual(resumed.weapons, stopped.weapons)
                    self.assertFalse(resumed.weapons[0].weapon_state.loaded)
                    self.assertEqual(kernel.call_count, 1)
                    self.assertEqual(resolve.call_count, 1)
                    self.assertEqual(move.call_count, 0 if wound else 1)
                    self.assertEqual(rng.randint.call_count, 8)
                    self.assertEqual(rng.randint(1, 10), 7)
