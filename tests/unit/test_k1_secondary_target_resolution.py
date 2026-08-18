from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.attack_models import ConditionAfterGiveGroundSpec
from towr.domain.condition_models import (
    Condition,
    ConditionState,
    StaggerChoice,
)
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundType,
    ProfileInjuryState,
    ProfileStateChangeRequest,
    WoundNegationOption,
)
from towr.domain.resolution_models import (
    ConditionAfterGiveGroundRequest,
    ConsumeWoundNegationRequest,
    GiveGroundRequest,
    IdentifiedStaggerTarget,
    NearbyTargetsStaggerRequest,
    NearbyTargetsStaggerResolutionRequest,
    StaggerImpactRequest,
    TargetInjuryPolicy,
)
from towr.rules.secondary_target_resolution import (
    resolve_nearby_targets_stagger,
)


class TargetDecisions:
    def __init__(
        self,
        *,
        stagger_choices: dict[str, StaggerChoice] | None = None,
        wound_negations: dict[str, str | None] | None = None,
    ) -> None:
        self.stagger_choices = stagger_choices or {}
        self.wound_negations = wound_negations or {}

    def choose_repeated_stagger(
        self,
        *,
        request,
        **_: object,
    ) -> StaggerChoice:
        return self.stagger_choices[request.id]

    def choose_wound_negation(self, *, request, **_: object) -> str | None:
        return self.wound_negations[request.id]


def staggered_prone() -> ConditionState:
    return ConditionState(
        frozenset({Condition.STAGGERED, Condition.PRONE})
    )


def target(
    target_id: str,
    *,
    impact_id: str | None = None,
    policy: TargetInjuryPolicy = TargetInjuryPolicy.PLAYER,
    state=None,
    can_leave_zone: bool = True,
    wound_negation_options: tuple[WoundNegationOption, ...] = (),
    after_give_ground_effects: tuple[ConditionAfterGiveGroundSpec, ...] = (),
) -> IdentifiedStaggerTarget:
    if state is None:
        state = CharacterInjuryState()
    return IdentifiedStaggerTarget(
        target_id=target_id,
        impact=StaggerImpactRequest(
            id=impact_id or f"secondary:{target_id}",
            target_policy=policy,
            target_state=state,
            can_target_leave_zone=can_leave_zone,
            target_has_given_ground_this_round=False,
            wound_negation_options=wound_negation_options,
            after_give_ground_effects=after_give_ground_effects,
        ),
    )


def batch(
    *targets: IdentifiedStaggerTarget,
    primary_target_id: str = "primary",
) -> NearbyTargetsStaggerResolutionRequest:
    return NearbyTargetsStaggerResolutionRequest(
        id="blunderbuss-secondary",
        source=NearbyTargetsStaggerRequest(
            resolution_id="primary-resolution",
            rule_id="RULE-WEAPON:blunderbuss",
        ),
        primary_target_id=primary_target_id,
        targets=targets,
    )


