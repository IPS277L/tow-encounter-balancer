from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.festering_wound_models import (
    FESTERING_WOUND_RULE_ID,
    FesteringWoundRecord,
    FesteringWoundState,
)
from towr.domain.infection_models import (
    DAILY_WOUND_REGISTRATION_RULE_ID,
    END_OF_DAY_INFECTION_RULE_ID,
    DailyWoundRegistrationRequest,
    DailyWoundState,
    EndOfDayInfectionRequest,
)
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundRequest,
    FixedCharacterWoundRequest,
    WoundEntryId,
    WoundNegationOption,
)
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.rules.infection_resolution import (
    register_daily_wound,
    resolve_end_of_day_infection,
)
from towr.rules.injury_resolution import (
    resolve_character_wound,
    resolve_fixed_character_wound,
)


class SelectNegation:
    def choose_wound_negation(self, **_: object) -> str:
        return "RULE-FATE:near-miss"


def accepted_wound_results(count: int):
    state = CharacterInjuryState()
    results = []
    for index in range(1, count + 1):
        result = resolve_character_wound(
            CharacterWoundRequest(
                id=f"battle:1:hero:wound:{index}",
                state=state,
            ),
            SequenceRandom([1] * index),
        )
        results.append(result)
        state = result.state
    return tuple(results)


def tracked_day(count: int):
    results = accepted_wound_results(count)
    state = DailyWoundState("day:1", "hero")
    for index, source in enumerate(results, start=1):
        registration = register_daily_wound(
            DailyWoundRegistrationRequest(
                id=f"day:1:hero:register:{index}",
                state=state,
                target_id="hero",
                source=source,
            )
        )
        state = registration.state
    return state, results[-1].state


def infection_request(
    daily_wounds: DailyWoundState,
    injury_state: CharacterInjuryState,
    *,
    festering_wound_state: FesteringWoundState | None = None,
    target_id: str = "hero",
    skill: Skill = Skill.ENDURANCE,
    rule_id: str = END_OF_DAY_INFECTION_RULE_ID,
) -> EndOfDayInfectionRequest:
    return EndOfDayInfectionRequest(
        id="day:1:hero:infection",
        daily_wounds=daily_wounds,
        target_id=target_id,
        injury_state=injury_state,
        festering_wound_state=(
            festering_wound_state
            if festering_wound_state is not None
            else FesteringWoundState("hero")
        ),
        endurance_test=TestRequest(
            id="day:1:hero:infection:endurance",
            profile=TestProfile(2, 6),
        ),
        skill=skill,
        rule_id=rule_id,
    )


class K1DailyWoundTrackingTests(unittest.TestCase):
    def test_accepted_table_wound_is_registered_once(self) -> None:
        source = accepted_wound_results(1)[0]
        previous = DailyWoundState("day:1", "hero")
        request = DailyWoundRegistrationRequest(
            id="day:1:hero:register:1",
            state=previous,
            target_id="hero",
            source=source,
        )

        result = register_daily_wound(request)

        self.assertEqual(result.previous_state, previous)
        self.assertEqual(result.state.wound_count, 1)
        self.assertEqual(result.receipt.wound, source.state.wounds[-1])
        self.assertEqual(result.receipt.source_request_id, source.request_id)
        self.assertIn(
            DAILY_WOUND_REGISTRATION_RULE_ID,
            result.applied_rule_ids,
        )
        with self.assertRaisesRegex(ValueError, "already registered"):
            DailyWoundRegistrationRequest(
                id="day:1:hero:repeat",
                state=result.state,
                target_id="hero",
                source=source,
            )

    def test_fixed_character_wound_is_also_registered(self) -> None:
        source = resolve_fixed_character_wound(
            FixedCharacterWoundRequest(
                id="hazard:hero:fixed-wound",
                state=CharacterInjuryState(),
                entry_id=WoundEntryId.SUPERFICIAL_INJURY,
                table_total=1,
                source_rule_id="RULE-HAZARD:fixed-wound",
            )
        )

        result = register_daily_wound(
            DailyWoundRegistrationRequest(
                id="day:1:hero:register:fixed",
                state=DailyWoundState("day:1", "hero"),
                target_id="hero",
                source=source,
            )
        )

        self.assertEqual(result.state.wound_count, 1)
        self.assertEqual(result.receipt.wound, source.state.wounds[-1])
        self.assertIn("RULE-HAZARD:fixed-wound", result.applied_rule_ids)

    def test_negated_or_forged_wound_result_is_rejected(self) -> None:
        negated = resolve_character_wound(
            CharacterWoundRequest(
                id="near-miss",
                state=CharacterInjuryState(),
                negation_options=(
                    WoundNegationOption("RULE-FATE:near-miss"),
                ),
            ),
            SequenceRandom([10]),
            decisions=SelectNegation(),
        )
        accepted = accepted_wound_results(1)[0]
        forged = replace(accepted, state=CharacterInjuryState())

        for source in (negated, forged):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    DailyWoundRegistrationRequest(
                        id="invalid:registration",
                        state=DailyWoundState("day:1", "hero"),
                        target_id="hero",
                        source=source,
                    )

    def test_registration_rejects_wrong_target_closed_day_and_rule(
        self,
    ) -> None:
        source = accepted_wound_results(1)[0]
        with self.assertRaisesRegex(ValueError, "another target"):
            DailyWoundRegistrationRequest(
                id="wrong-target",
                state=DailyWoundState("day:1", "hero"),
                target_id="ally",
                source=source,
            )
        with self.assertRaisesRegex(ValueError, "already closed"):
            DailyWoundRegistrationRequest(
                id="closed-day",
                state=DailyWoundState(
                    "day:1",
                    "hero",
                    closed_by_infection_id="infection:done",
                ),
                target_id="hero",
                source=source,
            )

        unknown = DailyWoundRegistrationRequest(
            id="unknown-rule",
            state=DailyWoundState("day:1", "hero"),
            target_id="hero",
            source=source,
            rule_id="RULE-UNKNOWN",
        )
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            register_daily_wound(unknown)

    def test_registration_result_rejects_forged_transition(self) -> None:
        source = accepted_wound_results(1)[0]
        result = register_daily_wound(
            DailyWoundRegistrationRequest(
                id="day:1:hero:register:1",
                state=DailyWoundState("day:1", "hero"),
                target_id="hero",
                source=source,
            )
        )

        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, state=result.previous_state)


