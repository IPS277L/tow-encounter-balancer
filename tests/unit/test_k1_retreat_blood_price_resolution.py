from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition
from towr.domain.fate_models import (
    FATE_NEAR_MISS_RULE_ID,
    FateNearMissBurnRequest,
    FateSessionState,
    prepare_retreat_alternative_price,
)
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundType,
    WoundDiceModifier,
)
from towr.domain.resolution_models import ConsumeWoundNegationRequest
from towr.domain.retreat_blood_price_models import (
    RetreatBloodPriceApplicationResult,
    RetreatBloodPriceWoundRequest,
)
from towr.domain.retreat_models import (
    RETREAT_ALTERNATIVE_PRICE_RULE_ID,
    GroupRetreatDeclaration,
    RetreatAlternativePrice,
    RetreatAlternativePriceDecision,
)
from towr.domain.turn_models import (
    CombatRoundState,
    CombatSide,
    CombatTurnParticipant,
)
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionRequest,
    CharacterWoundLifecycleOutcome,
)
from towr.rules.retreat_blood_price_resolution import (
    apply_retreat_blood_price_wound_completion,
    begin_retreat_blood_price_application,
)
from towr.rules.retreat_resolution import resolve_retreat_alternative_price
from towr.rules.wound_lifecycle_resolution import (
    complete_character_wound_lifecycle,
)


def alternative_price_cover(
    price: RetreatAlternativePrice = RetreatAlternativePrice.BLOOD,
):
    retreat = GroupRetreatDeclaration(
        id="retreat:battle:1:round:3",
        battle_id="battle:1",
        initiator_actor_id="ally",
        player_character_ids=("hero", "ally"),
        consenting_player_character_ids=("ally", "hero"),
        round_state=CombatRoundState(
            round_number=3,
            participants=(
                CombatTurnParticipant("hero", CombatSide.PLAYERS_AND_ALLIES),
                CombatTurnParticipant("ally", CombatSide.PLAYERS_AND_ALLIES),
                CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
            ),
            side_order=(
                CombatSide.PLAYERS_AND_ALLIES,
                CombatSide.OPPOSITION,
            ),
        ),
    )
    request = prepare_retreat_alternative_price(
        request_id=f"retreat:price:{price.value}",
        retreat=retreat,
        fate_states=(
            FateSessionState("session:1", "hero", 1, 0),
            FateSessionState("session:1", "ally", 1, 0),
        ),
    )
    return resolve_retreat_alternative_price(
        request,
        RetreatAlternativePriceDecision(
            id=f"decision:retreat-price:{price.value}",
            price=price,
        ),
    )


def blood_request(
    *,
    state: CharacterInjuryState = CharacterInjuryState(),
    consumed_application_ids: tuple[str, ...] = (),
) -> RetreatBloodPriceWoundRequest:
    return RetreatBloodPriceWoundRequest(
        id="retreat:blood:apply:1",
        source_price=alternative_price_cover(),
        target_id="ally",
        state=state,
        consumed_application_ids=consumed_application_ids,
    )


def completion_request(
    result: RetreatBloodPriceApplicationResult,
    *,
    near_miss: FateNearMissBurnRequest | None = None,
):
    pending = result.pending_character_wound
    assert pending is not None
    target_id = pending.source_request.target_id
    return CharacterWoundLifecycleCompletionRequest(
        id="retreat:blood:complete:1",
        roll=pending,
        current_state=result.state,
        daily_wounds=DailyWoundState("day:1", target_id),
        daily_registration_id=(
            None if near_miss is not None else "register:retreat:blood:1"
        ),
        near_miss=near_miss,
    )


