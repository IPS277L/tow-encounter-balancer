from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.attack_models import (
    AttackRequest,
    ConditionAfterGiveGroundSpec,
    ConditionImpactSpec,
    DamageImpactSpec,
    DamageProfile,
    NearbyTargetsStaggerSpec,
    ProneBeforeGiveGroundSpec,
    ResilienceProfile,
    ImpactSpec,
    SecondaryEffectSpec,
)
from towr.domain.condition_models import (
    Condition,
    ConditionState,
    StaggerChoice,
)
from towr.domain.injury_models import (
    CharacterInjuryState,
    ProfileInjuryState,
    ProfileStateChangeRequest,
)
from towr.domain.resolution_models import (
    AttackerStaggerRequest,
    ConditionAfterGiveGroundRequest,
    GiveGroundRequest,
    KernelAttackRequest,
    NearbyTargetsStaggerRequest,
    TargetInjuryPolicy,
)
from towr.domain.test_models import TestProfile, TestRequest
from towr.rules.condition_effect_resolution import (
    resolve_condition_after_give_ground,
)
from towr.rules.kernel import resolve_kernel_attack


class GiveGroundDecisions:
    def __init__(
        self,
        choice: StaggerChoice = StaggerChoice.GIVE_GROUND,
    ) -> None:
        self.choice = choice

    def choose_repeated_stagger(self, **_: object) -> StaggerChoice:
        return self.choice


def attack(
    *effects: SecondaryEffectSpec,
    impact_spec: ImpactSpec | None = None,
) -> AttackRequest:
    return AttackRequest(
        id="attack",
        attacker_test=TestRequest("attacker", TestProfile(3, 5)),
        defender_test=None,
        impact_spec=impact_spec
        or DamageImpactSpec(
            DamageProfile(3),
            ResilienceProfile(toughness=4, bonus=1),
        ),
        is_close_range=True,
        attacker_is_staggered=False,
        secondary_effects=effects,
    )


def request(
    *effects: SecondaryEffectSpec,
    policy: TargetInjuryPolicy = TargetInjuryPolicy.PLAYER,
    state: CharacterInjuryState | ProfileInjuryState | None = None,
    impact_spec: ImpactSpec | None = None,
) -> KernelAttackRequest:
    if state is None:
        state = CharacterInjuryState()
    return KernelAttackRequest(
        id="resolution",
        attack=attack(*effects, impact_spec=impact_spec),
        target_policy=policy,
        target_state=state,
        can_target_leave_zone=True,
        target_has_given_ground_this_round=False,
        monstrosity_reaction_rule_id=(
            "RULE-MONSTER:reaction"
            if policy is TargetInjuryPolicy.MONSTROSITY
            else None
        ),
    )


