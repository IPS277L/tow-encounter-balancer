from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock, patch

from tests.unit.test_m2_npc_nearby_consequences import chain_context, append, defeat_request, give_ground_request
from tests.unit.test_m2_npc_nearby_give_ground import context, spatial_context
from towr.domain.condition_models import ConditionState
from towr.domain.npc_nearby_completion_models import NpcNearbyCompletionRequest, NpcNearbyCompletionResult
from towr.domain.npc_nearby_consequence_models import NpcNearbyConsequenceChain
from towr.domain.npc_round_models import NpcRoundRequest, NpcRoundOutcome
from towr.domain.resolution_models import GiveGroundRequest
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules.npc_nearby_completion_resolution import complete_npc_nearby_consequences, apply_npc_nearby_completion
from towr.rules.npc_nearby_defeat_resolution import acknowledge_npc_nearby_defeat
from towr.rules.npc_nearby_give_ground_resolution import execute_npc_nearby_give_ground
from towr.rules.npc_nearby_stagger_resolution import execute_npc_nearby_stagger


def round_context(chain):
    primary = chain.batch.source_request.primary_attack.attack
    return NpcRoundRequest("round", chain.state, primary.state,
        tuple(p.entity_id for p in primary.state.participants), primary.resolution.follow_ups)


def completion_request(chain):
    return NpcNearbyCompletionRequest("complete", round_context(chain), chain.spatial_state, chain)


def finished_chain():
    chain = chain_context(enemy=True)
    chain = append(chain, acknowledge_npc_nearby_defeat(defeat_request(chain)))
    chain = append(chain, execute_npc_nearby_give_ground(give_ground_request(chain)))
    return append(chain, acknowledge_npc_nearby_defeat(defeat_request(chain, "brigand:4")))


def immediate_chain(*, empty=True, old_source=None):
    source = context().batch.source_request
    state = source.state
    participants = tuple(replace(p, state=replace(p.state, injury=replace(p.state.injury, conditions=ConditionState())))
                         if p.state.actor_id in ("brigand:1", "brigand:3") else p for p in state.roster.participants)
    state = replace(state, roster=replace(state.roster, participants=participants))
    if old_source is not None:
        state = replace(state, consumed_nearby_stagger_sources=(old_source,), completed_nearby_stagger_sources=(old_source,))
    targets = () if empty else tuple(replace(t, impact=replace(t.impact,
        target_state=state.roster.participant(t.target_id).state.injury)) for t in source.resolution.targets)
    batch = execute_npc_nearby_stagger(replace(source, state=state, resolution=replace(source.resolution, targets=targets)), Mock())
    return NpcNearbyConsequenceChain(batch, spatial_context(batch))


