from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.attack_models import (
    AttackRequest,
    ConditionAfterGiveGroundSpec,
    ConditionOnGiveGroundOrWoundSpec,
    ConditionOnHitSpec,
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
    EffectClassification,
    EffectImmunity,
    StaggerChoice,
)
from towr.domain.injury_models import (
    CharacterInjuryState,
    MonstrosityImpactChoice,
    ProfileInjuryState,
    ProfileStateChangeRequest,
    WoundNegationOption,
)
from towr.domain.infection_models import DailyWoundState
from towr.domain.resolution_models import (
    AttackerStaggerRequest,
    ConditionAfterGiveGroundRequest,
    ConsumeWoundNegationRequest,
    GiveGroundRequest,
    KernelAttackRequest,
    MonstrosityReactionRequest,
    MonstrousFlightReactionSpec,
    NearbyTargetsStaggerRequest,
    TargetInjuryPolicy,
)
from towr.domain.test_models import TestProfile, TestRequest
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionRequest,
)
from towr.rules.condition_effect_resolution import (
    resolve_condition_after_give_ground,
)
from towr.rules.kernel import (
    apply_kernel_character_wound_completion,
    resolve_kernel_attack,
)
from towr.rules.wound_lifecycle_resolution import (
    complete_character_wound_lifecycle,
)


