from __future__ import annotations

import unittest

from towr.domain.attack_models import ConditionOnGiveGroundOrWoundSpec
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    AdditionalProfileWound,
    ProfileInjuryState,
    ProfileStateChangeRequest,
)
from towr.domain.resolution_models import (
    ConditionAfterGiveGroundRequest,
    GiveGroundDestinationPreference,
    GiveGroundRequest,
    MonstrosityReactionOutcome,
    MonstrosityReactionRequest,
    MonstrosityReactionResolutionRequest,
    MonstrousFlightReactionSpec,
)
from towr.rules.monstrosity_reaction_resolution import (
    UnresolvedMonstrousFlightReactionError,
    resolve_monstrosity_reaction,
)


def source(
    *,
    additional_wounds: tuple[AdditionalProfileWound, ...] = (),
    terrifying: bool = False,
) -> MonstrosityReactionRequest:
    effects = (
        (
            ConditionOnGiveGroundOrWoundSpec(
                Condition.BROKEN,
                "RULE-NPC:terrifying",
            ),
        )
        if terrifying
        else ()
    )
    return MonstrosityReactionRequest(
        resolution_id="attack-resolution",
        reaction=MonstrousFlightReactionSpec(
            "RULE-NPC:monstrous-flight",
        ),
        additional_profile_wounds=additional_wounds,
        give_ground_or_wound_effects=effects,
    )


def request(
    *,
    reaction_source: MonstrosityReactionRequest | None = None,
    state: ProfileInjuryState | None = None,
    has_given_ground: bool = False,
    can_give_ground: bool = True,
) -> MonstrosityReactionResolutionRequest:
    return MonstrosityReactionResolutionRequest(
        id="reaction-resolution",
        source=reaction_source or source(),
        state=state or ProfileInjuryState(wounds=0, wound_limit=3),
        has_given_ground_this_turn=has_given_ground,
        can_give_ground=can_give_ground,
    )


class K1MonstrosityReactionResolutionTests(unittest.TestCase):
    def test_reaction_spec_requires_rule_id(self) -> None:
        with self.assertRaises(ValueError):
            MonstrousFlightReactionSpec(" ")

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


if __name__ == "__main__":
    unittest.main()