class K1EndOfDayInfectionTests(unittest.TestCase):
    def test_fewer_successes_than_wounds_adds_exactly_one_festering(
        self,
    ) -> None:
        daily, injury = tracked_day(3)
        request = infection_request(daily, injury)

        result = resolve_end_of_day_infection(
            request,
            SequenceRandom([1, 9]),
        )

        self.assertTrue(result.test_result.succeeded)
        self.assertEqual(result.test_result.successes, 1)
        self.assertEqual(result.wound_count, 3)
        self.assertFalse(result.avoided_infection)
        self.assertIsNotNone(result.added_festering_wound)
        added = result.added_festering_wound
        assert added is not None
        self.assertEqual(added.source_infection_id, request.id)
        self.assertEqual(added.rule_id, FESTERING_WOUND_RULE_ID)
        self.assertEqual(result.festering_wound_state.active_count, 1)
        self.assertEqual(
            result.daily_wounds.closed_by_infection_id,
            request.id,
        )

    def test_successes_equal_to_wounds_avoid_infection(self) -> None:
        daily, injury = tracked_day(2)

        result = resolve_end_of_day_infection(
            infection_request(daily, injury),
            SequenceRandom([1, 2]),
        )

        self.assertEqual(result.test_result.successes, 2)
        self.assertTrue(result.avoided_infection)
        self.assertIsNone(result.added_festering_wound)
        self.assertEqual(result.festering_wound_state.active_count, 0)
        self.assertTrue(result.daily_wounds.is_closed)

    def test_treated_and_healed_wound_still_counts_for_day(self) -> None:
        daily, injury = tracked_day(1)
        historical = replace(
            injury.wounds[0],
            treated=True,
            effect_resolved=True,
            healed=True,
        )
        current = CharacterInjuryState(wounds=(historical,))

        result = resolve_end_of_day_infection(
            infection_request(daily, current),
            SequenceRandom([1, 9]),
        )

        self.assertEqual(result.wound_count, 1)
        self.assertTrue(result.avoided_infection)

    def test_failure_appends_to_existing_festering_state(self) -> None:
        daily, injury = tracked_day(1)
        existing = FesteringWoundRecord(
            id="hero:festering:old",
            source_infection_id="day:0:hero:infection",
        )
        previous = FesteringWoundState("hero", (existing,))

        result = resolve_end_of_day_infection(
            infection_request(
                daily,
                injury,
                festering_wound_state=previous,
            ),
            SequenceRandom([8, 9]),
        )

        self.assertEqual(
            result.festering_wound_state.wounds[0],
            existing,
        )
        self.assertEqual(result.festering_wound_state.active_count, 2)

    def test_empty_closed_wrong_target_and_non_endurance_are_rejected(
        self,
    ) -> None:
        daily, injury = tracked_day(1)
        invalid = (
            lambda: infection_request(DailyWoundState("day:1", "hero"), injury),
            lambda: infection_request(
                replace(daily, closed_by_infection_id="infection:done"),
                injury,
            ),
            lambda: infection_request(daily, injury, target_id="ally"),
            lambda: infection_request(daily, injury, skill=Skill.RECALL),
        )
        for make_request in invalid:
            with self.subTest(make_request=make_request):
                with self.assertRaises(ValueError):
                    make_request()

    def test_changed_wound_identity_and_dead_character_are_rejected(
        self,
    ) -> None:
        daily, injury = tracked_day(1)
        changed = replace(
            injury,
            wounds=(
                replace(
                    injury.wounds[0],
                    entry_id=WoundEntryId.NICKED_ARM,
                ),
            ),
        )
        for current in (changed, replace(injury, dead=True)):
            with self.subTest(current=current):
                with self.assertRaises(ValueError):
                    infection_request(daily, current)

    def test_closed_day_cannot_be_resolved_twice(self) -> None:
        daily, injury = tracked_day(1)
        result = resolve_end_of_day_infection(
            infection_request(daily, injury),
            SequenceRandom([1, 9]),
        )

        with self.assertRaisesRegex(ValueError, "already resolved"):
            infection_request(result.daily_wounds, injury)

    def test_unknown_rule_and_forged_result_are_rejected(self) -> None:
        daily, injury = tracked_day(1)
        unknown = infection_request(
            daily,
            injury,
            rule_id="RULE-UNKNOWN",
        )
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            resolve_end_of_day_infection(
                unknown,
                SequenceRandom([1, 9]),
            )

        result = resolve_end_of_day_infection(
            infection_request(daily, injury),
            SequenceRandom([8, 9]),
        )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, avoided_infection=True)


if __name__ == "__main__":
    unittest.main()
