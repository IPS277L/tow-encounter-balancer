"""PG69 alternate Brawn success remains a pending physical consequence."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from towr.domain.attack_models import AttackOutcome, AttackRequest, ProneBeforeGiveGroundSpec
from towr.domain.brawn_impact_models import (
    BrawnAttackEffect, BrawnDisplacementImpactSpec, BrawnDisplacementImpactResult,
    BrawnDisplacementRequest, prepare_brawn_displacement_impact,
)
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.resolution_models import KernelAttackRequest, TargetInjuryPolicy, AttackerStaggerRequest
from towr.domain.test_models import TestProfile, TestRequest
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import (
    WeaponGrip, WeaponItemLocation, WeaponItemSource, initial_weapon_inventory,
)
from towr.domain.weapon_use_models import build_weapon_use
from towr.rules.kernel import resolve_kernel_attack


def request(kind, *, conditions=ConditionState(), profile=False, secondary=(), defenceless=False):
    state = (ProfileInjuryState(0, 3, conditions) if profile else CharacterInjuryState(conditions=conditions))
    attack = AttackRequest('attack', TestRequest('actual-brawn', TestProfile(3, 5)),
        None if defenceless else TestRequest('actual-endurance', TestProfile(2, 4)),
        BrawnDisplacementImpactSpec(kind, 'actor'), True, False, secondary_effects=secondary)
    return KernelAttackRequest('resolution', 'target', attack,
        TargetInjuryPolicy.BRUTE if profile else TargetInjuryPolicy.PLAYER,
        state, False, False, physical_attack=True)


class BrawnDisplacementTests(unittest.TestCase):
    def test_unarmed_source_freezes_actor_without_consuming_held_items_or_requiring_free_hands(self):
        inventory = initial_weapon_inventory('actor', (
            WeaponItemSource('left', WeaponKind.SWORD, WeaponItemLocation.HELD, WeaponGrip.LEFT),
            WeaponItemSource('right', WeaponKind.SWORD, WeaponItemLocation.HELD, WeaponGrip.RIGHT)))
        use = build_weapon_use('actor', inventory, None, usable_hands=())
        for effect in (BrawnAttackEffect.SHOVE, BrawnAttackEffect.DISMOUNT):
            with self.subTest(effect=effect):
                spec = prepare_brawn_displacement_impact(use, effect)
                self.assertIs(spec.kind, effect)
                self.assertEqual(spec.actor_id, 'actor')
                self.assertEqual(use.inventory, inventory)
                self.assertEqual(use.item_ids, ())
        with self.assertRaises(ValueError):
            prepare_brawn_displacement_impact(build_weapon_use('actor', inventory, inventory.items[0].id),
                BrawnAttackEffect.SHOVE)
        knuckles = initial_weapon_inventory('actor', (
            WeaponItemSource('knuckles', WeaponKind.KNUCKLEDUSTERS,
                WeaponItemLocation.HELD, WeaponGrip.LEFT),))
        with self.assertRaises(ValueError):
            prepare_brawn_displacement_impact(build_weapon_use('actor', knuckles, knuckles.items[0].id),
                BrawnAttackEffect.DISMOUNT)

    def test_real_hit_emits_exact_actor_target_source_and_no_damage_stagger_prone_or_wound(self):
        for effect in (BrawnAttackEffect.SHOVE, BrawnAttackEffect.DISMOUNT):
            with self.subTest(effect=effect):
                source = request(effect)
                result = resolve_kernel_attack(source, SequenceRandom([1, 1, 1, 10, 10]))
                self.assertIs(result.attack.outcome, AttackOutcome.HIT)
                self.assertEqual(result.target_state, source.target_state)
                self.assertIsNone(result.attack.damage)
                self.assertIsNone(result.attack.effective_resilience)
                self.assertIsNone(result.stagger)
                self.assertIsNone(result.character_wound)
                self.assertIsNone(result.profile_wound)
                self.assertIsNone(result.pending_character_wound)
                self.assertIs(type(result.replacement_impact), BrawnDisplacementImpactResult)
                pending, = result.follow_ups
                self.assertIs(type(pending), BrawnDisplacementRequest)
                self.assertEqual((pending.resolution_id, pending.attack_id,
                    pending.actor_id, pending.target_id, pending.kind),
                    ('resolution', 'attack', 'actor', 'target', effect))
                self.assertEqual(pending.source, source.attack.impact_spec)
                self.assertEqual(result.replacement_impact.request, pending)

    def test_defenceless_or_already_staggered_does_not_replace_the_alternative_with_a_wound(self):
        conditions = ConditionState({Condition.DEFENCELESS, Condition.STAGGERED})
        for effect in (BrawnAttackEffect.SHOVE, BrawnAttackEffect.DISMOUNT):
            with self.subTest(effect=effect):
                source = request(effect, conditions=conditions, defenceless=True)
                result = resolve_kernel_attack(source, SequenceRandom([1, 1, 1]))
                self.assertEqual(result.target_state, source.target_state)
                self.assertIsNone(result.stagger)
                self.assertIsNone(result.character_wound)
                self.assertEqual(len(result.follow_ups), 1)
                self.assertIs(type(result.follow_ups[0]), BrawnDisplacementRequest)

    def test_miss_preserves_old_close_attacker_stagger_without_moving_target(self):
        for effect in (BrawnAttackEffect.SHOVE, BrawnAttackEffect.DISMOUNT):
            with self.subTest(effect=effect):
                source = request(effect)
                result = resolve_kernel_attack(source, SequenceRandom([10, 10, 10, 1, 1]))
                self.assertIs(result.attack.outcome, AttackOutcome.MISS)
                self.assertEqual(result.target_state, source.target_state)
                self.assertIsNone(result.replacement_impact)
                self.assertEqual(result.follow_ups, (AttackerStaggerRequest('attack'),))
                self.assertIsNone(result.character_wound)

    def test_profile_displacement_leaves_actual_wound_count_limit_and_defeat_unchanged(self):
        for effect in (BrawnAttackEffect.SHOVE, BrawnAttackEffect.DISMOUNT):
            with self.subTest(effect=effect):
                source = request(effect, profile=True)
                result = resolve_kernel_attack(source, SequenceRandom([1, 1, 1, 10, 10]))
                self.assertEqual(result.target_state, ProfileInjuryState(0, 3))
                self.assertIsNone(result.profile_wound)
                self.assertIsNone(result.character_wound)
                self.assertIsNone(result.target_state.defeat_cause)

    def test_separate_real_horse_charge_trait_keeps_its_prone_without_inventing_primary_stagger(self):
        source = request(BrawnAttackEffect.DISMOUNT,
            secondary=(ProneBeforeGiveGroundSpec('actual-mounted-charge'),))
        result = resolve_kernel_attack(source, SequenceRandom([1, 1, 1, 10, 10]))
        self.assertTrue(result.target_state.conditions.has(Condition.PRONE))
        self.assertFalse(result.target_state.conditions.has(Condition.STAGGERED))
        self.assertEqual(result.applied_secondary_rule_ids, ('actual-mounted-charge',))
        self.assertIsNone(result.character_wound)
        self.assertIs(type(result.follow_ups[0]), BrawnDisplacementRequest)

    def test_spec_rejects_untyped_choice_noncanonical_rule_stagger_and_self_target(self):
        spec = BrawnDisplacementImpactSpec(BrawnAttackEffect.SHOVE, 'actor')
        for changes in ({'kind': 'shove'}, {'actor_id': ''}, {'rule_id': 'invented'},
                {'kind': BrawnAttackEffect.STAGGER}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(spec, **changes)
        with self.assertRaises(ValueError):
            BrawnDisplacementRequest('resolution', 'attack', spec, 'actor')
        with self.assertRaises(TypeError):
            BrawnDisplacementImpactResult(spec)

    def test_kernel_rejects_nonphysical_nonclose_or_self_target_displacement(self):
        source = request(BrawnAttackEffect.SHOVE)
        for changes in ({'physical_attack': False}, {'target_id': 'actor'},
                {'attack': replace(source.attack, is_close_range=False)}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(source, **changes)


if __name__ == '__main__':
    unittest.main()
