from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from itertools import product
import unittest
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from tests.unit.test_m2_npc_nearby_stagger import request as secondary_context
from tests.unit.test_m2_npc_roster_attack_execution import change_participant, request as attack_context
from towr.domain.condition_models import Condition
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_nearby_defeat_models import NpcNearbyDefeatAcknowledgementRequest
from towr.domain.npc_nearby_stagger_models import NpcNearbyStaggerExecutionRequest
from towr.domain.npc_roster_attack_models import NpcNearbyDefeatKey
from towr.domain.ranged_weapon_profiles import RangedWeaponId, RangedWeaponRange
from towr.domain.resolution_models import NearbyTargetsStaggerRequest
from towr.rules.npc_nearby_stagger_resolution import execute_npc_nearby_stagger
from towr.rules.npc_nearby_defeat_resolution import acknowledge_npc_nearby_defeat, apply_npc_nearby_defeat
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack
from towr.rules.ranged_weapon_attack_resolution import execute_ranged_weapon_attack


def context():
    source = secondary_context(states=((1, (Condition.STAGGERED, Condition.PRONE)),
                                       (3, (Condition.STAGGERED, Condition.PRONE))))
    base = attack_context(selected="warbow", source=source.state.roster)
    prepared = prepare_ranged_weapon_attack(preparation_request(RangedWeaponId.BLUNDERBUSS,
        attack=base.execution, target_range=RangedWeaponRange.SHORT, lore=True,
        next_cycle="weapon:blunderbuss:hero:1:reload:1"))
    primary = execute_ranged_weapon_attack(prepared.execution, SequenceRandom([1, 2, 10, 10, 10, 10, 10, 10]))
    trigger, = (f for f in primary.attack.resolution.follow_ups if isinstance(f, NearbyTargetsStaggerRequest))
    current = change_participant(source.state, 2, injury=primary.attack.resolution.target_state)
    current = replace(current, consumed_execution_ids=(*current.consumed_execution_ids, primary.attack.request_id))
    source = NpcNearbyStaggerExecutionRequest(current, replace(source.resolution, source=trigger), primary)
    return execute_npc_nearby_stagger(source, Mock())


def acknowledgement(batch, current=None, target="brigand:1", disposition=NpcDefeatDisposition.KNOCKED_OUT):
    return NpcNearbyDefeatAcknowledgementRequest("ack:" + target, current or batch.state, batch,
        MinionDefeatDecision("brigand:0", target, disposition, True))