class K1RetreatBloodPriceResolutionTests(unittest.TestCase):
    def test_explicit_pc_receives_one_normal_pending_wound(self) -> None:
        request = replace(
            blood_request(),
            wound_dice_modifiers=(WoundDiceModifier("RULE-TRAIT:HARDY", 1),),
        )

        result = begin_retreat_blood_price_application(
            request,
            SequenceRandom([2, 4]),
        )

        pending = result.pending_character_wound
        self.assertIsNotNone(pending)
        assert pending is not None
        self.assertEqual(result.target_id, "ally")
        self.assertIs(
            pending.source_request.wound.subject_type,
            CharacterWoundType.PLAYER,
        )
        self.assertEqual(pending.source_request.wound.base_dice, 1)
        self.assertEqual(pending.wound_result.table_roll.values, (2, 4))
        self.assertTrue(pending.near_miss_eligible)
        self.assertEqual(
            result.consumed_application_ids,
            (request.source_price.application_request.id,),
        )
        self.assertIn(
            RETREAT_ALTERNATIVE_PRICE_RULE_ID,
            result.applied_rule_ids,
        )

    def test_accepted_wound_is_registered_and_effect_is_resolved(self) -> None:
        pending = begin_retreat_blood_price_application(
            blood_request(),
            SequenceRandom([6]),
        )
        completion = complete_character_wound_lifecycle(
            completion_request(pending)
        )

        result = apply_retreat_blood_price_wound_completion(
            pending,
            completion,
        )

        self.assertIsNone(result.pending_character_wound)
        self.assertEqual(result.character_wound_completion, completion)
        self.assertIs(completion.outcome, CharacterWoundLifecycleOutcome.ACCEPTED)
        self.assertEqual(completion.daily_wounds.wound_count, 1)
        self.assertTrue(result.state.conditions.has(Condition.DRAINED))
        self.assertTrue(result.state.wounds[-1].effect_resolved)

    def test_near_miss_can_cancel_blood_wound_but_not_reopen_price(self) -> None:
        source_state = CharacterInjuryState()
        pending = begin_retreat_blood_price_application(
            blood_request(state=source_state),
            SequenceRandom([10]),
        )
        wound_id = pending.character_wound.request_id
        near_miss = FateNearMissBurnRequest(
            id="burn:retreat:blood:near-miss",
            state=FateSessionState("session:1", "ally", 1, 0),
            wound_negation=ConsumeWoundNegationRequest(
                resolution_id=wound_id,
                rule_id=FATE_NEAR_MISS_RULE_ID,
            ),
        )
        completion = complete_character_wound_lifecycle(
            completion_request(pending, near_miss=near_miss)
        )

        result = apply_retreat_blood_price_wound_completion(
            pending,
            completion,
        )

        self.assertIs(completion.outcome, CharacterWoundLifecycleOutcome.NEAR_MISS)
        self.assertEqual(result.state, source_state)
        self.assertEqual(completion.daily_wounds.wound_count, 0)
        self.assertEqual(
            result.consumed_application_ids,
            pending.consumed_application_ids,
        )

    def test_target_and_source_price_are_validated_before_rng(self) -> None:
        source = blood_request()
        with self.assertRaisesRegex(ValueError, "eligible PC"):
            replace(source, target_id="enemy")
        with self.assertRaisesRegex(ValueError, "not blood"):
            replace(
                source,
                source_price=alternative_price_cover(
                    RetreatAlternativePrice.MATERIEL
                ),
            )
        with self.assertRaisesRegex(ValueError, "living PC"):
            replace(source, state=CharacterInjuryState(dead=True))

    def test_price_application_is_one_shot(self) -> None:
        source = blood_request()
        application_id = source.source_price.application_request.id
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(
                source,
                consumed_application_ids=(application_id,),
            )

    def test_foreign_stale_and_repeated_completion_are_rejected(self) -> None:
        first = begin_retreat_blood_price_application(
            blood_request(),
            SequenceRandom([4]),
        )
        second_request = replace(
            blood_request(),
            id="retreat:blood:apply:2",
            target_id="hero",
        )
        second = begin_retreat_blood_price_application(
            second_request,
            SequenceRandom([5]),
        )
        foreign_completion = complete_character_wound_lifecycle(
            completion_request(second)
        )
        with self.assertRaisesRegex(ValueError, "another Retreat blood price"):
            apply_retreat_blood_price_wound_completion(
                first,
                foreign_completion,
            )

        completion = complete_character_wound_lifecycle(
            completion_request(first)
        )
        stale = replace(
            completion,
            source_request=replace(
                completion.source_request,
                current_state=replace(
                    completion.previous_state,
                    conditions=completion.previous_state.conditions.with_condition(
                        Condition.PRONE
                    ),
                ),
            ),
            previous_state=replace(
                completion.previous_state,
                conditions=completion.previous_state.conditions.with_condition(
                    Condition.PRONE
                ),
            ),
        )
        with self.assertRaisesRegex(ValueError, "stale target state"):
            apply_retreat_blood_price_wound_completion(first, stale)

        final = apply_retreat_blood_price_wound_completion(first, completion)
        with self.assertRaisesRegex(ValueError, "no pending Wound"):
            apply_retreat_blood_price_wound_completion(final, completion)

    def test_result_provenance_and_trace_are_closed(self) -> None:
        result = begin_retreat_blood_price_application(
            blood_request(),
            SequenceRandom([4]),
        )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, target_id="hero")
        with self.assertRaisesRegex(ValueError, "trace is incomplete"):
            replace(result, applied_rule_ids=())
        with self.assertRaisesRegex(ValueError, "either pending or completed"):
            replace(result, pending_character_wound=None)


if __name__ == "__main__":
    unittest.main()
