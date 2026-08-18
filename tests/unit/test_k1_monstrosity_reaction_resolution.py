from __future__ import annotations

import unittest

from towr.domain.attack_models import ConditionOnGiveGroundOrWoundSpec
from towr.domain.condition_models import (
    Condition,
    ConditionState,
    EffectClassification,
    EffectImmunity,
)
from towr.domain.injury_models import (
    AdditionalProfileWound,
    DecisionOwner,
    ProfileInjuryState,
    ProfileStateChangeRequest,
)
from towr.domain.resolution_models import (
    BoneDragonRider,
    ConditionAfterGiveGroundRequest,
    GiveGroundDestinationPreference,
    GiveGroundRequest,
    MonstrosityReactionOutcome,
    MonstrosityReactionContext,
    MonstrosityReactionRequest,
    MonstrosityReactionResolutionRequest,
    MonstrosityReactionSpec,
    MonstrousFlightReactionSpec,
    MonstrousFlightReactionContext,
    MonstrousRegenerationReactionSpec,
    ReactorZoneHazardRequest,
    SuppressRegenerationNextTurnRequest,
    UndeadMonstrosityReactionChoice,
    UndeadMonstrosityReactionContext,
    UndeadMonstrosityReactionSpec,
    UnsteadyReactionSpec,
)
from towr.domain.test_models import Skill
from towr.rules.monstrosity_reaction_resolution import (
    InvalidUndeadMonstrosityDecisionError,
    MissingUndeadMonstrosityDecisionError,
    UnresolvedMonstrousFlightReactionError,
    resolve_monstrosity_reaction,
)


class FixedUndeadDecision:
    def __init__(self, choice: UndeadMonstrosityReactionChoice) -> None:
        self.choice = choice
        self.owner: DecisionOwner | None = None
        self.choices: tuple[UndeadMonstrosityReactionChoice, ...] = ()

    def choose_undead_monstrosity_reaction(
        self,
        *,
        owner: DecisionOwner,
        choices: tuple[UndeadMonstrosityReactionChoice, ...],
        **_: object,
    ) -> UndeadMonstrosityReactionChoice:
        self.owner = owner
        self.choices = choices
        return self.choice


def source(
    *,
    reaction: MonstrosityReactionSpec | None = None,
    additional_wounds: tuple[AdditionalProfileWound, ...] = (),
    terrifying: bool = False,
    psychological_terrifying: bool = False,
    effect_immunities: tuple[EffectImmunity, ...] = (),
) -> MonstrosityReactionRequest:
    effects = (
        (
            ConditionOnGiveGroundOrWoundSpec(
                Condition.BROKEN,
                "RULE-NPC:terrifying",
                (
                    EffectClassification.PSYCHOLOGICAL
                    if psychological_terrifying
                    else EffectClassification.UNCLASSIFIED
                ),
            ),
        )
        if terrifying
        else ()
    )
    return MonstrosityReactionRequest(
        resolution_id="attack-resolution",
        reaction=reaction
        or MonstrousFlightReactionSpec("RULE-NPC:monstrous-flight"),
        additional_profile_wounds=additional_wounds,
        give_ground_or_wound_effects=effects,
        target_effect_immunities=effect_immunities,
    )


def request(
    *,
    reaction_source: MonstrosityReactionRequest | None = None,
    state: ProfileInjuryState | None = None,
    reaction_context: MonstrosityReactionContext | None = None,
    has_given_ground: bool = False,
    can_give_ground: bool = True,
) -> MonstrosityReactionResolutionRequest:
    resolved_source = reaction_source or source()
    is_flight = isinstance(
        resolved_source.reaction,
        MonstrousFlightReactionSpec,
    )
    return MonstrosityReactionResolutionRequest(
        id="reaction-resolution",
        source=resolved_source,
        state=state or ProfileInjuryState(wounds=0, wound_limit=3),
        context=(
            MonstrousFlightReactionContext(
                has_given_ground_this_turn=has_given_ground,
                can_give_ground=can_give_ground,
            )
            if is_flight
            else reaction_context
        ),
    )


