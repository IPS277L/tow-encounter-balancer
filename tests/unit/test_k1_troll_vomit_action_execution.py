from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.resolution_models import (
    IdentifiedHazardTarget,
    TargetInjuryPolicy,
)
from towr.domain.test_models import InlineProfile, Skill, TestRequest
from towr.domain.troll_vomit_models import (
    TROLL_VOMIT_ACTION_EXECUTION_RULE_ID,
    TROLL_VOMIT_RULE_ID,
    TrollVomitActionExecutionRequest,
)
from towr.domain.turn_models import (
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionKind,
    CombatActionSlotRequest,
    CombatRoundState,
    CombatSide,
    CombatTurnEndRequest,
    CombatTurnParticipant,
    CombatTurnStartRequest,
    ImproviseKind,
)
from towr.rules.troll_vomit_action_execution import (
    execute_troll_vomit_action,
)
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def active_round(
    *,
    improvise_kind: ImproviseKind = ImproviseKind.ABILITY,
    approach_id: str = TROLL_VOMIT_RULE_ID,
    produces_attack: bool = False,
) -> CombatRoundState:
    state = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant(
                "troll",
                CombatSide.PLAYERS_AND_ALLIES,
            ),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    state = start_combat_turn(
        CombatTurnStartRequest("turn:start", state, "troll")
    ).state
    return reserve_combat_action_slot(
        CombatActionSlotRequest(
            id="slot:troll-vomit",
            state=state,
            actor_id="troll",
            declaration=CombatActionDeclaration(
                CombatActionKind.IMPROVISE,
                improvise_kind=improvise_kind,
                improvise_approach_id=approach_id,
                improvise_produces_attack=produces_attack,
            ),
            grant=ActionSlotGrant.STANDARD,
        )
    ).state


def hazard_target(
    *,
    target_id: str = "enemy",
    conditions: ConditionState | None = None,
    skill: Skill = Skill.ENDURANCE,
    profile: InlineProfile = InlineProfile(3, 5),
) -> IdentifiedHazardTarget:
    return IdentifiedHazardTarget(
        target_id=target_id,
        avoidance_test=TestRequest("troll-vomit:endurance", profile),
        target_policy=TargetInjuryPolicy.BRUTE,
        target_state=ProfileInjuryState(
            wounds=0,
            wound_limit=6,
            conditions=(
                conditions
                if conditions is not None
                else ConditionState(frozenset({Condition.STAGGERED}))
            ),
        ),
        selected_avoidance_skill=skill,
    )


def request(
    *,
    round_state: CombatRoundState | None = None,
    actor_conditions: ConditionState | None = None,
    actor_ability_rule_ids: tuple[str, ...] = (TROLL_VOMIT_RULE_ID,),
    target: IdentifiedHazardTarget | None = None,
    target_in_close_range: bool = True,
    slot_index: int = 1,
) -> TrollVomitActionExecutionRequest:
    return TrollVomitActionExecutionRequest(
        id="troll-vomit:execute",
        round_state=round_state if round_state is not None else active_round(),
        actor_id="troll",
        actor_conditions=(
            actor_conditions
            if actor_conditions is not None
            else ConditionState()
        ),
        actor_ability_rule_ids=actor_ability_rule_ids,
        slot_index=slot_index,
        target=target if target is not None else hazard_target(),
        target_in_close_range=target_in_close_range,
    )


