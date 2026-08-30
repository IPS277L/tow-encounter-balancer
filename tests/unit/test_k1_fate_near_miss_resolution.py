from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.fate_models import (
    FATE_BURN_RULE_ID,
    FATE_NEAR_MISS_RULE_ID,
    FATE_SESSION_RULE_ID,
    FateNearMissBurnRequest,
    FateSessionState,
)
from towr.domain.fate_near_miss_models import (
    FATE_NEAR_MISS_APPLICATION_RULE_ID,
    FateNearMissApplicationRequest,
)
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundRequest,
    CharacterWoundType,
    HealingRequirement,
    WoundEntryId,
    WoundRecord,
    WoundTableEntry,
)
from towr.domain.resolution_models import ConsumeWoundNegationRequest
from towr.rules.fate_near_miss_resolution import apply_fate_near_miss
from towr.rules.fate_resolution import burn_fate
from towr.rules.injury_resolution import resolve_character_wound


def fate_state() -> FateSessionState:
    return FateSessionState(
        session_id="session:1",
        actor_id="hero",
        rating=1,
        session_spend_limit=1,
    )


def burn_near_miss(wound_id: str):
    return burn_fate(
        FateNearMissBurnRequest(
            id=f"burn:{wound_id}",
            state=fate_state(),
            wound_negation=ConsumeWoundNegationRequest(
                resolution_id=wound_id,
                rule_id=FATE_NEAR_MISS_RULE_ID,
            ),
        )
    )


def accepted_wound(
    *,
    state: CharacterInjuryState = CharacterInjuryState(),
    request_id: str = "wound:hero:1",
    values: tuple[int, ...] = (4,),
    base_dice: int = 1,
    subject_type: CharacterWoundType = CharacterWoundType.PLAYER,
):
    request = CharacterWoundRequest(
        id=request_id,
        state=state,
        subject_type=subject_type,
        base_dice=base_dice,
    )
    result = resolve_character_wound(request, SequenceRandom(list(values)))
    return request, result


def application_request(
    wound_request: CharacterWoundRequest,
    wound_result,
    *,
    consumed_effect_ids: tuple[str, ...] = (),
) -> FateNearMissApplicationRequest:
    return FateNearMissApplicationRequest(
        id=f"apply:{wound_request.id}",
        session_id="session:1",
        target_id="hero",
        burn=burn_near_miss(wound_request.id),
        wound_request=wound_request,
        wound_result=wound_result,
        consumed_effect_ids=consumed_effect_ids,
    )