class M2NpcNearbyDefeatTests(unittest.TestCase):
    def test_prior_acknowledgements_are_preserved_and_cannot_be_dropped(self):
        batch = context()
        source = batch.source_request
        old_source = replace(source.resolution.source, resolution_id="previous:primary")
        old_key = NpcNearbyDefeatKey(old_source, "previous:target")
        state = replace(source.state, consumed_nearby_stagger_sources=(old_source,), acknowledged_nearby_defeats=(old_key,))
        batch = execute_npc_nearby_stagger(replace(source, state=state), Mock())
        first = acknowledge_npc_nearby_defeat(acknowledgement(batch))
        self.assertEqual(first.state.acknowledged_nearby_defeats, (old_key, first.source_request.key))
        second_request = acknowledgement(batch, first.state, "brigand:3")
        second = acknowledge_npc_nearby_defeat(second_request)
        self.assertEqual(second.state.acknowledged_nearby_defeats[:2], first.state.acknowledged_nearby_defeats)
        with self.assertRaisesRegex(ValueError, "exact post-batch"):
            replace(second_request, current=replace(first.state, acknowledged_nearby_defeats=(first.source_request.key,)))

    def test_defeated_flag_without_its_scoped_wound_proof_does_not_authorize_acknowledgement(self):
        batch = context()
        first, second = batch.resolution.targets
        for impact in (replace(first.impact, profile_wound=None),
                       replace(first.impact, follow_ups=()),
                       replace(first.impact, profile_wound=replace(first.impact.profile_wound, wounds_inflicted=0))):
            malformed = replace(batch, resolution=replace(batch.resolution, targets=(replace(first, impact=impact), second)))
            with self.assertRaisesRegex(ValueError, "scoped defeat"):
                acknowledgement(malformed)

    def test_two_equal_defeats_keep_independent_decisions_in_either_acknowledgement_order(self):
        batch = context()
        self.assertEqual(batch.pending_targets[0].impact.follow_ups, batch.pending_targets[1].impact.follow_ups)
        before = deepcopy(batch)
        for reverse, first_choice, second_choice in product((False, True), NpcDefeatDisposition, NpcDefeatDisposition):
            with self.subTest(reverse=reverse, choices=(first_choice, second_choice)):
                targets = ("brigand:3", "brigand:1") if reverse else ("brigand:1", "brigand:3")
                first = acknowledge_npc_nearby_defeat(acknowledgement(batch, target=targets[0], disposition=first_choice))
                state = apply_npc_nearby_defeat(batch.state, first)
                self.assertEqual(tuple(t.target_id for t in first.pending_targets), (targets[1],))
                second = acknowledge_npc_nearby_defeat(acknowledgement(batch, state, targets[1], second_choice))
                updated = apply_npc_nearby_defeat(state, second)
                self.assertEqual(second.pending_targets, ())
                self.assertEqual(tuple(k.target_id for k in updated.acknowledged_nearby_defeats), targets)
                self.assertEqual(replace(updated, acknowledged_nearby_defeats=()), batch.state)
                self.assertIs(first.state.roster, first.source_request.current.roster)
                self.assertIs(second.state.roster, state.roster)
                self.assertEqual((first.source_request.decision.disposition, second.source_request.decision.disposition),
                                 (first_choice, second_choice))
                self.assertIs(second.source_request.batch, batch)
                self.assertEqual(second.applied_rule_ids, ("RULE-NPC-002",))
        self.assertEqual(batch, before)

    def test_decision_requires_actual_attacker_secondary_defeat_and_gm_approval(self):
        source = acknowledgement(context())
        for decision, error in ((replace(source.decision, attacker_id="brigand:3"), "attacker"),
                                 (replace(source.decision, target_id="unknown"), "scoped"),
                                 (replace(source.decision, target_id="brigand:2"), "scoped"),
                                 (replace(source.decision, gm_approved=False), "GM approval")):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                replace(source, decision=decision)

    def test_unbound_batch_cannot_acknowledge_and_invalid_primary_facts_fail_before_batch_execution(self):
        batch = context()
        bound = batch.source_request
        unbound = replace(batch, source_request=replace(bound, primary_attack=None))
        with self.assertRaisesRegex(ValueError, "full primary Attack"):
            acknowledgement(unbound)
        with self.assertRaises(TypeError):
            replace(bound, primary_attack=bound.primary_attack.attack)
        with self.assertRaisesRegex(ValueError, "registered primary"):
            replace(bound, state=replace(bound.state, consumed_execution_ids=("old:attack",)))
        with self.assertRaisesRegex(ValueError, "post-primary"):
            replace(bound, state=change_participant(bound.state, 2, injury=replace(
                bound.state.roster.participant("brigand:2").state.injury, wounds=0, defeated=False)))
        for batch_source in (replace(bound.resolution, source=replace(bound.resolution.source, resolution_id="foreign")),
                             replace(bound.resolution, primary_target_id="brigand:0")):
            with self.assertRaisesRegex(ValueError, "hit/trigger/target"):
                replace(bound, resolution=batch_source)
        missed = execute_ranged_weapon_attack(bound.primary_attack.source_request, SequenceRandom([10] * 8))
        with self.assertRaisesRegex(ValueError, "hit/trigger/target"):
            replace(bound, primary_attack=missed)
        primary = bound.primary_attack
        attack_request = primary.source_request.attack
        wrong_source = replace(primary, source_request=replace(primary.source_request, attack=replace(attack_request,
            kernel_request=replace(attack_request.kernel_request,
                attack=replace(attack_request.kernel_request.attack, secondary_effects=())))))
        with self.assertRaisesRegex(ValueError, "hit/trigger/target"):
            replace(bound, primary_attack=wrong_source)
        expected = attack_request.kernel_request.attack
        for changed in (replace(expected, id="foreign:attack"),
                        replace(expected, attacker_test=replace(expected.attacker_test, id="foreign:test")),
                        replace(expected, defender_test=None),
                        replace(expected, defender_test=replace(expected.defender_test, id="foreign:protection"))):
            wrong_source = replace(primary, source_request=replace(primary.source_request, attack=replace(attack_request,
                kernel_request=replace(attack_request.kernel_request, attack=changed))))
            with self.assertRaisesRegex(ValueError, "primary Attack source"):
                replace(bound, primary_attack=wrong_source)
        with self.assertRaisesRegex(ValueError, "actor/target"):
            replace(bound, state=change_participant(bound.state, 0, side=bound.state.roster.participant("brigand:2").state.side))

    def test_stale_roster_histories_and_foreign_acknowledgement_extensions_are_rejected(self):
        source = acknowledgement(context())
        state = source.current
        for changed in (change_participant(state, 0, holds_shield=not state.roster.participant("brigand:0").state.holds_shield),
                        replace(state, consumed_execution_ids=(*state.consumed_execution_ids, "later")),
                        replace(state, consumed_give_ground_execution_ids=())):
            with self.assertRaisesRegex(ValueError, "exact post-batch"):
                replace(source, current=changed)
        key = NpcNearbyDefeatKey(source.key.source, "brigand:2")
        with self.assertRaisesRegex(ValueError, "another batch/target"):
            replace(source, current=replace(state, acknowledged_nearby_defeats=(key,)))

    def test_replay_rejects_new_ack_batch_impact_ids_and_another_disposition(self):
        source = acknowledgement(context())
        result = acknowledge_npc_nearby_defeat(source)
        updated = apply_npc_nearby_defeat(source.current, result)
        with self.assertRaisesRegex(ValueError, "already acknowledged"):
            apply_npc_nearby_defeat(updated, result)
        with self.assertRaisesRegex(ValueError, "already acknowledged"):
            replace(source, id="another", current=updated, decision=replace(source.decision, disposition=NpcDefeatDisposition.KILLED))
        batch_source = source.batch.source_request
        renamed = replace(batch_source.resolution, id="renamed-batch", targets=tuple(
            replace(t, impact=replace(t.impact, id="renamed:" + t.impact.id)) for t in batch_source.resolution.targets))
        other_batch = execute_npc_nearby_stagger(replace(batch_source, resolution=renamed), Mock())
        with self.assertRaisesRegex(ValueError, "already acknowledged"):
            replace(source, current=updated, batch=other_batch)
        other = acknowledge_npc_nearby_defeat(acknowledgement(source.batch, target="brigand:3"))
        with self.assertRaisesRegex(ValueError, "source differs"):
            apply_npc_nearby_defeat(updated, other)

    def test_keys_are_unique_typed_and_bound_to_consumed_effect_and_objects_are_immutable(self):
        source = acknowledgement(context())
        for invalid in (("bad",),):
            with self.assertRaises(TypeError):
                replace(source.current, acknowledged_nearby_defeats=invalid)
        with self.assertRaises(ValueError):
            replace(source.current, acknowledged_nearby_defeats=(source.key, source.key))
        with self.assertRaises(ValueError):
            replace(source.current, acknowledged_nearby_defeats=(replace(source.key,
                source=replace(source.key.source, resolution_id="unknown")),))
        for changes in ({"current": None}, {"batch": None}, {"decision": None}):
            with self.assertRaises(TypeError):
                replace(source, **changes)
        with self.assertRaises(ValueError):
            replace(source, id="")
        with self.assertRaises(TypeError):
            acknowledge_npc_nearby_defeat(None)
        with self.assertRaises(TypeError):
            apply_npc_nearby_defeat(None, None)
        result = acknowledge_npc_nearby_defeat(source)
        with self.assertRaises(FrozenInstanceError):
            result.source_request = None
