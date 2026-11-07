"""Weighted Net primary impact, Throwing range and explicit armour identity."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_k1_npc_attack_preparation import request
from tests.unit.test_k1_attack_action_execution import kernel_request
from towr.domain.attack_models import (
    AttackOutcome, ConditionImpactSpec, ConditionOnHitSpec, DamageProfile,
    MissConsequence, ResilienceProfile,
)
from towr.domain.condition_models import Condition, EffectClassification
from towr.domain.npc_attack_preparation_models import (
    NPC_OUTSIDE_OPTIMUM_RULE_ID, NpcAttackProfile, NpcAttackSelectionSnapshot,
)
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_weapon_models import pc_weapon_damage_modifiers
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.test_models import DiceModifier, InlineProfile, Skill
from towr.rules.attack_resolution import resolve_attack
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.npc_attack_preparation import prepare_npc_attack


NET_RULE = 'RULE-EQUIPMENT-005:weighted-net-burdened'


def net():
    # PG1.4 Equipment96; GM1.1 Night Goblins157. Printed base2, BS3 cap6.
    return NpcAttackProfile('weighted_net', 'fixture:weighted_net', Skill.THROWING,
        InlineProfile(2, 3, pool_cap=6), None, Range.CLOSE, Range.SHORT, Hands.TWO_HANDED,
        condition_impact=ConditionImpactSpec(Condition.BURDENED, NET_RULE))


def net_request(**changes):
    profile = net()
    return request(snapshot=NpcAttackSelectionSnapshot('snapshot:net', 'goblin',
        (profile,), (profile.id,)), selected_attack_id=profile.id, **changes)


class M52NetCoreTests(unittest.TestCase):
    def test_net_preparation_preserves_primary_condition_and_printed_pool(self):
        for distance in (Range.CLOSE, Range.SHORT):
            source = net_request(target_range=distance,
                dice_modifiers=(DiceModifier('fixture:bonus', 4),))
            before = deepcopy(source)
            prepared = prepare_npc_attack(source)
            self.assertIs(prepared.attack.impact_spec, source.snapshot.profiles[0].condition_impact)
            self.assertIs(prepared.attack.impact_spec.classification, EffectClassification.UNCLASSIFIED)
            self.assertEqual(prepared.attack.attacker_test.profile, InlineProfile(2, 3, pool_cap=6))
            self.assertEqual(prepared.attack.attacker_test.dice_modifiers, source.dice_modifiers)
            self.assertEqual(prepared.attack.secondary_effects, ())
            self.assertEqual(prepared.applied_rule_ids.count(NET_RULE), 1)
            self.assertNotIn(NPC_OUTSIDE_OPTIMUM_RULE_ID, prepared.applied_rule_ids)
            self.assertEqual(source, before)
            result = resolve_attack(prepared.attack, SequenceRandom([1, 10, 10, 10, 10, 10]))
            self.assertIs(result.outcome, AttackOutcome.HIT)
            self.assertIsNone(result.damage)
            self.assertIsNone(result.effective_resilience)
            self.assertIsNone(result.impact)
            self.assertEqual(result.attacker_test.trace.rolled_dice, 6)

    def test_throwing_never_uses_shooting_extension_or_outside_optimum_penalty(self):
        for distance in (Range.MEDIUM, Range.LONG, Range.EXTREME):
            for approved in (False, True):
                with self.subTest(distance=distance, approved=approved):
                    with self.assertRaises(ValueError):
                        net_request(target_range=distance, range_approved_by_gm=approved)
        for distance in (Range.CLOSE, Range.SHORT):
            with self.assertRaisesRegex(ValueError, 'Throwing'):
                net_request(target_range=distance, range_approved_by_gm=True)
        # Unlike Shooting, an enemy Close does not prohibit an in-range throw.
        prepare_npc_attack(net_request(target_range=Range.SHORT, has_enemy_in_close_range=True))
        short_only = replace(net(), range_min=Range.SHORT)
        source = net_request()
        with self.assertRaisesRegex(ValueError, 'Optimum'):
            replace(source, snapshot=replace(source.snapshot, profiles=(short_only,)))

    def test_condition_hit_updates_kernel_without_stagger_or_wound(self):
        prepared = prepare_npc_attack(net_request())
        source = replace(kernel_request(), target_id='target', attack=prepared.attack)
        result = resolve_kernel_attack(source, SequenceRandom([1, 10]))
        self.assertTrue(result.target_state.conditions.has(Condition.BURDENED))
        self.assertFalse(result.target_state.conditions.has(Condition.STAGGERED))
        self.assertEqual(result.target_state.wounds, ())
        self.assertIsNone(result.character_wound)
        self.assertIsNone(result.stagger)
        self.assertIsNone(result.attack.damage)
        repeated = resolve_kernel_attack(replace(source, target_state=result.target_state), SequenceRandom([1, 10]))
        self.assertEqual(repeated.target_state.conditions, result.target_state.conditions)
        self.assertEqual(repeated.target_state.wounds, ())

    def test_miss_has_no_condition_and_close_miss_staggers_once(self):
        for distance, staggered, expected in (
            (Range.CLOSE, False, MissConsequence.STAGGER_ATTACKER),
            (Range.CLOSE, True, MissConsequence.NONE),
            (Range.SHORT, False, MissConsequence.NONE),
        ):
            prepared = prepare_npc_attack(net_request(target_range=distance, attacker_is_staggered=staggered))
            result = resolve_attack(prepared.attack, SequenceRandom([10, 10]))
            self.assertIs(result.outcome, AttackOutcome.MISS)
            self.assertIs(result.miss_consequence, expected)
            self.assertIsNone(result.damage)
            self.assertNotIn(NET_RULE, result.applied_rule_ids)

    def test_profile_has_exactly_one_primary_impact_and_condition_has_no_damage_traits(self):
        for changes in ({'damage': DamageProfile(0)}, {'condition_impact': None},
            {'condition_impact': 'burdened'}, {'ignores_armour': True},
            {'secondary_effects': (ConditionOnHitSpec(Condition.PRONE, 'fixture:prone'),)},
            {'hands': None}, {'hands': '2h'}):
            with self.subTest(changes=changes):
                with self.assertRaises((TypeError, ValueError)):
                    replace(net(), **changes)
        self.assertIsNone(replace(net(), damage=DamageProfile(3), condition_impact=None).condition_impact)

    def test_prepared_condition_result_is_bound_to_entire_source(self):
        prepared = prepare_npc_attack(net_request())
        changed = replace(net(), condition_impact=ConditionImpactSpec(Condition.PRONE, NET_RULE))
        for changes in ({'selected_profile': changed}, {'applied_rule_ids': ()},
            {'attack': replace(prepared.attack, impact_spec=changed.condition_impact)},
            {'source_request': replace(prepared.source_request,
                snapshot=replace(prepared.snapshot, profiles=(changed,)))}):
            with self.assertRaises(ValueError):
                replace(prepared, **changes)

    def test_explicit_armour_overrides_inference_without_changing_resilience(self):
        for bonus in (0, 2):
            self.assertEqual(ResilienceProfile(3, bonus).is_armoured, bonus > 0)
            for armoured in (False, True):
                profile = ResilienceProfile(3, bonus, armoured=armoured)
                self.assertIs(profile.is_armoured, armoured)
                self.assertEqual(profile.total, 3 + bonus)
        for invalid in (0, 1, 'true', (), []):
            with self.assertRaises(TypeError):
                ResilienceProfile(3, armoured=invalid)
        with self.assertRaises(TypeError):
            ResilienceProfile(3, 0, True)

    def test_armour_weapon_consumers_use_identity_at_zero_bonus(self):
        for weapon in (PcMeleeWeapon.AXE, PcMeleeWeapon.HALBERD, PcMeleeWeapon.GREATAXE):
            self.assertEqual(sum(m.amount for m in pc_weapon_damage_modifiers(
                weapon, ResilienceProfile(3, armoured=True))), 1)
            self.assertEqual(pc_weapon_damage_modifiers(weapon, ResilienceProfile(3)), ())
            self.assertEqual(pc_weapon_damage_modifiers(weapon, ResilienceProfile(3, 2, armoured=False)), ())

    def test_ignores_armour_uses_toughness_even_with_explicit_identity(self):
        source = kernel_request().attack
        for bonus in (0, 2):
            impact = replace(source.impact_spec, resilience=ResilienceProfile(3, bonus, armoured=True))
            for ignores, expected in ((False, 3 + bonus), (True, 3)):
                result = resolve_attack(replace(source, impact_spec=replace(impact, ignores_armour=ignores)),
                    SequenceRandom([1, 10, 10]))
                self.assertEqual(result.effective_resilience, expected)

    def test_crossbow_consumer_uses_explicit_armoured_with_zero_bonus(self):
        from tests.unit.test_k1_ranged_weapon_attack_preparation import base_attack, preparation_request
        from towr.domain.ranged_weapon_profiles import RangedWeaponId
        from towr.domain.ranged_weapon_attack_preparation_models import ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID
        from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack
        for armoured, expected in ((True, 1), (False, 0)):
            source = base_attack()
            impact = replace(source.kernel_request.attack.impact_spec,
                resilience=ResilienceProfile(3, armoured=armoured))
            source = replace(source, kernel_request=replace(source.kernel_request,
                attack=replace(source.kernel_request.attack, impact_spec=impact)))
            prepared = prepare_ranged_weapon_attack(preparation_request(RangedWeaponId.CROSSBOW,
                attack=source, target_range=Range.LONG, next_cycle='weapon:crossbow:hero:1:reload:1'))
            mods = prepared.execution.attack.kernel_request.attack.impact_spec.damage_modifiers
            self.assertEqual(sum(m.amount for m in mods if m.rule_id == ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID), expected)

    def test_other_families_reject_new_source_states_and_preserve_numeric_wire(self):
        from tests.unit.test_m2_npc_ranged_scenario import scenario as ranged
        from tests.unit.test_m6_npc_melee_scenario import scenario as melee
        from tests.unit.test_m7_npc_mixed_scenario import scenario as mixed
        from tests.unit.test_m8_npc_magic_scenario import scenario as magic
        from towr.adapters._ranged_scenario_json import scenario_document as ranged_document
        from towr.adapters._melee_scenario_json import scenario_document as melee_document
        from towr.adapters._mixed_scenario_json import scenario_document as mixed_document
        from towr.adapters._magic_scenario_json import scenario_document as magic_document
        for factory, encode, is_magic in ((ranged, ranged_document, False), (melee, melee_document, False),
                (mixed, mixed_document, False), (magic, magic_document, True)):
            source = factory()
            roster = source.initial.roster if is_magic else source.initial.current.state.roster
            order = tuple(dict.fromkeys(p.definition.id for p in roster.participants))
            baseline = encode(source, order)
            self.assertTrue(all(set(d['resilience']) == {'toughness', 'bonus'} for d in baseline['definitions']))
            for explicit in (True, False):
                forged = deepcopy(source)
                roster = forged.initial.roster if is_magic else forged.initial.current.state.roster
                object.__setattr__(roster.participants[-1].definition.resilience, 'armoured', explicit)
                with self.assertRaisesRegex(ValueError, 'armoured'):
                    replace(forged)
                with self.assertRaisesRegex(ValueError, 'armoured'):
                    encode(forged, order)
            forged = deepcopy(source)
            roster = forged.initial.roster if is_magic else forged.initial.current.state.roster
            attack = roster.participants[-1].definition.attacks[0]
            object.__setattr__(attack, 'damage', None)
            object.__setattr__(attack, 'condition_impact', net().condition_impact)
            with self.assertRaises(ValueError):
                replace(forged)
            with self.assertRaisesRegex(ValueError, 'numeric Damage'):
                encode(forged, order)


if __name__ == '__main__':
    unittest.main()
