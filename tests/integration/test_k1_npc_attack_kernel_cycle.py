from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_kernel import kernel_request
from tests.unit.test_k1_npc_attack_preparation import protection, request
from tests.unit.test_k1_wound_lifecycle_resolution import near_miss_request
from towr.domain.attack_models import AttackOutcome, ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.resolution_models import AttackerStaggerRequest, TargetInjuryPolicy
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionRequest,
    CharacterWoundLifecycleOutcome,
)
from towr.rules import kernel, wound_lifecycle_resolution as lifecycle
from towr.rules.npc_attack_preparation import (
    prepare_npc_attack, prepare_npc_attack_protection,
)


WEAPONS = (("axe", Range.CLOSE), ("warbow", Range.MEDIUM))
STAGGERED = ConditionState(frozenset({Condition.STAGGERED}))


class K1NpcAttackKernelCycleTests(unittest.TestCase):
    """GM 1.1 Allies and Antagonists pp91–93,97; PG 1.4 Rules pp118–121."""

    def execute(self, weapon, opposed, hit, policy, state):
        selected, distance = weapon
        source = request(
            selected_attack_id=selected, target_range=distance,
            has_enemy_in_close_range=distance is Range.CLOSE,
            target_resilience=ResilienceProfile(2),
        )
        # One attack, optional Protection, and only a character hit rolls a Wound.
        character_hit = hit and isinstance(state, CharacterInjuryState)
        dice = [1 if hit else 10, 10, 10]
        if opposed:
            dice += [10, 10, 10]
        if character_hit:
            dice += [6]  # PG 1.4 Wounds Table p190: Stomach blow, Drained.
        rng = Mock(wraps=SequenceRandom([*dice, 7]))
        npc = prepare_npc_attack(source)
        prepared = prepare_npc_attack_protection(npc, protection(npc, opposed=opposed))
        rng.randint.assert_not_called()
        before = deepcopy((source, prepared, state))
        attack_request = replace(kernel_request(policy=policy, state=state), attack=prepared.attack)
        with (
            patch.object(kernel, "resolve_attack", wraps=kernel.resolve_attack) as attack,
            patch.object(kernel, "roll_character_wound_lifecycle",
                         wraps=kernel.roll_character_wound_lifecycle) as wound,
            patch.object(kernel, "resolve_profile_wound",
                         wraps=kernel.resolve_profile_wound) as profile,
        ):
            result = kernel.resolve_kernel_attack(attack_request, rng)
        attack.assert_called_once_with(prepared.attack, rng, decisions=None)
        self.assertEqual(wound.call_count, int(character_hit))
        self.assertEqual(profile.call_count, int(hit and not character_hit))
        self.assertEqual(rng.randint.call_count, len(dice))
        self.assertEqual((source, prepared, state), before)
        self.assertIs(prepared.npc_attack, npc)
        self.assertIs(prepared.protection.source_request.attack, npc.attack)
        self.assertEqual(attack_request.target_id, prepared.npc_attack.target_id)
        self.assertEqual(result.attack.request_id, prepared.attack.id)
        self.assertEqual(result.attack.attacker_test.trace.request_id, source.attacker_test_id)
        self.assertEqual(result.attack.defender_test is not None, opposed)
        if opposed:
            self.assertEqual(result.attack.defender_test.trace.request_id, "test:target")
        self.assertEqual(result.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
        # Preparation provenance stays with the caller, alongside the kernel result.
        self.assertEqual(prepared.applied_rule_ids, tuple(dict.fromkeys((
            *npc.applied_rule_ids, *prepared.protection.applied_rule_ids,
        ))))
        self.assertIn(npc.selected_profile.source_rule_id, prepared.applied_rule_ids)
        self.assertEqual(result.attack.attacker_test.trace.initial_values, tuple(dice[:3]))
        if opposed:
            self.assertEqual(result.attack.defender_test.trace.initial_values, (10, 10, 10))
        if hit:
            self.assertEqual(result.attack.damage, 4)
            self.assertEqual(result.attack.effective_resilience, 2)
        else:
            self.assertIs(result.target_state, state)
            self.assertIsNone(result.pending_character_wound)
            self.assertIsNone(result.character_wound)
            self.assertIsNone(result.profile_wound)
            self.assertEqual(len(result.follow_ups), int(distance is Range.CLOSE))
            if distance is Range.CLOSE:
                self.assertIsInstance(result.follow_ups[0], AttackerStaggerRequest)
        return result, rng

    def complete(self, result, *, near_miss=False):
        pending = result.pending_character_wound
        self.assertIsNotNone(pending)
        self.assertIsNone(result.wound_effect)
        self.assertFalse(result.target_state.conditions.has(Condition.DRAINED))
        self.assertFalse(result.target_state.conditions.has(Condition.STAGGERED))
        self.assertFalse(result.target_state.wounds[-1].effect_resolved)
        source = CharacterWoundLifecycleCompletionRequest(
            id="complete:npc-attack", roll=pending, current_state=result.target_state,
            daily_wounds=DailyWoundState("day:1", "target"),
            daily_registration_id=None if near_miss else "daily:npc-attack",
            near_miss=(near_miss_request(pending.source_request.wound.id, actor_id="target")
                       if near_miss else None),
        )
        with (
            patch.object(lifecycle, "register_daily_wound",
                         wraps=lifecycle.register_daily_wound) as register,
            patch.object(lifecycle, "resolve_wound_effect",
                         wraps=lifecycle.resolve_wound_effect) as effect,
        ):
            completion = lifecycle.complete_character_wound_lifecycle(source)
            completed = kernel.apply_kernel_character_wound_completion(result, completion)
            self.assertEqual(register.call_count, int(not near_miss))
            self.assertEqual(effect.call_count, int(not near_miss))
            # Carry the returned consumption history; old snapshots are caller-owned.
            with self.assertRaisesRegex(ValueError, "already consumed"):
                lifecycle.complete_character_wound_lifecycle(replace(
                    source, consumed_roll_ids=completion.consumed_roll_ids,
                ))
            with self.assertRaisesRegex(ValueError, "no pending"):
                kernel.apply_kernel_character_wound_completion(completed, completion)
            self.assertEqual(register.call_count, int(not near_miss))
            self.assertEqual(effect.call_count, int(not near_miss))
        self.assertIs(completion.source_request.roll, pending)
        self.assertIs(completion.previous_state, result.target_state)
        self.assertIs(completed.character_wound_completion, completion)
        self.assertIs(completed.attack, result.attack)
        self.assertIsNone(completed.pending_character_wound)
        self.assertEqual(completion.consumed_roll_ids, (pending.request_id,))
        return completed, completion

    def test_player_and_champion_accept_one_pending_wound(self):
        for policy, weapon, opposed, hit in product(
            (TargetInjuryPolicy.PLAYER, TargetInjuryPolicy.CHAMPION), WEAPONS,
            (False, True), (False, True),
        ):
            with self.subTest(policy=policy, weapon=weapon, opposed=opposed, hit=hit):
                state = CharacterInjuryState(conditions=STAGGERED)
                result, rng = self.execute(weapon, opposed, hit, policy, state)
                if hit:
                    completed, completion = self.complete(result)
                    self.assertIs(completion.outcome, CharacterWoundLifecycleOutcome.ACCEPTED)
                    self.assertEqual(completion.daily_wounds.wound_count, 1)
                    self.assertFalse(completion.daily_registration.receipt.wound.effect_resolved)
                    self.assertEqual(len(completed.target_state.wounds), 1)
                    self.assertTrue(completed.target_state.wounds[0].effect_resolved)
                    self.assertTrue(completed.target_state.conditions.has(Condition.DRAINED))
                    self.assertFalse(completed.target_state.conditions.has(Condition.STAGGERED))
                self.assertEqual(rng.randint(1, 10), 7)

    def test_minion_and_brute_apply_profile_injury_without_wound_table(self):
        targets = (
            (TargetInjuryPolicy.MINION, ProfileInjuryState(0, 1, STAGGERED)),
            (TargetInjuryPolicy.BRUTE, ProfileInjuryState(0, 2, STAGGERED)),
            (TargetInjuryPolicy.BRUTE, ProfileInjuryState(1, 2, STAGGERED)),
        )
        for (policy, state), weapon, opposed, hit in product(
            targets, WEAPONS, (False, True), (False, True),
        ):
            with self.subTest(policy=policy, state=state, weapon=weapon, opposed=opposed, hit=hit):
                result, rng = self.execute(weapon, opposed, hit, policy, state)
                self.assertIsNone(result.pending_character_wound)
                self.assertIsNone(result.character_wound)
                self.assertIsNone(result.wound_effect)
                if hit:
                    self.assertEqual(result.target_state.wounds, state.wounds + 1)
                    self.assertEqual(result.target_state.defeated,
                                     state.wounds + 1 == state.wound_limit)
                    self.assertFalse(result.target_state.conditions.has(Condition.STAGGERED))
                    self.assertEqual(result.profile_wound.wounds_inflicted, 1)
                    self.assertEqual(result.follow_ups, (result.profile_wound.state_change,))
                self.assertEqual(rng.randint(1, 10), 7)

    def test_player_near_miss_cancels_rolled_wound_before_effect(self):
        # PG 1.4 Rules / Near Miss p112: retain Staggered, no untreated Wound.
        for weapon, opposed in product(WEAPONS, (False, True)):
            with self.subTest(weapon=weapon, opposed=opposed):
                state = CharacterInjuryState(conditions=STAGGERED)
                result, rng = self.execute(weapon, opposed, True, TargetInjuryPolicy.PLAYER, state)
                completed, completion = self.complete(result, near_miss=True)
                self.assertIs(completion.outcome, CharacterWoundLifecycleOutcome.NEAR_MISS)
                self.assertEqual(completed.target_state, state)
                self.assertIsNone(completed.wound_effect)
                self.assertIsNone(completion.daily_registration)
                self.assertEqual(completion.daily_wounds.wound_count, 0)
                self.assertEqual(completion.fate_burn.state.rating, 0)
                self.assertEqual(len(completion.consumed_near_miss_effect_ids), 1)
                self.assertEqual(rng.randint(1, 10), 7)
