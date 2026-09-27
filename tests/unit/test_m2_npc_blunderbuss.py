from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from tests.unit.test_m2_npc_roster_attack_execution import request as base_request
from towr.domain.attack_models import DamageProfile, NearbyTargetsStaggerSpec, AttackOutcome
from towr.domain.condition_models import Condition
from towr.domain.injury_models import AdditionalProfileWound
from towr.domain.npc_blunderbuss_models import NpcBlunderbussAttackExecutionRequest, NpcBlunderbussAttackExecutionResult
from towr.domain.npc_attack_preparation_models import NPC_OUTSIDE_OPTIMUM_RULE_ID
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.npc_roster_attack_models import NpcNearbyDefeatKey, NpcNearbyGiveGroundKey
from towr.domain.ranged_weapon_attack_preparation_models import BLUNDERBUSS_NEARBY_STAGGER_RULE_ID as EFFECT
from towr.domain.ranged_weapon_profiles import RangedWeaponId, RangedWeaponRange
from towr.domain.resolution_models import GiveGroundRequest, NearbyTargetsStaggerRequest
from towr.domain.test_models import DiceModifier, InlineProfile
from towr.rules import npc_blunderbuss_resolution as resolution, attack_action_execution as attack_executor
from towr.rules.protection_preparation import prepare_protection
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack


def request(*, target_range=RangedWeaponRange.SHORT, actor_staggered=False, roster=None):
    base = base_request(selected="warbow", actor_staggered=actor_staggered, source=roster)
    actor = base.state.roster.participant("brigand:0")
    # Explicit scenario equipment/traits; this is not a new canonical Brigand profile.
    profile = replace(actor.definition.attacks[1], id="scenario:blunderbuss", source_rule_id="scenario:gunner",
        damage=DamageProfile(4), range_min=RangedWeaponRange.SHORT, range_max=RangedWeaponRange.SHORT,
        secondary_effects=(NearbyTargetsStaggerSpec(EFFECT),))
    actor = replace(actor, definition=replace(actor.definition, id="scenario:gunner", attacks=(*actor.definition.attacks, profile)),
                    state=replace(actor.state, definition_id="scenario:gunner", available_attack_ids=(*actor.state.available_attack_ids, profile.id)))
    state = replace(base.state, roster=replace(base.state.roster, participants=(actor, *base.state.roster.participants[1:])))
    unprotected = base.preparation.protection.source_request.attack
    unprotected = replace(unprotected, impact_spec=replace(unprotected.impact_spec, damage=DamageProfile(4)))
    protection = prepare_protection(replace(base.preparation.protection.source_request, attack=unprotected))
    execution = replace(base.execution, kernel_request=replace(base.execution.kernel_request, attack=protection.attack))
    prepared = prepare_ranged_weapon_attack(preparation_request(RangedWeaponId.BLUNDERBUSS, attack=execution,
        target_range=target_range, lore=True, next_cycle="weapon:blunderbuss:hero:1:reload:1"))
    current = NpcRoundRequest("round:gunner", state, execution.state,
        tuple(p.entity_id for p in execution.state.participants), ())
    return NpcBlunderbussAttackExecutionRequest("npc:shot", current, prepared.source_request.weapon_state,
        profile.id, protection, prepared)


def change_actor(source, *, profile_changes=None, **state_changes):
    actor, *others = source.current.state.roster.participants
    if profile_changes is not None:
        actor = replace(actor, definition=replace(actor.definition, attacks=tuple(
            replace(p, **profile_changes) if p.id == source.attack_profile_id else p for p in actor.definition.attacks)))
    actor = replace(actor, state=replace(actor.state, **state_changes))
    state = replace(source.current.state, roster=replace(source.current.state.roster, participants=(actor, *others)))
    return replace(source.current, state=state)


