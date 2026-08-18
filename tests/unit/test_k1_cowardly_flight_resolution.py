from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.condition_models import (
    Condition,
    EffectClassification,
    EffectImmunity,
)
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.resolution_models import (
    CowardlyFlightRequest,
    CowardlyFlightWillpowerRequest,
    GiveGroundRequest,
)
from towr.domain.test_models import InlineProfile, TestRequest
from towr.rules.cowardly_flight_resolution import (
    resolve_cowardly_flight,
    resolve_cowardly_flight_willpower,
)


def immunity() -> EffectImmunity:
    return EffectImmunity(
        EffectClassification.PSYCHOLOGICAL,
        "RULE-NPC:undead-psychological-immunity",
    )


def request(
    *,
    potency: int = 2,
    can_give_ground: bool = True,
    immunities: tuple[EffectImmunity, ...] = (),
    state: CharacterInjuryState | None = None,
) -> CowardlyFlightRequest:
    return CowardlyFlightRequest(
        id="cowardly-flight",
        target_id="target",
        potency=potency,
        can_give_ground=can_give_ground,
        willpower_test=TestRequest(
            "cowardly-flight:target:willpower-test",
            InlineProfile(2, 5),
        ),
        target_state=state or CharacterInjuryState(),
        target_effect_immunities=immunities,
    )


class K1CowardlyFlightResolutionTests(unittest.TestCase):
    def test_immunity_blocks_movement_and_test_as_one_source(self) -> None:
        source = request(immunities=(immunity(),))

        result = resolve_cowardly_flight(source)

        self.assertTrue(result.application.blocked)
        self.assertEqual(
            result.application.blocked_by_rule_id,
            "RULE-NPC:undead-psychological-immunity",
        )
        self.assertEqual(result.follow_ups, ())

    def test_unblocked_source_orders_give_ground_before_willpower(self) -> None:
        source = request()

        result = resolve_cowardly_flight(source)

        self.assertFalse(result.application.blocked)
        self.assertEqual(len(result.follow_ups), 2)
        self.assertIsInstance(result.follow_ups[0], GiveGroundRequest)
        self.assertIsInstance(
            result.follow_ups[1],
            CowardlyFlightWillpowerRequest,
        )
        self.assertEqual(result.follow_ups[0].rule_id, source.rule_id)

    def test_impossible_give_ground_does_not_cancel_willpower_test(self) -> None:
        result = resolve_cowardly_flight(request(can_give_ground=False))

        self.assertEqual(len(result.follow_ups), 1)
        self.assertIsInstance(
            result.follow_ups[0],
            CowardlyFlightWillpowerRequest,
        )

    def test_insufficient_successes_apply_broken_after_movement_phase(self) -> None:
        source = request(potency=2)
        prepared = resolve_cowardly_flight(source)
        follow_up = prepared.follow_ups[-1]
        assert isinstance(follow_up, CowardlyFlightWillpowerRequest)

        result = resolve_cowardly_flight_willpower(
            follow_up,
            SequenceRandom([1, 10]),
        )

        self.assertFalse(result.resisted)
        self.assertEqual(result.test.successes, 1)
        self.assertTrue(result.state.conditions.has(Condition.BROKEN))
        self.assertIsNotNone(result.condition_application)
        assert result.condition_application is not None
        self.assertIs(
            result.condition_application.condition,
            Condition.BROKEN,
        )
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))

    def test_successes_equal_to_potency_resist_broken(self) -> None:
        state = CharacterInjuryState()
        source = request(potency=2, state=state)
        prepared = resolve_cowardly_flight(source)
        follow_up = prepared.follow_ups[-1]
        assert isinstance(follow_up, CowardlyFlightWillpowerRequest)

        result = resolve_cowardly_flight_willpower(
            follow_up,
            SequenceRandom([1, 2]),
        )

        self.assertTrue(result.resisted)
        self.assertIs(result.state, state)
        self.assertIsNone(result.condition_application)


if __name__ == "__main__":
    unittest.main()