class K1SecondaryEffectTests(unittest.TestCase):
    def test_after_give_ground_condition_cannot_be_staggered(self) -> None:
        with self.assertRaises(ValueError):
            ConditionAfterGiveGroundSpec(
                Condition.STAGGERED,
                "RULE-INVALID",
            )

    def test_secondary_effect_rule_ids_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            attack(
                ProneBeforeGiveGroundSpec("RULE-DUPLICATE"),
                NearbyTargetsStaggerSpec("RULE-DUPLICATE"),
            )

    def test_secondary_effects_do_not_trigger_on_a_miss(self) -> None:
        state = CharacterInjuryState()
        result = resolve_kernel_attack(
            request(
                ProneBeforeGiveGroundSpec("RULE-MOUNT:noble-steed"),
                NearbyTargetsStaggerSpec("RULE-WEAPON:blunderbuss"),
                state=state,
            ),
            SequenceRandom([10, 10, 10]),
        )

        self.assertIs(result.target_state, state)
        self.assertEqual(result.applied_secondary_rule_ids, ())
        self.assertEqual(len(result.follow_ups), 1)
        self.assertIsInstance(result.follow_ups[0], AttackerStaggerRequest)

    def test_prone_is_applied_before_repeated_stagger_choice(self) -> None:
        state = CharacterInjuryState(
            conditions=ConditionState(frozenset({Condition.STAGGERED}))
        )
        effect = ProneBeforeGiveGroundSpec("RULE-MOUNT:noble-steed")

        result = resolve_kernel_attack(
            request(effect, state=state),
            SequenceRandom([1, 10, 10, 4]),
            decisions=GiveGroundDecisions(),
        )

        self.assertIsNotNone(result.stagger)
        assert result.stagger is not None
        self.assertEqual(
            result.stagger.allowed_choices,
            (StaggerChoice.SUFFER_WOUND,),
        )
        self.assertTrue(result.stagger.wound_requested)
        self.assertIsNotNone(result.character_wound)
        self.assertTrue(result.target_state.conditions.has(Condition.PRONE))
        self.assertEqual(
            result.applied_secondary_rule_ids,
            (effect.rule_id,),
        )

    def test_prone_effect_can_exclude_monstrosities(self) -> None:
        effect = ProneBeforeGiveGroundSpec(
            "RULE-MOUNT:noble-steed",
            affects_monstrosities=False,
        )
        result = resolve_kernel_attack(
            request(
                effect,
                policy=TargetInjuryPolicy.MONSTROSITY,
                state=ProfileInjuryState(wounds=0, wound_limit=3),
                impact_spec=ConditionImpactSpec(
                    Condition.BURDENED,
                    "RULE-ATTACK:test-impact",
                ),
            ),
            SequenceRandom([1, 10, 10]),
        )

        self.assertFalse(result.target_state.conditions.has(Condition.PRONE))
        self.assertTrue(result.target_state.conditions.has(Condition.BURDENED))
        self.assertEqual(result.applied_secondary_rule_ids, ())

    def test_nearby_stagger_is_queued_after_primary_target_effects(self) -> None:
        effect = NearbyTargetsStaggerSpec("RULE-WEAPON:blunderbuss")
        result = resolve_kernel_attack(
            request(
                effect,
                policy=TargetInjuryPolicy.MINION,
                state=ProfileInjuryState(wounds=0, wound_limit=1),
                impact_spec=DamageImpactSpec(
                    DamageProfile(5),
                    ResilienceProfile(toughness=4, bonus=1),
                ),
            ),
            SequenceRandom([1, 10, 10]),
        )

        self.assertTrue(result.target_state.defeated)
        self.assertEqual(len(result.follow_ups), 2)
        self.assertIsInstance(result.follow_ups[0], ProfileStateChangeRequest)
        self.assertIsInstance(result.follow_ups[1], NearbyTargetsStaggerRequest)
        self.assertEqual(result.follow_ups[1].rule_id, effect.rule_id)
        self.assertEqual(
            result.applied_secondary_rule_ids,
            (effect.rule_id,),
        )

    def test_condition_is_queued_after_give_ground_movement(self) -> None:
        effect = ConditionAfterGiveGroundSpec(
            Condition.PRONE,
            "RULE-TALENT:troublemakers-out",
        )
        result = resolve_kernel_attack(
            request(
                effect,
                state=CharacterInjuryState(
                    conditions=ConditionState(
                        frozenset({Condition.STAGGERED})
                    )
                ),
            ),
            SequenceRandom([1, 10, 10]),
            decisions=GiveGroundDecisions(),
        )

        self.assertFalse(result.target_state.conditions.has(Condition.PRONE))
        self.assertEqual(len(result.follow_ups), 2)
        self.assertIsInstance(result.follow_ups[0], GiveGroundRequest)
        self.assertIsInstance(
            result.follow_ups[1],
            ConditionAfterGiveGroundRequest,
        )
        condition_request = result.follow_ups[1]
        assert isinstance(condition_request, ConditionAfterGiveGroundRequest)
        applied = resolve_condition_after_give_ground(
            condition_request,
            result.target_state,
        )
        self.assertTrue(applied.state.conditions.has(Condition.PRONE))
        self.assertFalse(applied.was_already_present)
        self.assertEqual(
            result.applied_secondary_rule_ids,
            (effect.rule_id,),
        )

    def test_after_give_ground_effect_does_not_trigger_on_first_stagger(self) -> None:
        effect = ConditionAfterGiveGroundSpec(
            Condition.BROKEN,
            "RULE-NPC:fearsome",
        )
        result = resolve_kernel_attack(
            request(effect),
            SequenceRandom([1, 10, 10]),
        )

        self.assertTrue(result.target_state.conditions.has(Condition.STAGGERED))
        self.assertEqual(result.follow_ups, ())
        self.assertEqual(result.applied_secondary_rule_ids, ())

    def test_after_give_ground_effect_requires_give_ground_choice(self) -> None:
        effect = ConditionAfterGiveGroundSpec(
            Condition.BROKEN,
            "RULE-NPC:fearsome",
        )
        result = resolve_kernel_attack(
            request(
                effect,
                state=CharacterInjuryState(
                    conditions=ConditionState(
                        frozenset({Condition.STAGGERED})
                    )
                ),
            ),
            SequenceRandom([1, 10, 10]),
            decisions=GiveGroundDecisions(StaggerChoice.FALL_PRONE),
        )

        self.assertTrue(result.target_state.conditions.has(Condition.PRONE))
        self.assertEqual(result.follow_ups, ())
        self.assertEqual(result.applied_secondary_rule_ids, ())


if __name__ == "__main__":
    unittest.main()