class GiveGroundDecisions:
    def __init__(
        self,
        choice: StaggerChoice = StaggerChoice.GIVE_GROUND,
        wound_negation: str | None = None,
    ) -> None:
        self.choice = choice
        self.wound_negation = wound_negation

    def choose_repeated_stagger(self, **_: object) -> StaggerChoice:
        return self.choice

    def choose_wound_negation(self, **_: object) -> str | None:
        return self.wound_negation

    def choose_monstrosity_impact(
        self,
        **_: object,
    ) -> MonstrosityImpactChoice:
        return MonstrosityImpactChoice.TRIGGER_REACTION


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
    effect_immunities: tuple[EffectImmunity, ...] = (),
) -> KernelAttackRequest:
    if state is None:
        state = CharacterInjuryState()
    return KernelAttackRequest(
        id="resolution",
        target_id="target",
        attack=attack(*effects, impact_spec=impact_spec),
        target_policy=policy,
        target_state=state,
        can_target_leave_zone=True,
        target_has_given_ground_this_round=False,
        target_effect_immunities=effect_immunities,
        monstrosity_reaction=(
            MonstrousFlightReactionSpec("RULE-MONSTER:monstrous-flight")
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

    def test_condition_on_hit_requires_damage_and_cannot_be_staggered(self) -> None:
        with self.assertRaises(ValueError):
            ConditionOnHitSpec(Condition.STAGGERED, "RULE-INVALID")
        with self.assertRaises(ValueError):
            attack(
                ConditionOnHitSpec(Condition.DRAINED, "RULE-INVALID"),
                impact_spec=ConditionImpactSpec(
                    Condition.BURDENED,
                    "RULE-REPLACEMENT",
                ),
            )

    def test_outcome_condition_requires_damage_and_cannot_be_staggered(self) -> None:
        with self.assertRaises(ValueError):
            ConditionOnGiveGroundOrWoundSpec(
                Condition.STAGGERED,
                "RULE-INVALID",
            )
        with self.assertRaises(ValueError):
            attack(
                ConditionOnGiveGroundOrWoundSpec(
                    Condition.BROKEN,
                    "RULE-INVALID",
                ),
                impact_spec=ConditionImpactSpec(
                    Condition.BURDENED,
                    "RULE-REPLACEMENT",
                ),
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
                ConditionOnHitSpec(
                    Condition.DRAINED,
                    "RULE-ATTACK:draining-hit",
                ),
                state=state,
            ),
            SequenceRandom([10, 10, 10]),
        )

        self.assertIs(result.target_state, state)
        self.assertFalse(result.target_state.conditions.has(Condition.DRAINED))
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

    def test_condition_on_hit_is_added_after_normal_damage_impact(self) -> None:
        effect = ConditionOnHitSpec(
            Condition.DRAINED,
            "RULE-ATTACK:serrated-maw",
        )
        result = resolve_kernel_attack(
            request(effect),
            SequenceRandom([1, 10, 10]),
        )

        self.assertIsNotNone(result.stagger)
        self.assertTrue(result.target_state.conditions.has(Condition.STAGGERED))
        self.assertTrue(result.target_state.conditions.has(Condition.DRAINED))
        self.assertEqual(
            result.applied_secondary_rule_ids,
            (effect.rule_id,),
        )

    def test_psychological_condition_on_hit_is_blocked(self) -> None:
        immunity = EffectImmunity(
            EffectClassification.PSYCHOLOGICAL,
            "RULE-NPC:undead-immunity",
        )
        effect = ConditionOnHitSpec(
            Condition.BROKEN,
            "RULE-ATTACK:psychological-hit",
            EffectClassification.PSYCHOLOGICAL,
        )
        result = resolve_kernel_attack(
            request(
                effect,
                policy=TargetInjuryPolicy.CHAMPION,
                effect_immunities=(immunity,),
            ),
            SequenceRandom([1, 10, 10]),
        )

        self.assertTrue(result.target_state.conditions.has(Condition.STAGGERED))
        self.assertFalse(result.target_state.conditions.has(Condition.BROKEN))
        self.assertEqual(len(result.condition_applications), 1)
        application = result.condition_applications[0]
        self.assertTrue(application.blocked)
        self.assertEqual(application.source_rule_id, effect.rule_id)
        self.assertEqual(application.blocked_by_rule_id, immunity.rule_id)
        self.assertEqual(
            result.applied_secondary_rule_ids,
            (immunity.rule_id,),
        )

    def test_near_miss_does_not_cancel_condition_on_hit(self) -> None:
        effect = ConditionOnHitSpec(
            Condition.DRAINED,
            "RULE-ATTACK:venomous-tail",
        )
        near_miss = WoundNegationOption("RULE-FATE:near-miss")
        result = resolve_kernel_attack(
            KernelAttackRequest(
                id="resolution",
                target_id="target",
                attack=attack(
                    effect,
                    impact_spec=DamageImpactSpec(
                        DamageProfile(5),
                        ResilienceProfile(toughness=4, bonus=1),
                    ),
                ),
                target_policy=TargetInjuryPolicy.PLAYER,
                target_state=CharacterInjuryState(
                    conditions=ConditionState(
                        frozenset({Condition.STAGGERED})
                    )
                ),
                can_target_leave_zone=True,
                target_has_given_ground_this_round=False,
                wound_negation_options=(near_miss,),
            ),
            SequenceRandom([1, 10, 10, 10]),
            decisions=GiveGroundDecisions(
                wound_negation=near_miss.rule_id,
            ),
        )

        assert result.character_wound is not None
        self.assertFalse(result.character_wound.wound_accepted)
        self.assertTrue(result.target_state.conditions.has(Condition.STAGGERED))
        self.assertTrue(result.target_state.conditions.has(Condition.DRAINED))
        self.assertIsInstance(result.follow_ups[0], ConsumeWoundNegationRequest)
        self.assertEqual(
            result.applied_secondary_rule_ids,
            (effect.rule_id,),
        )

    def test_condition_on_hit_is_applied_after_an_accepted_wound(self) -> None:
        effect = ConditionOnHitSpec(
            Condition.DRAINED,
            "RULE-ATTACK:serrated-maw",
        )
        result = resolve_kernel_attack(
            request(
                effect,
                impact_spec=DamageImpactSpec(
                    DamageProfile(5),
                    ResilienceProfile(toughness=4, bonus=1),
                ),
            ),
            SequenceRandom([1, 10, 10, 1]),
        )

        assert result.character_wound is not None
        self.assertTrue(result.character_wound.wound_accepted)
        self.assertEqual(len(result.target_state.wounds), 1)
        self.assertTrue(result.target_state.conditions.has(Condition.DRAINED))
        self.assertEqual(
            result.applied_secondary_rule_ids,
            (effect.rule_id,),
        )

    def test_condition_on_hit_precedes_after_give_ground_follow_up(self) -> None:
        after_ground = ConditionAfterGiveGroundSpec(
            Condition.BROKEN,
            "RULE-NPC:fearsome",
        )
        on_hit = ConditionOnHitSpec(
            Condition.DRAINED,
            "RULE-ATTACK:serrated-maw",
        )
        result = resolve_kernel_attack(
            request(
                after_ground,
                on_hit,
                state=CharacterInjuryState(
                    conditions=ConditionState(
                        frozenset({Condition.STAGGERED})
                    )
                ),
            ),
            SequenceRandom([1, 10, 10]),
            decisions=GiveGroundDecisions(),
        )

        self.assertTrue(result.target_state.conditions.has(Condition.DRAINED))
        self.assertFalse(result.target_state.conditions.has(Condition.BROKEN))
        self.assertIsInstance(result.follow_ups[0], GiveGroundRequest)
        self.assertIsInstance(
            result.follow_ups[1],
            ConditionAfterGiveGroundRequest,
        )
        self.assertEqual(
            result.applied_secondary_rule_ids,
            (on_hit.rule_id, after_ground.rule_id),
        )

    def test_terrifying_queues_broken_after_give_ground(self) -> None:
        effect = ConditionOnGiveGroundOrWoundSpec(
            Condition.BROKEN,
            "RULE-NPC:terrifying",
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

        self.assertFalse(result.target_state.conditions.has(Condition.BROKEN))
        self.assertEqual(len(result.follow_ups), 2)
        self.assertIsInstance(result.follow_ups[0], GiveGroundRequest)
        self.assertIsInstance(
            result.follow_ups[1],
            ConditionAfterGiveGroundRequest,
        )
        self.assertEqual(result.applied_secondary_rule_ids, (effect.rule_id,))

    def test_terrifying_is_deferred_while_wound_is_pending(self) -> None:
        effect = ConditionOnGiveGroundOrWoundSpec(
            Condition.BROKEN,
            "RULE-NPC:terrifying",
        )
        result = resolve_kernel_attack(
            request(
                effect,
                impact_spec=DamageImpactSpec(
                    DamageProfile(5),
                    ResilienceProfile(toughness=4, bonus=1),
                ),
            ),
            SequenceRandom([1, 10, 10, 1]),
        )

        assert result.character_wound is not None
        self.assertTrue(result.character_wound.wound_accepted)
        self.assertFalse(result.target_state.conditions.has(Condition.BROKEN))
        self.assertEqual(result.applied_secondary_rule_ids, ())
        self.assertEqual(result.deferred_wound_conditions, (effect,))

        assert result.pending_character_wound is not None
        completion = complete_character_wound_lifecycle(
            CharacterWoundLifecycleCompletionRequest(
                id="resolution:complete-wound",
                roll=result.pending_character_wound,
                current_state=result.target_state,
                daily_wounds=DailyWoundState("day:1", "target"),
                daily_registration_id="resolution:daily-wound",
            )
        )
        completed = apply_kernel_character_wound_completion(
            result,
            completion,
        )
        self.assertTrue(completed.target_state.conditions.has(Condition.BROKEN))
        self.assertEqual(
            completed.applied_secondary_rule_ids,
            (effect.rule_id,),
        )

    def test_psychological_terrifying_waits_for_wound_completion(self) -> None:
        immunity = EffectImmunity(
            EffectClassification.PSYCHOLOGICAL,
            "RULE-NPC:undead-immunity",
        )
        effect = ConditionOnGiveGroundOrWoundSpec(
            Condition.BROKEN,
            "RULE-NPC:terrifying",
            EffectClassification.PSYCHOLOGICAL,
        )
        result = resolve_kernel_attack(
            request(
                effect,
                impact_spec=DamageImpactSpec(
                    DamageProfile(5),
                    ResilienceProfile(toughness=4, bonus=1),
                ),
                policy=TargetInjuryPolicy.CHAMPION,
                effect_immunities=(immunity,),
            ),
            SequenceRandom([1, 10, 10, 1]),
        )

        assert result.character_wound is not None
        self.assertTrue(result.character_wound.wound_accepted)
        self.assertFalse(result.target_state.conditions.has(Condition.BROKEN))
        self.assertEqual(result.condition_applications, ())
        self.assertEqual(result.applied_secondary_rule_ids, ())
        self.assertEqual(result.deferred_wound_conditions, (effect,))

    def test_psychological_fearsome_is_blocked_after_give_ground(self) -> None:
        immunity = EffectImmunity(
            EffectClassification.PSYCHOLOGICAL,
            "RULE-NPC:undead-immunity",
        )
        effect = ConditionAfterGiveGroundSpec(
            Condition.BROKEN,
            "RULE-NPC:fearsome",
            EffectClassification.PSYCHOLOGICAL,
        )
        result = resolve_kernel_attack(
            request(
                effect,
                state=CharacterInjuryState(
                    conditions=ConditionState(
                        frozenset({Condition.STAGGERED})
                    )
                ),
                policy=TargetInjuryPolicy.CHAMPION,
                effect_immunities=(immunity,),
            ),
            SequenceRandom([1, 10, 10]),
            decisions=GiveGroundDecisions(),
        )

        follow_up = result.follow_ups[1]
        assert isinstance(follow_up, ConditionAfterGiveGroundRequest)
        self.assertEqual(
            follow_up.target_effect_immunities,
            (immunity,),
        )
        condition_result = resolve_condition_after_give_ground(
            follow_up,
            result.target_state,
        )
        self.assertTrue(condition_result.blocked)
        self.assertEqual(
            condition_result.source_rule_id,
            effect.rule_id,
        )
        self.assertEqual(
            condition_result.blocked_by_rule_id,
            immunity.rule_id,
        )
        self.assertFalse(
            condition_result.state.conditions.has(Condition.BROKEN)
        )

    def test_near_miss_prevents_terrifying_wound_trigger(self) -> None:
        effect = ConditionOnGiveGroundOrWoundSpec(
            Condition.BROKEN,
            "RULE-NPC:terrifying",
        )
        near_miss = WoundNegationOption("RULE-FATE:near-miss")
        result = resolve_kernel_attack(
            KernelAttackRequest(
                id="resolution",
                target_id="target",
                attack=attack(
                    effect,
                    impact_spec=DamageImpactSpec(
                        DamageProfile(5),
                        ResilienceProfile(toughness=4, bonus=1),
                    ),
                ),
                target_policy=TargetInjuryPolicy.PLAYER,
                target_state=CharacterInjuryState(),
                can_target_leave_zone=True,
                target_has_given_ground_this_round=False,
                wound_negation_options=(near_miss,),
            ),
            SequenceRandom([1, 10, 10, 10]),
            decisions=GiveGroundDecisions(wound_negation=near_miss.rule_id),
        )

        assert result.character_wound is not None
        self.assertFalse(result.character_wound.wound_accepted)
        self.assertFalse(result.target_state.conditions.has(Condition.BROKEN))
        self.assertEqual(result.applied_secondary_rule_ids, ())

    def test_terrifying_does_not_trigger_on_first_stagger(self) -> None:
        effect = ConditionOnGiveGroundOrWoundSpec(
            Condition.BROKEN,
            "RULE-NPC:terrifying",
        )
        result = resolve_kernel_attack(
            request(effect),
            SequenceRandom([1, 10, 10]),
        )

        self.assertTrue(result.target_state.conditions.has(Condition.STAGGERED))
        self.assertFalse(result.target_state.conditions.has(Condition.BROKEN))
        self.assertEqual(result.applied_secondary_rule_ids, ())

    def test_kernel_carries_terrifying_into_monstrosity_reaction(self) -> None:
        immunity = EffectImmunity(
            EffectClassification.PSYCHOLOGICAL,
            "RULE-NPC:undead-immunity",
        )
        effect = ConditionOnGiveGroundOrWoundSpec(
            Condition.BROKEN,
            "RULE-NPC:terrifying",
            EffectClassification.PSYCHOLOGICAL,
        )
        result = resolve_kernel_attack(
            request(
                effect,
                policy=TargetInjuryPolicy.MONSTROSITY,
                state=ProfileInjuryState(wounds=0, wound_limit=3),
                impact_spec=DamageImpactSpec(
                    DamageProfile(5),
                    ResilienceProfile(toughness=4, bonus=1),
                ),
                effect_immunities=(immunity,),
            ),
            SequenceRandom([1, 10, 10]),
            decisions=GiveGroundDecisions(),
        )

        self.assertEqual(len(result.follow_ups), 1)
        reaction = result.follow_ups[0]
        self.assertIsInstance(reaction, MonstrosityReactionRequest)
        assert isinstance(reaction, MonstrosityReactionRequest)
        self.assertEqual(
            reaction.give_ground_or_wound_effects,
            (effect,),
        )
        self.assertEqual(reaction.target_effect_immunities, (immunity,))


if __name__ == "__main__":
    unittest.main()
