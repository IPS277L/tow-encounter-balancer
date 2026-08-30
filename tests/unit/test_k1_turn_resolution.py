from __future__ import annotations

import unittest
from dataclasses import replace

from towr.domain.turn_models import (
    ActionExecutionReceipt,
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionKind,
    CombatActionSlot,
    CombatActionSlotRequest,
    CombatRoundAdvanceRequest,
    CombatRoundState,
    CombatSide,
    CombatTurnEndRequest,
    CombatTurnParticipant,
    CombatTurnStartRequest,
    CombatTurnState,
    ImproviseKind,
    ManoeuvreKind,
)
from towr.rules.turn_resolution import (
    ACTION_BUDGET_RULE_ID,
    COMBAT_TURN_RULE_ID,
    advance_combat_round,
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def participants() -> tuple[CombatTurnParticipant, ...]:
    return (
        CombatTurnParticipant("hero:a", CombatSide.PLAYERS_AND_ALLIES),
        CombatTurnParticipant("hero:b", CombatSide.PLAYERS_AND_ALLIES),
        CombatTurnParticipant("enemy:a", CombatSide.OPPOSITION),
        CombatTurnParticipant("enemy:b", CombatSide.OPPOSITION),
    )


def round_state(
    *,
    side_order: tuple[CombatSide, CombatSide] = (
        CombatSide.PLAYERS_AND_ALLIES,
        CombatSide.OPPOSITION,
    ),
) -> CombatRoundState:
    return CombatRoundState(
        round_number=1,
        participants=participants(),
        side_order=side_order,
    )


def start(state: CombatRoundState, actor_id: str) -> CombatRoundState:
    return start_combat_turn(
        CombatTurnStartRequest(
            id=f"start:{actor_id}",
            state=state,
            actor_id=actor_id,
        )
    ).state


def reserve(
    state: CombatRoundState,
    declaration: CombatActionDeclaration,
    *,
    actor_id: str = "hero:a",
    grant: ActionSlotGrant = ActionSlotGrant.STANDARD,
    grant_rule_id: str | None = None,
    allows_second_improvise: bool = False,
):
    return reserve_combat_action_slot(
        CombatActionSlotRequest(
            id=f"slot:{actor_id}:{len(state.active_turn.action_slots) + 1}",
            state=state,
            actor_id=actor_id,
            declaration=declaration,
            grant=grant,
            grant_rule_id=grant_rule_id,
            allows_second_improvise=allows_second_improvise,
        )
    )


def complete_with_ability_improvise(
    state: CombatRoundState,
    actor_id: str,
) -> CombatRoundState:
    state = start(state, actor_id)
    state = reserve(
        state,
        CombatActionDeclaration(
            CombatActionKind.IMPROVISE,
            improvise_kind=ImproviseKind.ABILITY,
            improvise_approach_id="round-progression-placeholder",
        ),
        actor_id=actor_id,
    ).state
    turn = state.active_turn
    assert turn is not None
    slot = turn.action_slots[0]
    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=f"execute:{actor_id}",
            executor_rule_id="RULE-TEST:round-progression-placeholder",
            source_request_id=f"execute:{actor_id}",
            result_request_id=f"execute:{actor_id}:result",
            actor_id=actor_id,
            round_number=state.round_number,
            slot_index=1,
            declaration=slot.declaration,
        ),
    )
    state = replace(
        state,
        active_turn=replace(turn, action_slots=(executed_slot,)),
    )
    return end_combat_turn(
        CombatTurnEndRequest(
            id=f"end:{actor_id}",
            state=state,
            actor_id=actor_id,
        )
    ).state


class K1TurnModelTests(unittest.TestCase):
    def test_round_requires_unique_participants_on_both_sides(self) -> None:
        with self.assertRaises(ValueError):
            CombatRoundState(
                round_number=1,
                participants=(
                    CombatTurnParticipant(
                        "hero",
                        CombatSide.PLAYERS_AND_ALLIES,
                    ),
                ),
            )
        with self.assertRaises(ValueError):
            CombatRoundState(
                round_number=1,
                participants=(
                    CombatTurnParticipant(
                        "same",
                        CombatSide.PLAYERS_AND_ALLIES,
                    ),
                    CombatTurnParticipant("same", CombatSide.OPPOSITION),
                ),
            )

    def test_action_declaration_identifies_every_attack_producing_form(self) -> None:
        self.assertTrue(
            CombatActionDeclaration(CombatActionKind.ATTACK).produces_attack
        )
        self.assertTrue(
            CombatActionDeclaration(
                CombatActionKind.MANOEUVRE,
                manoeuvre=ManoeuvreKind.CHARGE,
            ).produces_attack
        )
        self.assertTrue(
            CombatActionDeclaration(
                CombatActionKind.IMPROVISE,
                improvise_kind=ImproviseKind.SKILL,
                improvise_approach_id="throw-table",
                improvise_produces_attack=True,
            ).produces_attack
        )
        self.assertFalse(
            CombatActionDeclaration(
                CombatActionKind.MANOEUVRE,
                manoeuvre=ManoeuvreKind.RUN,
            ).produces_attack
        )

    def test_turn_state_rejects_forged_duplicate_actions(self) -> None:
        with self.assertRaises(ValueError):
            CombatTurnState(
                actor_id="hero:a",
                side=CombatSide.PLAYERS_AND_ALLIES,
                action_slots=(
                    CombatActionSlot(
                        1,
                        CombatActionDeclaration(CombatActionKind.HELP),
                        ActionSlotGrant.STANDARD,
                    ),
                    CombatActionSlot(
                        2,
                        CombatActionDeclaration(CombatActionKind.HELP),
                        ActionSlotGrant.FATE,
                    ),
                ),
            )