class K1SecondaryTargetResolutionTests(unittest.TestCase):
    def test_targets_must_be_distinct_from_primary_and_each_other(self) -> None:
        with self.assertRaises(ValueError):
            batch(target("primary"))
        with self.assertRaises(ValueError):
            batch(target("same"), target("same", impact_id="other-impact"))
        with self.assertRaises(ValueError):
            batch(target("one", impact_id="same"), target("two", impact_id="same"))

    def test_targets_resolve_left_to_right_with_shared_rng(self) -> None:
        result = resolve_nearby_targets_stagger(
            batch(
                target(
                    "player",
                    state=CharacterInjuryState(conditions=staggered_prone()),
                ),
                target(
                    "champion",
                    policy=TargetInjuryPolicy.CHAMPION,
                    state=CharacterInjuryState(conditions=staggered_prone()),
                ),
            ),
            SequenceRandom([2, 5]),
        )

        self.assertEqual(
            tuple(item.target_id for item in result.targets),
            ("player", "champion"),
        )
        player_wound = result.targets[0].impact.character_wound
        champion_wound = result.targets[1].impact.character_wound
        assert player_wound is not None
        assert champion_wound is not None
        self.assertEqual(player_wound.table_roll.values, (2,))
        self.assertEqual(champion_wound.table_roll.values, (5,))
        self.assertIs(player_wound.subject_type, CharacterWoundType.PLAYER)
        self.assertIs(champion_wound.subject_type, CharacterWoundType.CHAMPION)
        self.assertEqual(
            result.applied_rule_ids,
            ("RULE-WEAPON:blunderbuss",),
        )

    def test_each_target_uses_its_own_stagger_context_and_decision(self) -> None:
        first = target("first")
        second = target(
            "second",
            state=CharacterInjuryState(
                conditions=ConditionState(frozenset({Condition.STAGGERED}))
            ),
        )
        result = resolve_nearby_targets_stagger(
            batch(first, second),
            SequenceRandom([]),
            decisions=TargetDecisions(
                stagger_choices={
                    "secondary:second:stagger": StaggerChoice.GIVE_GROUND,
                }
            ),
        )

        self.assertTrue(
            result.targets[0].impact.state.conditions.has(Condition.STAGGERED)
        )
        self.assertEqual(result.targets[0].impact.follow_ups, ())
        self.assertTrue(result.targets[1].impact.stagger.gave_ground)
        self.assertIsInstance(
            result.targets[1].impact.follow_ups[0],
            GiveGroundRequest,
        )

    def test_profile_npcs_use_profile_wound_policy(self) -> None:
        cases = (
            (TargetInjuryPolicy.MINION, 1),
            (TargetInjuryPolicy.BRUTE, 3),
            (TargetInjuryPolicy.MONSTROSITY, 3),
        )
        for policy, wound_limit in cases:
            with self.subTest(policy=policy):
                result = resolve_nearby_targets_stagger(
                    batch(
                        target(
                            policy.value,
                            policy=policy,
                            state=ProfileInjuryState(
                                wounds=0,
                                wound_limit=wound_limit,
                                conditions=staggered_prone(),
                            ),
                        )
                    ),
                    SequenceRandom([]),
                )

                impact = result.targets[0].impact
                self.assertIsNotNone(impact.profile_wound)
                self.assertEqual(impact.state.wounds, 1)
                self.assertIsInstance(
                    impact.follow_ups[0],
                    ProfileStateChangeRequest,
                )

    def test_near_miss_preserves_secondary_target_staggered(self) -> None:
        near_miss = WoundNegationOption("RULE-FATE:near-miss")
        secondary = target(
            "player",
            state=CharacterInjuryState(conditions=staggered_prone()),
            wound_negation_options=(near_miss,),
        )
        result = resolve_nearby_targets_stagger(
            batch(secondary),
            SequenceRandom([9]),
            decisions=TargetDecisions(
                wound_negations={"secondary:player:wound": near_miss.rule_id}
            ),
        )

        impact = result.targets[0].impact
        assert impact.character_wound is not None
        self.assertFalse(impact.character_wound.wound_accepted)
        self.assertTrue(impact.state.conditions.has(Condition.STAGGERED))
        self.assertTrue(impact.state.conditions.has(Condition.PRONE))
        self.assertIsInstance(impact.follow_ups[0], ConsumeWoundNegationRequest)

    def test_secondary_target_can_emit_after_give_ground_condition(self) -> None:
        effect = ConditionAfterGiveGroundSpec(
            Condition.BROKEN,
            "RULE-NPC:fearsome",
        )
        secondary = target(
            "secondary",
            state=CharacterInjuryState(
                conditions=ConditionState(frozenset({Condition.STAGGERED}))
            ),
            after_give_ground_effects=(effect,),
        )
        result = resolve_nearby_targets_stagger(
            batch(secondary),
            SequenceRandom([]),
            decisions=TargetDecisions(
                stagger_choices={
                    "secondary:secondary:stagger": StaggerChoice.GIVE_GROUND,
                }
            ),
        )

        impact = result.targets[0].impact
        self.assertEqual(len(impact.follow_ups), 2)
        self.assertIsInstance(impact.follow_ups[0], GiveGroundRequest)
        self.assertIsInstance(
            impact.follow_ups[1],
            ConditionAfterGiveGroundRequest,
        )
        self.assertEqual(impact.applied_rule_ids, (effect.rule_id,))


if __name__ == "__main__":
    unittest.main()
