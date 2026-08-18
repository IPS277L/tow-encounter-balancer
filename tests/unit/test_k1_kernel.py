from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.attack_models import (
    AttackRequest,
    ConditionImpactSpec,
    DamageImpactSpec,
    DamageProfile,
    HazardImpactSpec,
    ImpactSpec,
    ResilienceProfile,
)
from towr.domain.condition_models import Condition, ConditionState, StaggerChoice
from towr.domain.injury_models import (
    CharacterInjuryState,
    MonstrosityImpactChoice,
    ProfileInjuryState,
    WoundEntryId,
    WoundEnduranceTestRequest,
    WoundNegationOption,
)
from towr.domain.resolution_models import (
    AttackerStaggerRequest,
    ConditionImpactResult,
    ConsumeWoundNegationRequest,
    HazardExposureRequest,
    HazardImpactResult,
    KernelAttackRequest,
    MonstrosityReactionRequest,
    TargetInjuryPolicy,
)
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.rules.kernel import resolve_kernel_attack


class FixedKernelDecisions:
    def __init__(
        self,
        *,
        stagger: StaggerChoice = StaggerChoice.SUFFER_WOUND,
        negation: str | None = None,
        monstrosity: MonstrosityImpactChoice = (
            MonstrosityImpactChoice.SUFFER_WOUND
        ),
    ) -> None:
        self.stagger = stagger
        self.negation = negation
        self.monstrosity = monstrosity

    def choose_glorious_rerolls(
        self,
        *,
        eligible_indices: tuple[int, ...],
        **_: object,
    ) -> tuple[int, ...]:
        return eligible_indices

    def choose_repeated_stagger(self, **_: object) -> StaggerChoice:
        return self.stagger

    def choose_wound_negation(self, **_: object) -> str | None:
        return self.negation

    def choose_monstrosity_impact(self, **_: object) -> MonstrosityImpactChoice:
        return self.monstrosity


def attack(
    *,
    base_damage: int = 3,
    close: bool = True,
    impact_spec: ImpactSpec | None = None,
) -> AttackRequest:
    resolved_impact = impact_spec or DamageImpactSpec(
        DamageProfile(base_damage),
        ResilienceProfile(toughness=4, bonus=1),
    )
    return AttackRequest(
        id="attack",
        attacker_test=TestRequest("attacker", TestProfile(3, 5)),
        defender_test=None,
        impact_spec=resolved_impact,
        is_close_range=close,
        attacker_is_staggered=False,
    )


def kernel_request(
    *,
    policy: TargetInjuryPolicy,
    state: CharacterInjuryState | ProfileInjuryState,
    base_damage: int = 3,
    impact_spec: ImpactSpec | None = None,
    negation_options: tuple[WoundNegationOption, ...] = (),
) -> KernelAttackRequest:
    return KernelAttackRequest(
        id="resolution",
        attack=attack(base_damage=base_damage, impact_spec=impact_spec),
        target_policy=policy,
        target_state=state,
        can_target_leave_zone=True,
        target_has_given_ground_this_round=False,
        wound_negation_options=negation_options,
        monstrosity_reaction_rule_id=(
            "RULE-MONSTER:reaction"
            if policy is TargetInjuryPolicy.MONSTROSITY
            else None
        ),
    )