class K1TurnResolutionTests(unittest.TestCase):
    def test_players_act_first_and_choose_order_within_their_side(self) -> None:
        result = start_combat_turn(
            CombatTurnStartRequest("start:b", round_state(), "hero:b")
        )

        self.assertEqual(result.turn.actor_id, "hero:b")
        self.assertEqual(result.state.next_side, CombatSide.PLAYERS_AND_ALLIES)
        self.assertEqual(result.applied_rule_ids, (COMBAT_TURN_RULE_ID,))
        with self.assertRaises(ValueError):
            start(round_state(), "enemy:a")

    def test_active_turn_blocks_other_actor_and_wrong_actor_actions(self) -> None:
        state = start(round_state(), "hero:a")

        with self.assertRaises(ValueError):
            start_combat_turn(
                CombatTurnStartRequest("start:b", state, "hero:b")
            )
        with self.assertRaises(ValueError):
            reserve(
                state,
                CombatActionDeclaration(CombatActionKind.AIM),
                actor_id="hero:b",
            )

    def test_first_action_uses_standard_slot_and_is_not_executed(self) -> None:
        state = start(round_state(), "hero:a")
        attack = CombatActionDeclaration(CombatActionKind.ATTACK)

        result = reserve(state, attack)

        self.assertEqual(result.slot.index, 1)
        self.assertIs(result.slot.declaration, attack)
        self.assertEqual(result.state.active_turn.action_slots, (result.slot,))
        self.assertEqual(result.applied_rule_ids, (ACTION_BUDGET_RULE_ID,))
        with self.assertRaises(ValueError):
            reserve(
                state,
                attack,
                grant=ActionSlotGrant.FATE,
            )

    def test_second_action_rejects_unproved_fate_and_accepts_traced_ability(self) -> None:
        state = start(round_state(), "hero:a")
        state = reserve(
            state,
            CombatActionDeclaration(CombatActionKind.AIM),
        ).state

        with self.assertRaisesRegex(ValueError, "requires a spend proof"):
            reserve(
                state,
                CombatActionDeclaration(CombatActionKind.ATTACK),
                grant=ActionSlotGrant.FATE,
            )
        with self.assertRaises(ValueError):
            reserve(
                state,
                CombatActionDeclaration(CombatActionKind.ATTACK),
            )
        with self.assertRaises(ValueError):
            CombatActionSlotRequest(
                id="slot:ability",
                state=state,
                actor_id="hero:a",
                declaration=CombatActionDeclaration(CombatActionKind.ATTACK),
                grant=ActionSlotGrant.ABILITY,
            )

        ability = reserve(
            state,
            CombatActionDeclaration(CombatActionKind.ATTACK),
            grant=ActionSlotGrant.ABILITY,
            grant_rule_id="RULE-ABILITY:test-extra-action",
        )
        self.assertEqual(
            ability.applied_rule_ids,
            (ACTION_BUDGET_RULE_ID, "RULE-ABILITY:test-extra-action"),
        )

    def test_no_third_action(self) -> None:
        state = start(round_state(), "hero:a")
        state = reserve(
            state,
            CombatActionDeclaration(CombatActionKind.AIM),
        ).state
        state = reserve(
            state,
            CombatActionDeclaration(CombatActionKind.ATTACK),
            grant=ActionSlotGrant.ABILITY,
            grant_rule_id="RULE-ABILITY:test-extra-action",
        ).state

        with self.assertRaises(ValueError):
            reserve(
                state,
                CombatActionDeclaration(CombatActionKind.RECOVER),
                grant=ActionSlotGrant.ABILITY,
                grant_rule_id="RULE-ABILITY:test-extra-action",
            )

    def test_same_action_cannot_be_repeated(self) -> None:
        state = start(round_state(), "hero:a")
        state = reserve(
            state,
            CombatActionDeclaration(
                CombatActionKind.MANOEUVRE,
                manoeuvre=ManoeuvreKind.RUN,
            ),
        ).state

        with self.assertRaises(ValueError):
            reserve(
                state,
                CombatActionDeclaration(
                    CombatActionKind.MANOEUVRE,
                    manoeuvre=ManoeuvreKind.CHARGE,
                ),
                grant=ActionSlotGrant.ABILITY,
                grant_rule_id="RULE-ABILITY:test-extra-action",
            )

    def test_charge_and_attack_are_two_attacks_regardless_of_order(self) -> None:
        charge = CombatActionDeclaration(
            CombatActionKind.MANOEUVRE,
            manoeuvre=ManoeuvreKind.CHARGE,
        )
        attack = CombatActionDeclaration(CombatActionKind.ATTACK)

        for first, second in ((charge, attack), (attack, charge)):
            with self.subTest(first=first.kind, second=second.kind):
                state = start(round_state(), "hero:a")
                state = reserve(state, first).state
                with self.assertRaises(ValueError):
                    reserve(
                        state,
                        second,
                        grant=ActionSlotGrant.ABILITY,
                        grant_rule_id="RULE-ABILITY:test-extra-action",
                    )

    def test_attack_producing_improvise_uses_attack_limit(self) -> None:
        state = start(round_state(), "hero:a")
        state = reserve(
            state,
            CombatActionDeclaration(CombatActionKind.ATTACK),
        ).state

        with self.assertRaises(ValueError):
            reserve(
                state,
                CombatActionDeclaration(
                    CombatActionKind.IMPROVISE,
                    improvise_kind=ImproviseKind.SKILL,
                    improvise_approach_id="drop-chandelier",
                    improvise_produces_attack=True,
                ),
                grant=ActionSlotGrant.ABILITY,
                grant_rule_id="RULE-ABILITY:test-extra-action",
            )

    def test_two_improvises_need_gm_allowance_and_different_approaches(self) -> None:
        state = start(round_state(), "hero:a")
        state = reserve(
            state,
            CombatActionDeclaration(
                CombatActionKind.IMPROVISE,
                improvise_kind=ImproviseKind.SKILL,
                improvise_approach_id="kick-table",
            ),
        ).state

        second = CombatActionDeclaration(
            CombatActionKind.IMPROVISE,
            improvise_kind=ImproviseKind.SKILL,
            improvise_approach_id="cut-rope",
        )
        with self.assertRaises(ValueError):
            reserve(
                state,
                second,
                grant=ActionSlotGrant.ABILITY,
                grant_rule_id="RULE-ABILITY:test-extra-action",
            )
        allowed = reserve(
            state,
            second,
            grant=ActionSlotGrant.ABILITY,
            grant_rule_id="RULE-ABILITY:test-extra-action",
            allows_second_improvise=True,
        )
        self.assertEqual(len(allowed.state.active_turn.action_slots), 2)

        with self.assertRaises(ValueError):
            reserve(
                state,
                CombatActionDeclaration(
                    CombatActionKind.IMPROVISE,
                    improvise_kind=ImproviseKind.SKILL,
                    improvise_approach_id="kick-table",
                ),
                grant=ActionSlotGrant.ABILITY,
                grant_rule_id="RULE-ABILITY:test-extra-action",
                allows_second_improvise=True,
            )

    def test_turn_cannot_end_before_standard_action(self) -> None:
        state = start(round_state(), "hero:a")

        with self.assertRaises(ValueError):
            end_combat_turn(
                CombatTurnEndRequest("end:a", state, "hero:a")
            )

    def test_side_changes_only_after_every_member_completes_turn(self) -> None:
        state = complete_with_ability_improvise(round_state(), "hero:b")
        self.assertEqual(state.next_side, CombatSide.PLAYERS_AND_ALLIES)
        with self.assertRaises(ValueError):
            start(state, "enemy:a")

        state = complete_with_ability_improvise(state, "hero:a")
        self.assertEqual(state.next_side, CombatSide.OPPOSITION)
        state = complete_with_ability_improvise(state, "enemy:b")
        self.assertEqual(state.next_side, CombatSide.OPPOSITION)
        state = complete_with_ability_improvise(state, "enemy:a")
        self.assertTrue(state.round_complete)
        self.assertIsNone(state.next_side)

    def test_ambush_order_persists_across_round_advance(self) -> None:
        opposition_first = (
            CombatSide.OPPOSITION,
            CombatSide.PLAYERS_AND_ALLIES,
        )
        state = round_state(side_order=opposition_first)
        for actor_id in ("enemy:b", "enemy:a", "hero:a", "hero:b"):
            state = complete_with_ability_improvise(state, actor_id)

        result = advance_combat_round(
            CombatRoundAdvanceRequest(
                id="round:2",
                state=state,
                next_round_participants=(
                    CombatTurnParticipant(
                        "hero:a",
                        CombatSide.PLAYERS_AND_ALLIES,
                    ),
                    CombatTurnParticipant(
                        "new-enemy",
                        CombatSide.OPPOSITION,
                    ),
                ),
            )
        )

        self.assertEqual(result.state.round_number, 2)
        self.assertEqual(result.state.side_order, opposition_first)
        self.assertEqual(result.state.next_side, CombatSide.OPPOSITION)
        self.assertEqual(result.state.completed_turn_entity_ids, ())
        self.assertEqual(result.applied_rule_ids, (COMBAT_TURN_RULE_ID,))

    def test_round_cannot_advance_early(self) -> None:
        with self.assertRaises(ValueError):
            advance_combat_round(
                CombatRoundAdvanceRequest(
                    id="round:2",
                    state=round_state(),
                    next_round_participants=participants(),
                )
            )


if __name__ == "__main__":
    unittest.main()
