from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.attack_models import (
    AttackOutcome,
    AttackRequest,
    ConditionImpactSpec,
    DamageImpactSpec,
    DamageModifier,
    DamageProfile,
    HazardImpactSpec,
    ImpactSpec,
    ImpactOutcome,
    MissConsequence,
    ResilienceModifier,
    ResilienceProfile,
)
from towr.domain.condition_models import Condition
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.rules.attack_resolution import resolve_attack


def attack_request(
    *,
    defender: bool = True,
    close: bool = True,
    attacker_staggered: bool = False,
    damage: DamageProfile = DamageProfile(4),
    resilience: ResilienceProfile = ResilienceProfile(4, 1),
    ignores_armour: bool = False,
    miss_immunity_rule_id: str | None = None,
    damage_modifiers: tuple[DamageModifier, ...] = (),
    resilience_modifiers: tuple[ResilienceModifier, ...] = (),
    impact_spec: ImpactSpec | None = None,
) -> AttackRequest:
    resolved_impact = impact_spec or DamageImpactSpec(
        damage=damage,
        resilience=resilience,
        ignores_armour=ignores_armour,
        damage_modifiers=damage_modifiers,
        resilience_modifiers=resilience_modifiers,
    )
    return AttackRequest(
        id="attack",
        attacker_test=TestRequest("attacker", TestProfile(3, 5)),
        defender_test=(
            TestRequest("defender", TestProfile(2, 5)) if defender else None
        ),
        impact_spec=resolved_impact,
        is_close_range=close,
        attacker_is_staggered=attacker_staggered,
        close_miss_stagger_immunity_rule_id=miss_immunity_rule_id,
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

    def test_monstrosity_rule_can_suppress_close_melee_miss_stagger(self) -> None:
        result = resolve_attack(
            attack_request(
                defender=False,
                miss_immunity_rule_id="RULE-NPC-005:failed-melee",
            ),
            SequenceRandom([10, 10, 10]),
        )

        self.assertIs(result.miss_consequence, MissConsequence.NONE)
        self.assertEqual(
            result.applied_rule_ids,
            ("RULE-NPC-005:failed-melee",),
        )

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

    def test_condition_impact_replaces_damage_and_resilience(self) -> None:
        spec = ConditionImpactSpec(
            Condition.BURDENED,
            "RULE-EQUIPMENT:weighted-net",
        )

        result = resolve_attack(
            attack_request(defender=False, impact_spec=spec),
            SequenceRandom([1, 10, 10]),
        )

        self.assertIs(result.outcome, AttackOutcome.HIT)
        self.assertIs(result.impact_spec, spec)
        self.assertIsNone(result.damage)
        self.assertIsNone(result.effective_resilience)
        self.assertIsNone(result.impact)
        self.assertEqual(
            result.applied_rule_ids,
            ("RULE-EQUIPMENT:weighted-net",),
        )

    def test_hazard_impact_keeps_rating_and_avoidance_skill(self) -> None:
        spec = HazardImpactSpec(
            3,
            Skill.ENDURANCE,
            "RULE-EFFECT-005:hazard-impact",
        )

        result = resolve_attack(
            attack_request(defender=False, impact_spec=spec),
            SequenceRandom([1, 10, 10]),
        )

        self.assertIs(result.impact_spec, spec)
        self.assertIsNone(result.damage)
        self.assertEqual(
            result.applied_rule_ids,
            ("RULE-EFFECT-005:hazard-impact",),
        )

    def test_hazard_requires_a_failure_consequence(self) -> None:
        with self.assertRaises(ValueError):
            HazardImpactSpec(
                1,
                Skill.ENDURANCE,
                "RULE-INVALID",
                inflicts_wound=False,
            )

    def test_hazard_rating_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            HazardImpactSpec(
                0,
                Skill.ENDURANCE,
                "RULE-INVALID",
            )

    def test_replacement_impact_is_not_applied_on_a_miss(self) -> None:
        result = resolve_attack(
            attack_request(
                defender=False,
                impact_spec=ConditionImpactSpec(
                    Condition.BURDENED,
                    "RULE-EQUIPMENT:weighted-net",
                ),
            ),
            SequenceRandom([10, 10, 10]),
        )

        self.assertIs(result.outcome, AttackOutcome.MISS)
        self.assertNotIn(
            "RULE-EQUIPMENT:weighted-net",
            result.applied_rule_ids,
        )


if __name__ == "__main__":
    unittest.main()