class M2NpcBlunderbussTests(unittest.TestCase):
    def test_all_existing_histories_survive_a_new_primary_attack(self):
        source = request()
        old = NearbyTargetsStaggerRequest("older:kernel", EFFECT)
        state = replace(source.current.state, consumed_execution_ids=("older:attack",),
            acknowledged_defeat_execution_ids=("older:attack",), consumed_give_ground_execution_ids=("older:attack",),
            consumed_nearby_stagger_sources=(old,), acknowledged_nearby_defeats=(NpcNearbyDefeatKey(old, "brigand:3"),),
            consumed_nearby_give_ground=(NpcNearbyGiveGroundKey(old, "brigand:1"),), completed_nearby_stagger_sources=(old,))
        source = replace(source, current=replace(source.current, state=state))
        result = resolution.execute_npc_blunderbuss_attack(source, SequenceRandom([10] * 8))
        current, _ = resolution.apply_npc_blunderbuss_attack(source.current, source.weapon_state, result)
        self.assertEqual(replace(current.state, roster=state.roster, consumed_execution_ids=state.consumed_execution_ids), state)
        self.assertEqual(current.state.consumed_execution_ids, ("older:attack", result.primary_attack.attack.request_id))

    def test_unreserved_slot_foreign_protection_and_additional_kernel_effects_fail_before_execution(self):
        source = request()
        baseline = source.preparation.source_request
        empty_round = replace(source.current.round_state, active_turn=replace(source.current.round_state.active_turn, action_slots=()))
        variants = (
            (replace(source.current, round_state=empty_round), replace(baseline.attack, state=empty_round), source.protection),
            (source.current, replace(baseline.attack, slot_index=2), source.protection),
            (source.current, replace(baseline.attack, actor_id="brigand:1"), source.protection),
        )
        for current, attack, protection in variants:
            prepared = prepare_ranged_weapon_attack(replace(baseline, attack=attack))
            with self.subTest(attack=attack), patch.object(resolution, "execute_prepared_ranged_weapon_attack") as execute:
                with self.assertRaisesRegex(ValueError, "reserved unexecuted"):
                    replace(source, current=current, preparation=prepared, protection=protection)
                execute.assert_not_called()
        protection_source = source.protection.source_request
        options = tuple(replace(option, test=replace(option.test, profile=InlineProfile(4, 2))) for option in protection_source.options)
        protection = prepare_protection(replace(protection_source, options=options))
        prepared = prepare_ranged_weapon_attack(replace(baseline, attack=replace(baseline.attack,
            kernel_request=replace(baseline.attack.kernel_request, attack=protection.attack))))
        with self.assertRaisesRegex(ValueError, "Protection Test"):
            replace(source, protection=protection, preparation=prepared)
        prepared = prepare_ranged_weapon_attack(replace(baseline, attack=replace(baseline.attack,
            kernel_request=replace(baseline.attack.kernel_request, additional_profile_wounds=(AdditionalProfileWound("extra"),)))))
        with self.assertRaisesRegex(ValueError, "unsupported effects"):
            replace(source, preparation=prepared)

    def test_hit_and_miss_use_one_kernel_receipt_and_reload_preserving_roster_histories(self):
        for hit in (False, True):
            source = request()
            before = deepcopy(source)
            rng = Mock(wraps=SequenceRandom(([1, 2] if hit else [10, 10]) + [10] * 6 + [7]))
            with (
                patch.object(resolution, "execute_prepared_ranged_weapon_attack", wraps=resolution.execute_prepared_ranged_weapon_attack) as execute,
                patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
            ):
                result = resolution.execute_npc_blunderbuss_attack(source, rng)
                current, weapon = resolution.apply_npc_blunderbuss_attack(source.current, source.weapon_state, result)
            self.assertEqual(execute.call_count, 1)
            self.assertEqual(kernel.call_count, 1)
            self.assertEqual(result.primary_attack.attack.resolution.attack.outcome is AttackOutcome.HIT, hit)
            self.assertEqual(current.state.roster.participant("brigand:2").state.injury.defeated, hit)
            self.assertEqual(any(isinstance(p, NearbyTargetsStaggerRequest) for p in current.pending_follow_ups), hit)
            self.assertIs(current.round_state, result.primary_attack.attack.state)
            self.assertEqual(current.round_state.active_turn.action_slots[0].execution.id, source.preparation.execution.attack.id)
            self.assertEqual(current.state.consumed_execution_ids, (source.preparation.execution.attack.id,))
            self.assertFalse(weapon.loaded)
            self.assertIs(weapon, result.primary_attack.weapon_state)
            for index in (0, 1, 3):
                self.assertIs(current.state.roster.participants[index], source.current.state.roster.participants[index])
            self.assertTrue(set(source.preparation.applied_rule_ids) <= set(result.applied_rule_ids))
            self.assertEqual(rng.randint.call_count, 8)
            self.assertEqual(rng.randint(1, 10), 7)
            self.assertEqual(source, before)

    def test_short_medium_and_staggered_dice_have_no_duplicate_range_adjustment(self):
        for distance, staggered, rolls in ((RangedWeaponRange.SHORT, False, 8),
                                           (RangedWeaponRange.MEDIUM, False, 5),
                                           (RangedWeaponRange.SHORT, True, 8)):
            with self.subTest(distance=distance, staggered=staggered):
                source = request(target_range=distance, actor_staggered=staggered)
                rng = Mock(wraps=SequenceRandom([10] * rolls + [7]))
                result = resolution.execute_npc_blunderbuss_attack(source, rng)
                self.assertEqual(rng.randint.call_count, rolls)
                self.assertEqual(rng.randint(1, 10), 7)
                self.assertEqual(result.continuation.pending_follow_ups, ())
        source = request()
        baseline = source.protection.source_request.attack
        baseline = replace(baseline, attacker_test=replace(baseline.attacker_test,
            dice_modifiers=(DiceModifier(NPC_OUTSIDE_OPTIMUM_RULE_ID, -1),)))
        protection = prepare_protection(replace(source.protection.source_request, attack=baseline))
        base = source.preparation.source_request
        prepared = prepare_ranged_weapon_attack(replace(base, attack=replace(base.attack,
            kernel_request=replace(base.attack.kernel_request, attack=protection.attack))))
        with self.assertRaisesRegex(ValueError, "range modifiers"):
            replace(source, protection=protection, preparation=prepared)

    def test_unavailable_implicit_or_changed_npc_profiles_fail_before_rng(self):
        source = request()
        for current in (change_actor(source, available_attack_ids=()),
                        change_actor(source, profile_changes={"secondary_effects": ()}),
                        change_actor(source, profile_changes={"damage": DamageProfile(5)}),
                        change_actor(source, profile_changes={"test_profile": InlineProfile(4, 3)}),
                        change_actor(source, profile_changes={"range_max": RangedWeaponRange.LONG})):
            with self.subTest(current=current), patch.object(resolution, "execute_prepared_ranged_weapon_attack") as execute:
                with self.assertRaises(ValueError):
                    replace(source, current=current)
                execute.assert_not_called()
        with self.assertRaisesRegex(ValueError, "explicitly declare"):
            replace(source, attack_profile_id="warbow")

    def test_pending_stale_slot_conditions_injury_and_weapon_fail_before_executor(self):
        source = request()
        actor = source.current.state.roster.participants[0]
        for current in (replace(source.current, pending_follow_ups=(GiveGroundRequest("older"),)),
                        replace(source.current, round_state=replace(source.current.round_state, active_turn=None)),
                        change_actor(source, injury=replace(actor.state.injury, conditions=actor.state.injury.conditions.with_condition(Condition.BROKEN))),
                        change_actor(source, injury=replace(actor.state.injury, conditions=actor.state.injury.conditions.with_condition(Condition.DEFENCELESS))),
                        change_actor(source, injury=replace(actor.state.injury, conditions=actor.state.injury.conditions.with_condition(Condition.STAGGERED)))):
            with self.subTest(current=current), patch.object(resolution, "execute_prepared_ranged_weapon_attack") as execute:
                with self.assertRaises(ValueError):
                    replace(source, current=current)
                execute.assert_not_called()
        with self.assertRaisesRegex(ValueError, "current weapon"):
            replace(source, weapon_state=replace(source.weapon_state, weapon_instance_id="other"))
        target = source.current.state.roster.participants[2]
        for changes in ({"holds_shield": True}, {"injury": replace(target.state.injury, wounds=1, defeated=True)}):
            participants = tuple(replace(p, state=replace(p.state, **changes)) if p is target else p
                                 for p in source.current.state.roster.participants)
            with self.assertRaises(ValueError):
                replace(source, current=replace(source.current, state=replace(source.current.state,
                    roster=replace(source.current.state.roster, participants=participants))))

    def test_replay_new_wrapper_id_and_old_weapon_or_round_are_rejected(self):
        source = request()
        result = resolution.execute_npc_blunderbuss_attack(source, SequenceRandom([10] * 8))
        current, weapon = resolution.apply_npc_blunderbuss_attack(source.current, source.weapon_state, result)
        for snapshot in (current, replace(source.current, state=current.state)):
            with self.assertRaisesRegex(ValueError, "already consumed"):
                replace(source, id="another", current=snapshot)
            with self.assertRaisesRegex(ValueError, "already consumed"):
                resolution.apply_npc_blunderbuss_attack(snapshot, source.weapon_state, result)
        with self.assertRaisesRegex(ValueError, "source differs"):
            resolution.apply_npc_blunderbuss_attack(source.current, weapon, result)
        with self.assertRaisesRegex(ValueError, "source differs"):
            resolution.apply_npc_blunderbuss_attack(replace(source.current, id="foreign"), source.weapon_state, result)

    def test_typed_frozen_result_binding_and_existing_weapon_preconditions(self):
        source = request()
        with self.assertRaises(FrozenInstanceError):
            source.id = "other"
        for change in ({"current": object()}, {"weapon_state": object()}, {"preparation": object()}, {"protection": object()}):
            with self.assertRaises(TypeError):
                replace(source, **change)
        with self.assertRaises(TypeError):
            resolution.execute_npc_blunderbuss_attack(object(), Mock())
        result = resolution.execute_npc_blunderbuss_attack(source, SequenceRandom([10] * 8))
        with self.assertRaisesRegex(ValueError, "another prepared"):
            NpcBlunderbussAttackExecutionResult(replace(source, id="other"), result.execution)
        for changes in ({"has_blackpowder_lore": False}, {"has_enemy_in_close_range": True},
                        {"target_range": RangedWeaponRange.LONG}, {"weapon_state": result.weapon_state}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                prepare_ranged_weapon_attack(replace(source.preparation.source_request, **changes))
