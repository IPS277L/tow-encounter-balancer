from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import (
    Condition,
    ConditionState,
    EffectClassification,
)
from towr.domain.skill_improvise_models import (
    SKILL_IMPROVISE_CONDITION_RULE_ID,
    SkillImproviseActionExecutionRequest,
    SkillImproviseApproach,
    SkillImproviseConditionEffect,
)
from towr.domain.test_models import (
    OpposedSide,
    OpposedTestRequest,
    Skill,
    TestProfile,
    TestRequest,
    TieBreak,
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
from towr.rules.skill_improvise_resolution import (
    execute_skill_improvise_action,
)
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def active_round(
    *,
    improvise_kind: ImproviseKind = ImproviseKind.SKILL,
    approach_id: str = "knock-down",
    produces_attack: bool = False,
) -> CombatRoundState:
    state = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant(
                "hero",
                CombatSide.PLAYERS_AND_ALLIES,
            ),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    state = start_combat_turn(
        CombatTurnStartRequest("turn:start", state, "hero")
    ).state
    return reserve_combat_action_slot(
        CombatActionSlotRequest(
            id="slot:improvise",
            state=state,
            actor_id="hero",
            declaration=CombatActionDeclaration(
                CombatActionKind.IMPROVISE,
                improvise_kind=improvise_kind,
                improvise_approach_id=approach_id,
                improvise_produces_attack=produces_attack,
            ),
            grant=ActionSlotGrant.STANDARD,
        )
    ).state


def basic_test() -> TestRequest:
    return TestRequest("improvise:test", TestProfile(2, 5))


def opposed_test() -> OpposedTestRequest:
    return OpposedTestRequest(
        id="improvise:opposed",
        initiator=TestRequest("improvise:actor", TestProfile(2, 5)),
        opponent=TestRequest("improvise:target", TestProfile(2, 5)),
        tie_break=TieBreak(
            rule_id="RULE-TEST-002:acting-side",
            winner=OpposedSide.INITIATOR,
        ),
    )


def request(
    *,
    round_state: CombatRoundState | None = None,
    test: TestRequest | OpposedTestRequest | None = None,
    effect: SkillImproviseConditionEffect | None = None,
    actor_conditions: ConditionState | None = None,
    approach: SkillImproviseApproach | None = None,
) -> SkillImproviseActionExecutionRequest:
    return SkillImproviseActionExecutionRequest(
        id="improvise:execute",
        round_state=round_state if round_state is not None else active_round(),
        actor_id="hero",
        actor_conditions=(
            actor_conditions
            if actor_conditions is not None
            else ConditionState()
        ),
        slot_index=1,
        approach=(
            approach
            if approach is not None
            else SkillImproviseApproach("knock-down", Skill.BRAWN)
        ),
        test=test if test is not None else basic_test(),
        condition_effect=effect,
    )


def prone_effect() -> SkillImproviseConditionEffect:
    return SkillImproviseConditionEffect(
        target_id="enemy",
        condition=Condition.PRONE,
        gm_approval_id="gm:knock-down-approved",
    )


class K1SkillImproviseResolutionTests(unittest.TestCase):
    def test_basic_success_creates_condition_application_and_receipt(self) -> None:
        source = request(effect=prone_effect())

        result = execute_skill_improvise_action(
            source,
            SequenceRandom([1, 10]),
        )

        self.assertTrue(result.test_result.succeeded)
        application = result.condition_application
        self.assertIsNotNone(application)
        assert application is not None
        self.assertEqual(application.source_action_id, source.id)
        self.assertEqual(application.source_test_id, source.test.id)
        self.assertEqual(application.target_id, "enemy")
        self.assertIs(application.condition, Condition.PRONE)
        self.assertEqual(
            application.gm_approval_id,
            "gm:knock-down-approved",
        )
        self.assertEqual(application.rule_id, SKILL_IMPROVISE_CONDITION_RULE_ID)
        receipt = result.slot.execution
        self.assertIsNotNone(receipt)
        assert receipt is not None
        self.assertEqual(receipt.actor_id, "hero")
        self.assertEqual(receipt.round_number, 1)
        self.assertEqual(receipt.slot_index, 1)
        self.assertEqual(receipt.declaration, result.slot.declaration)
        ended = end_combat_turn(
            CombatTurnEndRequest("turn:end", result.round_state, "hero")
        )
        self.assertEqual(ended.completed_turn.actor_id, "hero")

    def test_basic_failure_completes_slot_without_application(self) -> None:
        result = execute_skill_improvise_action(
            request(effect=prone_effect()),
            SequenceRandom([10, 10]),
        )

        self.assertFalse(result.test_result.succeeded)
        self.assertIsNone(result.condition_application)
        self.assertTrue(result.slot.executed)

    def test_opposed_win_creates_approved_condition_application(self) -> None:
        effect = SkillImproviseConditionEffect(
            target_id="enemy",
            condition=Condition.DISTRACTED,
            gm_approval_id="gm:admonish-approved",
            classification=EffectClassification.PSYCHOLOGICAL,
        )
        result = execute_skill_improvise_action(
            request(
                test=opposed_test(),
                effect=effect,
                approach=SkillImproviseApproach(
                    "knock-down",
                    Skill.LEADERSHIP,
                ),
            ),
            SequenceRandom([1, 10, 10, 10]),
        )

        self.assertIs(result.test_result.winner, OpposedSide.INITIATOR)
        application = result.condition_application
        self.assertIsNotNone(application)
        assert application is not None
        self.assertIs(
            application.classification,
            EffectClassification.PSYCHOLOGICAL,
        )
        self.assertEqual(
            result.slot.execution.result_request_id,
            "improvise:opposed",
        )

    def test_opposed_loss_completes_slot_without_application(self) -> None:
        result = execute_skill_improvise_action(
            request(test=opposed_test(), effect=prone_effect()),
            SequenceRandom([10, 10, 1, 10]),
        )

        self.assertIs(result.test_result.winner, OpposedSide.OPPONENT)
        self.assertIsNone(result.condition_application)
        self.assertTrue(result.slot.executed)

    def test_success_without_supported_effect_has_no_generic_follow_up(self) -> None:
        result = execute_skill_improvise_action(
            request(),
            SequenceRandom([1, 10]),
        )

        self.assertTrue(result.test_result.succeeded)
        self.assertIsNone(result.condition_application)

    def test_defenceless_wrong_kind_and_attacking_improvise_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            execute_skill_improvise_action(
                request(
                    actor_conditions=ConditionState(
                        frozenset({Condition.DEFENCELESS})
                    )
                ),
                SequenceRandom([]),
            )
        with self.assertRaises(ValueError):
            execute_skill_improvise_action(
                request(
                    round_state=active_round(
                        improvise_kind=ImproviseKind.ABILITY
                    )
                ),
                SequenceRandom([]),
            )
        with self.assertRaises(ValueError):
            execute_skill_improvise_action(
                request(round_state=active_round(produces_attack=True)),
                SequenceRandom([]),
            )

    def test_approach_target_actor_and_rule_provenance_are_checked(self) -> None:
        with self.assertRaises(ValueError):
            execute_skill_improvise_action(
                request(
                    approach=SkillImproviseApproach(
                        "another-way",
                        Skill.BRAWN,
                    )
                ),
                SequenceRandom([]),
            )
        with self.assertRaises(ValueError):
            request(
                effect=replace(prone_effect(), target_id="missing")
            )
        with self.assertRaises(ValueError):
            replace(prone_effect(), condition=Condition.STAGGERED)
        source = request()
        with self.assertRaises(ValueError):
            replace(source, actor_id="enemy")
        with self.assertRaises(ValueError):
            execute_skill_improvise_action(
                replace(source, rule_id="RULE-COMBAT-004:forged"),
                SequenceRandom([]),
            )

    def test_slot_must_be_reserved_ordered_and_executed_once(self) -> None:
        state = active_round()
        source = request(round_state=state)
        with self.assertRaises(ValueError):
            end_combat_turn(CombatTurnEndRequest("turn:end", state, "hero"))

        result = execute_skill_improvise_action(
            source,
            SequenceRandom([1, 10]),
        )
        with self.assertRaises(ValueError):
            execute_skill_improvise_action(
                replace(source, round_state=result.round_state),
                SequenceRandom([]),
            )

    def test_result_rejects_test_application_and_round_forgery(self) -> None:
        result = execute_skill_improvise_action(
            request(effect=prone_effect()),
            SequenceRandom([1, 10]),
        )
        application = result.condition_application
        assert application is not None

        with self.assertRaises(ValueError):
            replace(
                result,
                condition_application=replace(
                    application,
                    target_id="hero",
                ),
            )
        with self.assertRaises(ValueError):
            replace(
                result,
                test_result=replace(
                    result.test_result,
                    trace=replace(
                        result.test_result.trace,
                        request_id="forged:test",
                    ),
                ),
            )
        with self.assertRaises(ValueError):
            replace(result, round_state=result.previous_round_state)
        with self.assertRaises(ValueError):
            replace(result, applied_rule_ids=("RULE-COMBAT-004:forged",))


if __name__ == "__main__":
    unittest.main()