class K1FateNearMissApplicationTests(unittest.TestCase):
    def test_restores_exact_pre_wound_state_and_consumes_effect(self) -> None:
        source = CharacterInjuryState(
            conditions=ConditionState(
                frozenset({Condition.STAGGERED, Condition.PRONE})
            )
        )
        wound_request, wound_result = accepted_wound(state=source)
        request = application_request(wound_request, wound_result)

        result = apply_fate_near_miss(request)

        self.assertEqual(result.previous_state, wound_result.state)
        self.assertEqual(result.state, source)
        self.assertTrue(result.state.conditions.has(Condition.STAGGERED))
        self.assertTrue(result.state.conditions.has(Condition.PRONE))
        self.assertEqual(result.cancelled_wound, wound_result.state.wounds[-1])
        self.assertEqual(
            result.discarded_effect_request,
            wound_result.effect_request,
        )
        self.assertEqual(result.fate_state.rating, 0)
        self.assertEqual(
            result.consumed_effect_ids,
            (request.burn.effect_request.id,),
        )
        self.assertEqual(
            result.applied_rule_ids,
            (
                FATE_SESSION_RULE_ID,
                FATE_BURN_RULE_ID,
                FATE_NEAR_MISS_RULE_ID,
                FATE_NEAR_MISS_APPLICATION_RULE_ID,
            ),
        )

    def test_can_negate_a_lethal_wound(self) -> None:
        wound_request, wound_result = accepted_wound(
            values=(10, 10, 10),
            base_dice=3,
        )
        self.assertTrue(wound_result.state.dead)

        result = apply_fate_near_miss(
            application_request(wound_request, wound_result)
        )

        self.assertFalse(result.state.dead)
        self.assertEqual(result.state.wounds, ())
        self.assertIs(result.cancelled_wound.entry_id, WoundEntryId.DECAPITATION)

    def test_cancelled_wound_does_not_increase_future_wound_dice(self) -> None:
        first_wound = WoundRecord(
            sequence=1,
            entry_id=WoundEntryId.SUPERFICIAL_INJURY,
            table_total=1,
            roll_values=(1,),
        )
        source = CharacterInjuryState(wounds=(first_wound,))
        wound_request, wound_result = accepted_wound(
            state=source,
            values=(1, 1),
        )
        self.assertEqual(wound_result.table_roll.dice, 2)

        result = apply_fate_near_miss(
            application_request(wound_request, wound_result)
        )
        future = resolve_character_wound(
            CharacterWoundRequest("wound:hero:future", result.state),
            SequenceRandom([1, 1]),
        )

        self.assertEqual(result.state.wounds, (first_wound,))
        self.assertEqual(result.state.untreated_wounds, 1)
        self.assertEqual(future.table_roll.dice, 2)

    def test_rejects_wrong_actor_resolution_and_non_player(self) -> None:
        wound_request, wound_result = accepted_wound()
        valid = application_request(wound_request, wound_result)

        with self.assertRaisesRegex(ValueError, "another actor"):
            replace(valid, target_id="other")
        with self.assertRaisesRegex(ValueError, "another session"):
            replace(valid, session_id="session:other")
        with self.assertRaisesRegex(ValueError, "another Wound resolution"):
            replace(
                valid,
                burn=burn_near_miss("wound:hero:other"),
            )

        champion_request, champion_result = accepted_wound(
            request_id="wound:champion:1",
            subject_type=CharacterWoundType.CHAMPION,
        )
        with self.assertRaisesRegex(ValueError, "player character"):
            application_request(champion_request, champion_result)

    def test_rejects_nonaccepted_stale_and_repeated_wound_effects(self) -> None:
        wound_request, wound_result = accepted_wound()
        valid = application_request(wound_request, wound_result)

        with self.assertRaisesRegex(ValueError, "newly accepted Wound"):
            replace(
                valid,
                wound_result=replace(
                    wound_result,
                    state=wound_request.state,
                    wound_accepted=False,
                    negated_by_rule_id="RULE-NEGATION",
                    effect_request=None,
                    applied_rule_ids=("RULE-NEGATION",),
                ),
            )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(
                valid,
                wound_result=replace(
                    wound_result,
                    state=wound_request.state,
                ),
            )
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(
                valid,
                consumed_effect_ids=(valid.burn.effect_request.id,),
            )

    def test_rejects_unknown_rule_and_forged_application_result(self) -> None:
        wound_request, wound_result = accepted_wound()
        request = application_request(wound_request, wound_result)

        with self.assertRaisesRegex(ValueError, "unknown rule"):
            apply_fate_near_miss(replace(request, rule_id="RULE-UNKNOWN"))

        result = apply_fate_near_miss(request)
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, state=result.previous_state)
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, fate_state=request.burn.previous_state)

    def test_rejects_a_structurally_valid_but_noncanonical_table_entry(self) -> None:
        wound_request, wound_result = accepted_wound()
        forged_entry = WoundTableEntry(
            id=WoundEntryId.BATTERED_LEG,
            minimum=4,
            maximum=4,
            healing=HealingRequirement.CATCH_YOUR_BREATH,
            lethal=False,
        )
        forged_roll = replace(wound_result.table_roll, entry=forged_entry)
        forged_wound = replace(
            wound_result.state.wounds[-1],
            entry_id=forged_entry.id,
        )
        forged_state = replace(wound_result.state, wounds=(forged_wound,))
        assert wound_result.effect_request is not None
        forged_effect = replace(
            wound_result.effect_request,
            entry_id=forged_entry.id,
            rule_id=f"RULE-WOUND-TABLE:{forged_entry.id.value}",
        )
        forged_result = replace(
            wound_result,
            state=forged_state,
            table_roll=forged_roll,
            effect_request=forged_effect,
        )
        request = application_request(wound_request, forged_result)

        with self.assertRaisesRegex(ValueError, "canonical Wounds Table"):
            apply_fate_near_miss(request)


if __name__ == "__main__":
    unittest.main()