class K1TrollVomitActionExecutionTests(unittest.TestCase):
    def test_failed_endurance_applies_hazard_and_completes_slot(self) -> None:
        source = request()

        result = execute_troll_vomit_action(
            source,
            SequenceRandom([10, 10, 10]),
        )

        self.assertEqual(result.exposure.rule_id, TROLL_VOMIT_RULE_ID)
        self.assertIs(result.exposure.avoidance_skill, Skill.ENDURANCE)
        self.assertEqual(result.exposure.rating, 3)
        self.assertFalse(result.application.blocked)
        self.assertEqual(result.avoidance_test.successes, 0)
        self.assertFalse(result.hazard.avoided)
        self.assertEqual(result.hazard.shortfall, 3)
        self.assertEqual(result.target_state.wounds, 3)
        self.assertFalse(result.target_state.conditions.has(Condition.STAGGERED))
        receipt = result.slot.execution
        self.assertIsNotNone(receipt)
        assert receipt is not None
        self.assertEqual(
            receipt.executor_rule_id,
            TROLL_VOMIT_ACTION_EXECUTION_RULE_ID,
        )
        self.assertEqual(receipt.result_request_id, result.hazard.request_id)
        ended = end_combat_turn(
            CombatTurnEndRequest("turn:end", result.round_state, "troll")
        )
        self.assertEqual(ended.completed_turn.actor_id, "troll")

    def test_three_successes_avoid_hazard_and_still_complete_action(self) -> None:
        result = execute_troll_vomit_action(
            request(
                actor_conditions=ConditionState(
                    frozenset({Condition.STAGGERED})
                )
            ),
            SequenceRandom([1, 2, 3]),
        )

        self.assertTrue(result.hazard.avoided)
        self.assertEqual(result.hazard.shortfall, 0)
        self.assertEqual(result.target_state.wounds, 0)
        self.assertTrue(result.slot.executed)

    def test_ability_range_enemy_stagger_and_skill_preflight_before_rng(self) -> None:
        invalid_requests = (
            request(actor_ability_rule_ids=()),
            request(target_in_close_range=False),
            request(target=hazard_target(conditions=ConditionState())),
            request(target=hazard_target(target_id="troll")),
            request(target=hazard_target(skill=Skill.ATHLETICS)),
            request(
                actor_conditions=ConditionState(
                    frozenset({Condition.DEFENCELESS})
                )
            ),
        )
        for source in invalid_requests:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    execute_troll_vomit_action(source, SequenceRandom([]))

    def test_only_matching_non_attack_ability_slot_can_execute(self) -> None:
        invalid_rounds = (
            active_round(improvise_kind=ImproviseKind.SKILL),
            active_round(approach_id="RULE-NPC-020:swamp-breath"),
            active_round(produces_attack=True),
        )
        for state in invalid_rounds:
            with self.subTest(state=state):
                with self.assertRaises(ValueError):
                    execute_troll_vomit_action(
                        request(round_state=state),
                        SequenceRandom([]),
                    )
        with self.assertRaises(ValueError):
            execute_troll_vomit_action(
                replace(request(), rule_id="RULE-NPC-019:forged"),
                SequenceRandom([]),
            )

    def test_slot_must_be_ordered_executed_once_and_blocks_turn_end(self) -> None:
        state = active_round()
        source = request(round_state=state)
        with self.assertRaises(ValueError):
            end_combat_turn(CombatTurnEndRequest("turn:end", state, "troll"))

        result = execute_troll_vomit_action(
            source,
            SequenceRandom([1, 2, 3]),
        )
        with self.assertRaises(ValueError):
            execute_troll_vomit_action(
                replace(source, round_state=result.round_state),
                SequenceRandom([]),
            )

        state = start_combat_turn(
            CombatTurnStartRequest(
                "turn:ordered:start",
                CombatRoundState(
                    round_number=1,
                    participants=(
                        CombatTurnParticipant(
                            "troll",
                            CombatSide.PLAYERS_AND_ALLIES,
                        ),
                        CombatTurnParticipant(
                            "enemy",
                            CombatSide.OPPOSITION,
                        ),
                    ),
                ),
                "troll",
            )
        ).state
        state = reserve_combat_action_slot(
            CombatActionSlotRequest(
                "slot:first",
                state,
                "troll",
                CombatActionDeclaration(CombatActionKind.AIM),
                ActionSlotGrant.STANDARD,
            )
        ).state
        state = reserve_combat_action_slot(
            CombatActionSlotRequest(
                "slot:second",
                state,
                "troll",
                CombatActionDeclaration(
                    CombatActionKind.IMPROVISE,
                    improvise_kind=ImproviseKind.ABILITY,
                    improvise_approach_id=TROLL_VOMIT_RULE_ID,
                ),
                ActionSlotGrant.FATE,
            )
        ).state
        with self.assertRaises(ValueError):
            execute_troll_vomit_action(
                request(round_state=state, slot_index=2),
                SequenceRandom([]),
            )

    def test_result_rejects_hazard_receipt_and_state_forgery(self) -> None:
        result = execute_troll_vomit_action(
            request(),
            SequenceRandom([10, 10, 10]),
        )

        with self.assertRaises(ValueError):
            replace(result, target_id="another-target")
        with self.assertRaises(ValueError):
            replace(
                result,
                hazard=replace(result.hazard, shortfall=2),
            )
        with self.assertRaises(ValueError):
            replace(result, target_state=result.previous_target_state)
        with self.assertRaises(ValueError):
            replace(result, round_state=result.previous_round_state)
        with self.assertRaises(ValueError):
            replace(
                result,
                applied_rule_ids=(TROLL_VOMIT_RULE_ID,),
            )


if __name__ == "__main__":
    unittest.main()