class K1KernelTests(unittest.TestCase):
    def test_miss_leaves_target_unchanged_and_requests_attacker_stagger(self) -> None:
        state = CharacterInjuryState()

        result = resolve_kernel_attack(
            kernel_request(policy=TargetInjuryPolicy.PLAYER, state=state),
            SequenceRandom([10, 10, 10]),
        )

        self.assertIs(result.target_state, state)
        self.assertEqual(len(result.follow_ups), 1)
        self.assertIsInstance(result.follow_ups[0], AttackerStaggerRequest)

    def test_non_wounding_hit_applies_first_stagger_to_character(self) -> None:
        result = resolve_kernel_attack(
            kernel_request(
                policy=TargetInjuryPolicy.PLAYER,
                state=CharacterInjuryState(),
            ),
            SequenceRandom([1, 10, 10]),
        )

        self.assertIsNotNone(result.stagger)
        self.assertIsInstance(result.target_state, CharacterInjuryState)
        self.assertTrue(result.target_state.conditions.has(Condition.STAGGERED))
        self.assertIsNone(result.character_wound)

    def test_repeated_stagger_can_flow_into_wounds_table(self) -> None:
        state = CharacterInjuryState(
            conditions=ConditionState(frozenset({Condition.STAGGERED}))
        )

        result = resolve_kernel_attack(
            kernel_request(policy=TargetInjuryPolicy.PLAYER, state=state),
            SequenceRandom([1, 10, 10, 4]),
            decisions=FixedKernelDecisions(),
        )

        self.assertIsNotNone(result.stagger)
        self.assertIsNotNone(result.character_wound)
        assert result.character_wound is not None
        self.assertIs(
            result.character_wound.table_roll.entry.id,
            WoundEntryId.NICKED_ARM,
        )
        self.assertFalse(result.target_state.conditions.has(Condition.STAGGERED))
        self.assertEqual(len(result.follow_ups), 1)
        self.assertIsNotNone(result.wound_effect)
        self.assertIsInstance(result.follow_ups[0], WoundEnduranceTestRequest)
        self.assertEqual(
            result.follow_ups[0].test_id,
            "resolution:wound:effect:endurance",
        )

    def test_wound_effect_conditions_are_committed_by_kernel(self) -> None:
        result = resolve_kernel_attack(
            kernel_request(
                policy=TargetInjuryPolicy.PLAYER,
                state=CharacterInjuryState(),
                base_damage=5,
            ),
            SequenceRandom([1, 10, 10, 6]),
        )

        self.assertIsNotNone(result.wound_effect)
        self.assertIsInstance(result.target_state, CharacterInjuryState)
        self.assertTrue(result.target_state.conditions.has(Condition.DRAINED))
        self.assertTrue(result.target_state.wounds[0].effect_resolved)

    def test_condition_impact_replaces_damage_and_updates_target(self) -> None:
        result = resolve_kernel_attack(
            kernel_request(
                policy=TargetInjuryPolicy.PLAYER,
                state=CharacterInjuryState(),
                impact_spec=ConditionImpactSpec(
                    Condition.BURDENED,
                    "RULE-EQUIPMENT:weighted-net",
                ),
            ),
            SequenceRandom([1, 10, 10]),
        )

        self.assertIsInstance(result.replacement_impact, ConditionImpactResult)
        self.assertTrue(result.target_state.conditions.has(Condition.BURDENED))
        self.assertIsNone(result.stagger)
        self.assertIsNone(result.character_wound)
        self.assertIsNone(result.attack.damage)

    def test_stagger_replacement_uses_normal_repeated_stagger_policy(self) -> None:
        result = resolve_kernel_attack(
            kernel_request(
                policy=TargetInjuryPolicy.PLAYER,
                state=CharacterInjuryState(
                    conditions=ConditionState(frozenset({Condition.STAGGERED}))
                ),
                impact_spec=ConditionImpactSpec(
                    Condition.STAGGERED,
                    "RULE-EQUIPMENT:unarmed",
                ),
            ),
            SequenceRandom([1, 10, 10, 1]),
            decisions=FixedKernelDecisions(),
        )

        self.assertIsInstance(result.replacement_impact, ConditionImpactResult)
        self.assertIsNotNone(result.stagger)
        self.assertIsNotNone(result.character_wound)

    def test_hazard_impact_returns_typed_exposure_without_damage(self) -> None:
        state = CharacterInjuryState()
        result = resolve_kernel_attack(
            kernel_request(
                policy=TargetInjuryPolicy.PLAYER,
                state=state,
                impact_spec=HazardImpactSpec(
                    3,
                    Skill.ENDURANCE,
                    "RULE-EFFECT-005:hazard-impact",
                ),
            ),
            SequenceRandom([1, 10, 10]),
        )

        self.assertIs(result.target_state, state)
        self.assertIsInstance(result.replacement_impact, HazardImpactResult)
        self.assertEqual(len(result.follow_ups), 1)
        self.assertIsInstance(result.follow_ups[0], HazardExposureRequest)
        self.assertEqual(result.follow_ups[0].rating, 3)
        self.assertIsNone(result.attack.damage)

    def test_near_miss_preserves_staggered_through_full_attack_flow(self) -> None:
        state = CharacterInjuryState(
            conditions=ConditionState(frozenset({Condition.STAGGERED}))
        )
        near_miss = WoundNegationOption("RULE-FATE:near-miss")

        result = resolve_kernel_attack(
            kernel_request(
                policy=TargetInjuryPolicy.PLAYER,
                state=state,
                base_damage=5,
                negation_options=(near_miss,),
            ),
            SequenceRandom([1, 10, 10, 10]),
            decisions=FixedKernelDecisions(negation=near_miss.rule_id),
        )

        self.assertIsNotNone(result.character_wound)
        assert result.character_wound is not None
        self.assertFalse(result.character_wound.wound_accepted)
        self.assertTrue(result.target_state.conditions.has(Condition.STAGGERED))
        self.assertEqual(len(result.follow_ups), 1)
        self.assertIsInstance(
            result.follow_ups[0],
            ConsumeWoundNegationRequest,
        )

    def test_direct_wound_defeats_minion_and_emits_profile_change(self) -> None:
        result = resolve_kernel_attack(
            kernel_request(
                policy=TargetInjuryPolicy.MINION,
                state=ProfileInjuryState(wounds=0, wound_limit=1),
                base_damage=5,
            ),
            SequenceRandom([1, 10, 10]),
        )

        self.assertIsNotNone(result.profile_wound)
        self.assertIsInstance(result.target_state, ProfileInjuryState)
        self.assertTrue(result.target_state.defeated)
        self.assertEqual(len(result.follow_ups), 1)

    def test_monstrosity_reaction_is_returned_as_typed_follow_up(self) -> None:
        result = resolve_kernel_attack(
            kernel_request(
                policy=TargetInjuryPolicy.MONSTROSITY,
                state=ProfileInjuryState(wounds=0, wound_limit=3),
                base_damage=5,
            ),
            SequenceRandom([1, 10, 10]),
            decisions=FixedKernelDecisions(
                monstrosity=MonstrosityImpactChoice.TRIGGER_REACTION
            ),
        )

        self.assertIsNotNone(result.monstrosity_impact)
        self.assertIsNone(result.profile_wound)
        self.assertEqual(len(result.follow_ups), 1)
        self.assertIsInstance(result.follow_ups[0], MonstrosityReactionRequest)

    def test_monstrosity_wound_choice_flows_into_profile_policy(self) -> None:
        result = resolve_kernel_attack(
            kernel_request(
                policy=TargetInjuryPolicy.MONSTROSITY,
                state=ProfileInjuryState(wounds=0, wound_limit=3),
                base_damage=5,
            ),
            SequenceRandom([1, 10, 10]),
            decisions=FixedKernelDecisions(),
        )

        self.assertIsNotNone(result.monstrosity_impact)
        self.assertIsNotNone(result.profile_wound)
        self.assertIsInstance(result.target_state, ProfileInjuryState)
        self.assertEqual(result.target_state.wounds, 1)


if __name__ == "__main__":
    unittest.main()
