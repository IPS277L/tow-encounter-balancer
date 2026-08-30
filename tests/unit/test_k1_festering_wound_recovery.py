from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from tests.unit.test_k1_rest_and_recovery_healing import (
    endeavour_request,
    injury_state,
    successful_endeavour,
)
from towr.domain.festering_wound_models import (
    FESTERING_WOUND_DICE_RULE_ID,
    FESTERING_WOUNDS_RECOVERY_APPLICATION_RULE_ID,
    FesteringWoundRecord,
    FesteringWoundState,
    FesteringWoundsRecoveryApplicationRequest,
)
from towr.domain.injury_models import CharacterWoundRequest
from towr.rules.downtime_resolution import (
    execute_rest_and_recovery_endeavour,
)
from towr.rules.festering_wound_resolution import (
    apply_festering_wounds_recovery,
)
from towr.rules.injury_resolution import resolve_character_wound


def festering_state(
    *,
    target_id: str = "hero",
    count: int = 2,
) -> FesteringWoundState:
    return FesteringWoundState(
        target_id=target_id,
        wounds=tuple(
            FesteringWoundRecord(
                id=f"hero:festering:{index}",
                source_infection_id=f"day:{index}:infection",
            )
            for index in range(1, count + 1)
        ),
    )


def application_request(
    state: FesteringWoundState,
    *,
    consumed_source_ids: tuple[str, ...] = ("prior-source",),
    rule_id: str = FESTERING_WOUNDS_RECOVERY_APPLICATION_RULE_ID,
) -> FesteringWoundsRecoveryApplicationRequest:
    return FesteringWoundsRecoveryApplicationRequest(
        id="downtime:1:hero:recover-festering",
        endeavour=successful_endeavour(injury_state()),
        target_id="hero",
        state=state,
        consumed_source_ids=consumed_source_ids,
        rule_id=rule_id,
    )


class K1FesteringWoundRecoveryTests(unittest.TestCase):
    def test_state_explicitly_provides_all_additional_untreated_dice(
        self,
    ) -> None:
        state = festering_state()
        modifiers = state.wound_table_dice_modifiers

        self.assertEqual(state.active_count, 2)
        self.assertEqual(state.additional_untreated_dice, 2)
        self.assertEqual(len(modifiers), 1)
        modifier = modifiers[0]
        self.assertEqual(modifier.rule_id, FESTERING_WOUND_DICE_RULE_ID)
        self.assertEqual(modifier.amount, 2)

        result = resolve_character_wound(
            CharacterWoundRequest(
                id="hero:next-wound",
                state=injury_state(),
                dice_modifiers=modifiers,
            ),
            SequenceRandom([1, 1, 1, 1]),
        )

        self.assertEqual(result.table_roll.dice, 4)
        self.assertIn(FESTERING_WOUND_DICE_RULE_ID, result.applied_rule_ids)

    def test_success_removes_all_festering_wounds_once(self) -> None:
        state = festering_state()
        request = application_request(state)

        result = apply_festering_wounds_recovery(request)

        follow_up = request.endeavour.festering_wounds_recovery
        assert follow_up is not None
        self.assertEqual(result.previous_state, state)
        self.assertEqual(result.recovered_wounds, state.wounds)
        self.assertEqual(result.state, FesteringWoundState("hero"))
        self.assertEqual(
            result.consumed_source_ids,
            ("prior-source", follow_up.id),
        )
        self.assertIn(
            FESTERING_WOUNDS_RECOVERY_APPLICATION_RULE_ID,
            result.applied_rule_ids,
        )
        self.assertEqual(result.state.wound_table_dice_modifiers, ())

    def test_recovery_does_not_change_ordinary_wound_history(self) -> None:
        ordinary_state = injury_state()
        source = successful_endeavour(ordinary_state)
        request = FesteringWoundsRecoveryApplicationRequest(
            id="downtime:1:hero:recover-festering",
            endeavour=source,
            target_id="hero",
            state=festering_state(),
        )

        result = apply_festering_wounds_recovery(request)

        self.assertIs(source.source_request.injury_state, ordinary_state)
        self.assertIs(
            result.source_request.endeavour.source_request.injury_state,
            ordinary_state,
        )
        self.assertEqual(len(ordinary_state.wounds), 5)
        self.assertEqual(result.state.wounds, ())

    def test_empty_state_is_valid_and_still_consumes_follow_up(self) -> None:
        request = application_request(FesteringWoundState("hero"))

        result = apply_festering_wounds_recovery(request)

        self.assertEqual(result.recovered_wounds, ())
        self.assertEqual(result.state, request.state)
        self.assertEqual(len(result.consumed_source_ids), 2)

    def test_application_is_bound_to_endeavour_target_and_state(self) -> None:
        for target_id, state in (
            ("ally", festering_state()),
            ("hero", festering_state(target_id="ally")),
        ):
            with self.subTest(target_id=target_id, state=state.target_id):
                with self.assertRaisesRegex(ValueError, "another target"):
                    FesteringWoundsRecoveryApplicationRequest(
                        id="wrong-target",
                        endeavour=successful_endeavour(injury_state()),
                        target_id=target_id,
                        state=state,
                    )

    def test_failed_endeavour_cannot_recover_festering_wounds(self) -> None:
        failed = execute_rest_and_recovery_endeavour(
            endeavour_request(injury_state()),
            SequenceRandom([8, 9]),
        )

        with self.assertRaisesRegex(ValueError, "successful canonical"):
            FesteringWoundsRecoveryApplicationRequest(
                id="failed:festering",
                endeavour=failed,
                target_id="hero",
                state=festering_state(),
            )

    def test_follow_up_cannot_be_consumed_twice(self) -> None:
        source = successful_endeavour(injury_state())
        follow_up = source.festering_wounds_recovery
        assert follow_up is not None

        with self.assertRaisesRegex(ValueError, "already consumed"):
            FesteringWoundsRecoveryApplicationRequest(
                id="repeat:festering",
                endeavour=source,
                target_id="hero",
                state=festering_state(),
                consumed_source_ids=(follow_up.id,),
            )

    def test_unknown_application_rule_is_rejected_before_transition(
        self,
    ) -> None:
        request = application_request(
            festering_state(),
            rule_id="RULE-UNKNOWN",
        )

        with self.assertRaisesRegex(ValueError, "unknown rule"):
            apply_festering_wounds_recovery(request)
        self.assertEqual(request.state.active_count, 2)

    def test_result_rejects_forged_state_transition(self) -> None:
        request = application_request(festering_state())
        result = apply_festering_wounds_recovery(request)

        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, state=request.state)

    def test_state_rejects_duplicate_record_or_infection_identity(self) -> None:
        first = festering_state(count=1).wounds[0]
        duplicate_id = replace(
            first,
            source_infection_id="day:2:infection",
        )
        duplicate_source = replace(first, id="hero:festering:2")

        for wounds in ((first, duplicate_id), (first, duplicate_source)):
            with self.subTest(wounds=wounds):
                with self.assertRaisesRegex(ValueError, "must be unique"):
                    FesteringWoundState("hero", wounds)


if __name__ == "__main__":
    unittest.main()
