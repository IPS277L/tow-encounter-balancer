from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.attack_models import (
    AttackOutcome,
    AttackRequest,
    DamageModifier,
    DamageProfile,
    ImpactOutcome,
    MissConsequence,
    ResilienceModifier,
    ResilienceProfile,
)
from towr.domain.test_models import TestProfile, TestRequest
from towr.rules.attack_resolution import resolve_attack


def attack_request(
    *,
    defender: bool = True,
    close: bool = True,
    attacker_staggered: bool = False,
    damage: DamageProfile = DamageProfile(4),
    resilience: ResilienceProfile = ResilienceProfile(4, 1),
    ignores_armour: bool = False,
    damage_modifiers: tuple[DamageModifier, ...] = (),
    resilience_modifiers: tuple[ResilienceModifier, ...] = (),
) -> AttackRequest:
    return AttackRequest(
        id="attack",
        attacker_test=TestRequest("attacker", TestProfile(3, 5)),
        defender_test=(
            TestRequest("defender", TestProfile(2, 5)) if defender else None
        ),
        damage=damage,
        resilience=resilience,
        is_close_range=close,
        attacker_is_staggered=attacker_staggered,
        ignores_armour=ignores_armour,
        damage_modifiers=damage_modifiers,
        resilience_modifiers=resilience_modifiers,
    )


class K1AttackResolutionTests(unittest.TestCase):
    def test_nonzero_tie_hits_and_uses_base_damage(self) -> None:
        result = resolve_attack(
            attack_request(),
            SequenceRandom([1, 10, 10, 2, 10]),
        )

        self.assertIs(result.outcome, AttackOutcome.HIT)
        self.assertEqual(result.success_margin, 0)
        self.assertEqual(result.damage, 4)
        self.assertEqual(result.effective_resilience, 5)
        self.assertIs(result.impact, ImpactOutcome.STAGGERED)
        self.assertTrue(result.tie_break_applied)
        self.assertIn("RULE-COMBAT-006:attack-tie", result.applied_rule_ids)

    def test_success_margin_is_added_to_damage_and_can_wound(self) -> None:
        result = resolve_attack(
            attack_request(),
            SequenceRandom([1, 2, 3, 1, 10]),
        )

        self.assertEqual(result.success_margin, 2)
        self.assertEqual(result.damage, 6)
        self.assertIs(result.impact, ImpactOutcome.WOUND)

    def test_unopposed_attack_adds_all_attacker_successes(self) -> None:
        result = resolve_attack(
            attack_request(defender=False),
            SequenceRandom([1, 2, 10]),
        )

        self.assertEqual(result.success_margin, 2)
        self.assertEqual(result.damage, 6)
        self.assertIsNone(result.defender_test)

    def test_unopposed_attack_still_needs_one_success(self) -> None:
        result = resolve_attack(
            attack_request(defender=False),
            SequenceRandom([10, 10, 10]),
        )

        self.assertIs(result.outcome, AttackOutcome.MISS)
        self.assertIsNone(result.damage)

    def test_opposed_double_zero_is_a_miss(self) -> None:
        result = resolve_attack(
            attack_request(),
            SequenceRandom([10, 10, 10, 10, 10]),
        )

        self.assertIs(result.outcome, AttackOutcome.MISS)

    def test_close_range_miss_staggers_attacker_only_if_not_already_staggered(self) -> None:
        fresh = resolve_attack(
            attack_request(defender=False),
            SequenceRandom([10, 10, 10]),
        )
        already_staggered = resolve_attack(
            attack_request(defender=False, attacker_staggered=True),
            SequenceRandom([10, 10, 10]),
        )
        ranged = resolve_attack(
            attack_request(defender=False, close=False),
            SequenceRandom([10, 10, 10]),
        )

        self.assertIs(fresh.miss_consequence, MissConsequence.STAGGER_ATTACKER)
        self.assertIs(already_staggered.miss_consequence, MissConsequence.NONE)
        self.assertIs(ranged.miss_consequence, MissConsequence.NONE)

    def test_ignoring_armour_uses_toughness_for_this_attack(self) -> None:
        result = resolve_attack(
            attack_request(ignores_armour=True),
            SequenceRandom([1, 2, 10, 1, 10]),
        )

        self.assertEqual(result.damage, 5)
        self.assertEqual(result.effective_resilience, 4)
        self.assertIs(result.impact, ImpactOutcome.WOUND)

    def test_damage_and_resilience_modifiers_are_traced(self) -> None:
        result = resolve_attack(
            attack_request(
                damage_modifiers=(DamageModifier("RULE-WEAPON", 1),),
                resilience_modifiers=(ResilienceModifier("RULE-SPELL", -1),),
            ),
            SequenceRandom([1, 10, 10, 1, 10]),
        )

        self.assertEqual(result.damage, 5)
        self.assertEqual(result.effective_resilience, 4)
        self.assertEqual(
            result.applied_rule_ids,
            (
                "RULE-WEAPON",
                "RULE-SPELL",
                "RULE-COMBAT-006:attack-tie",
            ),
        )
        self.assertIs(result.impact, ImpactOutcome.WOUND)

    def test_success_multiplier_supports_profile_specific_damage(self) -> None:
        result = resolve_attack(
            attack_request(damage=DamageProfile(base=3, success_multiplier=2)),
            SequenceRandom([1, 2, 3, 1, 10]),
        )

        self.assertEqual(result.success_margin, 2)
        self.assertEqual(result.damage, 7)


if __name__ == "__main__":
    unittest.main()