class K1MonstrosityReactionResolutionTests(unittest.TestCase):
    def test_reaction_spec_requires_rule_id(self) -> None:
        with self.assertRaises(ValueError):
            MonstrousFlightReactionSpec(" ")
        with self.assertRaises(ValueError):
            UnsteadyReactionSpec("")
        with self.assertRaises(ValueError):
            MonstrousRegenerationReactionSpec(" ")
        with self.assertRaises(ValueError):
            UndeadMonstrosityReactionSpec("")
        with self.assertRaises(TypeError):
            UndeadMonstrosityReactionContext(
                rider="liche",  # type: ignore[arg-type]
                has_given_ground_this_round=False,
                can_give_ground=True,
            )

    def test_flight_gives_ground_and_queues_terrifying_after_movement(self) -> None:
        result = resolve_monstrosity_reaction(
            request(reaction_source=source(terrifying=True))
        )

        self.assertIs(result.outcome, MonstrosityReactionOutcome.GIVE_GROUND)
        self.assertIsNone(result.profile_wound)
        self.assertFalse(result.state.conditions.has(Condition.BROKEN))
        self.assertEqual(len(result.follow_ups), 2)
        self.assertIsInstance(result.follow_ups[0], GiveGroundRequest)
        movement = result.follow_ups[0]
        assert isinstance(movement, GiveGroundRequest)
        self.assertIs(
            movement.destination_preference,
            GiveGroundDestinationPreference.VERTICAL_MIDAIR_IF_ABLE,
        )
        self.assertIsInstance(
            result.follow_ups[1],
            ConditionAfterGiveGroundRequest,
        )
        self.assertEqual(
            result.applied_rule_ids,
            ("RULE-NPC:monstrous-flight", "RULE-NPC:terrifying"),
        )

    def test_second_flight_in_turn_suffers_profile_wound(self) -> None:
        extra = AdditionalProfileWound("RULE-WEAPON:wound-die")
        result = resolve_monstrosity_reaction(
            request(
                reaction_source=source(
                    additional_wounds=(extra,),
                    terrifying=True,
                ),
                state=ProfileInjuryState(
                    wounds=0,
                    wound_limit=3,
                    conditions=ConditionState(
                        frozenset({Condition.STAGGERED})
                    ),
                ),
                has_given_ground=True,
            )
        )

        self.assertIs(
            result.outcome,
            MonstrosityReactionOutcome.SUFFER_WOUND,
        )
        assert result.profile_wound is not None
        self.assertEqual(result.profile_wound.wounds_inflicted, 2)
        self.assertEqual(result.state.wounds, 2)
        self.assertFalse(result.state.conditions.has(Condition.STAGGERED))
        self.assertTrue(result.state.conditions.has(Condition.BROKEN))
        self.assertEqual(len(result.follow_ups), 1)
        self.assertIsInstance(
            result.follow_ups[0],
            ProfileStateChangeRequest,
        )
        self.assertEqual(
            result.applied_rule_ids,
            (
                "RULE-NPC:monstrous-flight",
                extra.rule_id,
                "RULE-NPC:terrifying",
            ),
        )

    def test_impossible_give_ground_requires_external_ruling(self) -> None:
        with self.assertRaises(UnresolvedMonstrousFlightReactionError):
            resolve_monstrosity_reaction(
                request(can_give_ground=False)
            )

    def test_unsteady_applies_prone_and_requests_zone_hazard(self) -> None:
        result = resolve_monstrosity_reaction(
            request(
                reaction_source=source(
                    reaction=UnsteadyReactionSpec("RULE-NPC:unsteady"),
                    terrifying=True,
                ),
                state=ProfileInjuryState(
                    wounds=0,
                    wound_limit=6,
                    conditions=ConditionState(
                        frozenset({Condition.STAGGERED})
                    ),
                ),
            )
        )

        self.assertIs(result.outcome, MonstrosityReactionOutcome.FALL_PRONE)
        self.assertTrue(result.state.conditions.has(Condition.PRONE))
        self.assertTrue(result.state.conditions.has(Condition.STAGGERED))
        self.assertFalse(result.state.conditions.has(Condition.BROKEN))
        self.assertEqual(len(result.follow_ups), 1)
        hazard = result.follow_ups[0]
        self.assertIsInstance(hazard, ReactorZoneHazardRequest)
        assert isinstance(hazard, ReactorZoneHazardRequest)
        self.assertEqual(hazard.rating, 3)
        self.assertIs(hazard.avoidance_skill, Skill.ATHLETICS)
        self.assertTrue(hazard.inflicts_wound)
        self.assertEqual(hazard.failure_conditions, ())
        self.assertEqual(result.applied_rule_ids, ("RULE-NPC:unsteady",))

    def test_unsteady_does_not_repeat_hazard_when_already_prone(self) -> None:
        state = ProfileInjuryState(
            wounds=0,
            wound_limit=6,
            conditions=ConditionState(frozenset({Condition.PRONE})),
        )
        result = resolve_monstrosity_reaction(
            request(
                reaction_source=source(
                    reaction=UnsteadyReactionSpec("RULE-NPC:unsteady")
                ),
                state=state,
            )
        )

        self.assertIs(
            result.outcome,
            MonstrosityReactionOutcome.ALREADY_PRONE,
        )
        self.assertIs(result.state, state)
        self.assertEqual(result.follow_ups, ())

    def test_unsteady_rejects_irrelevant_reaction_context(self) -> None:
        with self.assertRaises(ValueError):
            MonstrosityReactionResolutionRequest(
                id="reaction-resolution",
                source=source(
                    reaction=UnsteadyReactionSpec("RULE-NPC:unsteady")
                ),
                state=ProfileInjuryState(wounds=0, wound_limit=6),
                context=MonstrousFlightReactionContext(
                    has_given_ground_this_turn=False,
                    can_give_ground=True,
                ),
            )

    def test_regeneration_reaction_suppresses_next_turn(self) -> None:
        state = ProfileInjuryState(
            wounds=2,
            wound_limit=6,
            conditions=ConditionState(frozenset({Condition.STAGGERED})),
        )
        for rule_id in (
            "RULE-NPC:ghorgon-regeneration",
            "RULE-NPC:troll-hag-regeneration",
        ):
            with self.subTest(rule_id=rule_id):
                result = resolve_monstrosity_reaction(
                    request(
                        reaction_source=source(
                            reaction=MonstrousRegenerationReactionSpec(
                                rule_id
                            ),
                            terrifying=True,
                        ),
                        state=state,
                    )
                )

                self.assertIs(
                    result.outcome,
                    MonstrosityReactionOutcome.REGENERATION_SUPPRESSED,
                )
                self.assertIs(result.state, state)
                self.assertFalse(
                    result.state.conditions.has(Condition.BROKEN)
                )
                self.assertEqual(len(result.follow_ups), 1)
                suppression = result.follow_ups[0]
                self.assertIsInstance(
                    suppression,
                    SuppressRegenerationNextTurnRequest,
                )
                assert isinstance(
                    suppression,
                    SuppressRegenerationNextTurnRequest,
                )
                self.assertEqual(suppression.rule_id, rule_id)
                self.assertEqual(
                    suppression.resolution_id,
                    "attack-resolution",
                )
                self.assertEqual(result.applied_rule_ids, (rule_id,))

    def test_unmounted_undead_reaction_suffers_wound(self) -> None:
        extra = AdditionalProfileWound("RULE-WEAPON:wound-die")
        result = resolve_monstrosity_reaction(
            request(
                reaction_source=source(
                    reaction=UndeadMonstrosityReactionSpec(
                        "RULE-NPC:undead-monstrosity"
                    ),
                    additional_wounds=(extra,),
                    terrifying=True,
                ),
                state=ProfileInjuryState(
                    wounds=0,
                    wound_limit=5,
                    conditions=ConditionState(
                        frozenset({Condition.STAGGERED})
                    ),
                ),
            )
        )

        self.assertIs(
            result.outcome,
            MonstrosityReactionOutcome.SUFFER_WOUND,
        )
        assert result.profile_wound is not None
        self.assertEqual(result.profile_wound.wounds_inflicted, 2)
        self.assertEqual(result.state.wounds, 2)
        self.assertFalse(result.state.conditions.has(Condition.STAGGERED))
        self.assertTrue(result.state.conditions.has(Condition.BROKEN))
        self.assertEqual(
            result.applied_rule_ids,
            (
                "RULE-NPC:undead-monstrosity",
                extra.rule_id,
                "RULE-NPC:terrifying",
            ),
        )

    def test_undead_reaction_wound_blocks_psychological_terrifying(self) -> None:
        immunity = EffectImmunity(
            EffectClassification.PSYCHOLOGICAL,
            "RULE-NPC:undead-monstrosity-immunity",
        )
        result = resolve_monstrosity_reaction(
            request(
                reaction_source=source(
                    reaction=UndeadMonstrosityReactionSpec(
                        "RULE-NPC:undead-monstrosity"
                    ),
                    terrifying=True,
                    psychological_terrifying=True,
                    effect_immunities=(immunity,),
                )
            )
        )

        self.assertIs(
            result.outcome,
            MonstrosityReactionOutcome.SUFFER_WOUND,
        )
        self.assertEqual(result.state.wounds, 1)
        self.assertFalse(result.state.conditions.has(Condition.BROKEN))
        self.assertEqual(len(result.condition_applications), 1)
        application = result.condition_applications[0]
        self.assertTrue(application.blocked)
        self.assertEqual(
            application.source_rule_id,
            "RULE-NPC:terrifying",
        )
        self.assertEqual(application.blocked_by_rule_id, immunity.rule_id)
        self.assertEqual(
            result.applied_rule_ids,
            (
                "RULE-NPC:undead-monstrosity",
                immunity.rule_id,
            ),
        )

    def test_mounted_undead_reaction_can_give_ground(self) -> None:
        decision = FixedUndeadDecision(
            UndeadMonstrosityReactionChoice.GIVE_GROUND
        )
        result = resolve_monstrosity_reaction(
            request(
                reaction_source=source(
                    reaction=UndeadMonstrosityReactionSpec(
                        "RULE-NPC:undead-monstrosity"
                    ),
                    terrifying=True,
                ),
                reaction_context=UndeadMonstrosityReactionContext(
                    rider=BoneDragonRider.LICHE,
                    has_given_ground_this_round=False,
                    can_give_ground=True,
                ),
            ),
            decisions=decision,
        )

        self.assertIs(result.outcome, MonstrosityReactionOutcome.GIVE_GROUND)
        self.assertIs(decision.owner, DecisionOwner.MONSTROSITY)
        self.assertEqual(
            decision.choices,
            (
                UndeadMonstrosityReactionChoice.SUFFER_WOUND,
                UndeadMonstrosityReactionChoice.GIVE_GROUND,
                UndeadMonstrosityReactionChoice.FALL_PRONE,
            ),
        )
        self.assertEqual(len(result.follow_ups), 2)
        movement = result.follow_ups[0]
        self.assertIsInstance(movement, GiveGroundRequest)
        assert isinstance(movement, GiveGroundRequest)
        self.assertIs(
            movement.destination_preference,
            GiveGroundDestinationPreference.ANY_VALID_ADJACENT,
        )
        self.assertIsInstance(
            result.follow_ups[1],
            ConditionAfterGiveGroundRequest,
        )

    def test_mounted_undead_reaction_can_fall_prone(self) -> None:
        decision = FixedUndeadDecision(
            UndeadMonstrosityReactionChoice.FALL_PRONE
        )
        result = resolve_monstrosity_reaction(
            request(
                reaction_source=source(
                    reaction=UndeadMonstrosityReactionSpec(
                        "RULE-NPC:undead-monstrosity"
                    ),
                    terrifying=True,
                ),
                reaction_context=UndeadMonstrosityReactionContext(
                    rider=BoneDragonRider.TOMB_KING,
                    has_given_ground_this_round=False,
                    can_give_ground=True,
                ),
            ),
            decisions=decision,
        )

        self.assertIs(result.outcome, MonstrosityReactionOutcome.FALL_PRONE)
        self.assertTrue(result.state.conditions.has(Condition.PRONE))
        self.assertFalse(result.state.conditions.has(Condition.BROKEN))
        self.assertEqual(result.follow_ups, ())

    def test_mounted_undead_reaction_requires_decision(self) -> None:
        with self.assertRaises(MissingUndeadMonstrosityDecisionError):
            resolve_monstrosity_reaction(
                request(
                    reaction_source=source(
                        reaction=UndeadMonstrosityReactionSpec(
                            "RULE-NPC:undead-monstrosity"
                        )
                    ),
                    reaction_context=UndeadMonstrosityReactionContext(
                        rider=BoneDragonRider.LICHE,
                        has_given_ground_this_round=False,
                        can_give_ground=True,
                    ),
                )
            )

    def test_mounted_undead_reaction_rejects_unavailable_choice(self) -> None:
        decision = FixedUndeadDecision(
            UndeadMonstrosityReactionChoice.GIVE_GROUND
        )
        with self.assertRaises(InvalidUndeadMonstrosityDecisionError):
            resolve_monstrosity_reaction(
                request(
                    reaction_source=source(
                        reaction=UndeadMonstrosityReactionSpec(
                            "RULE-NPC:undead-monstrosity"
                        )
                    ),
                    reaction_context=UndeadMonstrosityReactionContext(
                        rider=BoneDragonRider.TOMB_KING,
                        has_given_ground_this_round=True,
                        can_give_ground=True,
                    ),
                ),
                decisions=decision,
            )


if __name__ == "__main__":
    unittest.main()