class M2NpcNearbyCompletionTests(unittest.TestCase):
    def test_mixed_chain_removes_only_its_trigger_preserves_full_sources_and_other_pending(self):
        source = completion_request(finished_chain())
        primary_pending = source.current.pending_follow_ups
        extras = (GiveGroundRequest("earlier"), GiveGroundRequest("later"))
        pending = (extras[0], *primary_pending, extras[1])
        source = replace(source, current=replace(source.current, pending_follow_ups=pending))
        before = deepcopy(source)
        with patch("towr.rules.npc_nearby_give_ground_resolution.resolve_give_ground") as move:
            result = complete_npc_nearby_consequences(source)
            current, spatial = apply_npc_nearby_completion(source.current, source.spatial_state, result)
            move.assert_not_called()
        self.assertEqual(current.pending_follow_ups, tuple(p for p in pending if p != source.source))
        self.assertIs(current.state.roster, source.current.state.roster)
        self.assertIs(current.round_state, source.current.round_state)
        self.assertIs(spatial, source.spatial_state)
        self.assertEqual(replace(current.state, completed_nearby_stagger_sources=()), source.current.state)
        self.assertEqual(current.state.completed_nearby_stagger_sources, (source.source,))
        self.assertIs(result.source_request.chain, source.chain)
        self.assertEqual(len(result.source_request.chain.acknowledgements), 2)
        self.assertEqual(result.applied_rule_ids, (source.source.rule_id,))
        self.assertEqual(source, before)
        candidates, rng = Mock(), Mock()
        stopped = run_npc_round(current, candidates, rng)
        self.assertIs(stopped.outcome, NpcRoundOutcome.PENDING_FOLLOW_UPS)
        self.assertEqual(stopped.pending_follow_ups, current.pending_follow_ups)
        self.assertEqual(stopped.steps, ())
        candidates.get_candidates.assert_not_called()
        rng.randint.assert_not_called()

    def test_partial_chain_is_rejected_until_every_secondary_pending_is_handled(self):
        chain = chain_context()
        for target in ("brigand:3", "brigand:1", "brigand:4"):
            with self.assertRaisesRegex(ValueError, "all secondary pending"):
                completion_request(chain)
            step = (execute_npc_nearby_give_ground(give_ground_request(chain)) if target == "brigand:1"
                    else acknowledge_npc_nearby_defeat(defeat_request(chain, target)))
            chain = append(chain, step)
        result = complete_npc_nearby_consequences(completion_request(chain))
        self.assertEqual(result.source_request.chain.pending_targets, ())

    def test_empty_and_fresh_stagger_batches_complete_without_artificial_steps(self):
        for empty in (False, True):
            with self.subTest(empty=empty):
                chain = immediate_chain(empty=empty)
                self.assertEqual(chain.steps, ())
                self.assertEqual(chain.pending_targets, ())
                self.assertEqual(len(chain.batch.resolution.targets), 0 if empty else 2)
                source = completion_request(chain)
                result = complete_npc_nearby_consequences(source)
                current, _ = apply_npc_nearby_completion(source.current, source.spatial_state, result)
                self.assertNotIn(source.source, current.pending_follow_ups)
                self.assertEqual(current.state.completed_nearby_stagger_sources, (source.source,))

    def test_missing_duplicate_foreign_or_reordered_primary_pending_is_rejected(self):
        source = completion_request(immediate_chain())
        pending, trigger = source.current.pending_follow_ups, source.source
        self.assertGreater(len(pending), 1)
        for items in ((), (trigger,), (*pending, trigger), tuple(reversed(pending)),
                      tuple(replace(p, resolution_id="foreign") if p == trigger else p for p in pending)):
            with self.subTest(items=items), self.assertRaises(ValueError):
                replace(source, current=replace(source.current, pending_follow_ups=items))

    def test_stale_roster_round_and_spatial_cannot_complete_or_apply(self):
        source = completion_request(finished_chain())
        result = complete_npc_nearby_consequences(source)
        roster = source.current.state.roster
        first = roster.participants[0]
        changed = replace(roster, participants=(replace(first, state=replace(first.state, available_attack_ids=())), *roster.participants[1:]))
        currents = (
            replace(source.current, state=replace(source.current.state, roster=changed)),
            replace(source.current, round_state=replace(source.current.round_state, active_turn=None)),
            replace(source.current, state=replace(source.current.state, acknowledged_nearby_defeats=())),
        )
        for current in currents:
            with self.subTest(current=current):
                with self.assertRaisesRegex(ValueError, "exact chain"):
                    replace(source, current=current)
                with self.assertRaisesRegex(ValueError, "source differs"):
                    apply_npc_nearby_completion(current, source.spatial_state, result)
        for spatial in (source.chain.initial_spatial_state, replace(source.spatial_state, round_number=99)):
            with self.subTest(spatial=spatial):
                with self.assertRaisesRegex(ValueError, "exact chain spatial"):
                    replace(source, spatial_state=spatial)
                with self.assertRaisesRegex(ValueError, "source differs"):
                    apply_npc_nearby_completion(source.current, spatial, result)
        with self.assertRaisesRegex(ValueError, "source differs"):
            apply_npc_nearby_completion(replace(source.current, id="different"), source.spatial_state, result)

    def test_replay_with_new_completion_id_requeued_trigger_and_relabelled_batch_fails(self):
        source = completion_request(immediate_chain())
        result = complete_npc_nearby_consequences(source)
        current, spatial = apply_npc_nearby_completion(source.current, source.spatial_state, result)
        original = source.chain.batch.source_request
        batch = execute_npc_nearby_stagger(replace(original, resolution=replace(original.resolution, id="new:batch")), Mock())
        relabelled = NpcNearbyConsequenceChain(batch, spatial)
        for pending in (current.pending_follow_ups, source.current.pending_follow_ups):
            requeued = replace(current, pending_follow_ups=pending)
            with self.assertRaisesRegex(ValueError, "already completed"):
                apply_npc_nearby_completion(requeued, spatial, result)
            for chain in (source.chain, relabelled):
                with self.subTest(chain=chain), self.assertRaisesRegex(ValueError, "already completed"):
                    replace(source, id="new:completion", current=requeued, chain=chain)

    def test_prior_completion_history_is_preserved_and_cannot_be_dropped(self):
        old = replace(immediate_chain().batch.source_request.resolution.source, resolution_id="old:effect")
        source = completion_request(immediate_chain(old_source=old))
        result = complete_npc_nearby_consequences(source)
        current, _ = apply_npc_nearby_completion(source.current, source.spatial_state, result)
        self.assertEqual(current.state.completed_nearby_stagger_sources, (old, source.source))
        with self.assertRaisesRegex(ValueError, "exact chain"):
            replace(source, current=replace(source.current, state=replace(source.current.state, completed_nearby_stagger_sources=())))

    def test_typed_frozen_contracts_and_completion_history_validation(self):
        source = completion_request(immediate_chain())
        with self.assertRaises(FrozenInstanceError):
            source.id = "changed"
        for change in ({"current": object()}, {"chain": object()}, {"spatial_state": object()}):
            with self.subTest(change=change), self.assertRaises(TypeError):
                replace(source, **change)
        with self.assertRaises(ValueError):
            replace(source, id="")
        with self.assertRaises(TypeError):
            NpcNearbyCompletionResult(object())
        with self.assertRaises(TypeError):
            complete_npc_nearby_consequences(object())
        with self.assertRaises(TypeError):
            apply_npc_nearby_completion(source.current, source.spatial_state, object())
        state = replace(source.current.state, completed_nearby_stagger_sources=[source.source])
        self.assertEqual(state.completed_nearby_stagger_sources, (source.source,))
        for entries, error in (((object(),), TypeError), ((source.source, source.source), ValueError),
                               ((replace(source.source, resolution_id="unknown"),), ValueError)):
            with self.subTest(entries=entries), self.assertRaises(error):
                replace(source.current.state, completed_nearby_stagger_sources=entries)
